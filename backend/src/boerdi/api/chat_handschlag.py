"""Was der ``connected``-Rahmen des Chat-Stroms dem Widget sagt (Review Paket 7, A-7/C-4).

Bricht der Strom nach dem Handschlag ab, rechnet der Zug zu Ende, und das Widget holt
die Antwort aus dem Verlauf (P2). Dafür braucht es zwei Angaben:

- ``history`` — ob die Antwort dort überhaupt ankommt. Mit
  ``privacy-config.logging.messages: false`` wird nichts gespeichert; das Widget
  fragte dann 100 s vergeblich nach. So fällt es wie vor Paket 7 auf
  ``POST /api/chat`` zurück, und der Zug bricht beim Auflegen ab, statt die
  Sitzungssperre gegen genau diesen zweiten Versand zu halten.
- ``after_id`` — die höchste Nachrichten-ID der Sitzung VOR dem Zug. Die Frage wird
  erst nach der Sitzungssperre gespeichert; ohne die ID hielte das Widget eine
  frühere Antwort auf dieselbe Frage („Ja“, „Weiter“) für die neue.

Gelesen wird, bevor der Zug startet — danach könnte er die Frage schon abgelegt
haben. Scheitert der Blick in den Verlauf, bleibt ``after_id`` offen (``None``), und
das Widget ordnet wie bisher nur über den Text zu.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.services.db_sessions import last_message_id, messages_enabled

logger = logging.getLogger(__name__)

#: Länger darf der Blick in den Verlauf den Handschlag nicht aufhalten.
_FRIST_S = 1.0


async def handschlag(
    session_id: str, sitzungen: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Die Nutzlast des ``connected``-Rahmens. Wirft nicht."""
    if not messages_enabled():
        return {"history": False, "after_id": None}
    try:
        async with asyncio.timeout(_FRIST_S), sitzungen() as session:
            letzte = await last_message_id(session, session_id)
    except Exception as e:  # noqa: BLE001 — ohne ID kostet es nur die Zuordnung
        logger.warning("Handschlag: letzte Nachrichten-ID nicht lesbar (%s)",
                       type(e).__name__)
        return {"history": True, "after_id": None}
    return {"history": True, "after_id": letzte or 0}
