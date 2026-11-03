"""UI-Blöcke einer Antwort: anlegen, Regeln anwenden, speichern, wiederherstellen (Paket U1).

Ein Block ist ein Aufruf eines UI-Moduls. Je Antwort gelten zwei Regeln (Plan
``2026-11-02-paket-u1-ui-module.md``, U-E4): höchstens fünf Blöcke, und höchstens ein offener
abfragender — zwei offene Fragen zugleich wären mehrdeutig, die nächste Eingabe der Person
gehörte keiner eindeutig. Dazu ein Deckel je Block, damit große Daten nicht still in Antwort
und Verlauf landen; große Daten gehören über eine Datenquelle nachgeladen.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Final

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from boerdi.api.schemas_ui import UiBlock

logger = logging.getLogger(__name__)

#: Schlüssel im gespeicherten Debug-Block der Nachricht (wie ``_dokumente``).
DEBUG_KEY: Final = "_ui_bloecke"
#: Was die Person live als Text sah, wenn der gespeicherte Text davon abweicht: auf dem geratenen
#: Weg (M09/M10/M11) bleibt das Roh-Markdown gespeichert — der Folgezug liest es —, gezeigt wurde
#: nur der Vorspann; der Inhalt steht im Inhaltsrahmen-Block (Review U1 gesamt, Befund 1).
ANZEIGE_TEXT_KEY: Final = "_anzeige_text"
HOECHSTENS_BLOECKE: Final = 5
#: Anzeigende Blöcke (samt Dokumenten), die eine Schleife je Antwort annimmt — ein Platz bleibt
#: der Frage (Review U1 gesamt, Befund 3).
HOECHSTENS_ANZEIGENDE: Final = HOECHSTENS_BLOECKE - 1
#: Werkzeug-Ergebnis für einen anzeigenden Modul-Aufruf ohne Platz.
GENUG_BLOECKE: Final = ("Nicht ausgeführt: Diese Antwort zeigt schon genug Blöcke. Verweise in "
                        "deiner Antwort nicht auf diese Anzeige.")
#: Zeichen der Daten eines Blocks als JSON (~256 KB, wie die gemerkten Schreib-Argumente).
DATEN_DECKEL_ZEICHEN: Final = 256_000


def neuer_block(modul: str, version: int, art: str, daten: dict[str, Any], text: str) -> UiBlock:
    """Ein Block mit frischer Kennung; wirft ``ValidationError`` bei falschen Werten."""
    return UiBlock(block_id=uuid.uuid4().hex[:16], modul=modul, version=version, art=art,
                   daten=daten, text=text)


def _nicht_speicherbar(block: UiBlock) -> str | None:
    """Grund, warum der Block nicht in Antwort und Verlauf darf, sonst ``None``."""
    try:
        groesse = len(block.model_dump_json(include={"daten"}))
    except PydanticSerializationError:
        return "Daten nicht als JSON darstellbar"
    return "Daten über dem Deckel" if groesse > DATEN_DECKEL_ZEICHEN else None


def _offen_abfragend(block: UiBlock) -> bool:
    return block.art == "abfragen" and block.status == "offen"


def platz_fuer_anzeige(belegt: int) -> bool:
    """Darf eine Schleife noch einen anzeigenden Block (Dokument, Baum …) annehmen, wenn schon
    ``belegt`` anzeigende in dieser Antwort stehen? Ein Platz bleibt immer der Frage."""
    return belegt < HOECHSTENS_ANZEIGENDE


def regeln_anwenden(bloecke: list[UiBlock]) -> list[UiBlock]:
    """Die Blöcke einer Antwort nach den Regeln; die Reihenfolge bleibt, Überzähliges fällt weg.

    Die erste offene Frage bleibt immer (Review U1 gesamt, Befund 3): der Zug hat sie sich schon
    gemerkt (``_offene_frage``), die nächste Eingabe der Person gilt als ihre Antwort. Ist kein
    Platz mehr, fallen anzeigende Blöcke weg. Wiederholt angewandt ändert sich nichts.
    """
    speicherbar: list[UiBlock] = []
    for block in bloecke:
        if grund := _nicht_speicherbar(block):
            logger.warning("UI-Block %s verworfen: %s", block.modul, grund)
            continue
        speicherbar.append(block)
    frage = next((b for b in speicherbar if _offen_abfragend(b)), None)
    behalten: list[UiBlock] = []
    platz_fuer_frage = frage is not None
    for block in speicherbar:
        if block is frage:
            behalten.append(block)
            platz_fuer_frage = False
            continue
        if _offen_abfragend(block):
            logger.warning("UI-Block %s verworfen: schon ein offener abfragender Block",
                           block.modul)
            continue
        if len(behalten) + platz_fuer_frage >= HOECHSTENS_BLOECKE:
            logger.warning("UI-Block %s verworfen: mehr als %d Blöcke", block.modul,
                           HOECHSTENS_BLOECKE)
            continue
        behalten.append(block)
    return behalten


def fuer_den_debug_block(bloecke: list[UiBlock]) -> list[dict[str, Any]]:
    """So, wie die Blöcke im gespeicherten Debug-Block der Nachricht stehen."""
    return [b.model_dump(mode="json") for b in bloecke]


def aus_gespeichert(wert: Any) -> list[UiBlock]:
    """Blöcke aus einer gespeicherten Nachricht. Kaputtes fällt weg — der Verlauf muss laden."""
    if not isinstance(wert, list):
        return []
    bloecke: list[UiBlock] = []
    for roh in wert:
        if not isinstance(roh, dict):
            continue
        try:
            bloecke.append(UiBlock.model_validate(roh))
        except ValidationError:
            logger.debug("gespeicherter UI-Block nicht lesbar, übersprungen")
    return bloecke
