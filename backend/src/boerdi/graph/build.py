"""Turn-graph assembly (R4e) — compose the nine turn nodes into a LangGraph
``StateGraph`` and compile it into the runnable pipeline the chat endpoint drives.

This is the composition root of the turn: the one place that knows the concrete
services and the request-scoped seams. ALT ran the turn as a linear ``_chat_impl``
(``chat.py`` + ``chat_turn_setup.py``); NEU expresses the same sequence — and the
same two early exits — as a graph:

    START → setup → tour ──early?──▶ END
                     └─▶ page_context_enrich → context_greeting ──early?──▶ END
                            └─▶ persist_user → preflight ──early?──▶ END
                                   └─▶ assess → safety_log → merge → route
                                          → respond → assemble → persist → END

``page_context_enrich`` (inject page IDs + best-effort MCP metadata resolve) runs
AFTER tour — so a tour tick skips the resolve latency (ALT returns before the resolve
block) — and never short-circuits. Only ``tour``, ``context_greeting`` and
``preflight`` short-circuit (they set ``ctx.early_response``). The LP-/Canvas-fast-paths
do NOT: ``route`` records ``fp_*`` markers that
``respond`` consumes, so the normal chain still flows through respond→assemble→
persist. The endpoint returns ``early_response or response`` (``.ainvoke`` yields a
dict; None-default fields are omitted — read via ``.get``).

Two inline glue steps live here because they are pure turn-sequencing side effects
that only make sense between the major nodes (ALT emitted them inline in
``_chat_impl`` too):

* ``_persist_user_message`` — ALT ``chat_turn_setup.py:128``. Runs AFTER tour and the
  context-greeting check (so an early-exit never persists here — tour saves its own
  user turn; a context-open ping is intentionally never persisted) and BEFORE
  preflight (so a direct-action turn still records the user message). Bare await,
  faithful to ALT: a DB failure propagates to the endpoint's top-level safety net.
* ``_log_turn_safety`` — ALT ``chat_turn_setup.py:202-212``. The main per-turn
  safety-log, config-gated. Runs after assess and BEFORE route, so route-fast-path
  early exits are still audited (this is why it is not in the terminal persist
  node). Wrapped in try/except like ALT — telemetry must never break a turn.

DI (Regel 3 — no module-global engine): the request ``AsyncSession``, the real peer
IP and the streaming ``on_token`` hook are bound per request via ``functools.partial``
at build time; ``memory_fetch`` for ``assess`` is likewise the concrete
``get_memory`` bound to this session. Building + compiling per request is cheap next
to a turn's LLM latency and keeps every seam request-scoped.

simplify: compiled WITHOUT a checkpointer. Turn state is durable in our own tables
(``setup`` loads session_state, ``persist`` writes it); a LangGraph checkpointer
would duplicate that and buys only interrupt/resume/time-travel, none of which the
run-to-completion turn needs. Upgrade path: pass an ``AsyncPostgresSaver`` to
``compile(checkpointer=...)`` if durable mid-turn resume is ever required.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.graph.nodes.assemble import assemble
from boerdi.graph.nodes.assess import assess
from boerdi.graph.nodes.context_greeting import context_greeting
from boerdi.graph.nodes.merge import merge
from boerdi.graph.nodes.page_context_enrich import page_context_enrich
from boerdi.graph.nodes.persist import persist
from boerdi.graph.nodes.preflight import preflight
from boerdi.graph.nodes.respond import respond
from boerdi.graph.nodes.route import route
from boerdi.graph.nodes.setup import setup
from boerdi.graph.nodes.tour import tour
from boerdi.graph.state import TurnContext
from boerdi.obs.progress import TurnProgress
from boerdi.obs.quality_events import log_safety_event
from boerdi.services.config_loader import load_safety_config
from boerdi.services.db_sessions import get_memory, save_message

logger = logging.getLogger(__name__)


async def _persist_user_message(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Persist the user turn (ALT ``chat_turn_setup.py:128``) between tour and
    preflight. Bare await like ALT — a DB failure propagates to the endpoint."""
    await save_message(session, ctx.req.session_id, "user", ctx.req.message)
    return ctx


async def _log_turn_safety(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Main per-turn safety-log (ALT ``chat_turn_setup.py:202-212``): every safety
    decision, gated by ``safety-config.logging.{enabled,log_all_turns}`` and
    ``risk_level``. After assess, before route — so fast-path early exits are audited
    too. Telemetry only: never let a log failure break the turn."""
    try:
        log_cfg = load_safety_config().get("logging") or {}
        if log_cfg.get("enabled", True) and (
            log_cfg.get("log_all_turns", False) or ctx.safety.risk_level != "low"
        ):
            await log_safety_event(
                session, ctx.req.session_id, ctx.req.message, ctx.safety, ip=ctx.client_ip,
            )
    except Exception as err:
        # The ``commit`` inside ``log_safety_event`` can fail and leave the
        # shared session in an aborted transaction; without the rollback the
        # turn's own persistence (state + assistant reply) fails afterwards.
        # Telemetry must not stop the turn — and must not take the real work
        # down with it either (audit 2026-08-12, F-1).
        logger.warning("safety log failed: %s", err)
        try:
            await session.rollback()
        except Exception:
            # No re-raise: this function promises never to break the turn.
            logger.debug("safety log: rollback failed too", exc_info=True)
    return ctx


def _after_tour(ctx: TurnContext) -> str:
    """Tour set an answer ⇒ end the turn; otherwise resolve page context, then greet."""
    return END if ctx.early_response is not None else "page_context_enrich"


def _after_context_greeting(ctx: TurnContext) -> str:
    """A context-open greeting (or its empty short-circuit) ⇒ end the turn; otherwise
    persist the user turn and continue the normal flow."""
    return END if ctx.early_response is not None else "persist_user"


def _after_preflight(ctx: TurnContext) -> str:
    """A direct action answered (or was blocked) ⇒ end; otherwise assess."""
    return END if ctx.early_response is not None else "assess"


def build_turn_graph(
    *,
    session: AsyncSession,
    peer_ip: str = "",
    on_token: Any = None,
    progress: TurnProgress | None = None,
    engine: str = "pattern",
) -> CompiledStateGraph:
    """Compose + compile the per-request turn graph with its seams bound.

    ``session`` is threaded into every DB-touching node; ``peer_ip`` reaches
    ``setup`` (client-IP resolution); ``on_token`` reaches ``respond`` (SSE token
    streaming). ``progress`` (C9) reaches the four nodes that report a step to the
    SSE stream; omitted (``POST /api/chat``) it becomes a sink-less no-op, so the
    nodes call it unconditionally. ``memory_fetch`` for ``assess`` is ``get_memory``
    bound to this session. ``engine`` (A4) picks the machine that answers this
    turn — ``"pattern"`` (the default, and the shipped one) or ``"agent"``;
    ``services/engine_choice.choose_engine`` resolves it at the HTTP edge. It
    reaches ``assess`` (no classifier), ``route`` (no pattern selection, no
    fast-paths) and ``respond`` (delegates to ``respond_agent``); every other
    node runs the same either way.
    Returns a compiled graph whose
    ``.ainvoke(TurnContext(req=...))`` runs the turn and yields a state dict — read
    ``early_response or response`` from it.
    """
    memory_fetch = functools.partial(get_memory, session)
    progress = progress or TurnProgress()

    g: StateGraph = StateGraph(TurnContext)
    g.add_node("setup", functools.partial(setup, session=session, peer_ip=peer_ip))
    g.add_node("tour", functools.partial(tour, session=session))
    g.add_node("page_context_enrich", page_context_enrich)
    g.add_node("context_greeting", functools.partial(context_greeting, session=session))
    g.add_node("persist_user", functools.partial(_persist_user_message, session=session))
    g.add_node("preflight", functools.partial(preflight, session=session))
    g.add_node("assess", functools.partial(
        assess, memory_fetch=memory_fetch, progress=progress, engine=engine))
    g.add_node("safety_log", functools.partial(_log_turn_safety, session=session))
    g.add_node("merge", merge)
    g.add_node("route", functools.partial(route, progress=progress, engine=engine))
    g.add_node("respond", functools.partial(
        respond, session=session, on_token=on_token, progress=progress,
        engine=engine))
    g.add_node("assemble", assemble)
    g.add_node("persist", functools.partial(persist, session=session, progress=progress))

    g.add_edge(START, "setup")
    g.add_edge("setup", "tour")
    g.add_conditional_edges(
        "tour", _after_tour, {"page_context_enrich": "page_context_enrich", END: END}
    )
    g.add_edge("page_context_enrich", "context_greeting")
    g.add_conditional_edges(
        "context_greeting", _after_context_greeting, {"persist_user": "persist_user", END: END}
    )
    g.add_edge("persist_user", "preflight")
    g.add_conditional_edges("preflight", _after_preflight, {"assess": "assess", END: END})
    g.add_edge("assess", "safety_log")
    g.add_edge("safety_log", "merge")
    g.add_edge("merge", "route")
    g.add_edge("route", "respond")
    g.add_edge("respond", "assemble")
    g.add_edge("assemble", "persist")
    g.add_edge("persist", END)

    return g.compile()
