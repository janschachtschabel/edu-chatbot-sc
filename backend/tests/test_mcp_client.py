"""Charakterisierungs-Tests für den MCP-Client-Kern (``services/mcp/client.py``).

Port des ``call_mcp_tool``-/``_query_metas``-/``_compact_subject_portals``-/
``_get_server_url_for_tool``-Clusters aus ALT ``tests/test_mcp_client.py``. Die
ALT-Cluster für Transport (``_get_http_client``/``_json_rpc``/``_ensure_…``),
den PEP-562-``__getattr__``-Shim und ``discover_server_tools`` fallen weg: dieser
Draht liegt im SDK-Transport (5-1b, dort getestet) bzw. existiert im NEU-Client
nicht mehr (kein Per-URL-Session-State). Resolver-/Vokabular-/Hints-Cluster sind
bereits in ``test_mcp_arg_resolvers.py`` abgedeckt.

**Boundary-Mock am Transport-Seam.** ALT skriptete rohe HTTP-Responses (Handshake
+ Notification + tools/call); NEU faked ``transport.call_tool`` und liefert direkt
die ALT-``_json_rpc``-geformten Dicts (``{"result": {"content": […]}}`` bzw.
``{"error": {"message": …}}``). Folge: die Call-Zähler sinken ggü. ALT — der
Handshake liegt UNTER diesem Seam, ein ``call_mcp_tool`` zählt hier genau einen
Transport-Call statt drei. Kein Verhaltensunterschied, nur ein anderer Seam.

ContextVar-Falle: ``asyncio.run`` kopiert den Kontext — Werte, die INNERHALB des
Coroutine-Laufs gesetzt werden (``_query_metas``), müssen in derselben Coroutine
ausgelesen werden (daher die ``szenario()``-Wrapper).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from mcp.types import CallToolResult, TextContent

from boerdi.services.mcp import arg_resolvers as ar
from boerdi.services.mcp import client, tool_cache, transport

FAKE_URL = "https://fake-server/mcp"


# ── Test-Doubles am Transport-Seam ─────────────────────────────────────────
def _result(parts):
    return {"result": {"content": parts}}


def _error(msg="kaputt"):
    return {"error": {"message": msg}}


def _text_part(text):
    return {"type": "text", "text": text}


def _wire_transport(monkeypatch, script):
    """Fake ``transport.call_tool``: liefert die Dicts in Reihenfolge + zeichnet
    (tool, arguments, url) je Call auf. Nach dem Skript: leeres Erfolgs-Result."""
    calls: list[dict] = []
    script = list(script)

    async def fake_call_tool(tool_name, arguments=None, *, url=None):
        calls.append({"tool": tool_name, "arguments": arguments, "url": url})
        if script:
            return script.pop(0)
        return {"result": {"content": []}}

    monkeypatch.setattr(transport, "call_tool", fake_call_tool)
    return calls


def _wire_tool_url(monkeypatch, url=FAKE_URL):
    """Server-URL-Lookup kurzschließen (sonst läse er die MCP-Server-Config)."""
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda t: url)


@pytest.fixture()
def mcp_state():
    """Frischer prozess-globaler Zustand pro Test: Tool-Cache (LRU + Meta +
    Stats) und der ``_query_metas``-ContextVar — vorher/nachher in-place
    geleert. Der Tool-Cache ist modul-global und überlebt ``asyncio.run``."""
    tool_cache.clear_tool_cache()
    client.reset_query_metas()
    yield
    tool_cache.clear_tool_cache()
    client.reset_query_metas()


# ═══ call_mcp_tool ═════════════════════════════════════════════════════════
def test_call_mcp_tool_happy_path_joint_texte_und_cached(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        _result([_text_part("Hallo"), _text_part("Welt"), "roher-string"]),
    ])
    out = asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
    # Text-Parts UND rohe String-Parts werden mit \n gejoint.
    assert out == "Hallo\nWelt\nroher-string"
    assert len(calls) == 1  # ein tools/call (Handshake liegt unter dem Seam)
    assert calls[0]["tool"] == "unknown_probe_tool"
    assert calls[0]["arguments"] == {"q": "x"}
    assert calls[0]["url"] == FAKE_URL
    # Ergebnis liegt im Tool-Cache → zweiter Call ohne Transport-Verkehr.
    out2 = asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
    assert out2 == out and len(calls) == 1


def test_call_mcp_tool_setzt_output_format_fuer_json_faehige_tools(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("{}")])])
    asyncio.run(client.call_mcp_tool("search_wlo_all", {"query": "x"}))
    sent = calls[0]["arguments"]
    assert sent["outputFormat"] == "json" and sent["query"] == "x"
    # Cache-Key wird NACH der outputFormat-Injektion gebildet.
    key = tool_cache._cache_key("search_wlo_all", sent, url=FAKE_URL)
    assert tool_cache._cache_get(key) is not None


def test_call_mcp_tool_output_format_wird_nicht_ueberschrieben(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("ok")])])
    asyncio.run(client.call_mcp_tool(
        "search_wlo_all", {"query": "x", "outputFormat": "markdown"}))
    assert calls[0]["arguments"]["outputFormat"] == "markdown"


# ── W5-3b: Volltexte dürfen nicht bei 8000 Zeichen enden ────────────────
# Bis 2026-08-21 hob der Client den Deckel zentral auf 50000 an, weil der
# Server-Standard 8000 betrug und live 2 von 6 Arbeitsblättern abschnitt. Mit
# dem MCP-Deploy vom 20.08. ist der Server-Standard selbst 200000 („wer nichts
# sagt, bekommt den ganzen Text", live gemessen: 59 398 Zeichen ungekürzt).
# Unsere Setzung wäre seither eine ABSENKUNG und zugleich eine Kopie einer
# fremden Grenze, die still veraltet — deshalb schicken wir gar nichts mehr.
def test_call_mcp_tool_ueberlaesst_den_volltext_deckel_dem_server(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("{}")])])
    asyncio.run(client.call_mcp_tool("get_wlo_content_text", {"nodeId": "n1"}))
    assert "maxChars" not in calls[0]["arguments"]


def test_call_mcp_tool_volltext_deckel_wird_nicht_ueberschrieben(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("{}")])])
    asyncio.run(client.call_mcp_tool(
        "get_wlo_content_text", {"nodeId": "n1", "maxChars": 3000}))
    assert calls[0]["arguments"]["maxChars"] == 3000


def test_call_mcp_tool_setzt_deckel_nur_beim_volltext_tool(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("{}")])])
    asyncio.run(client.call_mcp_tool("search_wlo_all", {"query": "x"}))
    assert "maxChars" not in calls[0]["arguments"]


def test_call_mcp_tool_fehler_retry_erfolgreich(mcp_state, monkeypatch):
    # NEU ggü. ALT: kein Session-Reset-Assert — der Transport öffnet pro Call
    # eine frische Session (5-1b), der Retry ist damit ein simpler Zweit-Call.
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_error("session tot"), _result([_text_part("OK")])])
    out = asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
    assert out == "OK"
    assert len(calls) == 2  # Fehler → Retry → Erfolg


def test_call_mcp_tool_zweiter_fehler_liefert_mcp_error_string(mcp_state, monkeypatch):
    # NOTE: pinnt IST-Verhalten — der doppelte Fehler wirft NICHT, sondern
    # liefert den String "MCP error: …" (der LLM sieht ihn als Tool-Ergebnis).
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_error("kaputt"), _error("immer noch kaputt")])
    out = asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
    assert out == "MCP error: immer noch kaputt"
    # Fehler-Antworten werden NICHT gecached.
    assert tool_cache.get_tool_cache_stats()["size"] == 0


# ── Die Fehler-ART bis zum Aufrufer (2026-08-15) ────────────────────────
#
# ``call_mcp_tool`` bleibt eine Zeichenkette — das Modell soll den Text als
# gewöhnliches Werkzeug-Ergebnis lesen. Wer OHNE Modell entscheidet, braucht
# aber mehr: ob der Server abgelehnt hat (dann steht fest, dass nichts geändert
# wurde) oder ob nie eine Antwort kam (dann steht das gerade nicht fest).
# Deshalb die zweite, ausdrückliche Funktion statt eines versteckten Zustands.


def test_status_meldet_die_art_des_fehlers(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [
        {"error": {"message": "weg", "kind": "transport"}},
        {"error": {"message": "immer noch weg", "kind": "transport"}},
    ])
    text, art = asyncio.run(
        client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert text == "MCP error: immer noch weg"
    assert art == "transport"


def test_status_unterscheidet_ablehnung_von_ausfall(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [
        {"error": {"message": "abgelehnt", "kind": "tool"}},
        {"error": {"message": "abgelehnt", "kind": "tool"}},
    ])
    _text, art = asyncio.run(
        client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert art == "tool"


def test_status_ist_bei_erfolg_leer(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("OK")])])
    text, art = asyncio.run(
        client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert (text, art) == ("OK", "")


def test_ohne_art_gilt_der_fehler_als_unbestimmt(mcp_state, monkeypatch):
    # Ein Fehler-Dict ohne ``kind`` (Attrappe, älterer Pfad) darf nicht als
    # „Server hat abgelehnt" durchgehen — das wäre die Behauptung, die man
    # nicht belegen kann. Unbekannt zählt wie „keine Antwort".
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_error("kaputt"), _error("kaputt")])
    _text, art = asyncio.run(
        client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert art == "transport"


def test_der_string_wrapper_bleibt_unveraendert(mcp_state, monkeypatch):
    # ``call_mcp_tool`` ist der Vertrag für 25 Aufrufstellen und das Modell.
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("OK")])])
    assert asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"})) == "OK"


# ── Wiederholt wird nur, wenn keine Antwort kam (Review 2026-09-29) ─────
#
# Die Wiederholung stammt aus ALT, wo eine abgelaufene Sitzung den Aufruf
# scheitern liess. Hat der Server dagegen GEANTWORTET und abgelehnt
# (``kind == "tool"``), sagt ein zweiter Aufruf dasselbe noch einmal. Gemessen
# an der Skill-Suche im Studio gegen einen Server ohne ``search_skill``: zwei
# Sitzungen und vier ERROR-Zeilen für einen Zustand, der kein Fehler ist.


def test_eine_ablehnung_wird_nicht_wiederholt(mcp_state, monkeypatch, caplog):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"error": {"message": "MCP error -32602: Tool search_skill not found",
                   "kind": "tool"}},
    ])
    with caplog.at_level("INFO"):
        text, art = asyncio.run(
            client.call_mcp_tool_status("search_skill", {"query": "Optik"}))
    assert len(calls) == 1
    assert (text, art) == ("MCP error: MCP error -32602: Tool search_skill not found", "tool")
    assert "Retrying" not in caplog.text
    assert "retry failed" not in caplog.text


def test_eine_ablehnung_kostet_eine_sitzung_und_eine_fehlerzeile(mcp_state, monkeypatch, caplog):
    # Die Messung aus dem Review, eine Ebene tiefer: der echte Transport läuft
    # mit, gefälscht ist nur die SDK-Sitzung. Vorher: 2 Sitzungen, 4 ERROR-Zeilen.
    sitzungen: list[str] = []

    class _Sitzung:
        async def call_tool(self, name, arguments=None):
            return CallToolResult(isError=True, content=[
                TextContent(type="text", text=f"MCP error -32602: Tool {name} not found")])

    @asynccontextmanager
    async def _oeffnen(url):
        sitzungen.append(url)
        yield _Sitzung()

    _wire_tool_url(monkeypatch)
    monkeypatch.setattr(transport, "_open_session", _oeffnen)
    with caplog.at_level("INFO"):
        _text, art = asyncio.run(
            client.call_mcp_tool_status("search_skill", {"query": "Optik"}))
    assert art == "tool"
    assert len(sitzungen) == 1
    # Paket 19 (N-15): eine Zeile — als Warnung, die Ablehnung ist erwartbar.
    stufen = [r.levelname for r in caplog.records]
    assert stufen.count("ERROR") == 0 and stufen.count("WARNING") == 1


def test_eine_ablehnung_behaelt_den_grund_des_ersten_aufrufs(mcp_state, monkeypatch):
    # Die Schreib-Abnahme (``services/write_approval``). Der MCP-Server löscht
    # einen ``confirmToken`` bei jedem Einlöseversuch (``consumeToken``), eine
    # Wiederholung bekäme also immer „unbekannt oder bereits benutzt" — und
    # verdeckte den Grund, aus dem der erste Aufruf abgelehnt wurde.
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"error": {"message": "Der Bestätigungsschlüssel ist abgelaufen (zehn Minuten).",
                   "kind": "tool"}},
        {"error": {"message": "Der Bestätigungsschlüssel ist unbekannt oder wurde "
                              "bereits benutzt.", "kind": "tool"}},
    ])
    text, art = asyncio.run(client.call_mcp_tool_status(
        "unknown_probe_tool", {"title": "Bruchrechnen", "confirmToken": "T" * 24}))
    assert len(calls) == 1
    assert (text, art) == (
        "MCP error: Der Bestätigungsschlüssel ist abgelaufen (zehn Minuten).", "tool")


def test_eine_zeitueberschreitung_wird_nicht_wiederholt(mcp_state, monkeypatch):
    """Paket 4, B2: Lief die Frist je Aufruf ab, hinge ein zweiter Versuch
    genauso lange — die doppelte Wartezeit, die der Befund F04 beschreibt.
    Nach außen bleibt es „keine Antwort“: ob geschrieben wurde, ist offen."""
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"error": {"message": "keine Antwort binnen 60 s", "kind": "timeout"}},
        _result([_text_part("OK")]),
    ])
    text, art = asyncio.run(
        client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert len(calls) == 1
    assert (text, art) == ("MCP error: keine Antwort binnen 60 s", "timeout")


def test_ein_abgewiesener_zugang_wird_nicht_wiederholt_und_faellt_weg(mcp_state, monkeypatch):
    """Paket 10 (Kurzaudit A-3): ein 401 ging als ``transport`` durch, der Client
    wiederholte denselben Block, und der Rest des Zuges scheiterte genauso. Jetzt:
    ein Aufruf, der Block fällt für den Zug weg, das Widget erfährt es."""
    from boerdi.services.mcp import anmeldung, auth

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"error": {"message": "Zugang abgewiesen (401)", "kind": "auth"}},
        _result([_text_part("OK")]),
    ])

    async def zug():
        auth.set_turn_auth_block("wlo2.abgelaufen")
        ergebnis = await client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"})
        return ergebnis, auth.has_auth_token(), anmeldung.abgelehnt_in_diesem_zug()

    try:
        (text, art), mit_block, abgelehnt = asyncio.run(zug())
    finally:
        anmeldung._cache.clear()
    assert len(calls) == 1
    assert art == "auth" and "abgewiesen" in text
    assert not mit_block and abgelehnt


def test_ein_ausfall_wird_weiter_wiederholt(mcp_state, monkeypatch):
    # Gegenprobe: kam keine Antwort, bleibt es bei einem zweiten Versuch.
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"error": {"message": "read timeout", "kind": "transport"}},
        _result([_text_part("OK")]),
    ])
    text, art = asyncio.run(
        client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert (text, art) == ("OK", "")
    assert len(calls) == 2


def test_ein_doppelter_ausfall_ist_eine_gedrosselte_warnung(mcp_state, monkeypatch, caplog):
    """Paket 19 (N-15): bis dahin zwei ERROR-Zeilen hier zu den zwei des Transports. Den Grund
    meldet der Transport; hier nur, dass auch die Wiederholung scheiterte — gedrosselt."""
    import logging

    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [
        {"error": {"message": "read timeout", "kind": "transport"}},
        {"error": {"message": "read timeout", "kind": "transport"}},
        {"error": {"message": "read timeout", "kind": "transport"}},
        {"error": {"message": "read timeout", "kind": "transport"}},
    ])
    with caplog.at_level(logging.INFO, logger=client.__name__):
        for _ in range(2):
            asyncio.run(client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    stufen = [r.levelname for r in caplog.records if r.levelno >= logging.WARNING]
    assert stufen == ["WARNING"]
    assert "Retrying" not in caplog.text  # DEBUG, nicht mehr INFO


def test_ein_bestaetigter_schreibaufruf_wird_nach_ausfall_nicht_wiederholt(
        mcp_state, monkeypatch):
    # Offener Befund 1.2 (2026-09-29): Der erste Aufruf kann angekommen und
    # ausgeführt sein, nur die Antwort ging verloren. Der Server löscht den
    # ``confirmToken`` beim ersten Einlöseversuch — eine Wiederholung bekäme
    # „unbekannt oder bereits benutzt" (``kind == "tool"``), und die Abnahme
    # meldete „nichts geändert", obwohl geschrieben wurde. Wer dann neu anlegt,
    # erzeugt eine Dublette. Ohne Wiederholung bleibt es bei ``transport``, und
    # ``write_approval`` schickt die Person zum Nachsehen.
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"error": {"message": "read timeout", "kind": "transport"}},
        {"error": {"message": "Der Bestätigungsschlüssel ist unbekannt oder wurde "
                              "bereits benutzt.", "kind": "tool"}},
    ])
    text, art = asyncio.run(client.call_mcp_tool_status(
        "unknown_probe_tool", {"title": "Bruchrechnen", "confirmToken": "T" * 24}))
    assert len(calls) == 1
    assert (text, art) == ("MCP error: read timeout", "transport")


def test_der_bestaetigungsschluessel_steht_nicht_im_protokoll(
        mcp_state, monkeypatch, caplog):
    # Offener Befund 1.3: die Argument-Zeile protokollierte die rohen
    # Argumente — bei einem bestätigten Schreibzugriff also den Schlüssel, der
    # die Änderung auslöst, und bei einem Upload die ganze Nutzlast. Das
    # Werkzeug und Filter bleiben lesbar, denn für die Fehlersuche an Filtern ist
    # die Zeile da; Freitext wie ein Titel seit Paket 18C/D nur als Länge.
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("OK")])])
    geheim = "S3cr3tT0k3n" * 3
    nutzlast = "Q" * 5000
    with caplog.at_level("INFO"):
        asyncio.run(client.call_mcp_tool_status(
            "unknown_probe_tool",
            {"title": "Bruchrechnen", "discipline": "Mathematik", "confirmToken": geheim,
             "content": nutzlast}))
    protokoll = "\n".join(r.getMessage() for r in caplog.records)
    assert geheim not in protokoll
    assert nutzlast not in protokoll
    assert "Bruchrechnen" not in protokoll and "‹12 Zeichen›" in protokoll
    assert "Mathematik" in protokoll


def test_call_mcp_tool_extrahiert_query_meta_in_contextvar(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    meta_text = '{"_queryMeta": {"queryType": "content", "filters": {"discipline": "d"}}}'
    _wire_transport(monkeypatch, [
        _result([_text_part(meta_text), _text_part("BODY")]),
    ])

    async def szenario():
        out = await client.call_mcp_tool("unknown_probe_tool", {"q": "x"})
        return out, client.get_query_metas()

    out, metas = asyncio.run(szenario())
    assert out == "BODY"  # Meta-Block verschmutzt den LLM-Text nicht
    assert metas == [{"queryType": "content", "filters": {"discipline": "d"}}]
    # Metas werden mitgecached (für Re-Emit bei Cache-Hits).
    key = tool_cache._cache_key("unknown_probe_tool", {"q": "x"}, url=FAKE_URL)
    assert tool_cache._TOOL_META_CACHE[key] == metas


def test_der_cache_trennt_die_server(mcp_state, monkeypatch):
    """Paket 4, C3: Stellt das Studio einen Registry-Server um, holt der
    nächste Aufruf beim neuen Server — nicht den Treffer des alten."""
    adresse = {"jetzt": "https://a.example/mcp"}
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda _t: adresse["jetzt"])
    calls = _wire_transport(monkeypatch, [
        _result([_text_part("VON-A")]),
        _result([_text_part("VON-B")]),
    ])

    erst, _ = asyncio.run(client.call_mcp_tool_status("get_node_details", {"nodeId": "n1"}))
    adresse["jetzt"] = "https://b.example/mcp"
    dann, _ = asyncio.run(client.call_mcp_tool_status("get_node_details", {"nodeId": "n1"}))

    assert (erst, dann) == ("VON-A", "VON-B")
    assert [c["url"] for c in calls] == ["https://a.example/mcp", "https://b.example/mcp"]


def test_call_mcp_tool_cache_hit_reemittiert_metas(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    meta_text = '{"_queryMeta": {"queryType": "content"}}'
    calls = _wire_transport(monkeypatch, [
        _result([_text_part(meta_text), _text_part("BODY")]),
    ])

    async def szenario():
        await client.call_mcp_tool("unknown_probe_tool", {"q": "x"})
        client.reset_query_metas()  # neuer Turn
        out2 = await client.call_mcp_tool("unknown_probe_tool", {"q": "x"})
        return out2, client.get_query_metas()

    out2, metas = asyncio.run(szenario())
    assert out2 == "BODY"
    assert metas == [{"queryType": "content"}]  # aus dem Meta-Cache re-emittiert
    assert len(calls) == 1  # zweiter Call war ein reiner Cache-Hit


def test_call_mcp_tool_nur_meta_antwort_dumpt_rohes_result(mcp_state, monkeypatch):
    # NOTE: pinnt IST-Verhalten — besteht die Antwort NUR aus einem _queryMeta-
    # Block, ist texts leer und der Fallback dumpt das komplette result_data-
    # Envelope (inklusive Meta-Block) als Response-String.
    _wire_tool_url(monkeypatch)
    meta_text = '{"_queryMeta": {"queryType": "content"}}'
    _wire_transport(monkeypatch, [_result([_text_part(meta_text)])])

    async def szenario():
        out = await client.call_mcp_tool("unknown_probe_tool", {"q": "x"})
        return out, client.get_query_metas()

    out, metas = asyncio.run(szenario())
    assert metas == [{"queryType": "content"}]
    assert json.loads(out) == {"content": [{"type": "text", "text": meta_text}]}


def test_call_mcp_tool_blocklist_tool_wird_nie_gecached(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        _result([_text_part("PONG")]),
        _result([_text_part("PONG2")]),
    ])
    out1 = asyncio.run(client.call_mcp_tool("wlo_health_check", {}))
    out2 = asyncio.run(client.call_mcp_tool("wlo_health_check", {}))
    assert (out1, out2) == ("PONG", "PONG2")  # zweiter Call ging wieder raus
    assert len(calls) == 2
    assert tool_cache.get_tool_cache_stats()["size"] == 0


def test_call_mcp_tool_preprocessor_fehler_laesst_args_unveraendert(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("ok")])])

    async def _explodiert(args):
        raise RuntimeError("preprocessor kaputt")

    monkeypatch.setitem(ar.TOOL_PREPROCESSORS, "unknown_probe_tool", _explodiert)
    out = asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
    assert out == "ok"
    assert calls[0]["arguments"] == {"q": "x"}


def test_call_mcp_tool_kompaktiert_subject_portals(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    lang = "B" * 300
    envelope = json.dumps({"total": 1, "results": [{
        "nodeId": "n1", "title": "Mathematik", "contentCount": 5,
        "description": lang, "keywords": ["k1", "k2"],
        "disciplines": ["a", "b", "c", "d", "e", "f"],
    }]})
    _wire_transport(monkeypatch, [_result([_text_part(envelope)])])
    out = asyncio.run(client.call_mcp_tool("get_subject_portals", {}))
    parsed = json.loads(out)
    assert parsed["_compacted"] is True
    item = parsed["results"][0]
    assert item["nodeId"] == "n1" and item["contentCount"] == 5
    assert "keywords" not in item  # Marketing-Ballast fliegt raus
    assert item["nodeType"] == "collection"  # Default, sonst falsche Karten-Box
    assert len(item["description"]) == 218 and item["description"].endswith("…")
    assert item["disciplines"] == ["a", "b", "c", "d"]  # Top 4


def test_call_mcp_tool_kompaktierung_fehlschlag_laesst_response_roh(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("kein json")])])
    out = asyncio.run(client.call_mcp_tool("get_subject_portals", {}))
    assert out == "kein json"  # Kompaktierung best-effort, Fehler geschluckt


# ═══ Query-Metas (ContextVar) ══════════════════════════════════════════════
def test_query_metas_reset_und_get_liefert_kopie(mcp_state):
    client.reset_query_metas()
    assert client.get_query_metas() == []
    client._query_metas.set([{"a": 1}])
    kopie = client.get_query_metas()
    assert kopie == [{"a": 1}]
    kopie.append({"b": 2})
    assert client.get_query_metas() == [{"a": 1}]  # interner Zustand unberührt


# ═══ _compact_subject_portals (pur) ════════════════════════════════════════
def test_compact_subject_portals_behaelt_nodetype_und_total():
    raw = json.dumps({"items": [
        {"nodeId": "n1", "title": "T", "nodeType": "ccm:io", "description": "kurz"},
        "junk-item",
    ]})
    out = json.loads(client._compact_subject_portals(raw))
    assert out["_compacted"] is True
    assert out["total"] == 1  # kein total im Input → len(compact_items)
    assert out["results"][0]["nodeType"] == "ccm:io"  # vorhandener Typ bleibt
    assert out["results"][0]["description"] == "kurz"  # ≤220 → unverändert


# ═══ _get_server_url_for_tool ══════════════════════════════════════════════
def test_get_server_url_registry_treffer_und_fallback(mcp_state, monkeypatch):
    import boerdi.services.config_loader as cl

    monkeypatch.setattr(cl, "get_enabled_mcp_servers", lambda: [
        {"url": "https://reg/mcp", "tools": ["spezial_tool"]},
        {"tools": ["ohne_url_tool"]},
    ])
    default = transport.resolve_mcp_url()
    assert client._get_server_url_for_tool("spezial_tool") == "https://reg/mcp"
    # Server ohne url-Feld → Default; unbekanntes Tool → Default.
    assert client._get_server_url_for_tool("ohne_url_tool") == default
    assert client._get_server_url_for_tool("nirgends") == default


def test_strukturierter_teil_ohne_schreibzugriff_bleibt_still(mcp_state, monkeypatch, caplog):
    """Live-Befund 2026-08-21: Der MCP-Server hängt ``structuredContent`` an
    JEDE Antwort (Markdown wie JSON, sein eigener Kommentar sagt es). Nur ein
    vorbereiteter Schreibzugriff ist daraus lesbar — bei jedem Leseaufruf lief
    also eine WARNING auf, und der Kommentar daneben verspricht ausdrücklich
    „still verworfen". Ein Warn-Level, das bei jedem Zug feuert, verdeckt
    echte Probleme."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [
        {"result": {"content": [_text_part("Quelle: https://e.org/ -- Text")],
                    "structuredContent": {"url": "https://e.org/", "charCount": 12,
                                          "truncated": False, "text": "Text"}}},
    ])
    with caplog.at_level("WARNING"):
        asyncio.run(client.call_mcp_tool("get_url_text", {"url": "https://e.org/"}))
    assert not [r for r in caplog.records if "strukturierten Teil" in r.message]


def test_ein_nicht_abrufbarer_skill_wird_nicht_gecached(mcp_state, monkeypatch):
    """Paket 6, G1 (Befund Gatekeeper-Skill, 2026-10-08): Der MCP-Server meldet
    jede Störung beim Laden eines Skills — falsche Kennung, fehlende Rechte, ein
    vorübergehender 5xx — mit demselben Satz als gewöhnliches Ergebnis. Der Cache
    hielt ihn 180 s als Treffer fest; ein erneuter Versuch spielte den Fehler ab."""
    _wire_tool_url(monkeypatch)
    kennung = "5400fc80-85dd-4240-8974-5485dd124076"
    fehl = f"Skill {kennung} ist nicht abrufbar (unbekannte nodeId oder kein Zugriff)."
    calls = _wire_transport(monkeypatch, [
        _result([_text_part(fehl)]),
        _result([_text_part("# Gatekeeper für Sammlungen")]),
    ])
    args = {"nodeId": kennung}
    assert asyncio.run(client.call_mcp_tool("get_skill", args)) == fehl
    assert asyncio.run(client.call_mcp_tool("get_skill", args)) == "# Gatekeeper für Sammlungen"
    assert len(calls) == 2
    # Ein Treffer bleibt im Cache wie bisher.
    assert asyncio.run(client.call_mcp_tool("get_skill", args)) == "# Gatekeeper für Sammlungen"
    assert len(calls) == 2


# ═══ Paket 10 (Audit 2026-10-10, A-8): Inhalte von Schreibvorgängen im Log ═══
def test_kurations_argumente_stehen_auf_info_nur_als_laengen(mcp_state, monkeypatch, caplog):
    # Titel, Beschreibungen und Schlagwörter unveröffentlichter Inhalte standen bis
    # 500 Zeichen im Klartext auf INFO; jetzt dort nur Schlüssel und Längen.
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("Vorschau")])])
    with caplog.at_level("INFO", logger="boerdi.services.mcp.client"):
        asyncio.run(client.call_mcp_tool("wlo_create_content", {
            "title": "Geheimer Entwurf", "keywords": ["Optik", "Linse"]}))
    info = " ".join(r.getMessage() for r in caplog.records if r.levelname == "INFO")
    assert "Geheimer Entwurf" not in info and "Linse" not in info
    assert "‹16 Zeichen›" in info and "‹2 Einträge›" in info


def test_such_argumente_auf_info_filter_lesbar_suchtext_als_laenge(mcp_state, monkeypatch,
                                                                    caplog):
    # Paket 18C/D: der Suchtext steht in der Zugakte des Zugs; das Log zeigt die Filter (der
    # häufigste Fehlertyp) und vom Freitext nur die Länge.
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("Treffer")])])
    with caplog.at_level("DEBUG", logger="boerdi.services.mcp.client"):
        asyncio.run(client.call_mcp_tool("search_wlo_content",
                                         {"query": "Optik", "discipline": "Physik"}))
    assert "Optik" not in caplog.text
    assert "‹5 Zeichen›" in caplog.text and "Physik" in caplog.text


def test_mit_log_content_stehen_die_werte_auf_debug(mcp_state, monkeypatch, caplog):
    from boerdi.settings import get_settings

    monkeypatch.setenv("LOG_CONTENT", "true")
    get_settings.cache_clear()
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("Treffer")])])
    with caplog.at_level("DEBUG", logger="boerdi.services.mcp.client"):
        asyncio.run(client.call_mcp_tool("search_wlo_content", {"query": "Optik"}))
    debug = [r.getMessage() for r in caplog.records if r.levelname == "DEBUG"]
    assert any("Optik" in z for z in debug)
    assert all("Optik" not in r.getMessage() for r in caplog.records if r.levelname == "INFO")


def test_jeder_aufruf_ist_ein_ereignis(mcp_state, monkeypatch, caplog):
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_result([_text_part("Treffer")]),
                                  {"error": {"message": "nein", "kind": "tool"}}])
    with caplog.at_level("INFO", logger="boerdi.services.mcp.client"):
        asyncio.run(client.call_mcp_tool_status("search_wlo_content", {"query": "a"}))
        asyncio.run(client.call_mcp_tool_status("search_wlo_content", {"query": "b"}))
    zeilen = [r for r in caplog.records if getattr(r, "ereignis", "") == "mcp_aufruf"]
    assert [(z.ereignis_felder["werkzeug"], z.ereignis_felder["status"]) for z in zeilen] == [
        ("search_wlo_content", "ok"), ("search_wlo_content", "tool")]
    assert {"aus_cache", "dauer_ms", "zeichen"} <= set(zeilen[0].ereignis_felder)



def test_ein_abgebrochener_aufruf_steht_in_der_zugakte(mcp_state, monkeypatch):
    """Review 2026-10-30: von außen abgebrochen (Frist, ``wait_for``) fehlte er in der Akte."""
    from boerdi.services.zugakte import aktuelle_zugakte, binde_zugakte

    async def haengt(tool_name, arguments=None, *, url=None):
        await asyncio.sleep(10)

    _wire_tool_url(monkeypatch)
    monkeypatch.setattr(transport, "call_tool", haengt)

    async def zug() -> dict:
        binde_zugakte()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(client.call_mcp_tool_status(
                "search_wlo_content", {"query": "Optik"}, use_cache=False), 0.05)
        return aktuelle_zugakte().als_dict()

    eintrag = asyncio.run(zug())["werkzeuge"][0]
    assert (eintrag["name"], eintrag["status"], eintrag["fehler"]) == (
        "search_wlo_content", "abgebrochen", "CancelledError")



def test_eine_unerwartete_ausnahme_steht_in_der_zugakte(mcp_state, monkeypatch):
    from boerdi.services.zugakte import aktuelle_zugakte, binde_zugakte

    async def kaputt(tool_name, arguments=None, *, url=None):
        raise RuntimeError("Programmfehler")

    _wire_tool_url(monkeypatch)
    monkeypatch.setattr(transport, "call_tool", kaputt)

    async def zug() -> dict:
        binde_zugakte()
        with pytest.raises(RuntimeError):
            await client.call_mcp_tool_status("search_wlo_content", {"query": "x"},
                                              use_cache=False)
        return aktuelle_zugakte().als_dict()

    eintrag = asyncio.run(zug())["werkzeuge"][0]
    assert (eintrag["status"], eintrag["fehler"]) == ("ausnahme", "RuntimeError")
