"""Der Aufrufweg für Werkzeuge fremder MCP-Server (Paket 11, E).

Ein eigener Weg neben dem WLO-Weg in ``mcp/client``: Originalname an die Adresse des Servers,
Adresse beim Aufruf erneut geprüft (DNS kann sich seit dem Speichern geändert haben), keine
vorbereiteten Schreibanfragen (die setzt sonst ein Browser mit den Rechten der Person ab), kein
Cache, kein Zugangsblock (``transport._client_fabrik`` gibt ihn nur dem WLO-Server). Gerufen
wird nur, was angeboten ist — ein abgeschaltetes oder schreibendes Werkzeug nicht, auch wenn das
Modell den Namen rät."""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.mcp import client, fremdwerkzeuge, transport
from boerdi.services.url_safety import UnsafeUrlError

_SERVER = {
    "id": "wikidata", "name": "Wikidata", "enabled": True, "url": "https://wd.example/mcp",
    "tool_schemas": [
        {"name": "search_entities", "read_only": True},
        {"name": "edit_entity", "read_only": False},
    ],
}


@pytest.fixture
def welt(monkeypatch):
    aufrufe: list[tuple] = []
    geprueft: list[str] = []
    antwort: dict = {"wert": {"result": {
        "content": [{"type": "text", "text": "Q42: Douglas Adams"}],
        "structuredContent": {"preparedRequest": {"method": "POST", "path": "/edu-sharing/x"}},
    }}}

    async def call_tool(name, arguments=None, *, url=None):
        aufrufe.append((name, arguments, url))
        return antwort["wert"]

    def pruefen(url):
        geprueft.append(url)

    monkeypatch.setattr(transport, "call_tool", call_tool)
    monkeypatch.setattr(fremdwerkzeuge, "assert_public_url", pruefen)
    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    client.reset_prepared_writes()
    return aufrufe, geprueft, antwort


def _ruf(name, args=None):
    return asyncio.run(client.call_mcp_tool_status(name, args or {"q": "Adams"}))


def test_ein_angebotenes_werkzeug_geht_mit_originalnamen_an_seinen_server(welt):
    aufrufe, geprueft, _a = welt
    assert _ruf("wikidata__search_entities") == ("Q42: Douglas Adams", "")
    assert aufrufe == [("search_entities", {"q": "Adams"}, "https://wd.example/mcp")]
    assert geprueft == ["https://wd.example/mcp"]


def test_ein_fremder_server_bereitet_nie_eine_schreibanfrage_vor(welt):
    _ruf("wikidata__search_entities")
    assert client.get_prepared_writes() == []


def test_nicht_angebotene_werkzeuge_werden_nicht_gerufen(welt):
    aufrufe, _g, _a = welt
    text, art = _ruf("wikidata__edit_entity")
    assert art == "tool" and client.is_mcp_error(text)
    text, art = _ruf("unbekannt__irgendwas")
    assert art == "tool" and client.is_mcp_error(text)
    assert aufrufe == []


def test_eine_unsichere_adresse_wird_nicht_gerufen(welt, monkeypatch):
    aufrufe, _g, _a = welt

    def unsicher(_url):
        raise UnsafeUrlError("private address")

    monkeypatch.setattr(fremdwerkzeuge, "assert_public_url", unsicher)
    text, art = _ruf("wikidata__search_entities")
    assert art == "tool" and client.is_mcp_error(text)
    assert aufrufe == []


def test_fehler_des_servers_behalten_ihre_art(welt):
    _auf, _g, antwort = welt
    antwort["wert"] = {"error": {"message": "kaputt", "kind": "timeout"}}
    text, art = _ruf("wikidata__search_entities")
    assert art == "timeout" and client.is_mcp_error(text)
    antwort["wert"] = {"error": {"message": "weg"}}
    assert _ruf("wikidata__search_entities")[1] == "transport"


def test_kein_cache(welt):
    aufrufe, _g, _a = welt
    _ruf("wikidata__search_entities")
    _ruf("wikidata__search_entities")
    assert len(aufrufe) == 2


# ── Angebot (Agent-Katalog, Muster-Katalog, Studio-Auswahl) ─────────────────────
def test_der_agent_bekommt_die_lesenden_fremdwerkzeuge(monkeypatch):
    from boerdi.services import agent_tools

    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    namen = agent_tools.angebotene_mcp_werkzeuge(
        allow_curation=False, blocked_tools=None, tool_mode=None)
    assert "wikidata__search_entities" in namen
    assert "wikidata__edit_entity" not in namen
    assert "search_wlo_content" in namen, "der WLO-Katalog bleibt"
    gesperrt = agent_tools.angebotene_mcp_werkzeuge(
        allow_curation=False, blocked_tools=["wikidata__search_entities"], tool_mode="read-only")
    assert "wikidata__search_entities" not in gesperrt


def test_ohne_fremden_server_bleibt_der_agent_katalog_gleich(monkeypatch):
    from boerdi.services import agent_tools

    kw = {"allow_curation": False, "blocked_tools": None, "tool_mode": None}
    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [])
    ohne = agent_tools.angebotene_mcp_werkzeuge(**kw)
    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    mit = agent_tools.angebotene_mcp_werkzeuge(**kw)
    assert mit - ohne == {"wikidata__search_entities"}


def test_ein_muster_darf_ein_fremdwerkzeug_namentlich_anfordern(monkeypatch):
    from boerdi.services.response_tool_selection import _nameable_tools

    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    namen = {t["function"]["name"] for t in _nameable_tools()}
    assert "wikidata__search_entities" in namen


def test_die_studio_auswahl_kennt_die_fremdwerkzeuge(monkeypatch):
    from boerdi.api import config_choices

    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    werte = {c["value"] if isinstance(c, dict) else c.value for c in config_choices._tools()}
    assert "wikidata__search_entities" in werte


def test_die_werkzeug_uebersicht_zeigt_fremdwerkzeuge_als_eigene_art(monkeypatch):
    from boerdi.services import agent_tool_overview as ov

    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    monkeypatch.setattr(ov, "load_policy_config", lambda: {})
    monkeypatch.setattr(ov, "load_rag_config", lambda: {})
    zeile = next(t for t in ov.werkzeugliste()["tools"]
                 if t["name"] == "wikidata__search_entities")
    assert zeile["kind"] == "external" and zeile["offered"] is True
    # Review-Runde 2 (R2-4): Server und Originalname für den Schalter im Studio.
    assert (zeile["server_id"], zeile["tool"]) == ("wikidata", "search_entities")
    assert zeile["locks"] == [{"code": "tool_mode", "modes": ["curate"]},
                              {"code": "safety_fixed", "signals": ["pii"]}]



def test_ein_abgeschaltetes_fremdwerkzeug_bleibt_in_der_uebersicht(monkeypatch):
    """Review Paket 15, #1: Der Schalter steht nur noch auf der Seite „Werkzeuge“. Fiele die Zeile
    nach dem Ausschalten weg, ließe sich das Werkzeug im Studio nie wieder einschalten."""
    from boerdi.services import agent_tool_overview as ov

    aus = {**_SERVER, "werkzeuge_aus": ["search_entities"]}
    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [aus])
    monkeypatch.setattr(ov, "load_policy_config", lambda: {})
    monkeypatch.setattr(ov, "load_rag_config", lambda: {})
    zeile = next(t for t in ov.werkzeugliste()["tools"]
                 if t["name"] == "wikidata__search_entities")
    assert zeile["kind"] == "external" and zeile["offered"] is False
    assert zeile["locks"] == [{"code": "hidden"}]
    # Dem Modell bleibt es entzogen.
    assert "wikidata__search_entities" not in {
        d["function"]["name"] for d in fremdwerkzeuge.definitionen()}

# ── Review Paket 11 (2026-10-15): acht Befunde, je ein Test ─────────────────────
def test_r1_ein_fremder_server_uebernimmt_nie_die_weiterleitung_eines_wlo_werkzeugs(monkeypatch):
    """Auch bei abgeschaltetem WLO-Server: übernommene Namen leiten nicht um."""
    from boerdi.services import config_loader

    fremd = {**_SERVER, "tools": ["search_wlo_all"],
             "tool_schemas": [{"name": "search_wlo_all", "read_only": True}]}
    monkeypatch.setattr(config_loader, "get_enabled_mcp_servers", lambda: [fremd])
    assert client._get_server_url_for_tool("search_wlo_all") == transport.resolve_mcp_url()


def test_r2_fremde_server_folgen_keiner_umleitung():
    """Eine 307 vom fremden Server nach 169.254.169.254 umginge die Adressprüfung."""
    fabrik = transport._client_fabrik("https://fremd.example/mcp")
    assert fabrik().follow_redirects is False


def test_r3_ein_eintrag_mit_der_adresse_des_wlo_servers_wird_nie_gerufen(monkeypatch):
    """Sonst bekäme er über ``_client_fabrik`` den Zugangsblock der Person."""
    aufrufe: list = []

    async def call_tool(*a, **k):
        aufrufe.append(a)
        return {"result": {"content": []}}

    getarnt = {**_SERVER, "url": transport.resolve_mcp_url() + "/",
               "tool_schemas": [{"name": "wlo_create_content", "read_only": True}]}
    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [getarnt])
    monkeypatch.setattr(transport, "call_tool", call_tool)
    assert fremdwerkzeuge.definitionen() == []
    text, art = asyncio.run(client.call_mcp_tool_status("wikidata__wlo_create_content", {}))
    assert art == "tool" and aufrufe == []


def test_r6_ein_uebergrosses_schema_wird_nicht_angeboten(monkeypatch):
    riesig = {"type": "object", "properties": {f"p{i}": {"type": "string", "description": "x" * 200}
                                               for i in range(100)}}
    server = {**_SERVER, "tool_schemas": [
        {"name": "riesig", "read_only": True, "input_schema": riesig},
        {"name": "klein", "read_only": True, "input_schema": {"type": "object"}}]}
    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [server])
    assert [d["function"]["name"] for d in fremdwerkzeuge.definitionen()] == ["wikidata__klein"]


def test_r7_persoenliche_daten_sperren_auch_fremde_dienste(monkeypatch):
    """Ein Satz mit Passwort darf nicht an einen fremden Betreiber gehen (DSGVO)."""
    from boerdi.services.safety import regex_gate as rg

    monkeypatch.setattr(fremdwerkzeuge, "_registry", lambda: [_SERVER])
    d = rg.regex_gate("mein passwort ist geheim123", [])
    assert "wikidata__search_entities" in d.blocked_tools
    harmlos = rg.regex_gate("wie geht bruchrechnung", [])
    assert "wikidata__search_entities" not in harmlos.blocked_tools


def test_r8_lange_antworten_werden_gekuerzt(welt):
    _auf, _g, antwort = welt
    antwort["wert"] = {"result": {"content": [{"type": "text", "text": "x" * 100_000}]}}
    text, art = _ruf("wikidata__search_entities")
    assert art == "" and len(text) <= fremdwerkzeuge.HOECHSTENS_ZEICHEN + 100
    assert "gekürzt" in text
