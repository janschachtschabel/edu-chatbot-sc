"""Paket 18C/D, Phase 1 (1.5): jeder MCP-Aufruf steht in der Zugakte.

Eingetragen wird an der einzigen Engstelle (``call_mcp_tool_status``): die Argumente beim Eingang
(vom Modell, vom Vorabruf, aus einer Direktaktion) und wie sie nach Prüfung und Auflösung
hinausgingen, dazu Status, Cache, Dauer und Länge bzw. Fehlertext. Gerade die gescheiterten
Aufrufe standen bisher nirgends außer im Log.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import zugakte as za
from boerdi.services.mcp import client, tool_cache, transport

FAKE_URL = "https://fake-server/mcp"


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    tool_cache.clear_tool_cache()
    client.reset_query_metas()
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda t: FAKE_URL)
    yield
    tool_cache.clear_tool_cache()


def _transport(monkeypatch, antworten):
    antworten = list(antworten)

    async def fake_call_tool(tool_name, arguments=None, *, url=None):
        return antworten.pop(0) if antworten else {"result": {"content": []}}

    monkeypatch.setattr(transport, "call_tool", fake_call_tool)


def _ok(text):
    return {"result": {"content": [{"type": "text", "text": text}]}}


def _im_zug(*aufrufe):
    async def zug():
        akte = za.binde_zugakte()
        for name, args in aufrufe:
            await client.call_mcp_tool_status(name, args)
        return akte.als_dict().get("werkzeuge", [])

    return asyncio.run(zug())


def test_ein_erfolgreicher_aufruf_mit_beiden_fassungen(monkeypatch):
    _transport(monkeypatch, [_ok("Treffer-Text")])
    eintraege = _im_zug(("unknown_probe_tool", {"q": "Klimawandel"}))
    assert len(eintraege) == 1
    e = eintraege[0]
    assert e["name"] == "unknown_probe_tool"
    assert e["argumente_eingang"] == {"q": "Klimawandel"}
    assert e["argumente_gesendet"]["q"] == "Klimawandel"
    assert (e["status"], e["aus_cache"], e["zeichen"], e["fehler"]) == (
        "ok", False, len("Treffer-Text"), None)
    assert isinstance(e["dauer_ms"], int)


def test_ein_abgelehnter_aufruf_steht_mit_fehlertext_drin(monkeypatch):
    _transport(monkeypatch, [{"error": {"message": "Input validation error: -32602",
                                        "kind": "tool"}}])
    e = _im_zug(("unknown_probe_tool", {"q": "x"}))[0]
    assert e["status"] == "tool"
    assert "-32602" in e["fehler"]
    assert e["zeichen"] is None


def test_eine_zeitueberschreitung_steht_drin_und_wird_nicht_wiederholt(monkeypatch):
    _transport(monkeypatch, [{"error": {"message": "keine Antwort binnen 30 s",
                                        "kind": "timeout"}}, _ok("zweiter Versuch")])
    eintraege = _im_zug(("unknown_probe_tool", {"q": "x"}))
    assert [(e["status"], e["zeichen"]) for e in eintraege] == [("timeout", None)]
    assert "30 s" in eintraege[0]["fehler"]


def test_ein_cache_treffer_ist_gekennzeichnet(monkeypatch):
    _transport(monkeypatch, [_ok("aus dem Server")])
    zweiter = _im_zug(("unknown_probe_tool", {"q": "x"}), ("unknown_probe_tool", {"q": "x"}))[1]
    assert zweiter["aus_cache"] is True and zweiter["status"] == "ok"


def test_eine_aufgefaecherte_liste_steht_als_zwei_aufrufe_drin(monkeypatch):
    umschlag = '{"total": 1, "count": 1, "results": [{"nodeId": "a"}]}'
    _transport(monkeypatch, [_ok(umschlag), _ok(umschlag.replace('"a"', '"b"'))])
    eintraege = _im_zug(("search_wlo_content",
                         {"query": "Klima", "learningResourceType": ["Arbeitsblatt", "Video"]}))
    # Die Auflösung der Bezeichnungen fragt selbst per MCP nach dem Vokabular — auch diese
    # Aufrufe stehen (zu Recht) in der Akte; hier zählen die beiden Suchen.
    suchen = [e for e in eintraege if e["name"] == "search_wlo_content"]
    assert [e["argumente_eingang"]["learningResourceType"] for e in suchen] == [
        "Arbeitsblatt", "Video"]
    # „gesendet“ ist der Stand nach Prüfung und Auflösung — hier mindestens das JSON-Format.
    assert all("outputFormat" not in e["argumente_eingang"] for e in suchen)
    assert all(e["argumente_gesendet"]["outputFormat"] == "json" for e in suchen)


def test_ein_fremdwerkzeug_steht_ebenfalls_drin(monkeypatch):
    from boerdi.services.mcp import fremdwerkzeuge

    async def rufen(name, args):
        return "keine Antwort", "timeout"

    monkeypatch.setattr(fremdwerkzeuge, "rufen", rufen)
    (e,) = _im_zug(("wikipedia__suche", {"q": "Optik"}))
    assert (e["name"], e["status"], e["argumente_gesendet"]) == (
        "wikipedia__suche", "timeout", {"q": "Optik"})
    assert e["fehler"].endswith("keine Antwort")


def test_ausserhalb_eines_zugs_wird_nichts_eingetragen(monkeypatch):
    _transport(monkeypatch, [_ok("x")])

    async def ohne_zug():
        return await client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"})

    assert asyncio.run(ohne_zug()) == ("x", "")
