"""Port der ALT-Normalisierungs-Tests (`test_card_pipeline.py`) für die pure
Card-Normalisierung (P5-4a).

Deckt `infer_intent_kind` + `normalize_cards` (node_type-Inferenz, Dedup, Sort,
Host-Rewrite, wlo_url-Repair) ab. Die ALT-Tests für Link-Bau
(`build_card_link`/`annotate_cards_with_link`, guide_mode) und Selektion
(`select_final_cards`) gehören zu späteren Cards-Sub-Slices und sind hier NICHT
enthalten. Die Config-Helfer-Tests (`rewrite_repo_host_v2`/`load_card_pipeline_config`/
`card_pipeline_v2_enabled`) liegen bereits in `test_config_loader_surface.py` (P2).
"""

from __future__ import annotations

from boerdi.domain.cards.normalize import infer_intent_kind, normalize_cards

PROD = "https://redaktion.openeduhub.net"
STAG = "https://repository.staging.openeduhub.net"


# ═══ infer_intent_kind ═════════════════════════════════════════════════════
class TestInferIntentKind:
    def test_general_default(self):
        assert infer_intent_kind(user_message="Material zu Photosynthese") == "general"

    def test_type_focus_when_wanted_types(self):
        out = infer_intent_kind(
            user_message="Videos zu Photosynthese",
            wanted_content_types={"video"},
        )
        assert out == "type-focus"

    def test_collection_contents_wins_over_types(self):
        out = infer_intent_kind(
            user_message="Was steht in der Sammlung?",
            wanted_content_types={"video"},
            collection_id="abc-uuid",
        )
        assert out == "collection-contents"

    def test_empty_message_returns_general(self):
        assert infer_intent_kind(user_message="") == "general"


# ═══ normalize_cards — node_type-Inferenz ══════════════════════════════════
class TestNormalizeCardsNodeType:
    def test_topic_page_with_pages(self):
        cards = [{
            "node_id": "tp1", "node_type": "collection",
            "topic_pages": [{"url": "https://wirlernenonline.de/x"}],
        }]
        out = normalize_cards(cards)
        assert out[0]["node_type"] == "topic_page"

    def test_pure_collection(self):
        cards = [{"node_id": "c1", "node_type": "collection", "topic_pages": []}]
        out = normalize_cards(cards)
        assert out[0]["node_type"] == "collection"

    def test_content_default(self):
        cards = [{"node_id": "v1", "node_type": "content"}]
        out = normalize_cards(cards)
        assert out[0]["node_type"] == "content"

    def test_empty_card_defaults_to_content(self):
        out = normalize_cards([{"node_id": "x"}])
        assert out[0]["node_type"] == "content"


# ═══ normalize_cards — Dedup + Sort ════════════════════════════════════════
class TestNormalizeCardsDedupAndSort:
    def test_dedup_by_node_id(self):
        cards = [
            {"node_id": "A", "node_type": "content", "title": "First"},
            {"node_id": "A", "node_type": "content", "title": "Duplicate"},
            {"node_id": "B", "node_type": "content", "title": "Other"},
        ]
        out = normalize_cards(cards)
        assert len(out) == 2
        assert out[0]["title"] == "First"  # Erstes Vorkommen gewinnt

    def test_idless_cards_all_kept(self):
        cards = [
            {"node_id": "", "title": "X1", "node_type": "content"},
            {"node_id": "", "title": "X2", "node_type": "content"},
        ]
        out = normalize_cards(cards)
        assert len(out) == 2

    def test_general_sorts_topic_collection_content(self):
        cards = [
            {"node_id": "v1", "node_type": "content"},
            {"node_id": "c1", "node_type": "collection"},
            {"node_id": "tp1", "node_type": "collection",
             "topic_pages": [{"url": "x"}]},
        ]
        out = normalize_cards(cards, intent_kind="general")
        assert [c["node_type"] for c in out] == ["topic_page", "collection", "content"]

    def test_type_focus_keeps_pool_order(self):
        cards = [
            {"node_id": "v1", "node_type": "content"},
            {"node_id": "c1", "node_type": "collection"},
            {"node_id": "tp1", "node_type": "collection",
             "topic_pages": [{"url": "x"}]},
        ]
        out = normalize_cards(cards, intent_kind="type-focus")
        # Keine Resortierung — Original-Order beibehalten
        assert [c["node_id"] for c in out] == ["v1", "c1", "tp1"]


# ═══ normalize_cards — Host-Rewrite ════════════════════════════════════════
class TestNormalizeCardsHostRewrite:
    def test_production_url_rewritten_to_staging(self):
        cards = [{
            "node_id": "x", "node_type": "content",
            "wlo_url": f"{PROD}/edu-sharing/components/render/x",
            "url": f"{PROD}/foo",
        }]
        out = normalize_cards(cards, target_repo_base=STAG)
        assert out[0]["wlo_url"].startswith(STAG)
        assert out[0]["url"].startswith(STAG)

    def test_external_urls_untouched(self):
        cards = [{
            "node_id": "x", "node_type": "content",
            "url": "https://www.youtube.com/watch?v=foo",
        }]
        out = normalize_cards(cards, target_repo_base=STAG)
        assert out[0]["url"] == "https://www.youtube.com/watch?v=foo"

    def test_topic_page_variant_urls_processed(self):
        cards = [{
            "node_id": "tp", "node_type": "collection",
            "topic_pages": [
                {"url": f"{PROD}/edu-sharing/render/x", "label": "X"},
            ],
        }]
        out = normalize_cards(cards, target_repo_base=STAG)
        assert out[0]["topic_pages"][0]["url"].startswith(STAG)


# ═══ normalize_cards — wlo_url-Repair ══════════════════════════════════════
class TestNormalizeWloUrlRepair:
    def test_collection_render_url_repaired_to_browse(self):
        cards = [{"node_id": "c1", "node_type": "collection",
                  "wlo_url": f"{PROD}/edu-sharing/components/render/c1"}]
        out = normalize_cards(cards, target_repo_base=PROD)
        assert out[0]["wlo_url"] == f"{PROD}/edu-sharing/components/collections?id=c1"

    def test_content_browse_url_repaired_to_render(self):
        cards = [{"node_id": "v1", "node_type": "content",
                  "wlo_url": f"{PROD}/edu-sharing/components/collections?id=v1"}]
        out = normalize_cards(cards, target_repo_base=PROD)
        assert out[0]["wlo_url"] == f"{PROD}/edu-sharing/components/render/v1"
