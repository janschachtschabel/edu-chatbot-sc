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
from boerdi.domain.werkzeug_freigabe import uebernommen
from boerdi.services import agent_kopf
from boerdi.services import config_loader as cl
from boerdi.services.mcp import fremdwerkzeuge

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


def _mcp_werkzeugnamen() -> set[str]:
    """Die Vereinigung der Werkzeuge aller EINGESCHALTETEN Server.

    Ein abgeschalteter Server steuert nichts bei: was der Bot nicht rufen kann,
    soll ein Muster auch nicht vorgeschlagen bekommen.
    """
    namen = {
        str(t).strip()
        for server in cl.get_enabled_mcp_servers()
        for t in (server.get("tools") or [])
        if str(t).strip() and str(t).strip() not in uebernommen(server)
    }
    # Paket 11 (E): fremde Werkzeuge unter dem Namen, unter dem das Modell sie sieht.
    namen.update(t["function"]["name"] for t in fremdwerkzeuge.definitionen())
    return namen


def _mcp_tools() -> list[Choice]:
    """Nur die MCP-Werkzeuge — für Sperrlisten (``crisis_blocked_tools``): ein Modul-Werkzeug
    ist dort nicht sperrbar (Review U1-d2, Befund 8)."""
    return _sorted([_entry(name, name, "") for name in _mcp_werkzeugnamen()])


def _tools() -> list[Choice]:
    """Die MCP-Werkzeuge, dazu die UI-Module mit ``agent: true`` (U1-d2) — für ``tools:`` der
    Muster."""
    namen = _mcp_werkzeugnamen()
    # Paket U1-d2 (U-F4): die UI-Module, die ein Muster als Werkzeug nennen darf — samt Titel.
    # Angeboten werden sie im Zug nur, wenn das Widget sie meldet.
    from boerdi.ui_module.werkzeuge import modul_werkzeug_titel

    module = modul_werkzeug_titel()
    # Paket AS-5b: Abläufe mit Auslöser ``agent`` als Werkzeug ``ablauf-<id>`` — angeboten im Zug
    # nur, solange der Ablauf vorschlagbar ist (aktiv, Voraussetzungen erfüllt).
    from boerdi.domain.ablauf_werkzeug import PRAEFIX
    from boerdi.services.ablauf import ausloeser

    # Ein ausgeschalteter Ablauf steht mit „(aus)“ da: genannt wird er erst angeboten, wenn er
    # an ist (Querschnitts-Review AS-5, Befund 7).
    ablaeufe = {PRAEFIX + a.id: (a.titel.get("de") or a.id) + ("" if a.aktiv else " (aus)")
                for a in ausloeser.katalog() if any(x.art == "agent" for x in a.ausloeser)}
    return _sorted([*(_entry(name, name, "") for name in namen - set(module)),
                    *(_entry(name, f"{name}: {titel}", "") for name, titel in module.items()),
                    *(_entry(name, f"{name}: {titel}", "") for name, titel in ablaeufe.items())])


def _guardrails() -> list[Choice]:
    """Paket 15: die Regeln der Leitplanken-Tabelle — Kennung mit Wortlaut, damit die
    Schutzregeln des Agenten nicht nur als „R-13“ dastehen."""
    tabelle = agent_kopf.regeln(cl.load_guardrails())
    return _sorted([_entry(k, f"{k}: {text}", "01-base/guardrails") for k, text in tabelle.items()])


def _ui_module() -> list[Choice]:
    """Paket U1-c: die abgeleiteten UI-Module (Linkbox …) mit ihrem Titel aus dem Manifest."""
    from boerdi.ui_module import katalog
    from boerdi.ui_module.namen import ABGELEITETE

    kat = katalog.katalog()
    return [c for name in ABGELEITETE
            if (c := _entry(name, f"{name}: {kat.get(name, {}).get('titel', {}).get('de', '')}",
                            ""))]


def _ablauf_flows() -> list[Choice]:
    """Paket K2c-1: die Flows, die der Betrieb für Abläufe freischaltet (``B_API_JOBS_FLOWS``).
    Ohne Abruf bei der b-api — dieser Endpunkt lädt alle Kataloge in einem Zug und ruft keinen
    Fremddienst."""
    from boerdi.services.auftraege import client

    # Kein Sprungziel: ein Flow wird in Kestra gepflegt, nicht im Studio.
    return _sorted([_entry(f, f, "") for f in client.freigeschaltete_flows()])


def _ablauf_werkzeuge() -> list[Choice]:
    """Was ein ``werkzeug``-Schritt rufen darf (``services/ablauf/werkzeuge``): Dienste, lesende
    WLO-Werkzeuge und freigebbare schreibende (nur mit Freigabe am Schritt) — für die Auswahl im
    Studio (Querschnitts-Review AS-D: vorher ein freies Feld, nur der Hinweis nannte die
    Dienste)."""
    from boerdi.domain.write_confirm import CURATION_TOOLS
    from boerdi.services.ablauf import werkzeuge

    eintraege = [_entry(n, f"{n} (Dienst)", "") for n in werkzeuge.DIENSTE]
    eintraege += [_entry(n, f"{n} (lesend)", "") for n in werkzeuge.LESENDE_MCP]
    eintraege += [_entry(n, f"{n} (schreibend, mit Freigabe)", "") for n in CURATION_TOOLS
                  if werkzeuge.freigebbar(n)]
    return _sorted(eintraege)


def _vorgang_teile() -> list[Choice]:
    """Paket K2c-3: die Teile, die Module in den Vorgang schreiben (``vorgang.schreibt`` im
    Manifest), dazu ``ablage`` (Übertragung in WLO, ``services/ablage/vorgang_teil``) — für die
    Auswahl „Teil“ in den Argumenten eines Ablaufschritts. Die Teile der vorigen Schritte
    (``schreibt``, ``agent.ausgabe``) kennt nur das Formular."""
    from boerdi.services.ablauf.typen import modul_teile
    from boerdi.ui_module import katalog

    # Review AS-Db, Befund 6: dieselbe Quelle wie die Prüfung (``typen``, mit ``ablage``)
    module = katalog.katalog()
    quellen: dict[str, list[str]] = {}
    for name in module:
        for teil in modul_teile(module, name):
            quellen.setdefault(teil, []).append(name)
    return _sorted([_entry(t, f"{t} ({', '.join(sorted(set(m)))})", "")
                    for t, m in quellen.items()])


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
    "mcp_tools": _mcp_tools,
    "ui_module": _ui_module,
    "ablauf_flows": _ablauf_flows,
    "ablauf_werkzeuge": _ablauf_werkzeuge,
    "vorgang_teile": _vorgang_teile,
    "guardrails": _guardrails,
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
