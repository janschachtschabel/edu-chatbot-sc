"""Port der ALT-Link-Bau-Tests (`test_card_pipeline.py`) für die Card-Links (P5-4c).

Deckt `build_card_link` (topic_page/collection/content-Lookup + Lotsen-Modus),
`validate_card_link` (Allow-List) und `annotate_cards_with_link` ab.

Test-Anpassung ggü. ALT: die `validate_card_link`-Tests OHNE explizite
`allowed_hosts` fallen auf `guide_mode.host_is_allowed` → die reale guide-mode-Config
zurück. Im NEU-Test-Env (kein PG) ist die Allow-Liste leer; ALT verließ sich auf die
ambiente `guide-mode.yaml`. Für Determinismus (Eiserne Regel) wird die Allow-Liste
hier explizit via `guide_mode._cfg`-Patch gepinnt — identisch zu `test_guide_mode.py`.
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import WloCard
from boerdi.domain import guide_mode
from boerdi.domain.cards.links import (
    annotate_cards_with_link,
    build_card_link,
    validate_card_link,
)

PROD = "https://redaktion.openeduhub.net"
STAG = "https://repository.staging.openeduhub.net"

_ALLOW = {
    "allowed_hosts": ["wirlernenonline.de", "wp-test.wirlernenonline.de", "*.openeduhub.net"],
    "url_fields_priority": ["topic_page_url", "wlo_url", "url", "content_url", "preview_url"],
    "max_guide_targets_per_turn": 5,
}


@pytest.fixture
def guide_cfg(monkeypatch):
    """Pinnt die guide-mode Allow-Liste (ALT las sie aus guide-mode.yaml)."""
    monkeypatch.setattr(guide_mode, "_cfg", lambda: _ALLOW)


# ═══ build_card_link — Themenseiten ════════════════════════════════════════
class TestBuildCardLinkTopicPage:
    def test_returns_topic_page_url(self):
        card = {
            "node_id": "tp1", "node_type": "topic_page",
            "topic_page_url": "https://wirlernenonline.de/themenseite/x",
        }
        out = build_card_link(card, repo_base=PROD)
        assert out == "https://wirlernenonline.de/themenseite/x"

    def test_same_in_guide_mode(self):
        card = {
            "node_id": "tp1", "node_type": "topic_page",
            "topic_page_url": "https://wirlernenonline.de/themenseite/x",
        }
        assert (
            build_card_link(card, guide_mode=True, repo_base=PROD)
            == build_card_link(card, guide_mode=False, repo_base=PROD)
        )

    def test_fallback_to_variant_url(self):
        card = {
            "node_id": "tp1", "node_type": "topic_page",
            "topic_pages": [{"url": "https://wirlernenonline.de/variant"}],
        }
        out = build_card_link(card, repo_base=PROD)
        assert out == "https://wirlernenonline.de/variant"

    def test_fallback_to_topic_page_renderer(self):
        # Themenseite ohne explizite URL → Themenseiten-Renderer, NICHT der
        # generische Sammlungs-Browse-Link.
        card = {"node_id": "tp1", "node_type": "topic_page"}
        out = build_card_link(card, repo_base=PROD)
        assert out == f"{PROD}/edu-sharing/components/topic-pages?collectionId=tp1"


# ═══ build_card_link — Sammlungen ══════════════════════════════════════════
class TestBuildCardLinkCollection:
    def test_returns_browse_url(self):
        card = {"node_id": "c1", "node_type": "collection"}
        out = build_card_link(card, repo_base=PROD)
        assert out == f"{PROD}/edu-sharing/components/collections?id=c1"

    def test_with_search_query(self):
        card = {"node_id": "c1", "node_type": "collection"}
        out = build_card_link(card, repo_base=PROD, search_query="Eiszeit")
        assert out == f"{PROD}/edu-sharing/components/collections?id=c1&q=Eiszeit"

    def test_search_query_url_encoded(self):
        card = {"node_id": "c1", "node_type": "collection"}
        out = build_card_link(card, repo_base=PROD, search_query="Erste Welt")
        # Leerzeichen muss URL-encoded sein
        assert "Erste%20Welt" in out or "Erste+Welt" in out

    def test_same_in_guide_and_normal_mode(self):
        card = {"node_id": "c1", "node_type": "collection"}
        assert (
            build_card_link(card, guide_mode=True, repo_base=PROD)
            == build_card_link(card, guide_mode=False, repo_base=PROD)
        )

    def test_uses_target_repo_base(self):
        card = {"node_id": "c1", "node_type": "collection"}
        out = build_card_link(card, repo_base=STAG)
        assert out.startswith(STAG)


# ═══ build_card_link — Einzelinhalte ═══════════════════════════════════════
class TestBuildCardLinkContent:
    def test_normal_mode_uses_external_url(self):
        card = {
            "node_id": "v1", "node_type": "content",
            "url": "https://www.youtube.com/watch?v=x",
        }
        out = build_card_link(card, guide_mode=False, repo_base=PROD)
        assert out == "https://www.youtube.com/watch?v=x"

    def test_guide_mode_uses_repo_render(self):
        card = {
            "node_id": "v1", "node_type": "content",
            "url": "https://www.youtube.com/watch?v=x",
        }
        out = build_card_link(card, guide_mode=True, repo_base=PROD)
        assert out == f"{PROD}/edu-sharing/components/render/v1"

    def test_no_external_falls_back_to_render(self):
        card = {"node_id": "v1", "node_type": "content"}
        out = build_card_link(card, guide_mode=False, repo_base=PROD)
        assert out == f"{PROD}/edu-sharing/components/render/v1"

    def test_no_id_uses_external_url(self):
        card = {"node_type": "content", "url": "https://example.com/foo"}
        out = build_card_link(card, repo_base=PROD)
        assert out == "https://example.com/foo"


# ═══ build_card_link — defensiv ════════════════════════════════════════════
class TestBuildCardLinkDefensive:
    def test_empty_dict(self):
        assert build_card_link({}, repo_base=PROD) == ""

    def test_none(self):
        assert build_card_link(None, repo_base=PROD) == ""  # type: ignore[arg-type]

    def test_unknown_node_type_falls_back_to_content(self):
        # node_type nicht kanonisch → _infer_node_type → content (Default).
        card = {"node_id": "x", "node_type": "weird", "url": "https://example.com"}
        out = build_card_link(card, repo_base=PROD)
        assert out == "https://example.com"


# ═══ validate_card_link — Allow-List ═══════════════════════════════════════
class TestValidateCardLink:
    def test_wlo_de_allowed(self, guide_cfg):
        assert validate_card_link("https://wirlernenonline.de/themenseite/x")

    def test_repo_prod_allowed(self, guide_cfg):
        assert validate_card_link(f"{PROD}/edu-sharing/components/render/x")

    def test_repo_staging_allowed(self, guide_cfg):
        assert validate_card_link(f"{STAG}/edu-sharing/components/render/x")

    def test_youtube_not_allowed(self, guide_cfg):
        assert not validate_card_link("https://www.youtube.com/watch?v=x")

    def test_empty_rejected(self):
        assert not validate_card_link("")

    def test_none_rejected(self):
        assert not validate_card_link(None)  # type: ignore[arg-type]

    def test_invalid_scheme_rejected(self):
        assert not validate_card_link("ftp://example.com/x")

    def test_custom_allow_list(self):
        # allowed_hosts übergeben → guide-mode.yaml-Default wird ignoriert.
        out = validate_card_link(
            "https://example.com/x",
            allowed_hosts=["example.com"],
        )
        assert out

    def test_custom_allow_list_wildcard(self):
        # ``*.example.com`` matcht Subdomains, aber NICHT den Bare-Host.
        assert validate_card_link(
            "https://sub.example.com/x", allowed_hosts=["*.example.com"],
        )
        assert not validate_card_link(
            "https://example.com/x", allowed_hosts=["*.example.com"],
        )


# ═══ annotate_cards_with_link ══════════════════════════════════════════════
class TestAnnotateCardsWithLink:
    def test_link_field_set_on_each_card(self):
        cards = [
            {"node_id": "c1", "node_type": "collection"},
            {"node_id": "v1", "node_type": "content", "url": "https://x.de/y"},
        ]
        out = annotate_cards_with_link(cards, repo_base=PROD)
        assert all("link" in c for c in out)
        assert out[0]["link"].startswith(PROD)
        assert out[1]["link"] == "https://x.de/y"

    def test_require_allowed_fallback_to_render(self):
        # YouTube-URL ist nicht in der Allow-Liste → Fallback auf Repo-Render
        cards = [{
            "node_id": "v1", "node_type": "content",
            "url": "https://www.youtube.com/watch?v=x",
        }]
        out = annotate_cards_with_link(
            cards, repo_base=PROD, require_allowed=True,
        )
        assert out[0]["link"] == f"{PROD}/edu-sharing/components/render/v1"

    def test_guide_mode_propagated(self):
        # Im Guide-Modus muss der Link für Einzelinhalte auf Repo-Render zeigen
        cards = [{
            "node_id": "v1", "node_type": "content",
            "url": "https://www.youtube.com/watch?v=x",
        }]
        out = annotate_cards_with_link(
            cards, guide_mode=True, repo_base=PROD,
        )
        assert out[0]["link"].endswith("/render/v1")


def test_annotate_guide_mode_overrides_card_url_to_repo_link():
    cards = [{"node_id": "v1", "node_type": "content", "url": "https://youtube.com/x"}]
    out = annotate_cards_with_link(cards, guide_mode=True, repo_base=PROD)
    assert out[0]["link"] == f"{PROD}/edu-sharing/components/render/v1"
    assert out[0]["url"] == out[0]["link"]     # url auf Repo-Link überschrieben


# ═══ collection_link — zweites Ziel für Sammlungen MIT Themenseite ═════════
#
# Eine Sammlung mit kuratierter Themenseite trägt `node_type="topic_page"`
# (so etikettiert `_infer_node_type`) und ist damit für jede Sammlungs-Prüfung
# unsichtbar — sie erschien nie im Sammlungen-Kasten (Live-Befund „Optik",
# 15.08.2026: von vier Optik-Sammlungen fehlten genau die zwei mit
# `topicPageUrl`). Sie soll in BEIDEN Kästen stehen, je mit dem passenden
# Ziel. `link` bleibt die Themenseite, `collection_link` trägt die Sammlung.
class TestCollectionLink:
    def test_topic_page_card_gets_browse_url(self):
        cards = [{
            "node_id": "opt1", "node_type": "topic_page",
            "topic_page_url": "https://wirlernenonline.de/themenseite/optik",
        }]
        out = annotate_cards_with_link(cards, repo_base=PROD)
        assert out[0]["link"] == "https://wirlernenonline.de/themenseite/optik"
        assert out[0]["collection_link"] == (
            f"{PROD}/edu-sharing/components/collections?id=opt1"
        )

    def test_search_query_appended(self):
        cards = [{"node_id": "opt1", "node_type": "topic_page"}]
        out = annotate_cards_with_link(cards, repo_base=PROD, search_query="Optik")
        assert out[0]["collection_link"].endswith("&q=Optik")

    def test_pure_collection_stays_empty(self):
        # Reine Sammlung: `link` IST schon der Browse-Link — ein zweites Feld
        # mit demselben Wert wäre nur eine Quelle für Drift.
        cards = [{"node_id": "c1", "node_type": "collection"}]
        out = annotate_cards_with_link(cards, repo_base=PROD)
        assert out[0]["collection_link"] == ""

    def test_content_stays_empty(self):
        cards = [{"node_id": "v1", "node_type": "content", "url": "https://x.de/y"}]
        out = annotate_cards_with_link(cards, repo_base=PROD)
        assert out[0]["collection_link"] == ""

    def test_pydantic_model_path(self):
        card = WloCard(
            node_id="opt1", node_type="topic_page",
            topic_pages=[{"url": "https://wirlernenonline.de/t/optik"}],
        )
        annotate_cards_with_link([card], repo_base=PROD)
        assert card.link == "https://wirlernenonline.de/t/optik"
        assert card.collection_link == (
            f"{PROD}/edu-sharing/components/collections?id=opt1"
        )

    def test_guide_mode_unchanged(self):
        # Der Browse-Link zeigt per Konstruktion aufs eigene Repo — der
        # Lotsen-Modus hat daran nichts zu korrigieren.
        cards = [{"node_id": "opt1", "node_type": "topic_page"}]
        normal = annotate_cards_with_link(
            [dict(cards[0])], repo_base=PROD,
        )[0]["collection_link"]
        lotse = annotate_cards_with_link(
            [dict(cards[0])], guide_mode=True, repo_base=PROD,
        )[0]["collection_link"]
        assert normal == lotse == f"{PROD}/edu-sharing/components/collections?id=opt1"
