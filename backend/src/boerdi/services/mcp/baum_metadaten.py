"""Fach, Bildungsstufe und Schlagworte gleich beim Anlegen eines Sammlungsbaums (Plan 2026-11-14,
SW-2).

``wlo_create_collection_tree`` nimmt ab dem MCP-Stand „Sammlungsstrukturen“ (14.11.2026) je Knoten
``discipline``, ``educationalContext`` und ``keywords`` und dazu gemeinsame Werte für den ganzen
Baum (``shared``). Vorher brauchte das einen zweiten Aufruf (``wlo_update_contents``) mit einer
zweiten Bestätigung. Derselbe Stand setzt die Reihenfolge der Eingabe ausdrücklich
(``order_not_set`` an einem Knoten heißt: angelegt, die Reihenfolge der Ebene ließ sich nicht
setzen).

Der bereitgestellte Server kennt die Felder noch nicht und prüft jede Ebene streng: Ein fremdes
Feld in einem tieferen Knoten kippt den ganzen Aufruf (Review 2026-11-07). Deshalb zwei Stellen:

- :func:`erweitert` bietet der KI die Felder nur an, wenn der Server sie führt.
- :func:`fuer_den_server` nimmt sie vor dem Senden wieder heraus, wenn er sie nicht führt — so
  wie das Argumentmodell fremde Felder schon immer herausnahm. Was dabei verloren ginge, sieht
  die Person in der Vorschau, die jeden Knoten mit seinen Werten nennt.
"""

from __future__ import annotations

import copy
from typing import Any, Final

from boerdi.api.schemas_mcp_curation import BAUM_METADATEN
from boerdi.services.mcp import faehigkeiten

WERKZEUG: Final = "wlo_create_collection_tree"
#: Die Felder je Knoten (und in ``shared``), die nur der neuere Server kennt.
FELDER: Final = BAUM_METADATEN

_ETIKETT: Final[dict[str, Any]] = {"type": "array", "items": {"type": "string"}}
_KNOTENFELDER: Final[dict[str, Any]] = {
    "discipline": {**_ETIKETT, "description": "Fach als Bezeichnung(en), z.B. ['Physik']. Eine "
                                              "leere Liste schaltet den gemeinsamen Wert fuer "
                                              "diesen Knoten ab."},
    "educationalContext": {**_ETIKETT, "description": "Bildungsstufe als Bezeichnung(en), z.B. "
                                                      "['Sekundarstufe I']."},
    "keywords": {**_ETIKETT, "description": "Schlagworte dieses Knotens."},
}
_SHARED: Final[dict[str, Any]] = {
    "type": "object",
    "description": "Gemeinsame Werte fuer JEDEN neuen Knoten des Baums. Ein Knoten, der dasselbe "
                   "Feld selbst nennt, ersetzt den gemeinsamen Wert.",
    "properties": {
        "discipline": {**_ETIKETT, "description": "Fach als Bezeichnung(en), z.B. ['Physik']."},
        "educationalContext": {**_ETIKETT,
                               "description": "Bildungsstufe, z.B. ['Sekundarstufe I']."},
        "keywords": {**_ETIKETT, "description": "Schlagworte."},
    },
    "additionalProperties": False,
}
ZUSATZ: Final = (
    " Fach (discipline), Bildungsstufe (educationalContext) und Schlagworte (keywords) gleich "
    "mitgeben: gemeinsam fuer den ganzen Baum als shared, abweichend am einzelnen Knoten — so "
    "braucht es keinen zweiten Aufruf. Nur Namen aus dem Vokabular, kein Teilwort; lehnt der "
    "Server einen Wert ab, einen seiner Vorschlaege nehmen. Eine mit merge uebernommene "
    "Sammlung bleibt unveraendert, auch ihre Werte. Die neuen Untersammlungen stehen danach in "
    "der Reihenfolge, in der du sie nennst."
)


def angeboten() -> bool:
    """Nimmt der bereitgestellte Server Fach, Stufe und Schlagworte im Baum an?"""
    return faehigkeiten.kennt(WERKZEUG, "shared")


def _mit_feldern(knoten: dict[str, Any]) -> None:
    """Die Felder an diesem Knoten-Schema und an allen darunter."""
    eigenschaften = knoten.get("properties")
    if not isinstance(eigenschaften, dict):
        return
    for feld, schema in _KNOTENFELDER.items():
        eigenschaften.setdefault(feld, dict(schema))
    kinder = eigenschaften.get("children")
    if isinstance(kinder, dict) and isinstance(kinder.get("items"), dict):
        _mit_feldern(kinder["items"])


def erweitert(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Definition des Baum-Werkzeugs mit ``shared`` und den Feldern je Knoten, wenn der
    Server sie kennt — sonst unverändert (dieselbe Definition, keine Kopie)."""
    if definition.get("function", {}).get("name") != WERKZEUG or not angeboten():
        return definition
    neu = copy.deepcopy(definition)
    funktion = neu["function"]
    eigenschaften = funktion["parameters"].setdefault("properties", {})
    eigenschaften["shared"] = copy.deepcopy(_SHARED)
    baum = eigenschaften.get("tree")
    if isinstance(baum, dict) and isinstance(baum.get("items"), dict):
        _mit_feldern(baum["items"])
        baum["description"] = (
            "Knoten {title, description?, discipline?, educationalContext?, keywords?, "
            "children?} — hoechstens 250, Tiefe 4, 15 Kinder je Knoten.")
    funktion["description"] = funktion["description"] + ZUSATZ
    return neu


def _ohne_felder(knoten: Any) -> Any:
    if not isinstance(knoten, dict):
        return knoten
    aus = {k: v for k, v in knoten.items() if k not in FELDER}
    if isinstance(aus.get("children"), list):
        aus["children"] = [_ohne_felder(k) for k in aus["children"]]
    return aus


def fuer_den_server(werkzeug: str, argumente: dict[str, Any]) -> dict[str, Any]:
    """Die Argumente, wie der bereitgestellte Server sie versteht: ohne ``shared`` und ohne die
    Felder je Knoten, solange er sie nicht führt. Andere Werkzeuge und ein Server, der sie
    kennt, bekommen die Argumente unverändert."""
    if werkzeug != WERKZEUG or angeboten():
        return argumente
    aus = {k: v for k, v in argumente.items() if k != "shared"}
    if isinstance(aus.get("tree"), list):
        aus["tree"] = [_ohne_felder(k) for k in aus["tree"]]
    return aus


HINWEIS: Final = (
    "Hinweis: Fach, Bildungsstufe und Schlagworte wurden NICHT mitgesendet — der Server nimmt "
    "sie beim Anlegen eines Baums noch nicht an. Angelegt wird nur mit Titel und Beschreibung.")


def hinweis(werkzeug: str, eingang: dict[str, Any], gesendet: dict[str, Any]) -> str | None:
    """Der Satz vor der Antwort, wenn :func:`fuer_den_server` Felder herausgenommen hat — sonst
    erführen weder KI noch Person, dass Fach, Stufe und Schlagworte nicht mitgingen (Review SW-2,
    Befund 4)."""
    return HINWEIS if werkzeug == WERKZEUG and eingang != gesendet else None
