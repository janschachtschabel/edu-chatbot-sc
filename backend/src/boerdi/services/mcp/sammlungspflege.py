"""Sammlungen pflegen: Stapel-Werkzeuge, Umhängen, Reihenfolge, Vorschläge (Plan 2026-11-14, SW-3).

Sieben Kuratier-Werkzeuge kennt der MCP-Server ab dem Stand „Sammlungsstrukturen“ (14.11.2026);
der bereitgestellte führt sie noch nicht:

- ``wlo_submit_contents``: viele Materialien zur Prüfung einreichen (Plan, bis 200).
- ``wlo_remove_from_collections``: viele Verweise aus Sammlungen nehmen (Plan, bis 200).
- ``wlo_delete_collections``: viele LEERE Sammlungen löschen (Plan, bis 200).
- ``wlo_move_collection``: eine Sammlung samt Teilbaum umhängen.
- ``wlo_order_collection``: die Reihenfolge der Untersammlungen oder der Inhalte setzen.
- ``wlo_list_collection_proposals`` / ``wlo_decide_collection_proposal``: Vorschläge an eine
  Sammlung lesen und entscheiden.

Anders als die bedingten Lesewerkzeuge (:mod:`suche_mehrfach`, :mod:`baum_lesen`) stehen sie im
Katalog (``tool_defs_curation``, Entscheid SE-2): Nur so greifen Bestätigung, Pläne,
Argumentmodelle, Cache-Sperre und die Wächter-Tests von selbst. Angeboten werden sie trotzdem
nur, wenn der Server sie führt (:func:`gefuehrt`) — die Agent-Schleife und der Muster-Weg fragen
das je Werkzeug ab.

Dazu zwei Erweiterungen an vorhandenen Werkzeugen desselben Stands:

- ``removeFrom`` je Paar an ``wlo_add_to_collections`` (Umsortieren: erst aufnehmen, dann aus der
  Quelle nehmen). An einem Server ohne den Parameter bliebe das Material still in der Quelle
  liegen — der Client lehnt den Aufruf deshalb selbst ab (:func:`nicht_moeglich`).
- Wo die Anmeldung an einer Sammlung nur lesen darf, schlägt der Server vor, statt aufzunehmen
  (Status ``proposed``). Die Beschreibung sagt der KI, was das heißt.
"""

from __future__ import annotations

import copy
from typing import Any, Final

from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD, FORTSETZEN_FIELD
from boerdi.services.mcp import faehigkeiten

#: Werkzeug → ein Pflichtparameter, an dem die Fähigkeitsabfrage es erkennt.
_MARKEN: Final[dict[str, str]] = {
    "wlo_submit_contents": "items",
    "wlo_remove_from_collections": "pairs",
    "wlo_delete_collections": "nodeIds",
    "wlo_move_collection": "newParentId",
    "wlo_order_collection": "order",
    "wlo_list_collection_proposals": "collectionId",
    "wlo_decide_collection_proposal": "decision",
}
#: Die Kuratier-Werkzeuge, die nur der neuere Server führt.
WERKZEUGE: Final = frozenset(_MARKEN)

STAPEL_AUFNAHME: Final = "wlo_add_to_collections"
_AUFNAHME: Final = frozenset({"wlo_add_to_collection", STAPEL_AUFNAHME})
#: Der Server-Stand, der ``removeFrom`` und das Vorschlagen kennt, führt auch dieses Werkzeug.
#: (Die Fähigkeitsabfrage sieht nur die oberste Ebene eines Schemas, ``removeFrom`` steht tiefer.)
_STAND: Final = ("wlo_remove_from_collections", "pairs")

_REMOVE_FROM: Final[dict[str, Any]] = {
    "type": "string",
    "description": "Zum UMSORTIEREN: nodeId der Quell-Sammlung, aus der das Material NACH dem "
                   "Aufnehmen herausgenommen wird.",
}
_VORSCHLAG: Final = (
    " Wo du an einer Sammlung nur lesen, aber nicht schreiben darfst, wird das Material "
    "VORGESCHLAGEN statt aufgenommen (Status proposed; die Vorschau sagt es vorher). Vorgeschlagen "
    "ist NICHT aufgenommen: Sag das der Person; die Redaktion der Sammlung entscheidet. Die "
    "Vorschau nennt auch Materialien, die noch nicht oeffentlich sind — das Einsortieren macht "
    "sie nicht oeffentlich."
)
_UMSORTIEREN: Final = (
    " Zum Umsortieren je Paar removeFrom nennen: erst wird aufgenommen, dann aus der Quelle "
    "genommen (Status moved). Scheitert das Herausnehmen, liegt das Material in beiden Sammlungen "
    "und die Antwort sagt es."
)
_KEIN_UMSORTIEREN: Final = (
    "removeFrom (Umsortieren) kennt der Server nicht. Nichts wurde geaendert: Nimm das Material "
    "erst auf und danach einzeln aus der alten Sammlung, oder sag der Person, dass es so nicht "
    "geht.")


def gefuehrt(werkzeug: str) -> bool:
    """Darf dieses Werkzeug angeboten werden? Ja für alles, was jeder Stand des Servers führt;
    für die sieben neuen nur, wenn der bereitgestellte Server sie nennt."""
    marke = _MARKEN.get(werkzeug)
    return marke is None or faehigkeiten.kennt(werkzeug, marke)


def _neuer_stand() -> bool:
    return faehigkeiten.kennt(*_STAND)


def erweitert(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Definition der beiden Einsortier-Werkzeuge, wie der neuere Server sie versteht: mit
    dem Hinweis aufs Vorschlagen und, im Stapel, mit ``removeFrom`` je Paar. Sonst unverändert
    (dieselbe Definition, keine Kopie)."""
    name = definition.get("function", {}).get("name")
    if name not in _AUFNAHME or not _neuer_stand():
        return definition
    neu = copy.deepcopy(definition)
    funktion = neu["function"]
    funktion["description"] += _VORSCHLAG
    if name == STAPEL_AUFNAHME:
        paare = funktion["parameters"]["properties"].get("pairs", {})
        if isinstance(paare.get("items"), dict):
            paare["items"].setdefault("properties", {})["removeFrom"] = dict(_REMOVE_FROM)
        funktion["description"] += _UMSORTIEREN
    return neu


_NUR_JE_PAAR: Final = (
    "removeFrom gehoert an jedes Paar von wlo_add_to_collections (pairs: [{nodeId, collectionId, "
    "removeFrom}]), nicht an diese Stelle. Nichts wurde geaendert: Fuer ein einzelnes Material "
    "nimm ein Paar, wenn das Werkzeug removeFrom anbietet; sonst erst aufnehmen, dann aus der "
    "alten Sammlung nehmen.")


def nicht_moeglich(werkzeug: str, argumente: dict[str, Any]) -> str | None:
    """Ein Satz für die KI, wenn ein Umsortieren so nicht gehen kann — sonst ``None``.

    - ``removeFrom`` an der falschen Stelle (am einzelnen Werkzeug, auf oberster Ebene): Der
      Server nähme nur auf, und die KI meldete „umsortiert“ (Review SW-3, Befund 5).
    - ``removeFrom`` je Paar an einem Server, der es nicht kennt: Er ließe das Material still in
      der Quelle liegen.

    Ein Aufruf mit einem Schlüssel des Servers (Bestätigung, Fortsetzung) wird nie lokal
    abgelehnt: Die Vorschau dazu hat der Server selbst ausgestellt, und eine Ablehnung hier
    verwürfe einen Plan, der dort schon läuft (Review SW-3, Befund 2 — etwa wenn der Stand des
    Servers nach einem Neustart noch unbekannt ist)."""
    if werkzeug not in _AUFNAHME:
        return None
    if argumente.get("removeFrom"):          # an der falschen Stelle: geht nie zum Server
        return _NUR_JE_PAAR
    if argumente.get(CONFIRM_TOKEN_FIELD) or argumente.get(FORTSETZEN_FIELD):
        return None
    if werkzeug != STAPEL_AUFNAHME or _neuer_stand():
        return None
    paare = argumente.get("pairs")
    if isinstance(paare, list) and any(isinstance(p, dict) and p.get("removeFrom") for p in paare):
        return _KEIN_UMSORTIEREN
    return None
