"""Preflight node — rate-limit guard + direct-action safety-dispatch (P4-2b, R2).

Port of ALT ``chat_pipeline_phases._run_preflight_guards``, in ALT's order.

**First the config-driven throttle (C6).** Every turn — action or not — is
counted against the ``rate_limits`` windows from the safety config; over the
limit the node answers with the editor's text and records the one safety event
that can move the ``rate_limited`` counter. Sitting in the graph rather than in
the endpoint gives both ``/api/chat`` and ``/api/chat/stream`` the same brake
from one place. The counter itself lives in ``services/rate_limits``.

**Then the direct actions.** When ``req.action`` is one of them
(browse_collection / generate_learning_path / curate_collection), the node
screens the concatenated user text through the same safety gate the regular flow
uses, blocks a high-risk request (persisted + logged), and otherwise dispatches
to the R5 handler — the result becomes ``ctx.early_response`` and the graph skips
assess/route/respond. Any other action (or none) leaves ``early_response`` None
so the turn continues.

**Neu über ALT hinaus: ``show_content_text`` (M17).** Die Volltext-Aktion des
neuen MCP-Servers gehört hierher und nicht in ein Antwort-Muster — sie muss den
Text unverändert ausliefern (``services/content_text_action``, Begründung dort).
Damit sie das Sicherheits-Gate nicht umgeht, steht sie in derselben Menge wie
die drei ALT-Aktionen.

**Two brakes, on purpose.** The slowapi decorator on the endpoints
(``api/ratelimit.py``, P1-4) is the outer, deployment-tuned guard: one per-IP
limit, answered with HTTP 429 before the graph even starts. The one here is the
inner, editorially-tuned courtesy brake with per-session windows and a friendly
bubble. Neither replaces the other — the outer one protects the process, the
inner one is what the editorial team can shape.

DI (Regel 3): ``session`` is injected — the graph-build (P4-6) binds the request
session, mirroring how ``assess`` injects ``memory_fetch``. Deviation over ALT:
the high-risk log passes the ``SafetyDecision`` object (not ``model_dump()``);
``log_safety_event`` reads it via ``_field`` (R3b), which fixes ALT's silent
getattr-on-dict default. Tests patch the boundaries on THIS module.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.graph.state import TurnContext
from boerdi.i18n import bot_text, resolve_locale
from boerdi.obs.quality_events import log_safety_event
from boerdi.services.content_text_action import _handle_show_content_text
from boerdi.services.db_sessions import save_message
from boerdi.services.direct_actions import (
    _direct_action_safety_text,
    _handle_browse_collection,
    _handle_curate_collection,
    _handle_generate_learning_path,
)
from boerdi.services.rate_limits import check_rate_limit
from boerdi.services.safety import assess_safety
from boerdi.services.safety.regex_gate import regex_gate

logger = logging.getLogger(__name__)

_DIRECT_ACTIONS = {
    "browse_collection",
    "generate_learning_path",
    "curate_collection",
    "show_content_text",
}


async def preflight(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Throttle, then screen + dispatch direct actions; set ``ctx.early_response``.

    The rate-limit check runs for EVERY turn (ALT's order), so a caller cannot
    walk around the brake by sending a direct action. Direct actions skip the
    pattern engine but MUST still pass the same safety gate as the standard flow.
    Turns that are neither throttled nor a direct action fall straight through
    (``early_response`` stays None).
    """
    req = ctx.req
    # Einmal je Zug aufgelöst: beide Texte dieses Knotens (Drosselung und
    # Sicherheits-Block) brauchen dieselbe Sprache.
    lang = resolve_locale(getattr(req.environment, "locale", None))

    verdict = await check_rate_limit(req.session_id, ctx.client_ip, lang)
    if not verdict.allowed:
        # The reason travels as a decision-shaped dict (``_field`` reads dicts):
        # without it every throttled row looks identical, and an operator cannot
        # tell whether to widen the session window or the IP one.
        await log_safety_event(
            session, req.session_id, req.message,
            decision={"reasons": [f"rate_limit:{verdict.reason}"]},
            ip=ctx.client_ip, rate_limited=True,
        )
        ctx.early_response = ChatResponse(
            session_id=req.session_id,
            content=verdict.blocked_message,
            quick_replies=[],
        )
        return ctx

    if req.action not in _DIRECT_ACTIONS:
        return ctx

    safety_text = _direct_action_safety_text(req)
    signals = ctx.session_state.get("signal_history", [])
    # ``assess_safety`` runs the regex gate first internally and short-circuits
    # on a hard hit, so one call gives the full multi-stage gate; on failure we
    # fall back to the pure regex gate.
    try:
        decision = await assess_safety(safety_text, signals, usage_acc=ctx.usage)
    except Exception as err:
        logger.warning("direct-action safety assess failed: %s", err)
        decision = regex_gate(safety_text, signals)

    if decision.risk_level == "high":
        await log_safety_event(
            session, req.session_id, safety_text, decision=decision, ip=ctx.client_ip,
        )
        err_debug = DebugInfo(
            pattern="SAFETY: blocked_direct_action",
            tools_called=[],
            safety=decision,
            entities={"action": str(req.action or "")},
        )
        # C1-f2b6b: die Abweisung folgt der Widget-Sprache. Sie steht direkt
        # hinter dem Sicherheits-Gate, das seit C1-f2c-a auch englische Krisen-
        # und Drohungsformulierungen erkennt — eine deutsche Abweisung darauf
        # wäre der Rest einer halben Übersetzung.
        _block_message = bot_text(lang, "error.safetyBlocked")
        try:
            await save_message(
                session, req.session_id, "assistant", _block_message,
                debug=err_debug.model_dump(),
            )
        except Exception:
            logger.debug("persisting blocked-action message failed", exc_info=True)
        ctx.early_response = ChatResponse(
            session_id=req.session_id,
            content=_block_message,
            quick_replies=[],
            debug=err_debug,
        )
        return ctx

    if req.action == "browse_collection":
        ctx.early_response = await _handle_browse_collection(
            session, req, ctx.session_state, usage_acc=ctx.usage)
    elif req.action == "generate_learning_path":
        # Der Zug-Merkposten muss mit: die Direkt-Aktion ruft dieselben
        # LLM-Generatoren wie der Hauptweg, und weil sie den Zug hier beendet,
        # gibt es danach keine Stelle mehr, die noch buchen könnte (K1b).
        ctx.early_response = await _handle_generate_learning_path(
            session, req, ctx.session_state, usage_acc=ctx.usage)
    elif req.action == "curate_collection":
        ctx.early_response = await _handle_curate_collection(
            session, req, ctx.session_state, usage_acc=ctx.usage)
    elif req.action == "show_content_text":
        ctx.early_response = await _handle_show_content_text(session, req, ctx.session_state)
    return ctx
