"""Context-greeting node — proactive on-load greeting dispatcher (P4-2d, R6).

Port of ALT ``chat_context_greeting.py::maybe_context_greeting`` (Seitenkontext-
Feature, 2026-07-10). When the widget opens/continues on a recognised WLO page it
sends a turn with ``environment.page_event == 'context_open'``. This node builds a
short greeting + action pills from ``01-base/context-actions`` — LLM-free — and
sets ``ctx.early_response`` so the graph short-circuits (like tour/preflight).

Contract (ALT-verbatim):
  * ``page_event != 'context_open'`` → ``early_response`` stays None (normal flow).
  * ``page_event == 'context_open'`` → ALWAYS an answer: a greeting when every gate
    passes, else ``content == ""`` (the frontend renders empty content as nothing).

Gates (all AND): continued conversation (non-empty history), page kind ∈
{collection, content, topic}, resolved metadata (title set, not ``unresolved``),
page not greeted before (signature ∉ ``_greeted_pages``).

Why it runs BEFORE ``persist_user`` in the graph: a ``context_open`` ping is not a
user message. Short-circuiting here means the ping is never persisted or classified.
Because the terminal persist node does not run on an early exit, the greeting
persists its own assistant message + dedup marker inline (like the tour node).

DI (Regel 3): ``session`` is injected by the graph-build (P4-6). NEU deviations over
ALT, both from the SQLite→Postgres move: ``update_session``/``save_message`` take the
session first, and ``entities`` is written as a native jsonb dict (ALT wrapped it in
``json.dumps``) — identical to the tour node's ``tour_state`` handling. Tests patch
the two DB writes on THIS module; ``page_context`` + ``load_context_actions`` run for
real.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.graph.state import TurnContext
from boerdi.services import page_context
from boerdi.services.config_loader import load_context_actions
from boerdi.services.db_sessions import save_message, update_session

logger = logging.getLogger(__name__)

_GREETABLE_KINDS = ("collection", "content", "topic")
_GREETED_KEY = "_greeted_pages"
_GREETED_CAP = 20


def _empty_response(session_id: str) -> ChatResponse:
    """Empty context answer — the frontend renders empty content as nothing."""
    return ChatResponse(
        session_id=session_id,
        content="",
        follow_up="none",
        debug=DebugInfo(pattern="CTX:skipped", tools_called=["context_greeting"]),
    )


def _build_quick_replies(
    cfg: dict[str, Any],
    page_kind: str,
    page_ctx: dict[str, Any],
    meta: dict[str, Any],
    title: str,
) -> list[str]:
    """Serialise the configured pills for this page kind into quick-reply strings:
      * text   → the plain label (sent as a normal message on click)
      * action → ``__action__|<label>|<action>|<params-json>`` (Direct-Action)
      * report → ``__guide__|<label>|<url>`` (existing guide-link encoding)
    IDs are injected at runtime: collection/topic actions carry the collection_id;
    the report link carries the node_id (content) resp. collection_id (else).
    """
    collection_id = (page_ctx.get("collection_id") or "").strip() or (
        meta.get("node_id") or ""
    ).strip()
    node_id = (page_ctx.get("node_id") or "").strip() or (meta.get("node_id") or "").strip()
    report_id = node_id if page_kind == "content" else collection_id
    action_id = collection_id or node_id

    report_url = (
        str(cfg.get("report_url") or "")
        .replace("{node_id}", report_id)
        .replace("{collection_id}", collection_id)
    )

    out: list[str] = []
    for pill in cfg.get("pills", {}).get(page_kind, []):
        label = str(pill.get("label") or "").replace("{title}", title)
        kind = pill.get("kind")
        if not label or not kind:
            continue
        if kind == "text":
            out.append(label)
        elif kind == "action":
            action = str(pill.get("action") or "").strip()
            if not action:
                continue
            params = {"collection_id": action_id, "title": title}
            out.append(f"__action__|{label}|{action}|{json.dumps(params, ensure_ascii=False)}")
        elif kind == "report":
            if report_url:
                out.append(f"__guide__|{label}|{report_url}")
    return out


async def maybe_context_greeting(
    session: AsyncSession,
    req: ChatRequest,
    env: dict[str, Any],
    session_state: dict[str, Any],
    history: list[Any],
) -> ChatResponse | None:
    """See the module docstring. Returns ``None`` only without a ``context_open``
    signal; otherwise always a ChatResponse (greeting or empty)."""
    if (env.get("page_event") or "").strip().lower() != "context_open":
        return None  # no context signal → normal flow

    # From here on: always return a ChatResponse (never None).
    page_ctx = env.get("page_context") or {}
    page_kind = (page_ctx.get("page_kind") or "").strip().lower()

    # Gate 1: continued conversation (session existence is not enough — IDs are
    # created eagerly; the discriminator is a non-empty history).
    if not history:
        return _empty_response(req.session_id)

    # Gate 2: greetable page kind.
    if page_kind not in _GREETABLE_KINDS:
        return _empty_response(req.session_id)

    # Gate 3: resolved metadata (title set, not just a fallback title).
    meta = page_context.get_cached(session_state)
    if not isinstance(meta, dict):
        return _empty_response(req.session_id)
    title = (meta.get("title") or "").strip()
    if not title or meta.get("unresolved"):
        return _empty_response(req.session_id)

    # Gate 4: page not greeted before (dedup over the context signature).
    signature = page_context._current_context_signature(page_ctx)
    entities = session_state.setdefault("entities", {})
    greeted = entities.get(_GREETED_KEY)
    if not isinstance(greeted, list):
        greeted = []
    if signature in greeted:
        return _empty_response(req.session_id)

    cfg = load_context_actions()
    if not cfg.get("enabled", True):
        return _empty_response(req.session_id)

    greeting = str(cfg.get("greetings", {}).get(page_kind) or "").replace("{title}", title)
    if not greeting.strip():
        return _empty_response(req.session_id)
    quick_replies = _build_quick_replies(cfg, page_kind, page_ctx, meta, title)

    # Record the dedup marker (FIFO cap — a list, because entities is jsonb-
    # persisted) and persist it explicitly on the short-circuit path.
    greeted.append(signature)
    if len(greeted) > _GREETED_CAP:
        greeted = greeted[-_GREETED_CAP:]
    entities[_GREETED_KEY] = greeted

    try:
        await update_session(session, req.session_id, entities=entities)
        await save_message(
            session, req.session_id, "assistant", greeting,
            debug={"pattern": f"CTX:{page_kind}"},
        )
    except Exception as exc:  # pragma: no cover — persistence must not break the turn
        logger.warning("context greeting persist failed: %s", exc)

    logger.info("context_greeting fired page_kind=%s sig=%s", page_kind, signature)
    return ChatResponse(
        session_id=req.session_id,
        content=greeting,
        quick_replies=quick_replies,
        follow_up="none",
        debug=DebugInfo(pattern=f"CTX:{page_kind}", tools_called=["context_greeting"]),
    )


async def context_greeting(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Node adapter: dispatch the greeting, short-circuit the turn on a hit.

    Sets ``ctx.early_response`` when ``maybe_context_greeting`` returns a response
    (greeting or empty) so a ``context_open`` ping never reaches persist/assess.
    Wrapped defensively (ALT wrapped the call-site the same way): a greeting bug
    must never break the turn — on error the turn falls through to the normal flow.
    """
    try:
        resp = await maybe_context_greeting(
            session, ctx.req, ctx.env, ctx.session_state, ctx.history
        )
    except Exception as err:
        logger.warning("context greeting skipped: %s", err)
        resp = None
    if resp is not None:
        ctx.early_response = resp
    return ctx
