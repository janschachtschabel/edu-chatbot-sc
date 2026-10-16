"""Werkzeuge fremder MCP-Server (Paket 11, E) — die reine Auswahl.

Nutzer 2026-10-15: Werkzeuge eines im Studio eingetragenen Servers sollen nutzbar sein, ohne
dass sich am WLO-Server etwas ändert. Angeboten wird nur, was der Server als lesend auszeichnet
(``annotations.readOnlyHint``) — schreibende Werkzeuge fremder Server bräuchten eine eigene
Abnahme. Das Modell sieht sie in einem eigenen Namensraum ``<server-id>__<werkzeug>``; eine
Kollision mit einem WLO-Namen ist damit ausgeschlossen."""

from __future__ import annotations

from boerdi.domain.fremdwerkzeug import angebotene, ist_fremd, modellname
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS


def _server(**kw) -> dict:
    basis = {
        "id": "wikidata", "name": "Wikidata", "enabled": True, "url": "https://wd.example/mcp",
        "tool_schemas": [
            {"name": "search_entities", "description": "Sucht Einträge.",
             "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
             "read_only": True},
            {"name": "edit_entity", "description": "Ändert einen Eintrag.", "read_only": False},
        ],
    }
    return {**basis, **kw}


def test_der_namensraum_ist_eindeutig_und_gueltig():
    assert modellname("wikidata", "search_entities") == "wikidata__search_entities"
    assert modellname("mein server!", "such.mal") == "mein_server___such_mal"
    lang = modellname("s" * 40, "w" * 40)
    assert len(lang) <= 64 and lang.startswith("s")
    # Review Paket 11, #4: der Trenner überlebt jede Kürzung.
    for sid in ("s" * 63, "s" * 100):
        assert ist_fremd(modellname(sid, "werkzeug")) and len(modellname(sid, "werkzeug")) <= 64


def test_kein_wlo_werkzeug_sieht_wie_ein_fremdes_aus():
    """Der Namensraum trägt nur, solange kein Katalogname den Trenner enthält."""
    for t in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS):
        assert not ist_fremd(t["function"]["name"]), t["function"]["name"]
    assert ist_fremd("wikidata__search_entities")


def test_nur_lesende_werkzeuge_werden_angeboten():
    werkzeuge = angebotene([_server()], primaer_id="wlo-mcp")
    assert [w.modellname for w in werkzeuge] == ["wikidata__search_entities"]
    w = werkzeuge[0]
    assert (w.name, w.url, w.server_id) == ("search_entities", "https://wd.example/mcp", "wikidata")
    fn = w.definition["function"]
    assert fn["name"] == "wikidata__search_entities"
    assert fn["parameters"]["properties"] == {"q": {"type": "string"}}
    assert "Wikidata" in fn["description"]


def test_ohne_schema_bekommt_das_modell_ein_leeres_objekt():
    server = _server(tool_schemas=[{"name": "ping", "read_only": True}])
    (w,) = angebotene([server], primaer_id="wlo-mcp")
    assert w.definition["function"]["parameters"] == {"type": "object", "properties": {}}


def test_abgeschaltet_ohne_adresse_oder_primaer_bietet_nichts():
    assert angebotene([_server(enabled=False)], primaer_id="wlo-mcp") == []
    assert angebotene([_server(url="")], primaer_id="wlo-mcp") == []
    assert angebotene([_server(id="wlo-mcp")], primaer_id="wlo-mcp") == []


def test_der_schalter_im_studio_nimmt_ein_werkzeug_heraus():
    server = _server(werkzeuge_aus=["search_entities"])
    assert angebotene([server], primaer_id="wlo-mcp") == []


def test_kaputte_eintraege_fallen_still_heraus():
    server = _server(tool_schemas=["quatsch", {"read_only": True}, {"name": "", "read_only": True},
                                   {"name": "ok", "read_only": True, "input_schema": "kein dict"}])
    (w,) = angebotene([server], primaer_id="wlo-mcp")
    assert w.name == "ok"
    assert w.definition["function"]["parameters"] == {"type": "object", "properties": {}}


def test_ein_schema_ohne_typ_behaelt_seine_parameter():
    server = _server(tool_schemas=[{"name": "s", "read_only": True,
                                    "input_schema": {"properties": {"q": {"type": "string"}}}}])
    (w,) = angebotene([server], primaer_id="wlo-mcp")
    assert w.definition["function"]["parameters"] == {
        "type": "object", "properties": {"q": {"type": "string"}}}
