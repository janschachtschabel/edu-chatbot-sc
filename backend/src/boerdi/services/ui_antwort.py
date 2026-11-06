"""Die offene Frage eines UI-Moduls im ersten Knoten des Zugs schließen (Paket U1-d1).

Gerufen in ``graph/nodes/setup`` — vor der Schreib-Abnahme (jede Modul-Antwort zählt dort als
NEIN, auch eine verworfene; Review U1-d1) und vor jedem frühen Ausgang. Prüfregeln in
``ui_module/antwort``.

**Jeder Vordergrund-Zug schließt die Frage**, auch ohne Antwort: Danach gehört die nächste Eingabe
der Person keiner Frage mehr, und eine späte ``ui_antwort`` (zweites Fenster, gespeicherter
Verlauf) trifft nichts. Gespeichert wird sofort — wie bei der Schreib-Abnahme gehen nicht alle
Wege nach dem Vorlauf über ``persist`` (Direkt-Aktionen, Tour).

**Ein Hintergrund-Zug** (Kontext-Ping, Tour-Tick; ``domain/hintergrund_zug``) schickt das Widget
von sich aus; er ist keine Antwort der Person. Er lässt die Frage stehen und trägt nie eine
Antwort.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest
from boerdi.services.db_sessions import update_session
from boerdi.ui_module.antwort import OFFENE_FRAGE, antwort_pruefen

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrageSchluss:
    """Was der Zug über die offene Frage weiß.

    ``antwort``: die geprüfte Antwort (``ui_module/antwort.antwort_pruefen``) oder ``None``.
    ``frage``: die Frage, die dieser Zug geschlossen hat (``merke_frage``) — ohne geprüfte Antwort
    steht sie gerahmt vor der Nachricht an die KI (Review U1-d1, Befund 3). ``None`` ohne offene
    Frage und im Hintergrund-Zug.
    """

    antwort: dict[str, Any] | None = None
    frage: dict[str, Any] | None = None


async def offene_frage_schliessen(
    session: AsyncSession | None, req: ChatRequest, session_state: dict, *,
    hintergrund: bool = False,
) -> FrageSchluss:
    """Die offene Frage schließen und eine mitgeschickte Antwort prüfen.

    ``hintergrund``: ein Zug, den das Widget von sich aus schickt (Kontext-Ping, Tour-Tick) oder das
    automatische Abholen eines Ablauf-Auftrags (Querschnitts-Review 2026-11-06, M1) — die offene
    Frage bleibt dann offen, eine mitgeschickte Antwort wird verworfen.

    Setzt ``req.ui_antwort`` auf ``None``, wenn sie nicht geprüft übernommen wird — die übrigen
    Knoten sehen dann einen gewöhnlich getippten Zug. Dass eine Antwort KAM, merkt sich ``setup``
    vorher: für die Schreib-Abnahme zählt auch eine verworfene als NEIN.
    """
    if hintergrund:
        if req.ui_antwort is not None:
            logger.info("UI-Antwort in einem Hintergrund-Zug verworfen")
        req.ui_antwort = None
        return FrageSchluss()
    entities = session_state.setdefault("entities", {})
    offen = entities.pop(OFFENE_FRAGE, None)
    geprueft = antwort_pruefen(offen, req.ui_antwort) if req.ui_antwort is not None else None
    if geprueft is None:
        req.ui_antwort = None
    if offen is not None:
        await update_session(session, req.session_id, entities=entities)
    return FrageSchluss(antwort=geprueft, frage=offen if isinstance(offen, dict) else None)
