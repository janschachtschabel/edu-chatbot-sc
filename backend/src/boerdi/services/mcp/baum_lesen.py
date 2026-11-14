"""Einen Sammlungsbaum ganz und in der gespeicherten Reihenfolge lesen (Plan 2026-11-14, SW-1).

Zwei Dinge, die der MCP-Server ab dem Stand „Sammlungsstrukturen“ (14.11.2026) kann und die der
bereitgestellte noch nicht führt:

- ``list_collection_tree``: der Teilbaum unter einer Sammlung als flache Liste — je Untersammlung
  Kennung, Titel, Pfad, Tiefe und Elternknoten, bis vier Ebenen, in Seiten zu höchstens 250. Das
  ist die Tiefe und Menge, die ``wlo_create_collection_tree`` anlegt; ``browse_collection_tree``
  reicht nur bis Ebene 3 und kürzt je Elternknoten. Gemessen am Fachportal Physik (lokal
  gestarteter Server, 14.11.): 144 Sammlungen in 4,7 s, 16,7 kB Text.
- ``order`` an ``browse_collection_tree`` und ``get_collection_overview``: ``"stored"`` liefert die
  Reihenfolge des Repositorys (gesetzte Position, sonst Reihenfolge des Anlegens) statt der
  alphabetischen. Die Abfolge eines Lehrplans geht alphabetisch verloren.

Das Lesewerkzeug steht NICHT im Katalog (``tool_defs.TOOL_DEFINITIONS``), aus demselben Grund wie
die Mehrfachsuche (:mod:`suche_mehrfach`): Den reicht der Muster-Weg als Ganzes weiter, und ein
Server ohne das Werkzeug wiese jeden Aufruf ab.

Die Antwort ist Text des Servers (Markdown, eine Zeile je Sammlung); das Modell bekommt ihn ganz
(``domain/tool_result_redaction``). Karten entstehen keine: Die Liste ist zum Rechnen gedacht
(Entwurf gegen Bestand abgleichen, einen angelegten Baum zurücklesen, Kennungen holen), nicht zum
Zeigen — dafür gibt es den Themenbaum. Aus dem Cache kommt sie nie
(``tool_cache._TOOL_CACHE_BLOCKLIST``): Nach dem Anlegen muss sie frisch sein.
"""

from __future__ import annotations

import copy
from typing import Any, Final

from boerdi.services.mcp import faehigkeiten

WERKZEUG: Final = "list_collection_tree"

DEFINITION: Final[dict[str, Any]] = {
    "type": "function",
    "function": {
        "name": WERKZEUG,
        "description": (
            "Der Teilbaum unter EINER Sammlung als flache Liste: je Untersammlung nodeId, Titel, "
            "Pfad (Titel von der Start-Sammlung abwaerts), Tiefe und parentId — bis 4 Ebenen "
            "tief, in der Reihenfolge, die das Repository haelt (gesetzte Position, sonst "
            "Reihenfolge des Anlegens). Gedacht zum RECHNEN: einen Entwurf gegen den Bestand "
            "abgleichen, einen angelegten Baum zuruecklesen, nodeIds fuer Folgeschritte holen. "
            "Nichts wird je Elternknoten gekuerzt; lange Listen kommen in Seiten — die Antwort "
            "nennt dann den skipCount fuer die naechste Seite. WICHTIG fuer wahrheitsgemaesse "
            "Antworten: vollstaendig ist die Liste nur, wenn die Antwort keinen Hinweis traegt, "
            "dass ein Zweig nicht geantwortet hat, mit dieser Anmeldung nicht lesbar ist oder der "
            "Lauf seine Grenze erreicht hat (dann eine Untersammlung als Start nehmen). "
            "NICHT zum Anschauen oder Stoebern (Themenbaum der Oberflaeche bzw. "
            "browse_collection_tree) und nicht fuer die Inhalte (get_collection_contents)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string",
                           "description": "nodeId der Start-Sammlung. nodeId ODER collection."},
                "collection": {"type": "string",
                               "description": "Titel der Start-Sammlung statt ihrer nodeId, z.B. "
                                              "'Optik'. Er muss genau stimmen; bei mehreren "
                                              "gleichnamigen kommen Kandidaten zurueck. Ein "
                                              "Fachportal besser ueber seine nodeId."},
                "discipline": {"type": "string",
                               "description": "Nur mit collection: Fach, um gleichnamige "
                                              "Sammlungen zu unterscheiden."},
                "depth": {"type": "integer",
                          "description": "Ebenen unter der Start-Sammlung (1-4, Vorgabe 4)."},
                "maxItems": {"type": "integer",
                             "description": "Eintraege je Seite (1-250, Vorgabe 250)."},
                "skipCount": {"type": "integer",
                              "description": "Fuer die naechste Seite: der Wert, den die "
                                             "Antwort nennt."},
                "includeContentCounts": {"type": "boolean",
                                         "description": "Je Sammlung die Zahl ihrer Inhalte "
                                                        "(direkt gelesen, kostet Zeit)."},
            },
        },
    },
}

#: Die Lesewerkzeuge, die ``order`` nehmen, wenn der Server es kennt.
ORDER_WERKZEUGE: Final = ("browse_collection_tree", "get_collection_overview")
_ORDER: Final[dict[str, Any]] = {
    "type": "string", "enum": ["title", "stored"],
    "description": "Reihenfolge der Untersammlungen. 'title' (Vorgabe): alphabetisch. 'stored': "
                   "wie das Repository sie haelt — die gesetzte Position, sonst die Reihenfolge "
                   "des Anlegens. Nimm 'stored', wo die Abfolge etwas bedeutet (Lehrplan, "
                   "angelegter Baum).",
}


_KEINE_REIHENFOLGE: Final = (
    "Die gespeicherte Reihenfolge (order: 'stored') kennt der Server an diesem Werkzeug nicht. "
    "Nichts wurde gelesen: Rufe es ohne order auf — die Reihenfolge ist dann alphabetisch, sag "
    "das, wenn die Abfolge etwas bedeutet.")


def nicht_moeglich(werkzeug: str, argumente: dict[str, Any]) -> str | None:
    """Ein Satz für die KI, wenn sie die gespeicherte Reihenfolge an einem Server verlangt, der
    ``order`` nicht kennt: Er verwürfe das Feld still und lieferte alphabetisch — die KI hielte
    das für die Abfolge des Repositorys (Review SW-1, Befund 7). Sonst ``None``."""
    if (werkzeug in ORDER_WERKZEUGE and argumente.get("order") == "stored"
            and not faehigkeiten.kennt(werkzeug, "order")):
        return _KEINE_REIHENFOLGE
    return None


def angeboten() -> bool:
    """Führt der bereitgestellte Server ``list_collection_tree``?"""
    return faehigkeiten.kennt(WERKZEUG, "depth")


def definitionen() -> list[dict[str, Any]]:
    """Die Definition für das Modell — leer, solange der Server das Werkzeug nicht führt."""
    return [DEFINITION] if angeboten() else []


def erweitert(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Definition mit ``order``, wenn der Server den Parameter an diesem Werkzeug kennt —
    sonst unverändert (dieselbe Definition, keine Kopie)."""
    name = definition.get("function", {}).get("name")
    if name not in ORDER_WERKZEUGE or not faehigkeiten.kennt(name, "order"):
        return definition
    neu = copy.deepcopy(definition)
    neu["function"]["parameters"].setdefault("properties", {})["order"] = dict(_ORDER)
    return neu
