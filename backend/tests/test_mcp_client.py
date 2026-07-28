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

import pytest

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
    key = tool_cache._cache_key("search_wlo_all", sent)
    assert tool_cache._cache_get(key) is not None


def test_call_mcp_tool_output_format_wird_nicht_ueberschrieben(mcp_state, monkeypatch):
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_result([_text_part("ok")])])
    asyncio.run(client.call_mcp_tool(
        "search_wlo_all", {"query": "x", "outputFormat": "markdown"}))
    assert calls[0]["arguments"]["outputFormat"] == "markdown"


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
    key = tool_cache._cache_key("unknown_probe_tool", {"q": "x"})
    assert tool_cache._TOOL_META_CACHE[key] == metas


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
