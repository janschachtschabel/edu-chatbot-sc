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

import pytest

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


def test_cache_key_unterscheidet_den_server():
    """Paket 4, C3 (externes Audit F12): Werkzeug, Aufrufer und Argumente
    reichten nicht — ein Registry-Server, dessen Adresse das Studio umstellt,
    lieferte bis zu 30 min (Vokabular 24 h) die Treffer des alten Servers."""
    a = _cache_key("get_node_details", {"nodeId": "n1"}, url="https://a.example/mcp")
    b = _cache_key("get_node_details", {"nodeId": "n1"}, url="https://b.example/mcp")
    assert a != b
    assert a[0] == b[0] == "get_node_details"  # die TTL hängt am Werkzeug


# ── Der Zwischenspeicher trennt nach Aufrufer (S6, 2026-08-15) ──────────
#
# Gemessen am Server, nicht angenommen: ``wlo_auth_status`` liefert
# ``{"mode":"user","authenticated":true,"configuredAs":"…"}`` — der MCP-Server
# handelt als BESTIMMTE Person, und seine eigene Werkzeug-Beschreibung sagt es
# ausdrücklich: ``mode="anonymous"`` = nur öffentliche Daten, ``mode="user"`` =
# die Rechte der angemeldeten Person („warum sie bestimmte Inhalte (nicht)
# sieht").
#
# Was gelesen wird, hängt also an der Identität. Der Speicher hier ist
# prozessweit und lebt über alle Sitzungen; ohne die Identität im Schlüssel
# bekäme die zweite Person die Treffer der ersten.

_ANFRAGE = ("search_wlo_content", {"searchTerm": "Optik"})


@pytest.fixture(autouse=True)
def _kein_zugangsblock():
    """Jeder Test startet und endet ohne Anmeldung — dieselbe Fixture wie in
    ``test_agent_tools``, und aus demselben Grund: der Block lebt in einem
    ``ContextVar``, und den nimmt ``monkeypatch`` nicht zurück (er ist kein
    Attribut).

    Gemessen, als sie hier fehlte: 7 Fehlschläge in ``test_mcp_auth``, die einen
    Zug ohne Anmeldung erwarten. Seit der Cache-Schlüssel den Aufrufer kennt,
    hängt daran auch dieser Speicher — ein übriggebliebener Block verschöbe
    fremde Tests in einen anderen Topf.
    """
    from boerdi.services.mcp.auth import set_turn_auth_block
    set_turn_auth_block(None)
    yield
    set_turn_auth_block(None)


def _als(monkeypatch, block: str):
    """Diesen Zug unter dem gegebenen Zugangsblock laufen lassen."""
    from boerdi.services.mcp.auth import set_turn_auth_block
    monkeypatch.setattr(
        "boerdi.services.mcp.auth._token", lambda: "", raising=True)
    set_turn_auth_block(block)


def test_zwei_personen_teilen_sich_keinen_treffer(monkeypatch):
    """DER BEFUND. Ohne Trennung liest die zweite Person, was die erste sah."""
    clear_tool_cache()
    _als(monkeypatch, "wlo2.personA")
    _cache_set(_cache_key(*_ANFRAGE), "TREFFER-VON-A")

    _als(monkeypatch, "wlo2.personB")
    assert _cache_get(_cache_key(*_ANFRAGE)) is None, (
        "Person B bekommt den Treffer von Person A aus dem Zwischenspeicher"
    )


def test_dieselbe_person_bekommt_ihren_treffer_wieder(monkeypatch):
    """Gegenprobe: die Trennung darf den Speicher nicht abschalten."""
    clear_tool_cache()
    _als(monkeypatch, "wlo2.personA")
    _cache_set(_cache_key(*_ANFRAGE), "TREFFER-VON-A")
    _als(monkeypatch, "wlo2.personA")
    assert _cache_get(_cache_key(*_ANFRAGE)) == "TREFFER-VON-A"


def test_anonyme_zuege_teilen_sich_einen_topf(monkeypatch):
    """Ohne Anmeldung sehen alle dasselbe — getrennte Töpfe wären Verschwendung."""
    clear_tool_cache()
    _als(monkeypatch, "")
    _cache_set(_cache_key(*_ANFRAGE), "OEFFENTLICH")
    _als(monkeypatch, "")
    assert _cache_get(_cache_key(*_ANFRAGE)) == "OEFFENTLICH"


def test_das_dienstkonto_ist_ein_topf_fuer_alle(monkeypatch):
    """``MCP_AUTH_TOKEN`` gilt allen Nutzenden gleich (so sagt es der Server:
    „dieselben Rechte für alle Nutzenden") — ein gemeinsamer Topf ist richtig."""
    clear_tool_cache()
    monkeypatch.setattr(
        "boerdi.services.mcp.auth._token", lambda: "wlo2.dienstkonto", raising=True)
    from boerdi.services.mcp.auth import set_turn_auth_block
    set_turn_auth_block("")          # Besucher 1: keine eigene Anmeldung
    _cache_set(_cache_key(*_ANFRAGE), "DIENSTKONTO-TREFFER")
    set_turn_auth_block("")          # Besucher 2: ebenfalls keine
    assert _cache_get(_cache_key(*_ANFRAGE)) == "DIENSTKONTO-TREFFER"


def test_der_schluessel_enthaelt_den_block_nicht(monkeypatch):
    """Der Zugangsblock verschlüsselt ein WLO-Passwort. Er darf nicht als
    Klartext in einem prozessweiten Dict stehen, das jeder Speicherauszug
    mitnimmt."""
    clear_tool_cache()
    _als(monkeypatch, "wlo2.sehrGeheimerBlock")
    schluessel = _cache_key(*_ANFRAGE)
    assert "sehrGeheimerBlock" not in "".join(schluessel)


def test_die_tool_ttl_greift_weiterhin(monkeypatch):
    """``_cache_get`` liest die TTL aus ``key[0]``. Stünde dort etwas anderes
    als der Werkzeugname, fiele jede Per-Tool-TTL still auf den Standard."""
    clear_tool_cache()
    _als(monkeypatch, "wlo2.personA")
    assert _cache_key("lookup_wlo_vocabulary", {})[0] == "lookup_wlo_vocabulary"


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


def test_ttl_skills_kuerzer_als_default():
    """Nutzer-Entscheid 2026-08-20: redaktionelle Skill-Änderungen sollen nach
    spätestens 3 Minuten beim Bot ankommen — vorher fielen beide Skill-Werkzeuge
    auf den 5-Minuten-Default."""
    assert _ttl_for_tool("get_skill") == 180
    assert _ttl_for_tool("get_skill_registry") == 180


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


# ── Paket 10 (Audit 2026-10-10, M-4): Metas gehören zu ihrem Wert ───────────
def test_ein_neuer_wert_ohne_metas_erbt_die_alten_nicht():
    # Lieferte der neue Aufruf keine ``_queryMeta``, gab der nächste Treffer die
    # Filter-Metas des alten Werts aus — falsche Such-CTA, falsche Facetten.
    from boerdi.services.mcp.tool_cache import _TOOL_META_CACHE

    clear_tool_cache()
    key = _cache_key("search_wlo_content", {"searchTerm": "Optik"})
    _cache_set(key, "alter Wert")
    _TOOL_META_CACHE[key] = [{"discipline": "alt"}]
    _cache_set(key, "neuer Wert")
    assert key not in _TOOL_META_CACHE


def test_ein_abgelaufener_eintrag_nimmt_seine_metas_mit(monkeypatch):
    from boerdi.services.mcp import tool_cache

    clear_tool_cache()
    key = _cache_key("search_wlo_content", {"searchTerm": "Optik"})
    _cache_set(key, "Wert")
    tool_cache._TOOL_META_CACHE[key] = [{"discipline": "alt"}]
    jetzt = tool_cache._time.time()
    monkeypatch.setattr(tool_cache._time, "time", lambda: jetzt + 10 ** 7)
    assert _cache_get(key) is None
    assert key not in tool_cache._TOOL_META_CACHE
