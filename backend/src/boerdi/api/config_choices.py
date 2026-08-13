"""S1: die Kataloge, aus denen ein Studio-Formularfeld seine Vorschläge zieht.

Ein Bereichsmodell kann ein Feld mit ``x-catalog: "patterns"`` auszeichnen
(siehe ``config_models/_shared.py``). Was hinter diesem Namen steckt, steht
hier — nicht im Studio: eine abgetippte Liste im Frontend driftet, und genau
das ist in ALT schon zweimal passiert (siehe ``reference-catalogs.ts``).

Eigener Endpunkt statt einer Erweiterung von ``/config/elements``: der
Element-Browser liefert ganze Persona- und Muster-Dokumente samt Fließtext.
Ein Auswahlfeld braucht davon drei Angaben — Wert, Beschriftung und den
Bereichsschlüssel, über den das Studio (Route ``/bereich/**``) direkt dorthin
springen kann. Leeres ``area`` heißt „dafür gibt es keine eigene Seite"; dann
zeigt das Formular keinen toten Link.

Sortiert wird durchgehend nach dem Wert: eine Vorschlagsliste wird
nachgeschlagen, nicht als Reihenfolge gelesen, und die Antwort soll nicht von
der Speicherreihenfolge abhängen.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Security

from boerdi.api.deps import require_studio_key
from boerdi.services import config_loader as cl

router = APIRouter(
    prefix="/api/config", tags=["config-choices"],
    dependencies=[Security(require_studio_key)],
)

Choice = dict[str, str]


def _entry(value: Any, label: Any, area: str) -> Choice | None:
    """Ein Katalog-Eintrag, oder ``None`` wenn er keinen Wert trägt.

    Eine leere Beschriftung fällt auf den Wert zurück — eine leere Zeile in
    einer Auswahlliste wäre nicht bedienbar.
    """
    wert = str(value or "").strip()
    if not wert:
        return None
    return {"value": wert, "label": str(label or "").strip() or wert, "area": area}


def _sorted(entries: list[Choice | None]) -> list[Choice]:
    return sorted((e for e in entries if e), key=lambda e: e["value"])


def _from_documents(docs: list[dict[str, Any]]) -> list[Choice]:
    """Muster und Personas liegen je ein Dokument pro Element.

    Das Sprungziel kommt aus ``_source_file`` — dem Schlüssel, unter dem das
    Dokument WIRKLICH liegt. Aus der Element-ID ließe es sich auch ableiten
    (``_persona_slug``), aber dann zeigte der Link ins Leere, sobald ein
    Dokument unter einem anderen Schlüssel gespeichert ist.
    """
    return _sorted([
        _entry(d.get("id"), d.get("label"), cl._strip_ext(d.get("_source_file", "")))
        for d in docs
    ])


def _from_list(entries: list[dict[str, Any]], area: str) -> list[Choice]:
    return _sorted([_entry(e.get("id"), e.get("label"), area) for e in entries])


def _rag_areas() -> list[Choice]:
    area = "05-knowledge/rag-config"
    return _sorted([_entry(name, name, area) for name in cl.get_all_rag_areas()])


def _tools() -> list[Choice]:
    """Die Vereinigung der Werkzeuge aller EINGESCHALTETEN Server.

    Ein abgeschalteter Server steuert nichts bei: was der Bot nicht rufen kann,
    soll ein Muster auch nicht vorgeschlagen bekommen.
    """
    namen = {
        str(t).strip()
        for server in cl.get_enabled_mcp_servers()
        for t in (server.get("tools") or [])
        if str(t).strip()
    }
    return _sorted([_entry(name, name, "") for name in namen])


#: Katalogname -> woher seine Einträge kommen. Die einzige Stelle, an der ein
#: Katalog benannt wird: ``CATALOG_NAMES`` und die Antwort des Endpunkts leiten
#: sich beide hieraus ab und können deshalb nicht auseinanderlaufen.
_SOURCES: dict[str, Callable[[], list[Choice]]] = {
    "patterns": lambda: _from_documents(cl.load_pattern_definitions()),
    "personas": lambda: _from_documents(cl.load_persona_definitions()),
    "intents": lambda: _from_list(cl.load_intents(), "04-intents/intents"),
    "states": lambda: _from_list(cl.load_states(), "04-states/states"),
    "entities": lambda: _from_list(cl.load_entities(), "04-entities/entities"),
    "rag_areas": _rag_areas,
    "tools": _tools,
}

#: Die Namen, auf die ein Modellfeld mit ``x-catalog`` zeigen darf. Ein Wächter
#: (``test_config_choices_annotations``) hält fest, dass kein Modell einen Namen
#: nennt, den es hier nicht gibt — ein Tippfehler bliebe sonst still: das Feld
#: sähe aus wie immer, nur ohne Vorschläge.
CATALOG_NAMES: tuple[str, ...] = tuple(_SOURCES)


@router.get("/choices")
async def get_choices() -> dict[str, list[Choice]]:
    """Alle Kataloge in einem Zug — ein Formular braucht sie gemeinsam."""
    return {name: quelle() for name, quelle in _SOURCES.items()}
