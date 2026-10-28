"""Graph-Knoten nach ``safety_log``: ein Zug ohne Moderation, wenn sie Pflicht ist.

Paket 18A (Nutzer-Entscheid E1, 2026-10-28). Die Moderation ist fail-open: fällt
sie aus, steht ``moderation_unavailable`` in der Entscheidung, und der Zug läuft
weiter (``MODERATION_BEI_AUSFALL=offen``, Vorgabe). Steht der Schalter auf
``geschlossen``, endet der Zug hier mit einer freundlichen Absage — vor ``merge``,
also bevor der Vorabruf und die Antwort starten (Klassifikation, Rechtsprüfung und
Einbettung liefen in ``assess`` schon nebenher).

Eigener Knoten statt einer Zeile in ``assess``: ``assess`` hat keine Sitzung und
kann den Zug nicht beenden; die Absage muss wie jede Bot-Antwort in den Verlauf.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langgraph.graph import END

from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.graph.state import TurnContext
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services.db_sessions import save_message
from boerdi.services.safety.service import sperrt_ohne_moderation
from boerdi.services.turn_quality import log_turn_quality

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def pruefung_fehlt(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Setzt bei geschlossenem Schalter und fehlender Moderation die Absage als
    ``early_response`` und speichert sie im Verlauf."""
    if not sperrt_ohne_moderation(ctx.safety):
        return ctx
    lang = resolve_locale(getattr(ctx.req.environment, "locale", None))
    absage = bot_text(lang, "error.moderationUnavailable")
    debug = DebugInfo(pattern="SAFETY: moderation_unavailable", safety=ctx.safety)
    logger.warning("turn not answered: moderation unavailable, "
                   "MODERATION_BEI_AUSFALL=geschlossen")
    try:
        await save_message(session, ctx.req.session_id, "assistant", absage,
                           debug=debug.model_dump())
    except Exception:
        # Die Absage geht trotzdem an die Person; nur der Verlauf fehlt ihr dann.
        logger.warning("persisting the moderation refusal failed", exc_info=True)
    ctx.early_response = ChatResponse(
        session_id=ctx.req.session_id, content=absage, quick_replies=[], debug=debug)
    # Der Zug endet vor ``persist`` — ohne diese Zeile fehlten die Abgewiesenen in der
    # Auswertung (Review 18). Ein Sicherheitsereignis ist es nicht: geprüft hat niemand.
    await log_turn_quality(
        session, ctx.req, debug,
        turn_count=int(ctx.session_state.get("turn_count") or 0),
        response_length=len(absage), cards_count=0,
        page=ctx.req.environment.page, device=ctx.req.environment.device,
    )
    return ctx


def nach_der_pruefung(ctx: TurnContext) -> str:
    """Absage gesetzt ⇒ Zug beenden; sonst weiter zur Musterwahl."""
    return END if ctx.early_response is not None else "merge"
