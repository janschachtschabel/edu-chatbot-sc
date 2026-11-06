"""Was ein ``werkzeug``-Schritt rufen darf (Paket A1): eigene Dienste und lesende MCP-Werkzeuge.

Schreibende Werkzeuge (``domain/write_confirm.CURATION_TOOLS``) sind ausgeschlossen, bis Paket S die
Freigabe am Schritt bringt. Ein Dienst ist eine reine Funktion Argumente → Wert (oder ``None``,
wenn nichts entsteht); sein Wert wird ein Teil des Vorgangs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Final

from boerdi.domain.write_confirm import CURATION_TOOLS
from boerdi.ui_module.namen import UPLOAD

Dienst = Callable[[dict[str, Any]], Awaitable[Any]]


async def _strukturentwurf_aus_ordnern(args: dict[str, Any]) -> Any:
    """Die erfasste Ordnerstruktur als Entwurf (ohne LLM, ``strukturentwurf_ordner``)."""
    from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern

    quelle = args.get("struktur")
    if isinstance(quelle, dict) and isinstance(quelle.get("struktur"), dict):
        quelle = quelle["struktur"]   # der Teil ``structure`` trägt {struktur, zahlen}
    return aus_ordnern(quelle)


DIENSTE: Final[dict[str, Dienst]] = {
    "strukturentwurf_aus_ordnern": _strukturentwurf_aus_ordnern,
}

#: Lesende MCP-Werkzeuge, die ein Schritt rufen darf (am Code geprüft, 2026-11-05).
LESENDE_MCP: Final = frozenset({
    "search_wlo_all", "get_node_details", "browse_collection_tree", "get_collection_contents",
    "get_topic_page_content",
})


def schreibend(name: str) -> bool:
    return name in CURATION_TOOLS


def bekannt(name: str) -> bool:
    return name in DIENSTE or name in LESENDE_MCP


#: Module, deren Block der Treiber über ihren Dienst bauen darf, wenn die Daten des Schritts nicht
#: schon fertig zum Vertrag passen — nur Dienste ohne Sprachmodell (Review A1, Befund 4).
MODUL_DIENST_OHNE_MODELL: Final = frozenset({UPLOAD})
