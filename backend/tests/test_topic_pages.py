"""P5-6b (slice): topic-pages MCP-search helpers — port of ALT
chat_topic_pages.py CHARACTERIZATION tests (test_chat_topic_pages.py).

Pins the IST-behaviour of the two pure helpers ``_is_empty_topic_pages_response``
+ ``_filter_topic_pages_by_title`` (offline, run for real), the async
``_topic_pages_with_warmup`` (MCP warmup → primary call → global-list fallback)
and — R6-wired (2026-07-24) — the M16 view resolver
``_resolve_m16_topic_page_view`` (M16-only Themenseiten-content → swimlane boxes).

Boundaries for the warmup: ``boerdi.services.mcp.client.call_mcp_tool`` (lazy-
imported inside the function → patched at the source module); the two pure
helpers run for real. For the M16 resolver: ``call_mcp_tool`` is a top-import →
patched on THIS module; ``parse_wlo_cards``/``parse_topic_page_swimlanes`` stay
lazy → patched at the source module; the TopicPageView/SwimlaneBox/WloCard
schemas are built for real.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.services.topic_pages import (
    _filter_topic_pages_by_title,
    _is_empty_topic_pages_response,
    _resolve_m16_topic_page_view,
    _topic_pages_with_warmup,
)

# ══════════════════════════════════════════════════════════════════════════
# _is_empty_topic_pages_response
# ══════════════════════════════════════════════════════════════════════════

class TestIsEmptyTopicPagesResponse:
    def test_empty_string_is_empty(self):
        assert _is_empty_topic_pages_response("") is True

    def test_none_is_empty(self):
        assert _is_empty_topic_pages_response(None) is True

    def test_german_marker_is_empty(self):
        assert _is_empty_topic_pages_response(
            "Keine Themenseiten gefunden für 'Mathematik'."
        ) is True

    def test_marker_anywhere_in_text(self):
        assert _is_empty_topic_pages_response(
            "Hinweis: Keine Themenseiten vorhanden"
        ) is True

    def test_json_empty_results_is_empty(self):
        assert _is_empty_topic_pages_response('{"results": []}') is True

    def test_json_empty_items_is_empty(self):
        assert _is_empty_topic_pages_response('{"items": []}') is True

    def test_json_dict_without_result_keys_is_empty(self):
        assert _is_empty_topic_pages_response('{"total": 0}') is True

    def test_json_with_results_not_empty(self):
        assert _is_empty_topic_pages_response(
            '{"results": [{"title": "Mathematik"}]}'
        ) is False

    def test_empty_results_but_filled_items_not_empty(self):
        # NOTE: pinnt IST-Verhalten — die or-Kette
        # ``parsed.get("results") or parsed.get("items")`` fällt bei leerem
        # results-Array auf items zurück → nicht-leer.
        raw = '{"results": [], "items": [{"title": "X"}]}'
        assert _is_empty_topic_pages_response(raw) is False

    def test_top_level_json_list_not_empty(self):
        # NOTE: pinnt IST-Verhalten — eine Top-Level-JSON-Liste (auch die
        # LEERE Liste "[]") ist kein dict → fällt durch bis ``return False``.
        assert _is_empty_topic_pages_response("[]") is False
        assert _is_empty_topic_pages_response('[{"title": "X"}]') is False

    def test_plain_text_without_marker_not_empty(self):
        assert _is_empty_topic_pages_response("3 Themenseiten gefunden: ...") is False


# ══════════════════════════════════════════════════════════════════════════
# _filter_topic_pages_by_title
# ══════════════════════════════════════════════════════════════════════════

ENVELOPE = json.dumps({
    "results": [
        {"title": "Mathematik", "node_id": "n1"},
        {"title": "Deutsch", "node_id": "n2"},
        {"title": "Mathematik Grundschule", "node_id": "n3"},
    ],
    "total": 3,
})


class TestFilterTopicPagesByTitle:
    def test_filters_by_title_contains(self):
        out = _filter_topic_pages_by_title(ENVELOPE, "Mathematik")
        assert out is not None
        parsed = json.loads(out)
        assert [r["node_id"] for r in parsed["results"]] == ["n1", "n3"]
        assert parsed["total"] == 2
        assert parsed["_query_fallback"] is True

    def test_case_insensitive(self):
        out = _filter_topic_pages_by_title(ENVELOPE, "MATHE")
        assert out is not None
        assert len(json.loads(out)["results"]) == 2

    def test_needle_is_stripped(self):
        out = _filter_topic_pages_by_title(ENVELOPE, "  deutsch  ")
        assert out is not None
        parsed = json.loads(out)
        assert [r["node_id"] for r in parsed["results"]] == ["n2"]

    def test_no_match_returns_none(self):
        assert _filter_topic_pages_by_title(ENVELOPE, "Chemie") is None

    def test_empty_raw_returns_none(self):
        assert _filter_topic_pages_by_title("", "Mathe") is None

    def test_empty_needle_returns_none(self):
        assert _filter_topic_pages_by_title(ENVELOPE, "") is None

    def test_invalid_json_returns_none(self):
        assert _filter_topic_pages_by_title("kein json {", "Mathe") is None

    def test_top_level_list_returns_none(self):
        assert _filter_topic_pages_by_title('[{"title": "Mathe"}]', "Mathe") is None

    def test_items_key_source_gets_results_key_added(self):
        # NOTE: pinnt IST-Verhalten — kommt der Input mit "items" statt
        # "results", schreibt der Filter das Ergebnis trotzdem nach
        # out["results"]; das originale "items"-Array bleibt UNGEFILTERT
        # daneben stehen.
        raw = json.dumps({"items": [
            {"title": "Mathematik"}, {"title": "Deutsch"},
        ]})
        out = _filter_topic_pages_by_title(raw, "mathe")
        assert out is not None
        parsed = json.loads(out)
        assert [r["title"] for r in parsed["results"]] == ["Mathematik"]
        assert len(parsed["items"]) == 2  # Original bleibt erhalten

    def test_non_dict_entries_are_dropped(self):
        raw = json.dumps({"results": [{"title": "Mathematik"}, "junk", 42]})
        out = _filter_topic_pages_by_title(raw, "mathe")
        assert out is not None
        assert len(json.loads(out)["results"]) == 1

    def test_entry_with_none_title_does_not_crash(self):
        raw = json.dumps({"results": [{"title": None}, {"title": "Mathematik"}]})
        out = _filter_topic_pages_by_title(raw, "mathe")
        assert out is not None
        assert len(json.loads(out)["results"]) == 1

    def test_umlauts_survive_ensure_ascii_false(self):
        raw = json.dumps({"results": [{"title": "Körper und Gesundheit"}]},
                         ensure_ascii=False)
        out = _filter_topic_pages_by_title(raw, "körper")
        assert out is not None
        assert "Körper" in out  # ensure_ascii=False → Umlaut literal im String

    def test_whitespace_needle_matches_everything(self):
        # NOTE: pinnt IST-Verhalten — needle "  " ist truthy, wird aber zu ""
        # gestrippt; der Leerstring ist Substring jedes Titels → ALLE
        # Ergebnisse passieren den Filter.
        out = _filter_topic_pages_by_title(ENVELOPE, "  ")
        assert out is not None
        assert len(json.loads(out)["results"]) == 3

    def test_extra_envelope_keys_preserved(self):
        raw = json.dumps({"results": [{"title": "Mathematik"}],
                          "total": 1, "server": "wlo"})
        out = _filter_topic_pages_by_title(raw, "mathe")
        parsed = json.loads(out)
        assert parsed["server"] == "wlo"


# ══════════════════════════════════════════════════════════════════════════
# _topic_pages_with_warmup
# Warmup (verworfen) → Primary-Call; bei 0 Treffern Global-List-Fallback:
# erst Titel-Filter, sonst bis zu 5 globale TPs, sonst Primary. Einzige
# Boundary = call_mcp_tool; die reinen Helfer laufen echt.
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def warmup_mcp(monkeypatch):
    calls: list[tuple] = []
    rec = {
        "warmup": '{"results": []}',
        "primary": '{"results": [{"title": "Mathematik"}]}',
        "global": '{"results": []}',
        "warmup_raises": False,
        "global_raises": False,
    }

    async def _call(tool, args):
        calls.append((tool, dict(args)))
        n = len(calls)
        if n == 1:                       # Warmup (search_wlo_collections)
            if rec["warmup_raises"]:
                raise RuntimeError("warmup boom")
            return rec["warmup"]
        if n == 2:                       # Primary (search_wlo_topic_pages, extra_args)
            return rec["primary"]
        if rec["global_raises"]:         # n == 3: Global-List-Fallback
            raise RuntimeError("global boom")
        return rec["global"]

    monkeypatch.setattr("boerdi.services.mcp.client.call_mcp_tool", _call)
    return calls, rec


def _warm(query="Mathematik", extra=None):
    return asyncio.run(_topic_pages_with_warmup(query, extra or {"query": query}))


class TestTopicPagesWithWarmup:
    def test_primary_hit_returns_primary_and_skips_global(self, warmup_mcp):
        calls, rec = warmup_mcp
        out = _warm()
        assert out == rec["primary"]
        assert len(calls) == 2                     # Warmup + Primary, KEIN Global-Call
        assert calls[0][0] == "search_wlo_collections"
        assert calls[1][0] == "search_wlo_topic_pages"

    def test_warmup_failure_is_best_effort(self, warmup_mcp):
        _calls, rec = warmup_mcp
        rec["warmup_raises"] = True
        assert _warm() == rec["primary"]           # Warmup-Fehler bricht den Flow nicht ab

    def test_empty_primary_uses_global_title_match(self, warmup_mcp):
        calls, rec = warmup_mcp
        rec["primary"] = '{"results": []}'
        rec["global"] = '{"results": [{"title": "Mathematik Grundlagen"}]}'
        out = _warm(query="Mathematik")
        assert "Mathematik Grundlagen" in out
        assert "_query_fallback" in out            # _filter_topic_pages_by_title-Marker
        assert len(calls) == 3

    def test_no_title_match_returns_global_fallback(self, warmup_mcp):
        _calls, rec = warmup_mcp
        rec["primary"] = '{"results": []}'
        rec["global"] = json.dumps({"results": [{"title": "Nachhaltigkeit"},
                                                 {"title": "Klimawandel"}]})
        out = _warm(query="Mathematik")            # kein Titel enthält "Mathematik"
        assert "_global_fallback" in out
        assert "Nachhaltigkeit" in out

    def test_both_empty_returns_primary(self, warmup_mcp):
        _calls, rec = warmup_mcp
        rec["primary"] = "Keine Themenseiten gefunden"
        rec["global"] = '{"results": []}'
        assert _warm(query="Nichtsda") == "Keine Themenseiten gefunden"

    def test_global_call_error_returns_primary(self, warmup_mcp):
        _calls, rec = warmup_mcp
        rec["primary"] = "Keine Themenseiten gefunden"
        rec["global_raises"] = True
        assert _warm(query="Nichtsda") == "Keine Themenseiten gefunden"


# ══════════════════════════════════════════════════════════════════════════
# _resolve_m16_topic_page_view  (R6-wired 2026-07-24)
# Only when winner_id=="M16": find the best topic page → build swimlane boxes;
# otherwise inputs come back unchanged. NEU deviations vs ALT: winner → winner_id
# (str), tracer dropped. Boundaries: call_mcp_tool (top-import → THIS module),
# parse_wlo_cards/parse_topic_page_swimlanes (lazy → source module); the schemas
# TopicPageView/SwimlaneBox/WloCard are built for real. classification is a fake.
# ══════════════════════════════════════════════════════════════════════════

class _Cls:
    def __init__(self, entities):
        self.entities = entities


@pytest.fixture
def m16(monkeypatch):
    # ``call_mcp_tool`` is a top-import on topic_pages → patch it there; the
    # parse-Fns stay lazy → patch at the source module (boerdi.services.mcp.parsers).
    import boerdi.services.topic_pages as topic_pages
    rec = {
        "candidates": [{"node_id": "c1", "title": "Klimawandel",
                        "topic_page_url": "http://tp/1"}],
        "swimlanes": {"swimlanes": [{"heading": "Videos", "type": "video",
                                     "cards": [{"node_id": "v1", "title": "Klima-Video"}]}],
                      "variant_title": "Klimawandel TP", "topic_page_url": "http://tp/1"},
        "mcp_raises": False,
        "calls": [],
    }

    async def _call(tool, args):
        rec["calls"].append(tool)
        if rec["mcp_raises"]:
            raise RuntimeError("mcp boom")
        return tool                       # raw text irrelevant — parse-Fns are mocked

    monkeypatch.setattr(topic_pages, "call_mcp_tool", _call)
    monkeypatch.setattr("boerdi.services.mcp.parsers.parse_wlo_cards",
                        lambda raw: list(rec["candidates"]))
    monkeypatch.setattr("boerdi.services.mcp.parsers.parse_topic_page_swimlanes",
                        lambda raw: rec["swimlanes"])
    return rec


def _run_m16(winner_id, entities=None, cards=None, final_text="ORIG"):
    req = ChatRequest(session_id="s", message="zeig themenseite")
    return asyncio.run(_resolve_m16_topic_page_view(
        req, _Cls(entities or {}), winner_id, "",
        cards if cards is not None else ["ORIG_CARD"], final_text,
    ))


def _run_m16_pc(winner_id, page_context, entities=None):
    """Like _run_m16, but with a page_context in the environment (T19 shortcut)."""
    req = ChatRequest(session_id="s", message="zeig themenseite",
                      environment=Environment(page_context=page_context))
    return asyncio.run(_resolve_m16_topic_page_view(
        req, _Cls(entities or {}), winner_id, "",
        ["ORIG_CARD"], "ORIG",
    ))


class TestResolveM16TopicPageView:
    def test_non_m16_returns_inputs_unchanged(self, m16):
        view, cards, text = _run_m16("M09", cards=["ORIG_CARD"], final_text="ORIG")
        assert view is None
        assert cards == ["ORIG_CARD"]
        assert text == "ORIG"
        assert m16["calls"] == []                # no MCP call for non-M16

    def test_m16_success_builds_topic_page_view(self, m16):
        view, cards, text = _run_m16("M16", entities={"thema": "Klimawandel"})
        assert view is not None
        assert view.variant_title == "Klimawandel"   # candidate title preferred
        assert len(view.swimlanes) == 1
        assert view.swimlanes[0].heading == "Videos"
        assert view.swimlanes[0].cards[0].node_id == "v1"
        assert cards == []                            # normal boxes suppressed
        assert "Auszug der Inhalte der Themenseite" in text

    def test_m16_no_swimlanes_sets_label_fallback_text(self, m16):
        m16["swimlanes"] = {"swimlanes": []}         # no displayable boxes
        view, cards, text = _run_m16("M16", entities={"thema": "TestBenedikt"})
        assert view is None
        assert cards == []
        assert "TestBenedikt" in text
        assert "keine anzeigbaren" in text

    def test_m16_mcp_exception_sets_fallback_text(self, m16):
        m16["mcp_raises"] = True
        view, cards, text = _run_m16("M16", entities={"thema": "Klima"})
        assert view is None
        assert cards == []
        assert "keine anzeigbaren" in text

    # ── T19: page-context shortcut (known collectionId → no search) ──
    def test_m16_known_collection_id_skips_search(self, m16):
        view, cards, text = _run_m16_pc(
            "M16", {"page_kind": "topic", "collection_id": "C-known"},
            entities={"thema": "Klimawandel"},
        )
        assert view is not None
        assert "search_wlo_collections" not in m16["calls"]   # NO collection search
        assert m16["calls"] == ["get_topic_page_content"]      # straight to content

    def test_m16_without_collection_id_uses_search(self, m16):
        _view, _cards, _text = _run_m16_pc("M16", {}, entities={"thema": "Klimawandel"})
        assert m16["calls"][0] == "search_wlo_collections"     # regression: search path

    def test_m16_collection_kind_not_topic_still_searches(self, m16):
        # collection_id present, but page_kind != topic → no shortcut.
        _view, _cards, _text = _run_m16_pc(
            "M16", {"page_kind": "collection", "collection_id": "C-x"},
            entities={"thema": "Klimawandel"},
        )
        assert m16["calls"][0] == "search_wlo_collections"
