"""Unterthemen im selben Baum aufklappen (Paket U1-h, Plan §18): ein Zweig als Block-Daten.

Der Themenbaum zeigt zwei Ebenen. Bis U1-h öffnete „Unterthemen öffnen“ einen neuen Baum als
neue Antwort (Direktaktion ``show_collection_tree``). Jetzt lädt das Widget die Unterthemen eines
Knotens über ``POST /api/ui/themenbaum/zweig`` und hängt sie in den bestehenden Baum — ohne Zug,
ohne KI, ohne Speichern.

Der Zweig hat die Form der Block-Daten (``themenbaum.daten_aus``): er kommt über dieselbe
Datenquelle wie der Baum selbst (``datenquelle.aufruf``) — Vorgaben aus dem Manifest
(``depth: 2``, ``maxResults: 31``), Deckel, nur http/https, Prüfung gegen ``eingabe``. Ohne
Überschrift: die steht im Modul schon.

Angeboten wie die Direktaktion (``themenbaum_aktion.angebot``), aber **ohne Sperren einer
Sicherheitsprüfung**: Sperren entstehen nur aus dem Text eines Zugs, und hier gibt es keinen.
Angebot und Laden sind getrennt (Review U1-h, Befund 7): der Endpunkt fragt das Angebot vor der
Anmeldung — es hängt nicht an ihr (``allow_curation=False``), die Prüfung der Anmeldung fragt
aber bis 5 s den MCP-Server.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, NamedTuple

from boerdi.services import themenbaum_aktion
from boerdi.ui_module import datenquelle
from boerdi.ui_module.namen import THEMENBAUM

logger = logging.getLogger(__name__)


class Zweig(NamedTuple):
    """``ok`` mit Daten; sonst ``nicht_geladen`` ohne Daten (ohne Text des Servers)."""

    status: Literal["ok", "nicht_geladen"]
    daten: dict[str, Any] | None = None


def zweig_angebot(*, tool_mode: str | None) -> Literal["ja", "aus", "nicht_angeboten"]:
    """Darf aufgeklappt werden? Studio-Schalter und Angebot des Werkzeugs, ohne Sperren."""
    stand = themenbaum_aktion.angebot(blocked_tools=(), tool_mode=tool_mode)
    if stand == "gesperrt":
        logger.info("themenbaum_zweig: Werkzeug in diesem Modus nicht angeboten")
        return "nicht_angeboten"
    return stand


async def zweig_laden(kennung: str) -> Zweig:
    """Die Unterthemen unter ``kennung`` — Kennung und Angebot prüft der Aufrufer."""
    ergebnis = await datenquelle.aufruf(THEMENBAUM, {"nodeId": kennung}, titel="")
    if ergebnis.block is None:
        logger.info("themenbaum_zweig: kein Zweig (%s)", ergebnis.outcome.error)
        return Zweig("nicht_geladen")
    return Zweig("ok", ergebnis.block.daten)
