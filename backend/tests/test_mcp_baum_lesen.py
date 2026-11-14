"""SW-1 (Plan 2026-11-14, Werkzeuge für Sammlungsstrukturen): einen Sammlungsbaum ganz und in der
gespeicherten Reihenfolge lesen.

``list_collection_tree`` und ``order`` an ``browse_collection_tree`` / ``get_collection_overview``
kennt der MCP-Server ab dem Stand „Sammlungsstrukturen“ (14.11.2026); der bereitgestellte nicht.
Beides hängt an der Werkzeugliste des Servers.

Die Antwortform stammt von diesem Stand, lokal gestartet gegen das Staging-Repository
(14.11.2026): eine Zeile je Sammlung als Text, dieselben Daten im strukturierten Teil.
"""
from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain import mcp_unvollstaendig
from boerdi.domain.tool_result_redaction import (
    _redact_search_content_for_llm,
    redigiere_strukturell,
)
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.services import agent_tool_overview, agent_tools, response_tool_selection
from boerdi.services.card_collect import collect_cards
from boerdi.services.mcp import (
    angebot,
    baum_lesen,
    faehigkeiten,
    tool_args,
    tool_cache,
    tool_descriptions,
)
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from tests.test_mcp_client import (  # noqa: F401 — ``mcp_state`` ist eine Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)

NAME = "list_collection_tree"
_SEEDS = pathlib.Path(__file__).parents[1] / "seeds"
_OPTIK = "9e7ae956-e9df-430f-bace-f3db4b910013"

#: Die Antwort des Servers (gekürzt, wörtlich): Kopfzeile, Hinweis auf die nächste Seite, je
#: Sammlung eine Zeile.
_ANTWORT = (
    f"Sammlungsbaum unter nodeId: {_OPTIK} (bis Tiefe 4): Einträge 1–3 — „Optik“\n"
    "Es gibt weitere Einträge — nächste Seite mit skipCount=3.\n"
    "- nodeId: f35c17d1-a29e-4b26-9d22-802682fad43d [Ebene 1] — „Optik“ › „Geometrische Optik“\n"
    "- nodeId: 95f2002f-1745-4b47-889d-8376af38fe41 [Ebene 1] — „Optik“ › „Farben“\n"
    "- nodeId: d309bab9-50e5-4a95-aeb4-d83c4ecea632 [Ebene 2] — „Optik“ › „Wellenoptik“ › "
    "„Beugung“")
_STRUKTUR = {
    "root": {"nodeId": _OPTIK, "title": "Optik"}, "depth": 4, "count": 3, "skipCount": 0,
    "items": [
        {"nodeId": "f35c17d1-a29e-4b26-9d22-802682fad43d", "title": "Geometrische Optik",
         "path": ["Optik", "Geometrische Optik"], "depth": 1, "parentId": _OPTIK},
        {"nodeId": "95f2002f-1745-4b47-889d-8376af38fe41", "title": "Farben",
         "path": ["Optik", "Farben"], "depth": 1, "parentId": _OPTIK},
        {"nodeId": "d309bab9-50e5-4a95-aeb4-d83c4ecea632", "title": "Beugung",
         "path": ["Optik", "Wellenoptik", "Beugung"], "depth": 2,
         "parentId": "bf729405-18ff-440b-9d5b-dd466ff563c3"}],
    "more": {"nextSkipCount": 3}}


def _werkzeug(name: str, *parameter: str) -> dict:
    return {"name": name, "input_schema": {"properties": {p: {} for p in parameter}}}


def _server_kennt(*, liste: bool = True, order: tuple[str, ...] = baum_lesen.ORDER_WERKZEUGE):
    werkzeuge = [_werkzeug("search_wlo_content", "query")]
    if liste:
        werkzeuge.append(_werkzeug(NAME, "nodeId", "collection", "depth", "maxItems"))
    for name in baum_lesen.ORDER_WERKZEUGE:
        werkzeuge.append(_werkzeug(name, "nodeId", *(("order",) if name in order else ())))
    assert faehigkeiten.uebernehmen(werkzeuge)


def _agent(**kw) -> dict[str, dict]:
    return {t["function"]["name"]: t for t in agent_tools._mcp_werkzeuge(
        **{"allow_curation": False, "blocked_tools": None, "tool_mode": None, **kw})}


def _eigenschaften(definition: dict) -> dict:
    return definition["function"]["parameters"]["properties"]


# ── Das Angebot ────────────────────────────────────────

def test_die_baumliste_steht_nicht_im_katalog():
    """Wie die Mehrfachsuche: Der Muster-Weg reicht ``TOOL_DEFINITIONS`` als Ganzes weiter — ein
    Server ohne das Werkzeug wiese dort jeden Aufruf ab."""
    assert NAME not in {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert baum_lesen.DEFINITION["function"]["name"] == NAME
    assert baum_lesen in angebot.BEDINGT_LESEND


def test_angeboten_wird_sie_nur_wenn_der_server_sie_fuehrt(monkeypatch):
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: False)

    def _muster() -> set[str]:
        return {t["function"]["name"] for t in response_tool_selection._nameable_tools()}

    assert NAME not in _agent() and NAME not in _muster()
    _server_kennt()
    assert NAME in _agent() and NAME in _muster()
    # Verborgen, gesperrt oder im Lesemodus: wie jedes Lesewerkzeug.
    assert NAME not in _agent(blocked_tools=[NAME])
    assert NAME in _agent(tool_mode="read-only")
    # Ein Rückbau des Servers nimmt sie wieder weg.
    _server_kennt(liste=False)
    assert NAME not in _agent()


def test_die_beschreibung_sagt_wann_die_liste_nicht_vollstaendig_ist():
    """Mit den Worten, die die KI in der Antwort liest: Sie bekommt den Text des Servers, nicht
    die Feldnamen des strukturierten Teils (Review SW-1, Befund 6)."""
    text = baum_lesen.DEFINITION["function"]["description"]
    for hinweis in ("skipCount fuer die naechste Seite", "nicht geantwortet hat",
                    "nicht lesbar ist", "Grenze erreicht"):
        assert hinweis in text
    for feldname in ("incomplete", "restricted", "walkCapped", "nextSkipCount"):
        assert feldname not in text
    assert set(_eigenschaften(baum_lesen.DEFINITION)) == {
        "nodeId", "collection", "discipline", "depth", "maxItems", "skipCount",
        "includeContentCounts"}


def test_die_gespeicherte_reihenfolge_gibt_es_nur_wo_der_server_sie_kennt():
    """``order`` an Baum und Übersicht, je Werkzeug einzeln geprüft: Ein Server, der es nur an
    einem kennt, bekommt es nur dort angeboten. Der Katalog selbst bleibt unverändert."""
    def _mit_order() -> set[str]:
        return {n for n in baum_lesen.ORDER_WERKZEUGE if "order" in _eigenschaften(_agent()[n])}

    assert _mit_order() == set()
    _server_kennt(order=("browse_collection_tree",))
    assert _mit_order() == {"browse_collection_tree"}
    _server_kennt()
    assert _mit_order() == set(baum_lesen.ORDER_WERKZEUGE)
    order = _eigenschaften(_agent()["browse_collection_tree"])["order"]
    assert order["enum"] == ["title", "stored"] and "Lehrplan" in order["description"]
    for definition in TOOL_DEFINITIONS:
        if definition["function"]["name"] in baum_lesen.ORDER_WERKZEUGE:
            assert "order" not in _eigenschaften(definition)
    # Ein Werkzeug ohne ``order`` bleibt dieselbe Definition, keine Kopie.
    andere = next(d for d in TOOL_DEFINITIONS if d["function"]["name"] == "search_wlo_content")
    assert baum_lesen.erweitert(andere) is andere


# ── Was an den Server geht ─────────────────────────────────

def test_die_argumente_der_baumliste_bleiben_in_den_grenzen_des_servers():
    aus = tool_args.validate_tool_args(NAME, {
        "nodeId": _OPTIK, "depth": 9, "maxItems": 999, "includeContentCounts": True, "fremd": 1,
        "outputFormat": "json"})
    assert aus == {"nodeId": _OPTIK, "depth": 4, "maxItems": 250, "skipCount": 0,
                   "includeContentCounts": True}
    # Der Titel statt der Kennung, mit Fach — beides kennt das Werkzeug von Haus aus.
    per_titel = tool_args.validate_tool_args(NAME, {"collection": "Optik", "discipline": "Physik",
                                                   "skipCount": 250})
    assert per_titel["collection"] == "Optik" and per_titel["discipline"] == "Physik"
    assert per_titel["skipCount"] == 250 and "nodeId" not in per_titel
    # Markdown, kein JSON: den Text für das Modell schreibt der Server.
    assert NAME not in tool_args._JSON_CAPABLE_TOOLS


@pytest.mark.parametrize("werkzeug, kennung", [
    ("browse_collection_tree", "nodeId"), ("get_collection_overview", "collectionId")])
def test_order_reist_mit_und_ein_unbekannter_wert_faellt_nicht_still_weg(werkzeug, kennung):
    aus = tool_args.validate_tool_args(werkzeug, {kennung: _OPTIK, "order": "stored"})
    assert aus["order"] == "stored"
    # Ohne Angabe reist nichts mit: Die Vorgabe des Servers gilt, ein älterer bekommt kein Feld.
    assert "order" not in tool_args.validate_tool_args(werkzeug, {kennung: _OPTIK})
    # Ein Wert, den es nicht gibt, geht roh hinaus — der Server lehnt ihn ab und sagt es.
    roh = {kennung: _OPTIK, "order": "rueckwaerts"}
    assert tool_args.validate_tool_args(werkzeug, dict(roh))["order"] == "rueckwaerts"


# ── Was zurückkommt ────────────────────────────────────

def test_die_antwort_kommt_als_text_des_servers_mit_den_daten_daneben(monkeypatch, mcp_state):  # noqa: F811
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"result": {"content": [_text_part(_ANTWORT)], "structuredContent": _STRUKTUR}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort(NAME, {"nodeId": _OPTIK, "maxItems": 3}))
    # Kein Umschlag davor (anders als die Mehrfachsuche): Karten entstehen hier keine.
    assert antwort.text == _ANTWORT and antwort.strukturiert == _STRUKTUR
    assert "outputFormat" not in calls[0]["arguments"]
    assert collect_cards([], NAME, antwort.text) == []
    # Der Hinweis auf die nächste Seite steht im Text — das Modell sieht nur ihn.
    assert "skipCount=3" in redigiere_strukturell(NAME, antwort.text)


def test_das_modell_bekommt_die_ganze_liste():
    """Im Muster-Weg schnitte der blinde Deckel bei 4 000 Zeichen ab. Eine VOLLE Seite (250
    Einträge, vier Ebenen, lange Titel) hat rund 50 kB — auch sie kommt ganz an, in beiden Wegen
    (Review SW-1, Befund 1: ein Deckel von 32 000 Zeichen ersetzte bis zu 100 Zeilen in der
    Mitte, und der Baum las sich wie vollständig)."""
    pfad = " › ".join(f"„{'Thema ' * 4}{e}“" for e in range(4))
    zeile = "- nodeId: f35c17d1-a29e-4b26-9d22-802682fad43d [Ebene 4] [12 Inhalte] — " + pfad + "\n"
    text = ("Sammlungsbaum unter nodeId: x (bis Tiefe 4): Einträge 1–250 — „Physik“\n"
            + zeile * 250).rstrip("\n")
    assert 45_000 < len(text) < 100_000
    assert redigiere_strukturell(NAME, text) == text
    for gruppiert in (True, False):
        assert _redact_search_content_for_llm(NAME, text, [], gruppiert) == text


def test_ueber_dem_sicherheitsdeckel_endet_die_liste_an_einer_zeile_und_sagt_es():
    """Titel deckelt der Server nicht. Greift der Sicherheitsdeckel doch, bleibt keine halbe
    Zeile stehen (eine angeschnittene nodeId wäre eine falsche), und ein Satz sagt, dass die
    Liste nicht vollständig ist und wie es weitergeht."""
    zeile = "- nodeId: f35c17d1-a29e-4b26-9d22-802682fad43d [Ebene 1] — „Physik“ › „{}“"
    zeilen = ["Sammlungsbaum unter nodeId: x (bis Tiefe 4): Einträge 1–250 — „Physik“",
              *(zeile.format("T" * 900 + str(i)) for i in range(250))]
    sicht = redigiere_strukturell(NAME, "\n".join(zeilen))
    assert len(sicht) < 121_000
    *ganze, schluss = sicht.split("\n")
    assert ganze == zeilen[:len(ganze)] and 100 < len(ganze) < 250
    assert "NICHT vollständig" in schluss and "kleinerem maxItems" in schluss
    assert str(len(ganze)) in schluss


def test_die_baumliste_kommt_nie_aus_dem_cache(monkeypatch, mcp_state):  # noqa: F811
    """Sie dient dem Zurücklesen nach dem Anlegen: Lesen, Baum anlegen, wieder lesen — der zweite
    Aufruf muss den Server erreichen (Review SW-1, Befund 5: mit einer Frist von 60 Sekunden
    zeigte er den Baum ohne die neuen Sammlungen)."""
    from boerdi.services.mcp import client

    assert tool_cache.cache_gesperrt(NAME, {"nodeId": _OPTIK})
    _wire_tool_url(monkeypatch)
    antwort = {"result": {"content": [_text_part(_ANTWORT)], "structuredContent": _STRUKTUR}}
    calls = _wire_transport(monkeypatch, [antwort, antwort])
    for _ in range(2):
        asyncio.run(client.call_mcp_tool(NAME, {"nodeId": _OPTIK}))
    assert len(calls) == 2
    # Das Ausfall-Kennzeichen kennt die Liste trotzdem (für den Hinweis an die KI).
    assert NAME in mcp_unvollstaendig.WERKZEUGE
    assert mcp_unvollstaendig.ist_unvollstaendig(NAME, {**_STRUKTUR, "incomplete": True}, _ANTWORT)
    assert not mcp_unvollstaendig.ist_unvollstaendig(NAME, _STRUKTUR, _ANTWORT)


def test_die_antwort_traegt_keinen_fremdinhalt_rahmen():
    """Wie der Baum: eine Zeile je Sammlung, der Server hält jede einzeilig.
    ``tests/test_untrusted_text.py`` sieht dieses Werkzeug nicht — es steht nicht im Katalog."""
    assert frame_untrusted(NAME, _ANTWORT) == frame_untrusted("browse_collection_tree", _ANTWORT)


# ── Studio und Registry ───────────────────────────────────

def test_das_studio_zeigt_die_baumliste_und_warum_sie_fehlt(monkeypatch):
    monkeypatch.setattr(agent_tool_overview, "schreiben_erlaubt", lambda: False)

    def _zeile() -> dict:
        return next(t for t in agent_tool_overview.werkzeugliste()["tools"] if t["name"] == NAME)

    ohne = _zeile()
    assert ohne["kind"] == "read" and ohne["offered"] is False
    assert ohne["locks"] == [{"code": "server_lacks"}]
    _server_kennt()
    assert _zeile()["offered"] is True and _zeile()["locks"] == []
    # Jedes bedingte Lesewerkzeug steht genau einmal da.
    namen = [t["name"] for t in agent_tool_overview.werkzeugliste()["tools"]]
    for modul in angebot.BEDINGT_LESEND:
        assert namen.count(modul.WERKZEUG) == 1


def test_schalter_ja_warnung_nein(monkeypatch):
    """Am MCP-Server trägt das Werkzeug einen Schalter. Die Warnung „fehlt am Server —
    eingeschaltet scheitert jeder Aufruf“ gilt für es nicht: Ohne den Server wird es gar nicht
    angeboten."""
    primaer = {"id": "wlo-mcp", "enabled": True, "url": "https://mcp.example",
               "tools": [NAME, "get_url_text"]}

    async def _live(_url):
        return {"get_url_text": "holt Text"}

    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers", lambda: [primaer])
    monkeypatch.setattr(tool_descriptions, "_fetch_tool_descriptions", _live)
    (server,) = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert server["werkzeuge_fehlen_am_server"] == [] and NAME in server["werkzeuge_im_katalog"]


def test_die_registry_des_servers_nennt_die_baumliste():
    roh = yaml.safe_load((_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(encoding="utf-8"))
    [wlo] = [s for s in roh["servers"] if s["id"] == "wlo-mcp"]
    assert NAME in wlo["tools"]


# ── Review SW-1: ``order`` an einem Server ohne den Parameter, und im Muster-Weg ───────────

def test_die_gespeicherte_reihenfolge_an_einem_aelteren_server_wird_abgelehnt(
        monkeypatch, mcp_state):  # noqa: F811
    """Er verwürfe ``order`` still und lieferte alphabetisch — die KI hielte das für die Abfolge
    des Repositorys (Befund 7). Der Client sagt es, statt zu senden."""
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [{"result": {"content": [_text_part("{}")]}}] * 2)
    _server_kennt(order=())
    antwort = asyncio.run(client.call_mcp_tool_antwort(
        "browse_collection_tree", {"nodeId": _OPTIK, "order": "stored"}))
    assert calls == [] and antwort.code == "invalid_input"
    assert "kennt der Server an diesem Werkzeug nicht" in antwort.text
    assert "alphabetisch" in antwort.text
    # ``title`` ist die Vorgabe jedes Stands; und der neue Server bekommt ``stored``.
    assert angebot.lokale_ablehnung("browse_collection_tree", {"order": "title"}) is None
    _server_kennt()
    assert angebot.lokale_ablehnung("get_collection_overview", {"order": "stored"}) is None
    asyncio.run(client.call_mcp_tool("browse_collection_tree", {"nodeId": _OPTIK,
                                                                "order": "stored"}))
    assert calls[0]["arguments"]["order"] == "stored"


def test_ein_muster_das_den_baum_nennt_bekommt_order_ebenso(monkeypatch):
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: False)

    def _order() -> bool:
        baum = next(t for t in response_tool_selection._nameable_tools()
                    if t["function"]["name"] == "browse_collection_tree")
        return "order" in _eigenschaften(baum)

    assert not _order()
    _server_kennt()
    assert _order()
