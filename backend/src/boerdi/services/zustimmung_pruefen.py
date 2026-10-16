"""Stimmt die Person der offenen Vorschau zu? Liste, Veto, dann ein kurzer LLM-Aufruf.

Paket 10, A-6 (Nutzer-Entscheid 2026-10-15): Eine Person darf nicht daran scheitern,
dass ihr Wortlaut nicht in der Erlaubnisliste steht — „ja, rein damit“ führte bis hier
zu einer neuen Vorschau statt zur Ausführung (Kurzaudit S-5). Die Reihenfolge hält die
alte Sicherheit:

1. Erlaubnisliste (``domain/zustimmung.is_affirmation``) — trifft sie, ist es Zustimmung.
2. Veto (``hat_veto``) — Absage, Rückfrage oder Änderungswunsch ist nie Zustimmung.
3. Erst dann das Modell, Temperatur 0, mit fester Antwortform. Nur ``zustimmung`` zählt;
   Fehler, Zeitüberschreitung und jede andere Antwort heißen „nein“ — der Preis ist
   eine zweite Frage, keine Änderung ohne Zustimmung.

Geprüft wird einmal je Zug (``write_approval.discard_stale_approval``); die Leser im
Vorlauf und in der Werkzeug-Schleife nehmen das Urteil über :func:`zugestimmt`.
"""

from __future__ import annotations

import asyncio
import logging

from boerdi.domain.zustimmung import hat_veto, is_affirmation
from boerdi.obs.usage import current_turn_usage
from boerdi.services import llm

logger = logging.getLogger(__name__)

#: Das Urteil dieses Zugs — ein Schlüssel auf oberster Ebene von ``session_state``,
#: lebt also nur diesen Zug.
MERKER = "_zustimmung"

#: Länger wartet die Person nicht auf ein „ja“; danach gilt es als keine Zustimmung.
FRIST_S = 3.0

# Lange Nachrichten sind ein neues Anliegen, keine Antwort auf die Vorschau.
_HOECHSTENS_ZEICHEN = 300

_ANWEISUNG = (
    "Der Chatbot hat einen Schreibvorgang im Bildungsportal WLO vorbereitet "
    "(Werkzeug: {werkzeug}) und die Person gefragt, ob er ausgeführt werden soll. "
    "Ordne ihre Antwort genau einer Klasse zu:\n"
    "zustimmung — sie will den Vorgang so ausführen, wie er gezeigt wurde\n"
    "absage — sie will ihn nicht, nicht jetzt oder bricht ab\n"
    "aenderung — sie will ihn mit anderen Werten oder fragt nach einer Änderung\n"
    "anderes — eine Rückfrage, ein neues Anliegen oder unklar\n"
    "Im Zweifel nicht zustimmung. Antworte nur mit dem einen Wort."
)


async def _llm_urteil(nachricht: str, werkzeug: str) -> bool:
    """Das Modell entscheidet — nur ein klares ``zustimmung`` zählt."""
    try:
        async with asyncio.timeout(FRIST_S):
            resp = await llm.chat_completion(
                messages=[
                    {"role": "system", "content": _ANWEISUNG.format(werkzeug=werkzeug or "?")},
                    {"role": "user", "content": nachricht[:_HOECHSTENS_ZEICHEN]},
                ],
                max_tokens=5,
                temperature=0,
                usage_acc=current_turn_usage(),
                phase="zustimmung",
            )
        urteil = (resp.choices[0].message.content or "").strip().strip(".").lower()
    except Exception:  # noqa: BLE001 — jeder Fehler heißt „keine Zustimmung“
        logger.warning("Zustimmungs-Prüfung fehlgeschlagen — gilt als keine Zustimmung",
                       exc_info=True)
        return False
    logger.info("Zustimmungs-Prüfung für %s: %s", werkzeug, urteil[:20])
    return urteil == "zustimmung"


async def stimmt_zu(nachricht: str, werkzeug: str) -> bool:
    """Ist ``nachricht`` eine Zustimmung zur offenen Vorschau für ``werkzeug``?"""
    if is_affirmation(nachricht):
        return True
    if hat_veto(nachricht) or len(nachricht or "") > _HOECHSTENS_ZEICHEN:
        return False
    return await _llm_urteil(nachricht, werkzeug)


def zugestimmt(session_state: dict, nachricht: str) -> bool:
    """Das Urteil dieses Zugs — ohne gespeichertes Urteil die Erlaubnisliste."""
    if MERKER in session_state:
        return bool(session_state[MERKER])
    return is_affirmation(nachricht)
