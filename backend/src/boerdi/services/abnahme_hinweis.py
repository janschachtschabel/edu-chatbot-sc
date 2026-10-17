"""Ein „Ja“ zu einer Vorschau, die dieser Zug nicht einlösen kann.

Paket 10, Kurzaudit 2026-10-10 S-1/S-3/S-4/S-9.

Eine Abnahme gehört der Anmeldung, unter der die Vorschau entstand
(``write_approval._gehoert_dem_aufrufer``). Gilt die in diesem Zug nicht — ein neuer
Tab (der Zugangsblock liegt je Tab im ``sessionStorage``), eine abgelaufene oder
abgewiesene Anmeldung, ein noch nicht getauschtes Ticket, ein MCP-Server, der bei der
Echtheitsprüfung nicht antwortete —, verwirft ``setup`` den Vorgang. Bis hier ging das
„ja“ dann ohne Zusammenhang an das Modell, und es kam eine neue Vorschau: die Schleife
aus den Meldungen. Jetzt sagt ein fester Satz, warum nichts geschieht, und bietet die
Anmeldung an.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.domain.auth_qr import inject_auth_qr
from boerdi.i18n import Locale, bot_text
from boerdi.services.db_sessions import save_message
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

#: Gesetzt von ``write_approval.discard_stale_approval``, gelesen vom Vorlauf — ein
#: Schlüssel auf oberster Ebene von ``session_state``, lebt also nur diesen Zug.
MERKER = "_zustimmung_ohne_anmeldung"


async def antwort(
    session: AsyncSession | None, req: ChatRequest, session_state: dict, lang: Locale,
) -> ChatResponse | None:
    """Der Hinweis, wenn ``setup`` eine Zustimmung zu einer fremden Vorschau sah."""
    if not session_state.pop(MERKER, False):
        return None
    text = bot_text(lang, "write.callerChanged")
    debug = DebugInfo(pattern="M18", tools_called=[], entities={"reason": "caller_changed"})
    try:
        await save_message(session, req.session_id, "assistant", text, debug=debug.model_dump())
    except Exception:  # noqa: BLE001 — der Hinweis erreicht die Person trotzdem
        logger.warning("Hinweis zur Abnahme nicht gespeichert", exc_info=True)
    return ChatResponse(
        session_id=req.session_id, content=text, debug=debug,
        quick_replies=inject_auth_qr([], blocked=not has_personal_auth(), lang=lang),
    )
