"""R6: Charakterisierungs-Tests für services/page_context — Port von ALT
tests/test_page_context_service.py (verbatim; nur Imports + MCP-Patch-Ziel
angepasst). Reine sync-Funktionen: JSON-Parsing, Cache-Frische, Kontext-
Signatur und die Prompt-Block-Renderer (``render_raw_for_prompt`` /
``render_for_prompt``) plus der async Netz-Resolver (``resolve_page_context``,
MCP an der Boundary gefakt — NEU-Konvention: ``setattr(module, 'call_mcp_tool')``).
"""

from __future__ import annotations

import asyncio
import json
import time

from boerdi.services import page_context as p


# ── _safe_json ──────────────────────────────────────────────────────────
def test_safe_json_valid_and_invalid():
    assert p._safe_json('{"a": 1}') == {"a": 1}
    assert p._safe_json("[1, 2]") == [1, 2]
    assert p._safe_json("kein json") is None
    assert p._safe_json("") is None


# ── Cache-Logik ─────────────────────────────────────────────────────────
def test_get_cached_empty_state_is_none():
    assert p.get_cached({}) is None


def test_cached_is_fresh_empty_state_is_false():
    assert p._cached_is_fresh({}, "irgendeine-signatur") is False


def test_context_signature_is_deterministic():
    pc = {"title": "Bruchrechnen", "url": "https://wlo.de/x"}
    assert p._current_context_signature(pc) == p._current_context_signature(pc)


# ── render_raw_for_prompt (Heuristik-Block) ─────────────────────────────
def test_render_raw_none_and_empty_return_empty():
    assert p.render_raw_for_prompt(None) == ""
    assert p.render_raw_for_prompt({}) == ""            # kein page_text
    assert p.render_raw_for_prompt({"page_text": "   "}) == ""   # nur Whitespace


def test_render_raw_with_page_text_builds_block():
    out = p.render_raw_for_prompt({
        "page_text": "Bruchrechnen üben mit Arbeitsblättern.",
        "page_kind": "topic",
        "detection_source": "dom",
    })
    assert out.startswith("## Inhalt der aktuellen Seite (Heuristik)")
    assert "Seitentyp: Themenseite" in out          # page_kind='topic' → Label
    assert "Bruchrechnen üben" in out               # Seitentext enthalten
    assert "Erkennungs-Quelle: dom" in out


def test_render_for_prompt_none_returns_empty():
    assert p.render_for_prompt(None) == ""


# ── Ausbau 2026-07-05: Wert-Asserts + async resolve_page_context ───────────
def _state_with(meta):
    return {"entities": {"_page_metadata": meta}}


def test_signature_exact_join():
    assert p._current_context_signature({"node_id": "a", "collection_id": "b"}) == "a|b||"
    assert p._current_context_signature({}) == "|||"


def test_get_cached_requires_title():
    assert p.get_cached({"entities": {"_page_metadata": {"title": "T"}}})["title"] == "T"
    assert p.get_cached({"entities": {"_page_metadata": {"title": ""}}}) is None


def test_cached_fresh_true_for_recent_matching():
    st = _state_with({"_signature": "sig", "_resolved_at": time.time(), "unresolved": False})
    assert p._cached_is_fresh(st, "sig") is True


def test_cached_fresh_false_for_wrong_signature():
    st = _state_with({"_signature": "other", "_resolved_at": time.time()})
    assert p._cached_is_fresh(st, "sig") is False


def test_cached_fresh_false_when_stale():
    st = _state_with(
        {"_signature": "sig", "_resolved_at": time.time() - 10_000, "unresolved": False}
    )
    assert p._cached_is_fresh(st, "sig") is False


def test_cached_fresh_unresolved_uses_short_ttl():
    fresh = _state_with(
        {"_signature": "sig", "_resolved_at": time.time() - 100, "unresolved": True}
    )
    stale = _state_with(
        {"_signature": "sig", "_resolved_at": time.time() - 200, "unresolved": True}
    )
    assert p._cached_is_fresh(fresh, "sig") is True
    assert p._cached_is_fresh(stale, "sig") is False


def test_extract_empty_returns_blank():
    out = p._extract_node_fields("")
    assert out["title"] == "" and out["disciplines"] == []


def test_extract_mcp_v2_json():
    raw = json.dumps({
        "nodeId": "abc", "title": "Bruchrechnung", "description": "Ein Kurs",
        "keywords": ["Brüche"], "disciplines": ["Mathematik"],
        "educationalContexts": ["Sekundarstufe I"], "learningResourceTypes": ["Video"],
        "url": "https://x/render",
    })
    out = p._extract_node_fields(raw)
    assert out["title"] == "Bruchrechnung"
    assert out["disciplines"] == ["Mathematik"]
    assert out["educational_contexts"] == ["Sekundarstufe I"]
    assert out["learning_resource_types"] == ["Video"]
    assert out["url"] == "https://x/render"


def test_extract_legacy_ccm_json():
    raw = json.dumps({"properties": {
        "cm:title": ["Titel X"],
        "ccm:taxonid_DISPLAYNAME": ["Mathematik"],
        "cclom:general_keyword": ["k1", "k2"],
    }})
    out = p._extract_node_fields(raw)
    assert out["title"] == "Titel X"
    assert out["disciplines"] == ["Mathematik"]
    assert out["keywords"] == ["k1", "k2"]


def test_extract_markdown_key_value():
    raw = "Titel: Photosynthese\nBeschreibung: Wie Pflanzen wachsen\nFächer: Biologie, Chemie\nURL: https://x"
    out = p._extract_node_fields(raw)
    assert out["title"] == "Photosynthese"
    assert out["description"] == "Wie Pflanzen wachsen"
    assert out["disciplines"] == ["Biologie", "Chemie"]
    assert out["url"] == "https://x"


def test_render_empty_when_no_title():
    assert p.render_for_prompt({"title": ""}) == ""


def test_render_collection_page_with_ids_and_filter():
    meta = {
        "title": "Bruchrechnung", "description": "desc", "disciplines": ["Mathe"],
        "educational_contexts": ["Sek I"], "keywords": ["k"], "learning_resource_types": ["Video"],
        "url": "https://x",
    }
    pc = {"page_kind": "collection", "collection_id": "C1", "search_query": "brüche"}
    out = p.render_for_prompt(meta, pc)
    assert "Sammlung (edu-sharing)" in out
    assert "Titel: Bruchrechnung" in out
    assert "Fächer: Mathe" in out
    assert "Sammlungs-ID (collection_id): C1" in out
    assert "get_collection_contents" in out
    assert "brüche" in out


def test_render_unresolved_adds_hint_and_truncates_desc():
    meta = {"title": "T", "description": "D" * 500, "unresolved": True}
    out = p.render_for_prompt(meta)
    assert "Aktuelle Seite" in out
    assert "nicht geladen" in out          # Unresolved-Hinweis
    assert "…" in out                      # Beschreibung gekürzt


def test_render_raw_includes_fields_and_snippet():
    pc = {
        "page_text": "Sichtbarer Seiteninhalt zum Thema Wasserkreislauf.",
        "page_kind": "topic", "topic_page_slug": "wasser",
        "search_query": "kreislauf", "detection_source": "dom",
    }
    out = p.render_raw_for_prompt(pc)
    assert "Themenseite-Slug: wasser" in out
    assert "Aktiver Suchbegriff: kreislauf" in out
    assert "Wasserkreislauf" in out


def test_render_raw_truncates_long_text():
    out = p.render_raw_for_prompt({"page_text": "x" * 2000})
    assert "…" in out
    assert "x" * 2000 not in out


def _patch_mcp(monkeypatch, fn):
    monkeypatch.setattr(p, "call_mcp_tool", fn)


def test_resolve_empty_context_returns_none():
    assert asyncio.run(p.resolve_page_context({}, {})) is None
    assert asyncio.run(p.resolve_page_context(None, {})) is None


def test_resolve_no_signature_uses_document_title():
    state = {}
    meta = asyncio.run(p.resolve_page_context({"document_title": "Nur Titel"}, state))
    assert meta["source"] == "document_title_only"
    assert meta["title"] == "Nur Titel"
    assert meta["unresolved"] is True
    assert state["entities"]["_page_metadata"]["title"] == "Nur Titel"


def test_resolve_no_signature_no_title_returns_none():
    assert asyncio.run(p.resolve_page_context({"search_query": "x"}, {})) is None


def test_resolve_node_id_path_success(monkeypatch):
    async def fake_call(tool, args):
        assert tool == "get_node_details"
        return json.dumps({
            "nodeId": args["nodeId"], "title": "Bruchrechnung",
            "disciplines": ["Mathematik"], "educationalContexts": ["Sek I"],
        })

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context({"node_id": "abc-123"}, state))
    assert meta["title"] == "Bruchrechnung"
    assert meta["source"] == "get_node_details"
    assert meta["unresolved"] is False
    assert meta["disciplines"] == ["Mathematik"]
    assert state["entities"]["_page_metadata"]["title"] == "Bruchrechnung"


def test_resolve_mcp_error_falls_back_to_title(monkeypatch):
    async def fake_call(tool, args):
        return "MCP error: upstream down"

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "abc-123", "document_title": "Seite X"}, {}))
    assert meta["source"] == "fallback_title"
    assert meta["title"] == "Seite X"
    assert meta["unresolved"] is True


def test_resolve_returns_cached_when_fresh(monkeypatch):
    called = {"n": 0}

    async def fake_call(tool, args):
        called["n"] += 1
        return "MCP error"

    _patch_mcp(monkeypatch, fake_call)
    sig = p._current_context_signature({"node_id": "abc"})
    state = _state_with(
        {"title": "Cached", "_signature": sig, "_resolved_at": time.time(), "unresolved": False}
    )
    meta = asyncio.run(p.resolve_page_context({"node_id": "abc"}, state))
    assert meta["title"] == "Cached"
    assert called["n"] == 0  # frischer Cache → kein MCP-Call


# ── T7/T8: kompendialer Text + Volltext (2026-07-10 Seitenkontext) ─────────

def test_extract_surfaces_compendium_and_textcontent():
    raw = json.dumps({
        "nodeId": "c1", "title": "Optik", "disciplines": ["Physik"],
        "compendiumText": "Die Optik ist ein Teilgebiet der Physik.",
        "textContent": "Langer Volltext des Materials.",
    })
    out = p._extract_node_fields(raw)
    assert out["compendium_text"] == "Die Optik ist ein Teilgebiet der Physik."
    assert out["text_content"] == "Langer Volltext des Materials."


def test_extract_no_compendium_fields_are_blank():
    raw = json.dumps({"nodeId": "c1", "title": "X", "disciplines": ["Y"]})
    out = p._extract_node_fields(raw)
    assert out["compendium_text"] == ""
    assert out["text_content"] == ""


def test_resolve_content_page_requests_textcontent(monkeypatch):
    seen = {}

    async def fake_call(tool, args):
        seen["args"] = args
        return json.dumps({
            "nodeId": args["nodeId"], "title": "Material", "disciplines": [],
            "textContent": "Volltext hier", "compendiumText": "Komp",
        })

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "abc", "page_kind": "content"}, state))
    assert seen["args"].get("includeTextContent") is True
    assert meta["text_content"] == "Volltext hier"


def test_resolve_collection_page_omits_textcontent(monkeypatch):
    seen = {}

    async def fake_call(tool, args):
        seen["args"] = args
        return json.dumps({
            "nodeId": args["nodeId"], "title": "Sammlung", "disciplines": [],
            "compendiumText": "Kompendialer Text",
        })

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"collection_id": "C1", "page_kind": "collection"}, state))
    assert "includeTextContent" not in seen["args"]
    assert meta["compendium_text"] == "Kompendialer Text"


def test_render_includes_compendium_block_and_curation_hint():
    meta = {"title": "Optik", "compendium_text": "Sollinhalt der Sammlung."}
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})
    assert "Kompendium" in out
    assert "Sollinhalt der Sammlung." in out
    assert "Lücken" in out  # Kuratier-Instruktion (Soll-vs-Ist) nur bei vorhandenem Kompendium


def test_render_compendium_trims_to_budget():
    meta = {"title": "X", "compendium_text": "K" * 5000}
    out = p.render_for_prompt(meta, {"page_kind": "collection"})
    assert "…" in out
    assert "K" * 4001 not in out  # auf ~4000er-Budget gekürzt


def test_render_includes_textcontent_block_for_content():
    meta = {"title": "Material", "text_content": "Voller Text des Materials."}
    out = p.render_for_prompt(meta, {"page_kind": "content", "node_id": "N1"})
    assert "Voller Text des Materials." in out


def test_render_includes_publisher_filter_line():
    meta = {"title": "Suchergebnisse"}
    pc = {"page_kind": "search", "search_filters": {"publisher": ["Serlo"]}}
    out = p.render_for_prompt(meta, pc)
    assert "Serlo" in out


def test_render_without_compendium_or_textcontent_is_unchanged():
    meta = {"title": "T", "disciplines": ["Mathe"]}
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})
    assert "Kompendium" not in out
    assert "Volltext" not in out
