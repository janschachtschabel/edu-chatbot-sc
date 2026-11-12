"""Was ein ``werkzeug``-Schritt rufen darf (Paket A1): eigene Dienste und lesende MCP-Werkzeuge.

Schreibende Werkzeuge (``domain/write_confirm.CURATION_TOOLS``) nur mit Freigabe am Schritt
(Paket S,
:func:`freigebbar`). Ein Dienst ist eine Funktion Argumente → Wert (oder ``None``, wenn nichts
entsteht); sein Wert wird ein Teil des Vorgangs. Dienste ohne Netz stehen in :data:`REINE_DIENSTE`,
die übrigen rufen MCP-Werkzeuge (:data:`DIENST_MCP`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Final

from boerdi.domain.write_confirm import CURATION_TOOLS, is_confirmable
from boerdi.ui_module.namen import UPLOAD

Dienst = Callable[[dict[str, Any]], Awaitable[Any]]


async def _strukturentwurf_aus_ordnern(args: dict[str, Any]) -> Any:
    """Die erfasste Ordnerstruktur als Entwurf (ohne LLM, ``strukturentwurf_ordner``)."""
    from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern

    quelle = args.get("struktur")
    if isinstance(quelle, dict) and isinstance(quelle.get("struktur"), dict):
        quelle = quelle["struktur"]   # der Teil ``structure`` trägt {struktur, zahlen}
    return aus_ordnern(quelle)


async def _abdeckung_zaehlen(args: dict[str, Any]) -> Any:
    """Paket M1: wie viele WLO-Inhalte es zu den Punkten des Entwurfs ``entwurf`` gibt
    (``services/abdeckung``, ohne LLM; Zahlen für ganz WLO)."""
    from boerdi.services.abdeckung import fuer_entwurf

    entwurf = args.get("entwurf")
    return await fuer_entwurf(entwurf) if isinstance(entwurf, dict) and entwurf.get(
        "knoten") else None


async def _struktur_mit_nodeids(args: dict[str, Any]) -> Any:
    """Paket AS-Dd: der Entwurf ``entwurf`` mit den Kennungen der Sammlungen, die
    ``wlo_create_collection_tree`` angelegt hat (``angelegt``) — Folgeschritte treffen so die
    richtigen Knoten (``strukturentwurf_bestand.mit_kennungen``, ohne LLM)."""
    from boerdi.ui_module.strukturentwurf_bestand import mit_kennungen

    return mit_kennungen(args.get("entwurf"), args.get("angelegt"))


async def _baum_aus_entwurf(args: dict[str, Any]) -> Any:
    """Paket AS-Dd (Review, Befund 5): der Baum für ``wlo_create_collection_tree`` aus dem Entwurf
    ``entwurf`` — mit dessen Titeln, damit ``struktur_mit_nodeids`` danach jeden Punkt findet."""
    from boerdi.ui_module.strukturentwurf_bestand import baum_aus_entwurf

    return baum_aus_entwurf(args.get("entwurf"))


async def _metadaten_lesen(args: dict[str, Any]) -> Any:
    """Plan 2026-11-10, TB-F2: die Metadaten der abgelegten Nodes aus dem Teil ``ablage``
    (``services/ablauf/metadaten``, ohne LLM, unter der Anmeldung der Person, ohne Cache)."""
    from boerdi.services.ablauf.metadaten import lesen

    return await lesen(args.get("ablage"))


DIENSTE: Final[dict[str, Dienst]] = {
    "strukturentwurf_aus_ordnern": _strukturentwurf_aus_ordnern,
    "abdeckung_zaehlen": _abdeckung_zaehlen,
    "struktur_mit_nodeids": _struktur_mit_nodeids,
    "baum_aus_entwurf": _baum_aus_entwurf,
    "metadaten_lesen": _metadaten_lesen,
}

#: Die MCP-Werkzeuge, die ein Dienst ruft — sperrt die Sicherheitsprüfung eines davon (etwa bei
#: persönlichen Daten, ``regex_gate.SPERRE_PERSOENLICH``), ist der Dienst mit gesperrt (Review M1,
#: Befund 6).
DIENST_MCP: Final[dict[str, frozenset[str]]] = {
    "abdeckung_zaehlen": frozenset({"count_wlo_content_matches"}),
    "metadaten_lesen": frozenset({"get_nodes_details"}),
}

#: Dienste ohne Netz — die Simulation rechnet sie selbst (Querschnitts-Review AS-D, Befund 1: sonst
#: sagte ein von Hand geschriebenes Ergebnis einen Weg voraus, den es nicht gibt).
REINE_DIENSTE: Final = frozenset(DIENSTE) - set(DIENST_MCP)

#: Lesende MCP-Werkzeuge, die ein Schritt rufen darf (am Code geprüft, 2026-11-05).
LESENDE_MCP: Final = frozenset({
    "search_wlo_all", "get_node_details", "browse_collection_tree", "get_collection_contents",
    "get_topic_page_content",
})


def ablauf_schreibt(ablauf: Any) -> bool:
    """Ändert der Ablauf etwas im Repositorium — ein schreibendes Werkzeug, ein Auftrag oder der
    Upload (Querschnitts-Review AS-5, Befund 6)? Solche Abläufe bietet die KI nur mit voller
    Erlaubnis an und startet sie nie direkt (TB-E3)."""
    return any(s.typ == "auftrag" or (s.typ == "modul" and s.modul == UPLOAD)
               or (s.typ == "werkzeug" and schreibend(s.werkzeug or ""))
               # Review TB-E3, Befund 3: auch ein KI-Schritt, der hochladen oder schreiben darf
               or (s.typ == "agent" and s.agent is not None
                   and any(w == UPLOAD or schreibend(w) for w in s.agent.werkzeuge))
               for s in ablauf.schritte)


def ablauf_schreibt_selbst(ablauf: Any) -> bool:
    """TW-6 (Rückmeldung 12.11.): schreibt der Ablauf **von sich aus** — ein Auftrag oder ein
    schreibendes Werkzeug (auch am KI-Schritt)? Das Upload-Feld zählt hier nicht: es überträgt nur
    nach einem eigenen Klick der Person, mit Anmeldung und eingeschaltetem Studio-Schalter. Maßstab
    für den Direktstart (``vorschlag._direkt``); für die Erlaubnis der Einbettung bleibt
    :func:`ablauf_schreibt` (mit Upload)."""
    return any(s.typ == "auftrag"
               or (s.typ == "werkzeug" and schreibend(s.werkzeug or ""))
               or (s.typ == "agent" and s.agent is not None
                   and any(schreibend(w) for w in s.agent.werkzeuge))
               for s in ablauf.schritte)


def schreibend(name: str) -> bool:
    return name in CURATION_TOOLS


#: Paket S (Review S1, Befund 8): Löschen nicht aus einem Ablauf — offen als Entscheid des Nutzers.
_NICHT_IM_ABLAUF: Final = frozenset({"wlo_delete_content", "wlo_delete_collection"})


def freigebbar(name: str) -> bool:
    """Paket S: ein schreibendes Werkzeug, das ein Schritt mit Freigabe rufen darf — bestätigbar
    (Vorschau, Schlüssel), kein Löschen. Seit S4 auch ein Plan (``is_plan``): er läuft nach dem Ja
    mit „Plan fortsetzen“ über mehrere Züge, der Lauf geht weiter, wenn er fertig ist."""
    return is_confirmable(name) and name not in _NICHT_IM_ABLAUF


def bekannt(name: str) -> bool:
    return name in DIENSTE or name in LESENDE_MCP


#: Module, deren Block der Treiber über ihren Dienst bauen darf, wenn die Daten des Schritts nicht
#: schon fertig zum Vertrag passen — nur Dienste ohne Sprachmodell (Review A1, Befund 4).
MODUL_DIENST_OHNE_MODELL: Final = frozenset({UPLOAD})
