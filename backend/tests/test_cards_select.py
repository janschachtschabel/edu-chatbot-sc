"""Port der ALT-Selektions/Ranking-Tests (`test_card_pipeline.py`) für die pure
Card-Selektion (P5-4b).

Deckt `select_final_cards` (Mix + LLM-Re-Rank + type-focus-Filter + Relevance-Sort)
sowie die reinen Helfer `_tokenize_query`/`_relevance_score`/`_sort_by_relevance` und
`summarize_pipeline_result` ab. Der Config-Seam `load_card_pipeline_config` läuft ECHT
(settings-Default → kein PG). Die ALT-Tests für Link-Bau/Annotate (guide_mode, 5-4c) und
die async-Orchestrierung (`fetch_card_pool`/`run_pipeline_v2`) sind hier NICHT enthalten.
"""

from __future__ import annotations

import pytest

from boerdi.domain.cards.select import (
    _relevance_score,
    _sort_by_relevance,
    _tokenize_query,
    select_final_cards,
    summarize_pipeline_result,
)


def _make_pool() -> list[dict]:
    """Standard-Test-Pool: 1 Themenseite, 3 Sammlungen, 12 Videos."""
    pool = [
        {"node_id": "TP1", "title": "TP-Math", "node_type": "topic_page",
         "topic_pages": [{"url": "x"}]},
        {"node_id": "C1", "title": "Col-1", "node_type": "collection"},
        {"node_id": "C2", "title": "Col-2", "node_type": "collection"},
        {"node_id": "C3", "title": "Col-3", "node_type": "collection"},
    ]
    for i in range(1, 13):
        pool.append({
            "node_id": f"V{i}", "title": f"Video-{i}", "node_type": "content",
            "learning_resource_types": ["Video"],
        })
    return pool


# ═══ select_final_cards ════════════════════════════════════════════════════
class TestSelectFinalCards:
    def test_general_default_mix(self):
        out = select_final_cards(
            _make_pool(), intent_kind="general", final_size=5,
        )
        types = [c["node_type"] for c in out]
        # 1 Themenseite + 1 Sammlung + 3 Einzel
        assert types == ["topic_page", "collection", "content", "content", "content"]

    def test_general_llm_selection_used(self):
        out = select_final_cards(
            _make_pool(), intent_kind="general", final_size=5,
            selected_node_ids=["C2", "V8", "V5"],
        )
        ids = [c["node_id"] for c in out]
        # LLM-picks zuerst, dann deterministischer Fill
        assert ids[:3] == ["C2", "V8", "V5"]

    def test_general_hallucinated_ids_ignored(self):
        out = select_final_cards(
            _make_pool(), intent_kind="general", final_size=5,
            selected_node_ids=["DOES-NOT-EXIST", "V1", "ALSO-FAKE"],
        )
        ids = [c["node_id"] for c in out]
        # V1 wird gefunden, der Rest deterministisch
        assert "V1" in ids
        assert "DOES-NOT-EXIST" not in ids
        assert "ALSO-FAKE" not in ids

    def test_type_focus_strict_filter(self):
        out = select_final_cards(
            _make_pool(), intent_kind="type-focus", final_size=5,
            wanted_content_types={"video"},
        )
        # Alle Treffer müssen content-Typ sein (Sammlungen + Themenseiten raus)
        assert all(c["node_type"] == "content" for c in out)
        assert len(out) == 5

    def test_type_focus_no_match_returns_empty(self):
        out = select_final_cards(
            _make_pool(), intent_kind="type-focus", final_size=5,
            wanted_content_types={"arbeitsblatt"},  # nichts im Pool
        )
        assert out == []

    def test_small_pool_returns_all(self):
        small = [
            {"node_id": "X1", "node_type": "content"},
            {"node_id": "X2", "node_type": "content"},
        ]
        out = select_final_cards(small, intent_kind="general", final_size=5)
        assert len(out) == 2

    def test_collection_contents_no_resort(self):
        # Bei collection-contents bleibt die Pool-Reihenfolge erhalten
        contents = [
            {"node_id": f"CC{i}", "node_type": "content"} for i in range(1, 8)
        ]
        out = select_final_cards(contents, intent_kind="collection-contents",
                                  final_size=5)
        assert [c["node_id"] for c in out] == ["CC1", "CC2", "CC3", "CC4", "CC5"]

    def test_empty_pool_returns_empty(self):
        out = select_final_cards([], intent_kind="general", final_size=5)
        assert out == []


# ═══ _tokenize_query ═══════════════════════════════════════════════════════
class TestTokenizeQuery:
    def test_simple(self):
        assert _tokenize_query("Bruchrechnung") == {"bruchrechnung"}

    def test_strips_stopwords(self):
        out = _tokenize_query("Material zu Bruchrechnung")
        assert out == {"bruchrechnung"}, f"got {out}"

    def test_multi_token(self):
        out = _tokenize_query("Eiszeit (Geographie)")
        assert out == {"eiszeit", "geographie"}

    def test_german_umlauts(self):
        out = _tokenize_query("Brücke über die Donau")
        assert "brücke" in out
        assert "donau" in out

    def test_drops_short_tokens(self):
        # 1-Zeichen-Tokens raus
        out = _tokenize_query("a b ab")
        assert out == {"ab"}

    def test_empty_returns_empty_set(self):
        assert _tokenize_query("") == set()
        assert _tokenize_query(None) == set()  # type: ignore[arg-type]


# ═══ _relevance_score ══════════════════════════════════════════════════════
class TestRelevanceScore:
    def test_no_tokens_returns_zero(self):
        assert _relevance_score({"title": "X"}, set()) == 0.0

    def test_title_match_strongest(self):
        s = _relevance_score(
            {"title": "Bruchrechnung Einführung"},
            {"bruchrechnung"},
        )
        assert s == 2.0

    def test_keywords_match(self):
        s = _relevance_score(
            {"title": "X", "keywords": ["Bruchrechnung", "Mathe"]},
            {"bruchrechnung"},
        )
        assert s == 1.0

    def test_combined_signals_add_up(self):
        s = _relevance_score(
            {
                "title": "Bruchrechnung",
                "keywords": ["Bruchrechnung"],
                "disciplines": ["Mathematik"],
                "description": "Eine Einführung in die Bruchrechnung.",
            },
            {"bruchrechnung", "mathematik"},
        )
        # Token "bruchrechnung": title 2.0 + keywords 1.0 + description 0.3 = 3.3
        # Token "mathematik":    disciplines 0.5
        # Summe: 3.8
        assert s == pytest.approx(3.8, abs=0.01)

    def test_no_match_returns_zero(self):
        assert _relevance_score(
            {"title": "Politische Bildung"},
            {"bruchrechnung"},
        ) == 0.0


# ═══ _sort_by_relevance ════════════════════════════════════════════════════
class TestSortByRelevance:
    def test_relevant_first(self):
        cards = [
            {"node_id": "A", "title": "Politische Bildung"},
            {"node_id": "B", "title": "Bruchrechnung Übungen"},
            {"node_id": "C", "title": "Geometrie"},
        ]
        out = _sort_by_relevance(cards, {"bruchrechnung"})
        assert out[0]["node_id"] == "B"

    def test_stable_for_ties(self):
        cards = [
            {"node_id": "A", "title": "Zero-1"},
            {"node_id": "B", "title": "Zero-2"},
        ]
        out = _sort_by_relevance(cards, {"unrelated"})
        # Beide Score 0 → MCP-Reihenfolge erhalten
        assert [c["node_id"] for c in out] == ["A", "B"]

    def test_empty_tokens_passthrough(self):
        cards = [{"node_id": "X"}, {"node_id": "Y"}]
        out = _sort_by_relevance(cards, set())
        assert [c["node_id"] for c in out] == ["X", "Y"]


# ═══ select_final_cards — Relevance ════════════════════════════════════════
class TestSelectFinalCardsRelevance:
    """Live-Bug Reproduktion: bei query="Bruchrechnung" liefert die alte v2
    "Politische Bildung" als erste Sammlung. Mit Relevance-Sort muss eine
    Bruchrechnung-Sammlung gewinnen.
    """

    def test_relevant_collection_wins(self):
        pool = [
            {"node_id": "C-pol", "node_type": "collection",
             "title": "Politische Bildung"},
            {"node_id": "C-mat", "node_type": "collection",
             "title": "Sammlung Bruchrechnung Übungen"},
            {"node_id": "V1", "node_type": "content",
             "title": "Andere Mathematik-Inhalte"},
        ]
        out = select_final_cards(
            pool, intent_kind="general", final_size=3,
            query="Material zu Bruchrechnung",
        )
        # Erste Card muss die Bruchrechnung-Sammlung sein
        assert out[0]["node_id"] == "C-mat"

    def test_type_focus_relevance_sort(self):
        pool = [
            {"node_id": "V-off", "node_type": "content",
             "title": "Andere Sache",
             "learning_resource_types": ["Video"]},
            {"node_id": "V-on", "node_type": "content",
             "title": "Photosynthese-Video",
             "learning_resource_types": ["Video"]},
        ]
        out = select_final_cards(
            pool, intent_kind="type-focus", final_size=2,
            wanted_content_types={"video"},
            query="Videos zur Photosynthese",
        )
        assert out[0]["node_id"] == "V-on"

    def test_no_query_keeps_pool_order(self):
        pool = [
            {"node_id": "C1", "node_type": "collection", "title": "Erste"},
            {"node_id": "C2", "node_type": "collection", "title": "Zweite"},
            {"node_id": "V1", "node_type": "content", "title": "Drei"},
        ]
        out = select_final_cards(pool, intent_kind="general", final_size=3)
        # Ohne Query: Mix bleibt deterministisch (1 Coll dann content)
        assert out[0]["node_id"] == "C1"

    def test_irrelevant_group_dropped_when_other_matches(self):
        """Live-Bug: bei Bruchrechnung-Query waren ALLE 7 Sammlungen
        irrelevant; aber Inhalte enthielten 4 Bruchrechnung-Matches. Die
        irrelevante Sammlung "Politische Bildung" wurde trotzdem als erste
        Card angezeigt. Fix: Score-0-Gruppen werden ganz weggelassen.
        """
        pool = [
            # 3 Sammlungen, KEINE mit "Bruchrechnung"-Match
            {"node_id": "C-pol", "node_type": "collection", "title": "Politische Bildung"},
            {"node_id": "C-bio", "node_type": "collection", "title": "Biologie-Sammlung"},
            {"node_id": "C-his", "node_type": "collection", "title": "Geschichte"},
            # 3 Inhalte, ALLE mit Match
            {"node_id": "V1", "node_type": "content", "title": "Bruchrechnung Übung 1"},
            {"node_id": "V2", "node_type": "content", "title": "Bruchrechnung Video"},
            {"node_id": "V3", "node_type": "content", "title": "Bruchrechnung Aufgabenblatt"},
        ]
        out = select_final_cards(
            pool, intent_kind="general", final_size=5,
            query="Material zu Bruchrechnung",
        )
        # Keine der irrelevanten Sammlungen darf in der Auswahl sein.
        ids = [c["node_id"] for c in out]
        assert "C-pol" not in ids
        assert "C-bio" not in ids
        assert "C-his" not in ids
        assert ids == ["V1", "V2", "V3"]

    def test_all_irrelevant_fallback_to_pool_order(self):
        """Wenn keine Card im Pool zur Query passt (vage Query, leerer
        Pool-Match), behalten wir alle Cards in MCP-Reihenfolge — sonst
        bekäme der User leere Hände."""
        pool = [
            {"node_id": "A", "node_type": "collection", "title": "Etwas"},
            {"node_id": "B", "node_type": "content", "title": "Anderes"},
            {"node_id": "C", "node_type": "content", "title": "Drittes"},
        ]
        out = select_final_cards(
            pool, intent_kind="general", final_size=5,
            query="völlig unmatching Quantenchromodynamik",
        )
        # Mix-Logik nimmt 1 Sammlung + 2 Inhalte (Reihenfolge stable)
        assert len(out) == 3
        ids = [c["node_id"] for c in out]
        assert "A" in ids and "B" in ids and "C" in ids

    def test_collection_contents_no_relevance_resort(self):
        # Bei collection-contents bleibt die kuratierte Reihenfolge — auch
        # wenn die Query nicht zu allen Titeln matcht.
        pool = [
            {"node_id": "Off1", "node_type": "content", "title": "Anderes A"},
            {"node_id": "On1", "node_type": "content", "title": "Photosynthese B"},
        ]
        out = select_final_cards(
            pool, intent_kind="collection-contents", final_size=2,
            query="Photosynthese",
        )
        # Original-Reihenfolge muss bleiben (kuratierte Sammlung)
        assert [c["node_id"] for c in out] == ["Off1", "On1"]


# ═══ summarize_pipeline_result ═════════════════════════════════════════════
class TestSummarizePipelineResult:
    def test_format_contains_counts(self):
        result = {
            "intent_kind": "general",
            "pool_size": 20,
            "normalized_size": 18,
            "final_size": 5,
            "cards": [
                {"node_type": "content", "node_id": "v1", "title": "X"},
            ],
        }
        s = summarize_pipeline_result(result)
        assert "[v2]" in s
        assert "intent=general" in s
        assert "pool=20>18>5" in s

    def test_ascii_only_no_unicode_arrows(self):
        result = {
            "intent_kind": "general",
            "pool_size": 1, "normalized_size": 1, "final_size": 1,
            "cards": [{"node_type": "content", "node_id": "x", "title": "y"}],
        }
        s = summarize_pipeline_result(result)
        # Kein Unicode-Pfeil — sonst crasht Windows-cp1252 stdout im Logger
        assert "→" not in s


def test_select_general_fills_from_collection_then_topic_when_no_content():
    pool = [
        {"node_id": "TP1", "node_type": "topic_page", "topic_pages": [{"url": "x"}]},
        {"node_id": "TP2", "node_type": "topic_page", "topic_pages": [{"url": "x"}]},
        {"node_id": "C1", "node_type": "collection"},
        {"node_id": "C2", "node_type": "collection"},
        {"node_id": "C3", "node_type": "collection"},
    ]
    out = select_final_cards(pool, intent_kind="general", final_size=5)
    # Slot1 TP1, Slot2 C1, kein content → Fill Sammlungen (C2,C3), dann Themenseite TP2
    assert [c["node_id"] for c in out] == ["TP1", "C1", "C2", "C3", "TP2"]
