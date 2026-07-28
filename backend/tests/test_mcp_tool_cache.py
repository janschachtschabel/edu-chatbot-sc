"""Charakterisierungs-Pins für den Tool-Result-Cache des MCP-Pakets.

1:1-Port aus ALT ``tests/test_mcp_tool_cache.py``: pinnt Key-Bildung,
Empty-Erkennung, Per-Tool-TTL, Set/Get-Roundtrip, Negativ-Cache (`__NEG__`) und
Reset. Der Cache hält mutablen Modul-Zustand (LRU-Dict + Hit/Miss-Zähler) — per
Eiserne Regel 3 ausdrücklich erlaubt (MCP-TTL-Cache pro Prozess, nur Performance).
Deviation ggü. ALT: Import aus ``boerdi.services.mcp.tool_cache`` (in ALT lief er
über die ``mcp_client``-Re-Export-Fassade, die im Neubau erst mit 5-1c entsteht).

Jeder zustandsberührende Test ruft zuerst ``clear_tool_cache()`` — die Zähler
sind prozess-global und würden sonst über Tests hinweg lecken.
"""

from __future__ import annotations

from boerdi.services.mcp.tool_cache import (
    _cache_get,
    _cache_key,
    _cache_set,
    _is_empty_response,
    _ttl_for_tool,
    clear_tool_cache,
    get_tool_cache_stats,
)


# ── _cache_key: stabil + arg-order-unabhängig ───────────────────────────
def test_cache_key_is_order_independent():
    k1 = _cache_key("search", {"a": 1, "b": 2})
    k2 = _cache_key("search", {"b": 2, "a": 1})
    assert k1 == k2


def test_cache_key_differs_by_tool_and_args():
    assert _cache_key("t1", {"a": 1}) != _cache_key("t2", {"a": 1})
    assert _cache_key("t1", {"a": 1}) != _cache_key("t1", {"a": 2})


# ── _is_empty_response ──────────────────────────────────────────────────
def test_is_empty_response():
    assert _is_empty_response("") is True
    assert _is_empty_response("   ") is True
    assert _is_empty_response('{"items": []}') is True
    assert _is_empty_response('[]') is True
    assert _is_empty_response('{"items": [1]}') is False
    assert _is_empty_response("kein json") is False


# ── _ttl_for_tool ───────────────────────────────────────────────────────
def test_ttl_per_tool_and_default():
    assert _ttl_for_tool("lookup_wlo_vocabulary") == 86400
    assert _ttl_for_tool("get_subject_portals") == 1800
    assert _ttl_for_tool("__unknown_tool__") == 300  # Default


# ── Set/Get-Roundtrip + Zähler ──────────────────────────────────────────
def test_set_then_get_returns_value_and_counts_hit():
    clear_tool_cache()
    key = _cache_key("search_wlo_content", {"query": "x"})
    _cache_set(key, "ECHTES_ERGEBNIS")
    assert _cache_get(key) == "ECHTES_ERGEBNIS"
    stats = get_tool_cache_stats()
    assert stats["hits"] == 1 and stats["misses"] == 0


def test_get_miss_returns_none_and_counts_miss():
    clear_tool_cache()
    assert _cache_get(_cache_key("t", {"nope": 1})) is None
    assert get_tool_cache_stats()["misses"] == 1


# ── Negativ-Cache: leeres Ergebnis wird kurz gecached, Marker gestrippt ──
def test_negative_cache_strips_marker_and_counts_neg_hit():
    clear_tool_cache()
    key = _cache_key("search_wlo_content", {"query": "leer"})
    _cache_set(key, '{"items": []}')          # empty → Negativ-Eintrag
    assert _cache_get(key) == '{"items": []}'  # Marker transparent gestrippt
    assert get_tool_cache_stats()["negative_hits"] == 1


# ── clear_tool_cache setzt alles zurück ─────────────────────────────────
def test_clear_resets_state():
    _cache_set(_cache_key("t", {"a": 1}), "v")
    _cache_get(_cache_key("t", {"a": 1}))
    clear_tool_cache()
    stats = get_tool_cache_stats()
    assert stats["hits"] == 0 and stats["misses"] == 0
    assert stats["size"] == 0 and stats["negative_hits"] == 0


def test_stats_shape():
    stats = get_tool_cache_stats()
    for k in ("hits", "misses", "negative_hits", "size", "max_entries", "hit_rate"):
        assert k in stats
