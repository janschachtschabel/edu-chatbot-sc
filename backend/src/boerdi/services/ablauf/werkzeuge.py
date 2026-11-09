"""Was ein ``werkzeug``-Schritt rufen darf (Paket A1): eigene Dienste und lesende MCP-Werkzeuge.

Schreibende Werkzeuge (``domain/write_confirm.CURATION_TOOLS``) nur mit Freigabe am Schritt
(Paket S,
:func:`freigebbar`). Ein Dienst ist eine reine Funktion Argumente → Wert (oder ``None``,
wenn nichts entsteht); sein Wert wird ein Teil des Vorgangs.
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


DIENSTE: Final[dict[str, Dienst]] = {
    "strukturentwurf_aus_ordnern": _strukturentwurf_aus_ordnern,
    "abdeckung_zaehlen": _abdeckung_zaehlen,
}

#: Die MCP-Werkzeuge, die ein Dienst ruft — sperrt die Sicherheitsprüfung eines davon (etwa bei
#: persönlichen Daten, ``regex_gate.SPERRE_PERSOENLICH``), ist der Dienst mit gesperrt (Review M1,
#: Befund 6).
DIENST_MCP: Final[dict[str, frozenset[str]]] = {
    "abdeckung_zaehlen": frozenset({"count_wlo_content_matches"}),
}

#: Lesende MCP-Werkzeuge, die ein Schritt rufen darf (am Code geprüft, 2026-11-05).
LESENDE_MCP: Final = frozenset({
    "search_wlo_all", "get_node_details", "browse_collection_tree", "get_collection_contents",
    "get_topic_page_content",
})


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
