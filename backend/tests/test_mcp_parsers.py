"""Charakterisierungs-Tests für die MCP-Response-Parser (``services/mcp/parsers.py``).

Port aus ALT ``tests/test_mcp_parsers.py``. Die Parser sind reine Funktionen
(JSON/Text → Card-Dicts), ohne geteilten Zustand — nur ``config_loader`` für
Repo-URLs (env-getrieben, kein PG). Diese Tests pinnen Feld-Mapping, Envelope-
Erkennung, Placeholder-Titel und Varianten-Dedup. Anders als ALT importiert alles
direkt aus ``parsers`` (NEU-Baum hat keine ``mcp_client``-Re-Export-Fassade).
"""

from __future__ import annotations

import json

from boerdi.services.mcp.parsers import (
    _first_json_object,
    _topic_page_display_title,
    parse_search_all_cards,
    parse_topic_page_swimlanes,
    parse_total_count,
    parse_wlo_cards,
    parse_wlo_topic_page_cards,
)


# ── parse_total_count ───────────────────────────────────────────────────
def test_total_count_gesamt():
    assert parse_total_count("Gesamt: 42 Materialien") == 42


def test_total_count_ergebnisse_suffix():
    assert parse_total_count("17 Ergebnisse gefunden") == 17


def test_total_count_found():
    assert parse_total_count("Found 5 results") == 5


def test_total_count_no_match_is_zero():
    assert parse_total_count("kein Zähler hier") == 0


# ── parse_wlo_cards (v2-JSON-Envelope) ──────────────────────────────────
_V2_ENVELOPE = json.dumps({
    "total": 2, "count": 2,
    "results": [
        {"nodeId": "n-content-1", "title": "Bruchrechnen", "nodeType": "content",
         "description": "Ein Arbeitsblatt", "disciplines": ["Mathematik"]},
        {"nodeId": "n-coll-1", "title": "Sammlung Algebra", "nodeType": "collection"},
    ],
})


def test_parse_wlo_cards_maps_fields_and_types():
    cards = parse_wlo_cards(_V2_ENVELOPE)
    assert len(cards) == 2
    a, b = cards
    assert a["node_id"] == "n-content-1"
    assert a["title"] == "Bruchrechnen"
    assert a["node_type"] == "content"
    assert a["disciplines"] == ["Mathematik"]
    # content-Node → render-Permalink; collection → collections-Browse-URL
    assert "/edu-sharing/components/render/n-content-1" in a["wlo_url"]
    assert "/edu-sharing/components/collections?id=n-coll-1" in b["wlo_url"]
    assert b["node_type"] == "collection"


def test_parse_wlo_cards_non_json_returns_empty():
    assert parse_wlo_cards("das ist kein JSON") == []


def test_parse_wlo_cards_empty_returns_empty():
    assert parse_wlo_cards("") == []


def test_parse_wlo_cards_without_total_is_not_v2_envelope():
    # Ohne total/count ist es kein v2-Envelope → [] (Fallback-Signal).
    payload = json.dumps({"results": [{"nodeId": "x", "title": "T"}]})
    assert parse_wlo_cards(payload) == []


def test_parse_wlo_cards_skips_results_without_nodeid():
    payload = json.dumps({"total": 1, "results": [{"title": "ohne id"}]})
    assert parse_wlo_cards(payload) == []


# ── parse_wlo_topic_page_cards ──────────────────────────────────────────
def test_topic_page_cards_basic():
    payload = json.dumps({
        "total": 1,
        "results": [{
            "title": "Mathematik", "collectionId": "c-1",
            "topicPageUrl": "https://wlo/themenseite/c-1",
            "educationalContexts": ["Sek I"], "variants": [],
        }],
    })
    cards = parse_wlo_topic_page_cards(payload)
    assert len(cards) == 1
    assert cards[0]["title"] == "Mathematik"


def test_topic_page_cards_placeholder_title_becomes_readable():
    # PAGE_VARIANT_<uuid> ist ein Platzhalter → lesbares Label mit Bildungsstufe.
    payload = json.dumps({
        "total": 1,
        "results": [{
            "title": "PAGE_VARIANT_037c4c53-abc", "collectionId": "c-2",
            "topicPageUrl": "https://wlo/x", "educationalContexts": ["Sek II"],
            "variants": [],
        }],
    })
    cards = parse_wlo_topic_page_cards(payload)
    assert cards[0]["title"] == "Themenseite (Sek II)"


def test_topic_page_cards_non_envelope_returns_empty():
    assert parse_wlo_topic_page_cards("kein JSON") == []
    assert parse_wlo_topic_page_cards("") == []


# ── parse_search_all_cards / parse_topic_page_swimlanes: Envelope-Robustheit ─
def test_search_all_non_envelope_returns_empty_buckets():
    # Ist-Verhalten: drei leere Buckets statt Fehler.
    assert parse_search_all_cards("kein JSON") == {
        "content": [], "collections": [], "topic_pages": [],
    }


def test_swimlanes_non_envelope_returns_empty_shape():
    # Ist-Verhalten: dict mit leeren Feldern (NICHT eine Liste).
    assert parse_topic_page_swimlanes("kein JSON") == {
        "variant_title": "", "topic_page_url": "", "swimlanes": [],
    }


# ── Ausbau 2026-07-05: Happy-Paths + Helfer ────────────────────────────────
def test_total_count_total_and_treffer_prefix():
    assert parse_total_count("Total: 9") == 9
    assert parse_total_count("Treffer: 3 gefunden") == 3
    # Bare "Found 12"/"Gefunden 7" (ohne "results"-Suffix) → dritte Regex-Stufe.
    assert parse_total_count("Found 12") == 12
    assert parse_total_count("Gefunden 7") == 7


# ── _first_json_object (balancierter Extraktor) ────────────────────────────
def test_first_json_object_extracts_balanced():
    assert _first_json_object('prefix {"a": 1} suffix') == '{"a": 1}'


def test_first_json_object_ignores_braces_in_strings():
    assert _first_json_object('{"a": "}{"}') == '{"a": "}{"}'


def test_first_json_object_none_when_absent():
    assert _first_json_object("kein objekt hier") is None


# ── _topic_page_display_title (Placeholder-Erkennung) ──────────────────────
def test_display_title_clean_passthrough():
    assert _topic_page_display_title("Mathematik", "c1", ["Sek I"]) == "Mathematik"


def test_display_title_uuid_placeholder_no_ctx():
    assert _topic_page_display_title(
        "037c4c53-1234-1234-1234-123456789abc", "c1", None) == "Themenseite"


def test_display_title_equals_collection_id_with_ctx():
    assert _topic_page_display_title("c1", "c1", ["Grundschule"]) == "Themenseite (Grundschule)"


def test_display_title_variant_prefix_empty_ctx():
    assert _topic_page_display_title("variant_5", "c1", []) == "Themenseite"


# ── parse_wlo_topic_page_cards: Varianten + Dedup ──────────────────────────
def test_topic_page_cards_variants_dedup_and_clean_label():
    payload = json.dumps({
        "total": 1,
        "results": [{
            "title": "Physik", "collectionId": "c-9",
            "topicPageUrl": "https://wlo/tp/c-9", "educationalContexts": ["Sek I"],
            "variants": [
                {"variantId": "v1", "targetGroup": "teacher",
                 "targetGroupLabel": "Lehrkräfte", "topicPageUrl": "https://wlo/tp/teacher"},
                # funktional identisch → collapse
                {"variantId": "v2", "targetGroup": "teacher",
                 "targetGroupLabel": "Lehrkräfte", "topicPageUrl": "https://wlo/tp/teacher"},
                # uninformatives Label → "Themenseite"
                {"variantId": "v3", "targetGroup": "student",
                 "targetGroupLabel": "nicht gesetzt", "topicPageUrl": "https://wlo/tp/student"},
            ],
        }],
    })
    tps = parse_wlo_topic_page_cards(payload)[0]["topic_pages"]
    assert len(tps) == 2  # v1 & v2 kollabiert
    assert {tp["url"] for tp in tps} == {"https://wlo/tp/teacher", "https://wlo/tp/student"}
    student = next(tp for tp in tps if tp["target_group"] == "student")
    assert student["label"] == "Themenseite"  # "nicht gesetzt" → Fallback


# ── parse_search_all_cards: Happy-Path + Fragment-Fallback ─────────────────
def test_search_all_three_buckets():
    payload = json.dumps({
        "query": "bruch",
        "content": {"total": 1, "count": 1,
                    "results": [{"nodeId": "ct1", "title": "Content", "nodeType": "content"}]},
        "collections": {"total": 1, "count": 1,
                        "results": [{"nodeId": "co1", "title": "Coll", "nodeType": "collection"}]},
        "topicPages": {"total": 1, "count": 1,
                       "results": [{"nodeId": "tp1", "title": "TP", "nodeType": "collection"}]},
    })
    out = parse_search_all_cards(payload)
    assert [c["node_id"] for c in out["content"]] == ["ct1"]
    assert [c["node_id"] for c in out["collections"]] == ["co1"]
    assert [c["node_id"] for c in out["topic_pages"]] == ["tp1"]


def test_search_all_with_trailing_text_uses_fragment():
    env = json.dumps({
        "content": {
            "total": 1,
            "results": [{"nodeId": "x", "title": "T", "nodeType": "content"}],
        },
    })
    out = parse_search_all_cards(env + "\n\n[meta trailing text]")
    assert [c["node_id"] for c in out["content"]] == ["x"]


# ── parse_topic_page_swimlanes: Happy-Path ─────────────────────────────────
def test_swimlanes_happy_path_maps_items_to_cards():
    payload = json.dumps({
        "variantTitle": "Sek I Variante", "topicPageUrl": "https://wlo/tp", "swimlaneCount": 1,
        "swimlanes": [{
            "heading": "Videos", "type": "container", "hasMore": True,
            "items": [{"nodeId": "n1", "title": "Video 1", "nodeType": "content"}],
        }],
    })
    out = parse_topic_page_swimlanes(payload)
    assert out["variant_title"] == "Sek I Variante"
    assert out["topic_page_url"] == "https://wlo/tp"
    assert len(out["swimlanes"]) == 1
    sl = out["swimlanes"][0]
    assert (sl["heading"], sl["type"], sl["has_more"]) == ("Videos", "container", True)
    assert [c["node_id"] for c in sl["cards"]] == ["n1"]
