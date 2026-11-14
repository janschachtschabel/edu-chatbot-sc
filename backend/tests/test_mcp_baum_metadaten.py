"""SW-2 (Plan 2026-11-14, Werkzeuge für Sammlungsstrukturen): Fach, Bildungsstufe und Schlagworte
gleich beim Anlegen eines Sammlungsbaums.

``wlo_create_collection_tree`` nimmt ab dem MCP-Stand „Sammlungsstrukturen“ (14.11.2026) je Knoten
``discipline``, ``educationalContext`` und ``keywords`` und gemeinsame Werte als ``shared``. Der
bereitgestellte Server kennt sie nicht und prüft jede Ebene streng — ein fremdes Feld kippt dort
den ganzen Aufruf. Angeboten wird es deshalb nur, wenn der Server es führt, und vor dem Senden
nimmt der Client die Felder für einen älteren Server wieder heraus.

Das Schema stammt aus ``tools/list`` dieses Stands (lokal gestartet, 14.11.2026).
"""
from __future__ import annotations

import asyncio

from boerdi.services import agent_tools, response_tool_selection
from boerdi.services.ablauf import werkzeuge
from boerdi.services.mcp import angebot, arg_resolvers, baum_metadaten, faehigkeiten, tool_args
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
from tests.test_mcp_client import (  # noqa: F401 — ``mcp_state`` ist eine Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)

NAME = "wlo_create_collection_tree"
_ELTERN = "9e7ae956-e9df-430f-bace-f3db4b910013"
_SEK1 = "Sekundarstufe I"


def _server(*parameter: str) -> None:
    assert faehigkeiten.uebernehmen([
        {"name": NAME, "input_schema": {"properties": {p: {} for p in (
            "parentCollectionId", "tree", "onExisting", *parameter)}}},
        {"name": "search_wlo_content", "input_schema": {"properties": {"query": {}}}}])


def _definition(tools: list[dict]) -> dict:
    return next(t for t in tools if t["function"]["name"] == NAME)


def _agent() -> dict:
    return _definition(agent_tools._mcp_werkzeuge(allow_curation=True, blocked_tools=None,
                                                  tool_mode=None))


def _knoten_schemata(definition: dict) -> list[dict]:
    """Die Schemata der vier Baumebenen, von oben nach unten."""
    ebene = definition["function"]["parameters"]["properties"]["tree"]["items"]
    aus = []
    while isinstance(ebene, dict):
        aus.append(ebene)
        ebene = (ebene["properties"].get("children") or {}).get("items")
    return aus


# ── Das Angebot ────────────────────────────────────────

def test_die_felder_gibt_es_nur_wenn_der_server_sie_fuehrt(monkeypatch):
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: True)
    katalog = _definition(list(CURATION_TOOL_DEFINITIONS))

    _server()                                     # der bereitgestellte Stand: ohne ``shared``
    assert not baum_metadaten.angeboten()
    assert baum_metadaten.erweitert(katalog) is katalog
    assert "shared" not in _agent()["function"]["parameters"]["properties"]

    _server("shared")
    agent = _agent()
    eigenschaften = agent["function"]["parameters"]["properties"]
    assert set(eigenschaften["shared"]["properties"]) == set(baum_metadaten.FELDER)
    assert eigenschaften["shared"]["additionalProperties"] is False
    ebenen = _knoten_schemata(agent)
    assert len(ebenen) == 4
    for ebene in ebenen:                          # auf JEDER Ebene, auch der tiefsten
        assert set(baum_metadaten.FELDER) <= set(ebene["properties"])
        assert ebene["additionalProperties"] is False and ebene["required"] == ["title"]
    assert "shared" in agent["function"]["description"]
    assert "discipline?" in eigenschaften["tree"]["description"]
    assert "Reihenfolge, in der du sie nennst" in agent["function"]["description"]
    # Ein Muster, das das Werkzeug nennt (M18), bekommt dieselbe Definition.
    muster = _definition(response_tool_selection._nameable_tools())
    assert muster == agent
    # Der Katalog selbst bleibt, wie er ist.
    assert "shared" not in katalog["function"]["parameters"]["properties"]
    assert "discipline" not in _knoten_schemata(katalog)[0]["properties"]


# ── Was an den Server geht ─────────────────────────────────

def test_das_modell_behaelt_die_felder_in_der_form_des_servers():
    aus = tool_args.validate_tool_args(NAME, {
        "parentCollectionId": _ELTERN,
        "shared": {"discipline": [" Physik "], "educationalContext": "Sekundarstufe I",
                   "keywords": "Lehrplan", "fremd": 1, "userRole": "Lehrer/in"},
        "tree": [
            {"title": "Optik", "description": "Licht", "keywords": [" Linse ", ""], "nodeId": "x",
             "children": [
                 # Eine leere Liste schaltet den gemeinsamen Wert für diesen Knoten ab — sie bleibt.
                 {"title": "Methoden", "discipline": [], "educationalContext": "  ",
                  "keywords": None,
                  "children": [
                      {"title": "Messen", "discipline": "Mathematik", "titel": "falsch"}]}]},
        ]})
    assert aus["shared"] == {"discipline": ["Physik"], "educationalContext": "Sekundarstufe I",
                             "keywords": ["Lehrplan"]}
    assert aus["tree"] == [
        {"title": "Optik", "description": "Licht", "keywords": ["Linse"], "children": [
            {"title": "Methoden", "discipline": [], "children": [
                {"title": "Messen", "discipline": "Mathematik"}]}]}]


def test_eine_liste_nur_aus_leertext_schaltet_nichts_ab():
    """Review SW-2, Befund 3: ``[""]`` am Knoten wurde zu ``[]`` — für den Server heißt das
    „gemeinsamen Wert für diesen Knoten abschalten“. Nur eine wörtlich leere Liste bleibt."""
    aus = tool_args.validate_tool_args(NAME, {
        "parentCollectionId": _ELTERN, "shared": {"discipline": ["Physik"]},
        "tree": [{"title": "A", "discipline": [""]}, {"title": "B", "discipline": []},
                 {"title": "C", "keywords": [" ", ""]}]})
    assert aus["tree"] == [{"title": "A"}, {"title": "B", "discipline": []}, {"title": "C"}]


def test_ohne_gemeinsame_werte_reist_kein_shared_mit():
    for leer in ({}, {"fremd": 1}, {"discipline": " "}, None):
        aus = tool_args.validate_tool_args(NAME, {
            "parentCollectionId": _ELTERN, "tree": [{"title": "Optik"}], "shared": leer})
        assert "shared" not in aus
    # Was kein Objekt ist, geht roh hinaus — der Server lehnt es ab und sagt es.
    roh = {"parentCollectionId": _ELTERN, "tree": [{"title": "Optik"}], "shared": "Physik"}
    assert tool_args.validate_tool_args(NAME, dict(roh))["shared"] == "Physik"


def test_ein_aelterer_server_bekommt_den_baum_ohne_die_neuen_felder(monkeypatch, mcp_state):  # noqa: F811
    """Er prüft jede Ebene streng: mit einem der Felder scheiterte der ganze Baum. Herausgenommen
    wird auf allen Ebenen; Titel, Beschreibung und Kinder bleiben."""
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"result": {"content": [_text_part("Vorschau")]}},
        {"result": {"content": [_text_part("Vorschau")]}}])
    args = {"parentCollectionId": _ELTERN, "shared": {"discipline": "Physik"}, "tree": [
        {"title": "Optik", "keywords": ["Linse"], "children": [
            {"title": "Farben", "educationalContext": "Sekundarstufe I", "children": [
                {"title": "Spektrum", "discipline": "Physik", "description": "Regenbogen"}]}]}]}

    _server()
    alt = asyncio.run(client.call_mcp_tool(NAME, dict(args)))
    assert calls[0]["arguments"] == {"parentCollectionId": _ELTERN, "tree": [
        {"title": "Optik", "children": [{"title": "Farben", "children": [
            {"title": "Spektrum", "description": "Regenbogen"}]}]}]}
    # KI und Person erfahren es: Der Satz steht vor der Vorschau (Review SW-2, Befund 4).
    assert alt == f"{baum_metadaten.HINWEIS}\nVorschau"

    _server("shared")
    neu = asyncio.run(client.call_mcp_tool(NAME, dict(args)))
    assert calls[1]["arguments"] == args and neu == "Vorschau"


def test_ohne_die_felder_gibt_es_keinen_hinweis_und_im_rohfall_bleibt_der_schutz(
        monkeypatch, mcp_state):  # noqa: F811
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [{"result": {"content": [_text_part("Vorschau")]}}] * 2)
    _server()
    schlicht = {"parentCollectionId": _ELTERN, "tree": [{"title": "Optik"}]}
    assert asyncio.run(client.call_mcp_tool(NAME, dict(schlicht))) == "Vorschau"
    # Scheitert die Prüfung an etwas anderem (``onExisting`` unbekannt), gehen die Argumente roh
    # hinaus — die Felder nimmt ``fuer_den_server`` trotzdem heraus, auf jeder Ebene.
    roh = {"parentCollectionId": _ELTERN, "onExisting": "skip", "shared": {"keywords": ["x"]},
           "tree": [{"title": "Optik", "keywords": ["x"], "children": [
               {"title": "Farben", "discipline": "Physik"}]}]}
    asyncio.run(client.call_mcp_tool(NAME, dict(roh)))
    assert calls[1]["arguments"] == {
        "parentCollectionId": _ELTERN, "onExisting": "skip",
        "tree": [{"title": "Optik", "children": [{"title": "Farben"}]}]}


def test_andere_werkzeuge_bleiben_unberuehrt():
    _server()
    args = {"nodeId": "n-1", "keywords": ["x"], "discipline": "Physik"}
    assert angebot.fuer_den_server("wlo_update_content", args) is args
    _server("shared")
    baum = {"parentCollectionId": _ELTERN, "tree": [{"title": "Optik", "keywords": ["x"]}]}
    assert angebot.fuer_den_server(NAME, baum) is baum


# ── Der Ablauf-Dienst: der Entwurf trägt die Werte ─────────────────────

def test_fach_und_stufe_des_entwurfs_gelten_fuer_jeden_punkt_der_keine_eigenen_nennt(
        monkeypatch):
    """Das Fach reist nur mit, wenn das Vokabular es kennt (Review SW-2, Befund 2): Im Entwurf
    ist es Freitext, der Server lehnte mit einem unbekannten den ganzen Baum ab, und die Person
    könnte es im Entwurf nicht ändern. Ein Punkt mit eigenem, unbekanntem Fach bekommt keins —
    auch nicht das des Entwurfs."""
    gefragt: list[tuple[str, str]] = []

    async def _bekannt(vocab: str, wert: str) -> bool:
        gefragt.append((vocab, wert))
        return wert == "Physik"

    monkeypatch.setattr(arg_resolvers, "bezeichnung_bekannt", _bekannt)
    entwurf = {"titel": "Lehrplan Physik 8", "fach": "Physik", "bildungsstufe": "Sekundarstufe I",
               "knoten": [
                   {"id": "a", "titel": "Optik", "keywords": ["Licht", " ", 7], "kinder": [
                       {"id": "a1", "titel": "Farben", "fach": "Kunst und Gestaltung"},
                       {"id": "a2", "titel": "Linsen", "bildungsstufe": "Sekundarstufe II"}]},
                   {"id": "b", "titel": "Mechanik"}]}
    baum = asyncio.run(werkzeuge.DIENSTE["baum_aus_entwurf"]({"entwurf": entwurf}))
    assert baum == [
        {"title": "Optik", "discipline": "Physik", "educationalContext": _SEK1,
         "keywords": ["Licht"], "children": [
             {"title": "Farben", "educationalContext": _SEK1},
             {"title": "Linsen", "discipline": "Physik",
              "educationalContext": "Sekundarstufe II"}]},
        {"title": "Mechanik", "discipline": "Physik", "educationalContext": _SEK1}]
    assert sorted(gefragt) == [("discipline", "Kunst und Gestaltung"), ("discipline", "Physik")]
    # Das Argumentmodell nimmt genau diese Form an.
    aus = tool_args.validate_tool_args(NAME, {"parentCollectionId": _ELTERN, "tree": baum})
    assert aus["tree"] == baum


def test_ohne_vokabular_reist_kein_fach_mit(monkeypatch):
    """Server nicht erreichbar, Vokabular leer: lieber ein Baum ohne Fach als ein abgelehnter."""
    monkeypatch.setattr(arg_resolvers, "_label_cache_loaded",
                        {**arg_resolvers._label_cache_loaded, "discipline": True})
    monkeypatch.setattr(arg_resolvers, "_label_to_uri_cache",
                        {**arg_resolvers._label_to_uri_cache, "discipline": {}})
    entwurf = {"fach": "Physik", "knoten": [{"id": "a", "titel": "Optik"}]}
    assert asyncio.run(werkzeuge.DIENSTE["baum_aus_entwurf"]({"entwurf": entwurf})) == [
        {"title": "Optik"}]


def test_bekannt_ist_ein_name_oder_alias_nie_ein_teilwort(monkeypatch):
    monkeypatch.setattr(arg_resolvers, "_label_cache_loaded",
                        {**arg_resolvers._label_cache_loaded, "discipline": True})
    monkeypatch.setattr(arg_resolvers, "_label_to_uri_cache", {
        **arg_resolvers._label_to_uri_cache,
        "discipline": {"physik": "uri:physik", "agrarwirtschaft": "uri:agrar", "mathe": "uri:m"}})

    def _kennt(wert: str) -> bool:
        return asyncio.run(arg_resolvers.bezeichnung_bekannt("discipline", wert))

    assert _kennt("Physik") and _kennt(" physik ") and _kennt("Mathe")
    assert not _kennt("Wirtschaft") and not _kennt("") and not _kennt("Kfz-Mechatronik")
    assert not asyncio.run(arg_resolvers.bezeichnung_bekannt("gibt-es-nicht", "Physik"))
