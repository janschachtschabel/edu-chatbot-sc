"""Charakterisierungs-Tests für die MCP-Argument-Resolution (5-2 arg_resolvers).

Portiert aus ALT ``tests/test_mcp_client.py`` (dem kombinierten Netz-Phase-Test),
und zwar GENAU der Teil, der in ``mcp_arg_resolvers.py`` lebt: Request-Hints,
die Selbstheilungs-Resolver (Fachportal-/Sammlungs-UUID), die Vokabular-Kette
(Label→URI-Cache · Fuzzy · LLM-Fallback · Filter-Auflösung · Prewarm) und die
``TOOL_PREPROCESSORS``-Registry. Der Client-Kern (``call_mcp_tool``, Cache-/
Retry-/queryMeta-Pfade, ``_compact_subject_portals``, Discovery) folgt in 5-1c
und wird dort getestet.

Boundaries gefaked:
  * ``arg_resolvers.call_mcp_tool`` — der Late-bound-Shim (in 5-1c gegen den
    echten Client re-verdrahtet); hier ersetzt durch ein Skript-Double. Wir
    patchen den Modul-Global ``ar.call_mcp_tool``, den die Resolver per Namen
    nachschlagen — genau der Isolations-Punkt der arg_resolvers-Einheit.
  * ``llm._acompletion`` — die patchbare LLM-Netz-Grenze (Hausstil, wie
    ``test_quick_replies_llm``); ``_llm_vocab_match`` läuft durch das echte
    ``llm.chat_completion`` (Routing/Semaphore), nur der Netz-Call ist gefaket.

ContextVar-Falle: ``asyncio.run`` kopiert den aktuellen Kontext — vor dem Lauf
gesetzte Hints (``set_request_hints``) sind innerhalb sichtbar.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from boerdi.obs import usage as usage_mod
from boerdi.services import llm
from boerdi.services.mcp import arg_resolvers as ar
from boerdi.settings import get_settings


def _reset_ar_state() -> None:
    """Prozess-globale arg_resolvers-Caches IN-PLACE leeren (kein Rebind)."""
    for _vocab_cache in ar._label_to_uri_cache.values():
        _vocab_cache.clear()
    for _k in list(ar._label_cache_loaded):
        ar._label_cache_loaded[_k] = False
    ar._llm_vocab_cache.clear()
    ar.set_request_hints({})


@pytest.fixture()
def ar_state(monkeypatch):
    """Frischer Modul-Zustand pro Test: Vokabular-Caches, Request-Hints,
    LLM-Semaphore + Settings-Cache (für die _llm_vocab_match-Pfade)."""
    get_settings.cache_clear()
    llm.reset()
    _reset_ar_state()
    yield monkeypatch
    _reset_ar_state()
    llm.reset()


def _wire_call(monkeypatch, raw):
    """``ar.call_mcp_tool`` durch ein Double ersetzen, das ``raw`` liefert und
    seine Aufrufe protokolliert."""
    calls: list[tuple] = []

    async def fake_call(tool, args):
        calls.append((tool, args))
        return raw

    monkeypatch.setattr(ar, "call_mcp_tool", fake_call)
    return calls


def _wire_llm(monkeypatch, content):
    """Fake LLM-Netz-Grenze (llm._acompletion) — zählt Calls, liefert content."""
    zaehler = {"calls": 0}

    async def fake_acompletion(**kwargs):
        zaehler["calls"] += 1
        return SimpleNamespace(
            model="gpt-5.6-luna",
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(
                prompt_tokens=10, completion_tokens=5,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
        )

    monkeypatch.setattr(llm, "_acompletion", fake_acompletion)
    return zaehler


# ═══ Request-Hints (ContextVars) ══════════════════════════════════════════
def test_set_request_hints_verwirft_leere_werte(ar_state):
    # NOTE: pinnt IST-Verhalten — nur None/""/[]/{} werden gedroppt;
    # die Zahl 0 überlebt das Cleaning (0 == "" ist False).
    ar.set_request_hints({
        "fach": "Mathe", "thema": "", "stufe": None,
        "liste": [], "mapping": {}, "zahl": 0,
    })
    assert ar.get_request_hint("fach") == "Mathe"
    assert ar.get_request_hint("zahl") == 0
    for tot in ("thema", "stufe", "liste", "mapping"):
        assert ar.get_request_hint(tot) == ""
    assert ar.get_request_hint("fehlt", default="X") == "X"


def test_set_active_fach_ersetzt_alle_hints(ar_state):
    # NOTE: pinnt IST-Verhalten — set_active_fach ruft set_request_hints und
    # ERSETZT damit das komplette Hint-Dict (vorherige Hints gehen verloren).
    ar.set_request_hints({"thema": "Brüche"})
    ar.set_active_fach("  Bio  ")
    assert ar.get_request_hint("fach") == "Bio"
    assert ar.get_request_hint("thema") == ""


# ═══ _find_portal_by_name (pur) ═══════════════════════════════════════════
def test_find_portal_strategien_exakt_ci_prefix_contains():
    exakt = [{"title": "mathematik"}, {"title": "Mathematik"}]
    assert ar._find_portal_by_name(exakt, "Mathematik") is exakt[1]
    ci = [{"title": "MATHEMATIK"}, {"title": "Mathematik für alle"}]
    assert ar._find_portal_by_name(ci, "Mathematik") is ci[0]
    prefix = [{"title": "Höhere Algebra"}, {"title": "Mathematik"}]
    assert ar._find_portal_by_name(prefix, "Mathe") is prefix[1]
    contains = [{"title": "Mathematik"}]
    assert ar._find_portal_by_name(contains, "thema") is contains[0]


def test_find_portal_leere_eingaben_und_kein_treffer():
    assert ar._find_portal_by_name([], "Mathe") is None
    assert ar._find_portal_by_name([{"title": "Physik"}], "") is None
    assert ar._find_portal_by_name([{"title": "Physik"}, "junk", 42], "Chemie") is None


# ═══ _resolve_browse_node_id (Selbstheilung Fachportal-UUID) ══════════════
_PORTALS_JSON = json.dumps({"results": [
    {"nodeId": "aaaaaaaa-1111-4111-8111-111111111111", "title": "Mathematik"},
    {"nodeId": "bbbbbbbb-2222-4222-8222-222222222222", "title": "Geographie"},
]})


def test_browse_resolver_loest_fachnamen_zu_uuid(ar_state, monkeypatch):
    calls = _wire_call(monkeypatch, _PORTALS_JSON)
    out = asyncio.run(ar._resolve_browse_node_id(
        {"nodeId": "Mathematik", "maxDepth": 2}))
    assert out == {"nodeId": "aaaaaaaa-1111-4111-8111-111111111111", "maxDepth": 2}
    assert calls == [("get_subject_portals", {"includeContentCounts": False})]


def test_browse_resolver_junk_mit_fach_hint(ar_state, monkeypatch):
    _wire_call(monkeypatch, _PORTALS_JSON)
    ar.set_request_hints({"fach": "Mathematik"})
    out = asyncio.run(ar._resolve_browse_node_id({"nodeId": "dummmy"}))
    assert out["nodeId"] == "aaaaaaaa-1111-4111-8111-111111111111"


def test_browse_resolver_uuid_mit_falschem_fach_wird_uebersteuert(ar_state, monkeypatch):
    _wire_call(monkeypatch, _PORTALS_JSON)
    ar.set_request_hints({"fach": "Mathematik"})
    out = asyncio.run(ar._resolve_browse_node_id(
        {"nodeId": "bbbbbbbb-2222-4222-8222-222222222222"}))  # Geographie
    assert out["nodeId"] == "aaaaaaaa-1111-4111-8111-111111111111"
    # Passende UUID bleibt unangetastet (No-op-Pfad).
    out2 = asyncio.run(ar._resolve_browse_node_id(
        {"nodeId": "aaaaaaaa-1111-4111-8111-111111111111"}))
    assert out2 == {"nodeId": "aaaaaaaa-1111-4111-8111-111111111111"}


def test_browse_resolver_uuid_ohne_hint_und_fehler_sind_passthrough(ar_state, monkeypatch):
    # Ohne fach-Hint wird eine UUID nie angefasst (und nichts nachgeladen).
    calls = _wire_call(monkeypatch, _PORTALS_JSON)
    args = {"nodeId": "bbbbbbbb-2222-4222-8222-222222222222"}
    assert asyncio.run(ar._resolve_browse_node_id(args)) == args
    assert calls == []

    # Portal-Fetch explodiert → Original-Args unverändert zurück.
    async def kaputt(tool, a):
        raise RuntimeError("mcp down")

    monkeypatch.setattr(ar, "call_mcp_tool", kaputt)
    junk = {"nodeId": "Mathematik"}
    assert asyncio.run(ar._resolve_browse_node_id(junk)) == junk


def test_browse_resolver_unaufloesbarer_name_passthrough(ar_state, monkeypatch):
    _wire_call(monkeypatch, _PORTALS_JSON)
    out = asyncio.run(ar._resolve_browse_node_id({"nodeId": "Unterwasserkorbflechten"}))
    assert out == {"nodeId": "Unterwasserkorbflechten"}


# ═══ _resolve_collection_node_id (Selbstheilung Sammlungs-UUID) ═══════════
def test_collection_resolver_uuid_und_leer_sind_passthrough(ar_state, monkeypatch):
    calls = _wire_call(monkeypatch, _PORTALS_JSON)  # dürfte nie aufgerufen werden
    uuid_args = {"nodeId": "cccccccc-3333-4333-8333-333333333333"}
    assert asyncio.run(ar._resolve_collection_node_id(uuid_args)) == uuid_args
    leer = {"nodeId": ""}
    assert asyncio.run(ar._resolve_collection_node_id(leer)) == leer
    assert calls == []


def test_collection_resolver_name_via_suche(ar_state, monkeypatch):
    raw = json.dumps({"results": [
        {"title": "ohne id"},
        {"nodeId": "cccccccc-3333-4333-8333-333333333333", "title": "Eiszeit"},
    ]})
    calls = _wire_call(monkeypatch, raw)
    out = asyncio.run(ar._resolve_collection_node_id({"nodeId": "Eiszeit"}))
    assert out == {"nodeId": "cccccccc-3333-4333-8333-333333333333"}
    assert calls == [("search_wlo_collections", {"query": "Eiszeit", "maxResults": 3})]


def test_collection_resolver_markdown_regex_fallback(ar_state, monkeypatch):
    raw = 'Treffer:\n"nodeId": "dddddddd-4444-4444-8444-444444444444"\nmehr text'
    _wire_call(monkeypatch, raw)
    out = asyncio.run(ar._resolve_collection_node_id({"nodeId": "Klimawandel"}))
    assert out == {"nodeId": "dddddddd-4444-4444-8444-444444444444"}


def test_collection_resolver_nicht_uuid_treffer_und_fehler_passthrough(ar_state, monkeypatch):
    _wire_call(monkeypatch, json.dumps({"results": [{"nodeId": "keine-uuid"}]}))
    args = {"nodeId": "Eiszeit"}
    assert asyncio.run(ar._resolve_collection_node_id(args)) == args

    async def kaputt(tool, a):
        raise RuntimeError("mcp down")

    monkeypatch.setattr(ar, "call_mcp_tool", kaputt)
    assert asyncio.run(ar._resolve_collection_node_id(args)) == args


# ═══ Vokabular: _norm_label / _fuzzy_lookup ═══════════════════════════════
def test_norm_label():
    assert ar._norm_label("  ViDeo  ") == "video"
    assert ar._norm_label(None) == ""


def test_fuzzy_lookup_exact_und_leer():
    cache = {"video": "u-video"}
    assert ar._fuzzy_lookup(cache, "Video") == ("video", "u-video")
    assert ar._fuzzy_lookup(cache, "") is None
    assert ar._fuzzy_lookup(cache, "Podcast") is None


def test_fuzzy_lookup_substring_und_laengster_treffer_gewinnt():
    cache = {"interaktiv": "u-alias", "interaktives medium": "u-medium"}
    # Alias steckt im Needle drin ("interaktiv" ⊂ "interaktives material").
    assert ar._fuzzy_lookup(cache, "Interaktives Material") == ("interaktiv", "u-alias")
    # Mehrere Kandidaten → längster Key gewinnt (spezifisch vor generisch).
    cache2 = {"kunst": "u1", "kunstgeschichte": "u2"}
    assert ar._fuzzy_lookup(cache2, "Epochen der Kunstgeschichte") == (
        "kunstgeschichte", "u2")


# ═══ _ensure_label_cache ══════════════════════════════════════════════════
_VOCAB_MD = (
    "- **Video**\n"
    "  URI: http://x/video\n"
    "- **Interaktives medium** | Aliases: interactive media, interaktiv\n"
    "  URI: http://x/im\n"
)


def test_ensure_label_cache_parst_markdown_mit_aliassen(ar_state, monkeypatch):
    calls = _wire_call(monkeypatch, _VOCAB_MD)
    asyncio.run(ar._ensure_label_cache("lrt"))
    assert ar._label_to_uri_cache["lrt"] == {
        "video": "http://x/video",
        "interaktives medium": "http://x/im",
        "interactive media": "http://x/im",
        "interaktiv": "http://x/im",
    }
    assert ar._label_cache_loaded["lrt"] is True
    assert calls == [("lookup_wlo_vocabulary", {"vocabulary": "lrt"})]
    # Loaded-Latch: zweiter Aufruf macht keinen weiteren Tool-Call.
    asyncio.run(ar._ensure_label_cache("lrt"))
    assert len(calls) == 1


def test_ensure_label_cache_fehler_latcht_nicht(ar_state, monkeypatch):
    versuche = []

    async def kaputt(tool, args):
        versuche.append(tool)
        raise RuntimeError("mcp down")

    monkeypatch.setattr(ar, "call_mcp_tool", kaputt)
    asyncio.run(ar._ensure_label_cache("lrt"))
    assert ar._label_cache_loaded["lrt"] is False  # B5: kein Permanent-Latch
    asyncio.run(ar._ensure_label_cache("lrt"))  # nächster Bedarf → Retry
    assert len(versuche) == 2


def test_ensure_label_cache_unbekanntes_vokabular_ist_noop(ar_state, monkeypatch):
    calls = _wire_call(monkeypatch, _PORTALS_JSON)
    asyncio.run(ar._ensure_label_cache("gibtsnicht"))
    assert calls == []


# ═══ prewarm_vocabularies ═════════════════════════════════════════════════
def test_prewarm_laedt_alle_vier_vokabulare_best_effort(ar_state, monkeypatch):
    geladen = []

    async def fake_ensure(vocab):
        geladen.append(vocab)
        if vocab == "userRole":
            raise RuntimeError("kalt")

    monkeypatch.setattr(ar, "_ensure_label_cache", fake_ensure)
    asyncio.run(ar.prewarm_vocabularies())  # darf trotz Fehler nicht werfen
    assert sorted(geladen) == sorted(
        ["lrt", "discipline", "educationalContext", "userRole"])


# ═══ _llm_vocab_match ═════════════════════════════════════════════════════
def test_llm_vocab_match_gueltige_uri_wird_gecached(ar_state, monkeypatch):
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    zaehler = _wire_llm(monkeypatch, "http://x/im")
    assert asyncio.run(ar._llm_vocab_match("lrt", "Simulation")) == "http://x/im"
    # Zweiter Aufruf: nur noch Cache, kein LLM-Roundtrip.
    assert asyncio.run(ar._llm_vocab_match("lrt", "Simulation")) == "http://x/im"
    assert zaehler["calls"] == 1
    assert ar._llm_vocab_cache[("lrt", "simulation")] == "http://x/im"


def test_llm_vocab_match_none_und_dekorierte_uri(ar_state, monkeypatch):
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    _wire_llm(monkeypatch, "NONE")
    assert asyncio.run(ar._llm_vocab_match("lrt", "Quatschwert")) is None
    assert ar._llm_vocab_cache[("lrt", "quatschwert")] is None
    # Backticks werden gestrippt; URI-in-Prosa via Contains-Fallback gefunden.
    _wire_llm(monkeypatch, "`http://x/im`")
    assert asyncio.run(ar._llm_vocab_match("lrt", "Simulator")) == "http://x/im"
    _wire_llm(monkeypatch, "Die URI ist http://x/im gell")
    assert asyncio.run(ar._llm_vocab_match("lrt", "Simulierung")) == "http://x/im"


def test_llm_vocab_match_guards_ohne_llm_call(ar_state, monkeypatch):
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    zaehler = _wire_llm(monkeypatch, "http://x/im")
    assert asyncio.run(ar._llm_vocab_match("lrt", "")) is None
    assert asyncio.run(ar._llm_vocab_match("lrt", "x")) is None  # < MIN_LEN 2
    assert asyncio.run(ar._llm_vocab_match("lrt", "y" * 81)) is None  # > MAX_LEN 80
    assert asyncio.run(ar._llm_vocab_match("discipline", "Mathe")) is None  # Cache leer
    assert zaehler["calls"] == 0


def test_llm_vocab_match_nicht_uri_antwort_und_exception(ar_state, monkeypatch):
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    _wire_llm(monkeypatch, "http://ganz-andere-uri/xyz")
    assert asyncio.run(ar._llm_vocab_match("lrt", "Dings")) is None
    assert ar._llm_vocab_cache[("lrt", "dings")] is None

    # LLM-Transport wirft → None + Negativ-Cache.
    async def _boom(**kwargs):
        raise RuntimeError("kein key")

    monkeypatch.setattr(llm, "_acompletion", _boom)
    assert asyncio.run(ar._llm_vocab_match("lrt", "Anderes")) is None
    assert ar._llm_vocab_cache[("lrt", "anderes")] is None


# ═══ _resolve_filter_uris ═════════════════════════════════════════════════
def test_resolve_filter_uris_label_zu_uri(ar_state, monkeypatch):
    ensured = []

    async def fake_ensure(vocab):
        ensured.append(vocab)

    monkeypatch.setattr(ar, "_ensure_label_cache", fake_ensure)
    ar._label_to_uri_cache["discipline"]["mathematik"] = "http://d/math"
    ar._label_to_uri_cache["lrt"]["video"] = "http://l/video"
    out = asyncio.run(ar._resolve_filter_uris({
        "query": "Brüche",
        "discipline": "Mathematik",
        "learningResourceType": "Video",
    }))
    assert out["discipline"] == "http://d/math"
    assert out["learningResourceType"] == "http://l/video"
    assert out["query"] == "Brüche"  # Nicht-Filter-Keys unangetastet
    assert set(ensured) == {"discipline", "lrt"}


def test_resolve_filter_uris_uri_und_nicht_string_passthrough(ar_state, monkeypatch):
    ensured = []

    async def fake_ensure(vocab):
        ensured.append(vocab)

    monkeypatch.setattr(ar, "_ensure_label_cache", fake_ensure)
    args = {"discipline": "https://w3id.org/schon-uri", "educationalContext": 42}
    out = asyncio.run(ar._resolve_filter_uris(args))
    assert out == args
    assert ensured == []  # URIs/Nicht-Strings lösen keinen Vocab-Load aus


def test_resolve_filter_uris_llm_fallback_und_passthrough(ar_state, monkeypatch):
    async def fake_ensure(vocab):
        pass

    monkeypatch.setattr(ar, "_ensure_label_cache", fake_ensure)

    async def fake_llm(vocab, value):
        return "http://llm/treffer" if value == "sciences" else None

    monkeypatch.setattr(ar, "_llm_vocab_match", fake_llm)
    out = asyncio.run(ar._resolve_filter_uris(
        {"discipline": "sciences", "userRole": "Marsmensch"}))
    assert out["discipline"] == "http://llm/treffer"  # LLM-Fallback greift
    assert out["userRole"] == "Marsmensch"  # unauflösbar → Label durchreichen


# ═══ TOOL_PREPROCESSORS-Registry ══════════════════════════════════════════
def test_tool_preprocessor_registry_verdrahtung():
    assert ar.TOOL_PREPROCESSORS["search_wlo_content"] is ar._resolve_filter_uris
    assert ar.TOOL_PREPROCESSORS["search_wlo_collections"] is ar._resolve_filter_uris
    assert ar.TOOL_PREPROCESSORS["search_wlo_all"] is ar._resolve_filter_uris
    assert ar.TOOL_PREPROCESSORS["browse_collection_tree"] is ar._resolve_browse_node_id
    assert ar.TOOL_PREPROCESSORS["get_collection_contents"] is ar._resolve_collection_node_id


# ═══ K1e: der Vokabular-Abgleich bucht seine Token ════════════════════════
# Gemessen am 2026-08-11 gegen die echten WLO-Vokabulare: ein Aufruf traegt
# das GANZE Vokabular im Prompt — 2422 (discipline) bzw. 2727 (lrt) Token.
# Der Merkposten kommt nicht als Parameter, sondern aus dem ContextVar des
# Zuges (Begruendung in obs/usage.py).

def test_llm_vocab_match_bucht_in_den_zug_merkposten(ar_state, monkeypatch):
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    _wire_llm(monkeypatch, "http://x/im")
    acc = usage_mod.new_accumulator()
    usage_mod.bind_turn_usage(acc)
    try:
        assert asyncio.run(ar._llm_vocab_match("lrt", "Simulation")) == "http://x/im"
    finally:
        usage_mod.bind_turn_usage(None)

    assert acc["calls"] == 1
    assert acc["prompt_tokens"] == 10 and acc["completion_tokens"] == 5
    assert acc["per_phase"]["vocab_match"]["prompt"] == 10


def test_llm_vocab_match_cache_treffer_bucht_nichts(ar_state, monkeypatch):
    # Ein Treffer im Prozess-Cache macht keinen LLM-Aufruf, kostet also nichts
    # und darf folglich auch nichts buchen.
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    _wire_llm(monkeypatch, "http://x/im")
    acc = usage_mod.new_accumulator()
    usage_mod.bind_turn_usage(acc)
    try:
        asyncio.run(ar._llm_vocab_match("lrt", "Simulation"))
        asyncio.run(ar._llm_vocab_match("lrt", "Simulation"))
    finally:
        usage_mod.bind_turn_usage(None)

    assert acc["calls"] == 1


def test_llm_vocab_match_ohne_zug_bucht_nicht_und_faellt_nicht_um(
        ar_state, monkeypatch):
    # Start-Vorwaermung und Werkzeug-Aufrufe ausserhalb eines Zuges haben
    # keinen Merkposten. Das ist kein Fehlerfall — es darf nur nicht knallen.
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    _wire_llm(monkeypatch, "http://x/im")
    usage_mod.bind_turn_usage(None)
    assert asyncio.run(ar._llm_vocab_match("lrt", "Simulation")) == "http://x/im"
