"""Preflight node — direct-action safety-dispatch (P4-2b, R2).

Port of the direct-action half of ALT ``chat_pipeline_phases._run_preflight_guards``.
When ``req.action`` is one of the three direct actions (browse_collection /
generate_learning_path / curate_collection), the node screens the concatenated
user text through the same safety gate the regular flow uses, blocks a high-risk
request (persisted + logged), and otherwise dispatches to the R5 handler — the
result becomes ``ctx.early_response`` and the graph skips assess/route/respond.
Any other action (or none) leaves ``early_response`` None so the turn continues.

**Not ported here — the rate-limit branch.** NEU rate-limits at the slowapi HTTP
layer (``api/ratelimit.py``, P1-4): a decorator on ``/api/chat`` that raises
``RateLimitExceeded`` before the graph runs, so there is no in-pipeline
``check_rate_limit``. ALT's friendly rate-limit bubble + its
``log_safety_event(rate_limited=True)`` land with the endpoint layer (R4).

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
from boerdi.obs.quality_events import log_safety_event
from boerdi.services.db_sessions import save_message
from boerdi.services.direct_actions import (
    _direct_action_safety_text,
    _handle_browse_collection,
    _handle_curate_collection,
    _handle_generate_learning_path,
)
from boerdi.services.safety import assess_safety
from boerdi.services.safety.regex_gate import regex_gate

logger = logging.getLogger(__name__)

_DIRECT_ACTIONS = {
    "browse_collection",
    "generate_learning_path",
    "curate_collection",
}

_BLOCK_MESSAGE = (
    "Diese Anfrage konnte ich nicht bearbeiten — sie verletzt "
    "Sicherheits- oder Inhaltsregeln. Probier es bitte mit einer "
    "anderen Formulierung erneut."
)


async def preflight(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Screen + dispatch direct actions; set ``ctx.early_response`` on block/dispatch.

    Direct actions skip the pattern engine but MUST still pass the same safety
    gate as the standard flow. Non-direct-action turns fall straight through
    (``early_response`` stays None).
    """
    req = ctx.req
    if req.action not in _DIRECT_ACTIONS:
        return ctx

    safety_text = _direct_action_safety_text(req)
    signals = ctx.session_state.get("signal_history", [])
    # ``assess_safety`` runs the regex gate first internally and short-circuits
    # on a hard hit, so one call gives the full multi-stage gate; on failure we
    # fall back to the pure regex gate.
    try:
        decision = await assess_safety(safety_text, signals)
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
        try:
            await save_message(
                session, req.session_id, "assistant", _BLOCK_MESSAGE,
                debug=err_debug.model_dump(),
            )
        except Exception:
            logger.debug("persisting blocked-action message failed", exc_info=True)
        ctx.early_response = ChatResponse(
            session_id=req.session_id,
            content=_BLOCK_MESSAGE,
            quick_replies=[],
            debug=err_debug,
        )
        return ctx

    if req.action == "browse_collection":
        ctx.early_response = await _handle_browse_collection(session, req, ctx.session_state)
    elif req.action == "generate_learning_path":
        ctx.early_response = await _handle_generate_learning_path(session, req, ctx.session_state)
    elif req.action == "curate_collection":
        ctx.early_response = await _handle_curate_collection(session, req, ctx.session_state)
    return ctx
