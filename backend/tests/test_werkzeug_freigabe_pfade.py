"""Die Werkzeug-Freigabe je MCP-Server erreicht jeden Pfad (Paket 7, S5).

Dieselbe Menge (``agent_tools.verborgene_werkzeuge``) für die Agent-Schleife,
den Muster-Weg und die Werkzeugübersicht im Studio — sonst zeigte das Studio
einen Katalog, den das Modell nicht sieht. Der Registry-GET liefert dem Studio
die wirksame Liste und, welche Werkzeuge der Chatbot überhaupt kennt.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import agent_tool_overview as ov
from boerdi.services import agent_tools
from boerdi.services import response_tool_selection as rts
from boerdi.services.mcp import tool_descriptions


def _registry(monkeypatch, **primaer) -> None:
    server = {"id": "wlo-mcp", "enabled": True, "tools": ["search_skill", "get_url_text"],
              **primaer}
    monkeypatch.setattr(agent_tools, "load_mcp_servers", lambda: [server])


def _namen(tools) -> set[str]:
    return {t["function"]["name"] for t in tools}


def test_ohne_pflege_bleibt_search_skill_verborgen(monkeypatch):
    _registry(monkeypatch)
    assert "search_skill" not in _namen(agent_tools.build_agent_tools())
    assert "get_url_text" in _namen(agent_tools.build_agent_tools())


def test_das_studio_schaltet_im_agenten_ein_und_aus(monkeypatch):
    _registry(monkeypatch, werkzeuge_aus=["get_url_text"])
    namen = _namen(agent_tools.build_agent_tools())
    assert "search_skill" in namen      # eingeschaltet: steht nicht mehr in der Liste
    assert "get_url_text" not in namen


def test_auch_schreibende_werkzeuge_lassen_sich_abschalten(monkeypatch):
    _registry(monkeypatch, werkzeuge_aus=["wlo_create_content"])
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    namen = _namen(agent_tools.build_agent_tools(allow_curation=True))
    assert "wlo_create_content" not in namen
    assert "wlo_add_to_collection" in namen


def test_der_muster_weg_folgt_derselben_liste(monkeypatch):
    _registry(monkeypatch, werkzeuge_aus=["get_url_text"])
    monkeypatch.setattr(rts, "schreiben_erlaubt", lambda: False)
    namen = _namen(rts._nameable_tools())
    assert "get_url_text" not in namen
    assert "search_skill" in namen


def test_die_uebersicht_nennt_die_sperre(monkeypatch):
    _registry(monkeypatch, werkzeuge_aus=["get_url_text"])
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    monkeypatch.setattr(ov, "load_policy_config", lambda: {})
    monkeypatch.setattr(ov, "load_rag_config", lambda: {})
    zeile = next(t for t in ov.werkzeugliste()["tools"] if t["name"] == "get_url_text")
    assert zeile["offered"] is False
    assert zeile["locks"] == [{"code": "hidden"}]


def test_der_registry_get_liefert_die_wirksame_liste(monkeypatch):
    weiterer = {"id": "x", "enabled": False, "tools": ["suche_x"], "url": "https://x.example"}
    primaer = {"id": "wlo-mcp", "enabled": False, "tools": ["search_skill", "get_url_text"]}
    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers",
                        lambda: [primaer, weiterer])
    servers = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert servers[0]["werkzeuge_aus"] == ["search_skill"]       # Vorgabe sichtbar
    assert servers[0]["werkzeuge_im_katalog"] == ["get_url_text", "search_skill"]
    assert servers[1]["werkzeuge_aus"] == []
    # Werkzeuge eines weiteren Servers kennt der Chatbot nicht — kein Schalter.
    assert servers[1]["werkzeuge_im_katalog"] == []


@pytest.mark.parametrize("schluessel", ["werkzeuge_im_katalog"])
def test_die_katalog_angabe_wird_nicht_gespeichert(schluessel):
    from boerdi.services.config_loader import mcp as mcp_loader
    assert schluessel in mcp_loader._UI_META_KEYS


def test_das_speichern_schreibt_die_vorgabe_nicht_fest(monkeypatch):
    """Review Paket 7, A-10: ein Speichern ohne Änderung an den Schaltern schrieb
    die angezeigte Vorgabe bisher als gepflegte Liste fest."""
    from boerdi.services.config_loader import _store as store_mod
    from boerdi.services.config_loader import mcp as mcp_loader
    geschrieben: list = []

    class _Fake:
        async def put(self, key, data, *, updated_by, expected_version=None):
            geschrieben.append(data)
            return 1

    monkeypatch.setattr(store_mod, "_store", _Fake())
    asyncio.run(mcp_loader.save_mcp_servers([
        {"id": "wlo-mcp", "tools": ["search_skill", "get_url_text"],
         "werkzeuge_aus": ["search_skill"]},
        {"id": "x", "url": "https://x.example", "tools": ["suche_x"],
         "werkzeuge_aus": ["suche_x"]},
    ]))
    primaer, weiterer = geschrieben[0]["servers"]
    assert "werkzeuge_aus" not in primaer               # die Vorgabe: nicht gepflegt
    assert weiterer["werkzeuge_aus"] == ["suche_x"]     # gepflegt bleibt gepflegt


def test_uebernommene_lesende_werkzeuge_eines_weiteren_servers_tragen_einen_schalter(monkeypatch):
    """Paket 11 (E): übernommen und lesend → der Chatbot bietet es an, also wirkt der Schalter.
    Schreibende bietet er nicht an — kein Schalter."""
    weiterer = {"id": "x", "enabled": True, "url": "https://x.example",
                "tools": ["suche_x", "aendere_x"],
                "tool_schemas": [{"name": "suche_x", "read_only": True},
                                 {"name": "aendere_x", "read_only": False}]}

    async def _keine(_url):
        return {}

    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers", lambda: [weiterer])
    monkeypatch.setattr(tool_descriptions, "_fetch_tool_descriptions", _keine)
    (server,) = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert server["werkzeuge_im_katalog"] == ["suche_x"]



def test_das_studio_erfaehrt_welche_katalog_werkzeuge_der_server_nicht_fuehrt(monkeypatch):
    """Paket 11 (gemessen 2026-10-15): ``search_skill`` steht im Katalog, der Server führt es nicht
    mehr. Eingeschaltet scheiterte jeder Aufruf — das Studio soll es neben dem Schalter sagen."""
    primaer = {"id": "wlo-mcp", "enabled": True, "url": "https://mcp.example",
               "tools": ["search_skill", "get_url_text"]}

    async def _live(_url):
        return {"get_url_text": "holt Text"}

    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers", lambda: [primaer])
    monkeypatch.setattr(tool_descriptions, "_fetch_tool_descriptions", _live)
    (server,) = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert server["werkzeuge_fehlen_am_server"] == ["search_skill"]


def test_ohne_live_antwort_wird_nichts_als_fehlend_gemeldet(monkeypatch):
    """Ist der Server beim Laden nicht erreichbar, weiß niemand, was fehlt — dann keine Warnung."""
    primaer = {"id": "wlo-mcp", "enabled": True, "url": "https://mcp.example",
               "tools": ["search_skill"]}

    async def _weg(_url):
        return {}

    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers", lambda: [primaer])
    monkeypatch.setattr(tool_descriptions, "_fetch_tool_descriptions", _weg)
    (server,) = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert server["werkzeuge_fehlen_am_server"] == []


def test_die_warnung_wird_nicht_gespeichert():
    from boerdi.services.config_loader.mcp import _UI_META_KEYS

    assert "werkzeuge_fehlen_am_server" in _UI_META_KEYS
