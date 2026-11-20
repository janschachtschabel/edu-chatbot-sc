"""Die Moderation des ganzen Texts vor Ebene 1 (Plan 2026-11-19, A4, E2) — aus ``dienst`` gelöst.

Was ganz ans Modell geht (``strukturentwurf_dokument.ganzer_text``), ist vorher geprüft, je Stück
über dieselbe Prüfung wie Übersicht und Anfang (``dienst._ebene_eins_pruefen``: Moderation,
``MODERATION_FAILURE_MODE``). Auch ein Chat-Text, dessen Anfang beim Lesen schon geprüft wurde —
das Lesen prüfte nur 4 000 Zeichen.

Review Paket A, MAJOR 2: **ein Platz je Entwurf** — die Moderation teilt ihre Plätze
(``llm_parallel.MODERATION_PARALLEL``) mit den Chat-Zügen aller Personen; die Stücke gehen
nacheinander hinaus (wie die Auszüge, ``strukturentwurf_auszug``). Ein Stück ist so groß, wie
``safety/moderation`` in EINEM Aufruf ganz prüft (8 Abschnitte zu 4 000 mit 200 Überlappung) —
100 000 Zeichen sind vier Aufrufe. Benachbarte Stücke überlappen (NIT 12), damit ein Wort auf der
Grenze ganz in einem steht.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Final

logger = logging.getLogger(__name__)

STUECK_ZEICHEN: Final = 8 * (4000 - 200) + 200
UEBERLAPPUNG: Final = 200
#: Drittes Review A, MAJOR 4: so viel Zeit bleibt nach der Moderation für Ebene 1 (Weg „gliederung“
#: mit kurzer Aufforderung; gemessen 12–25 s mit dem ganzen Text, deutlich weniger ohne).
EBENE1_RESERVE_S: Final = 20.0
#: Ergebnis im Modus ``open``, wenn ein Stück kein Urteil bekam oder die Frist ablief (drittes
#: Review A, MAJOR 4; viertes, MINOR 7) — der Aufrufer nimmt den Weg „gliederung“.
OHNE_URTEIL: Final = "ohne_urteil"

#: Ein Stück → ``abgewiesen``, ``pruefung_fehlt`` oder ``None``.
Pruefe = Callable[[str], Awaitable[str | None]]


def stuecke(text: str) -> list[str]:
    """Die Stücke von ``text`` mit :data:`UEBERLAPPUNG` zwischen Nachbarn."""
    schritt = STUECK_ZEICHEN - UEBERLAPPUNG
    return [text[i:i + STUECK_ZEICHEN]
            for i in range(0, max(len(text) - UEBERLAPPUNG, 1), schritt)]


async def pruefen(text: str, pruefe: Pruefe) -> str | None:
    """Alle Stücke nacheinander — ``abgewiesen`` beendet sofort; sonst ``pruefung_fehlt`` (ein Stück
    ohne Urteil im Modus ``closed``) vor :data:`OHNE_URTEIL` (ohne Urteil im Modus ``open``) vor
    ``None`` (alles geprüft)."""
    gruende = set()
    for teil in stuecke(text):
        grund = await pruefe(teil)
        if grund == "abgewiesen":
            return grund
        gruende.add(grund)
    return next((g for g in ("pruefung_fehlt", OHNE_URTEIL) if g in gruende), None)


async def in_frist(text: str, pruefe: Pruefe, frist_ende: float) -> str | None:
    """:func:`pruefen`, spätestens ``MINDEST_REST_S`` + :data:`EBENE1_RESERVE_S` vor ``frist_ende``
    (Zeitpunkt der Schleife) — zweites Review A, MINOR 4: bis zu vier Aufrufe zu je 8 s überzögen
    sonst die Frist des Laufs. Ergebnis wie :func:`pruefen`; läuft die Frist ab, im Modus
    ``closed`` ``pruefung_fehlt``, sonst :data:`OHNE_URTEIL` — drittes Review A, MAJOR 4: der
    Aufrufer nimmt dann den Weg „gliederung“ (ungeprüft geht der ganze Text nie ans Modell), und
    für dessen Ebene 1 bleibt die Reserve."""
    from boerdi.services.strukturentwurf_lauf import MINDEST_REST_S
    from boerdi.settings import get_settings

    try:
        async with asyncio.timeout_at(frist_ende - MINDEST_REST_S - EBENE1_RESERVE_S):
            return await pruefen(text, pruefe)
    except TimeoutError:
        logger.info("Strukturentwurf: Moderation des ganzen Texts nicht vor der Frist fertig")
        closed = get_settings().moderation_failure_mode == "closed"
        return "pruefung_fehlt" if closed else OHNE_URTEIL
