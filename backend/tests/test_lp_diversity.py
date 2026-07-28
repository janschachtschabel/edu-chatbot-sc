"""P4-4-Tail LP-Diversity (slice): pure used-id/diversity helpers — port of ALT
``chat_cards.py``'s "Lernpfad-Diversity helper" cluster.

Characterization tests ported 1:1 from ALT ``test_chat_card_helpers.py`` (the
``_filter_unused_cards`` / ``_filter_cards_used_in_text`` / ``_get_used_lp_ids`` +
``_add_used_lp_ids`` classes — the other card helpers tested there belong to a
separate chat_cards-rendering slice and stay deferred).

All four helpers are pure (json + dict/text only) → run for real, no mocks.
"""
from __future__ import annotations

import json

from boerdi.domain.cards.lp_diversity import (
    _add_used_lp_ids,
    _filter_cards_used_in_text,
    _filter_unused_cards,
    _get_used_lp_ids,
)

# ══════════════════════════════════════════════════════════════════════════
# _filter_unused_cards
# ══════════════════════════════════════════════════════════════════════════

class TestFilterUnusedCards:
    def test_empty_used_returns_input_unchanged(self):
        cards = [{"node_id": "a"}, {"node_id": "b"}]
        out, reset = _filter_unused_cards(cards, set())
        assert out is cards  # Identität: dieselbe Liste, kein Kopieren
        assert reset is False

    def test_filters_used_ids(self):
        cards = [{"node_id": "a"}, {"node_id": "b"}]
        out, reset = _filter_unused_cards(cards, {"a"})
        assert [c["node_id"] for c in out] == ["b"]
        assert reset is False

    def test_all_used_resets_and_returns_all(self):
        cards = [{"node_id": "a"}, {"node_id": "b"}]
        out, reset = _filter_unused_cards(cards, {"a", "b"})
        assert out is cards
        assert reset is True

    def test_card_without_node_id_dropped_when_filter_active(self):
        # NOTE: pinnt IST-Verhalten — Cards ohne node_id überleben den
        # Filter NICHT (fresh verlangt truthy node_id), obwohl sie nie
        # "used" sein können.
        cards = [{"title": "ohne id"}, {"node_id": "b"}]
        out, reset = _filter_unused_cards(cards, {"a"})
        assert out == [{"node_id": "b"}]
        assert reset is False

    def test_duplicates_are_preserved(self):
        b = {"node_id": "b"}
        out, reset = _filter_unused_cards([b, b], {"a"})
        assert out == [b, b]  # keine Deduplizierung
        assert reset is False

    def test_empty_cards_with_used(self):
        out, reset = _filter_unused_cards([], {"a"})
        assert out == []
        # NOTE: pinnt IST-Verhalten — leere Liste gilt als "nichts Neues" → reset
        assert reset is True


# ══════════════════════════════════════════════════════════════════════════
# _filter_cards_used_in_text
# ══════════════════════════════════════════════════════════════════════════

class TestFilterCardsUsedInText:
    def test_empty_text_returns_input(self):
        cards = [{"node_id": "a", "url": "https://x/a"}]
        assert _filter_cards_used_in_text(cards, "") is cards

    def test_empty_cards_returns_input(self):
        assert _filter_cards_used_in_text([], "irgendein Text") == []

    def test_url_match_and_order_by_first_occurrence(self):
        c1 = {"node_id": "a", "url": "https://x/erste"}
        c2 = {"node_id": "b", "url": "https://x/zweite"}
        text = "Schritt 1: [B](https://x/zweite) — Schritt 2: [A](https://x/erste)"
        out = _filter_cards_used_in_text([c1, c2], text)
        assert [c["node_id"] for c in out] == ["b", "a"]

    def test_wlo_url_match(self):
        c = {"node_id": "a", "url": "https://ext/x", "wlo_url": "https://repo/render/a"}
        out = _filter_cards_used_in_text([c], "Siehe https://repo/render/a hier")
        assert out == [c]

    def test_node_id_match(self):
        c = {"node_id": "abc-123-uuid", "url": ""}
        out = _filter_cards_used_in_text([c], "Material abc-123-uuid ist gut")
        assert out == [c]

    def test_title_fallback_multiword_with_provider_suffix(self):
        c = {"node_id": "a", "url": "https://x/nie-im-text",
             "title": "Photosynthese einfach erklärt | Mathe by Daniel Jung"}
        d = {"node_id": "b", "url": "https://x/im-text", "title": "Anderes"}
        text = ("1. Photosynthese Einfach Erklärt anschauen. "
                "2. https://x/im-text lesen.")
        out = _filter_cards_used_in_text([c, d], text)
        # Titel-Match (case-insensitive, Suffix ' | …' abgetrennt) an Pos 3,
        # URL-Match von d weiter hinten → c vor d.
        assert [x["node_id"] for x in out] == ["a", "b"]

    def test_single_word_title_does_not_match(self):
        # Einzelwort-Titel ist als Fallback zu generisch → kein Match; da die
        # andere Card matcht, wird die Einzelwort-Card weggefiltert.
        c = {"node_id": "a", "url": "https://x/a", "title": "Photosynthese"}
        d = {"node_id": "b", "url": "https://x/b", "title": "B"}
        text = "Photosynthese ist toll, siehe https://x/b"
        out = _filter_cards_used_in_text([c, d], text)
        assert [x["node_id"] for x in out] == ["b"]

    def test_no_match_falls_back_to_original_list(self):
        cards = [{"node_id": "a", "url": "https://x/a", "title": "Kurz"}]
        out = _filter_cards_used_in_text(cards, "Text ohne jeden Link.")
        assert out is cards

    def test_dedup_by_url(self):
        c1 = {"node_id": "a", "url": "https://x/gleich"}
        c2 = {"node_id": "b", "url": "https://x/gleich"}
        out = _filter_cards_used_in_text([c1, c2], "Link: https://x/gleich")
        assert [x["node_id"] for x in out] == ["a"]

    def test_dedup_by_node_id(self):
        c1 = {"node_id": "a", "url": "https://x/1"}
        c2 = {"node_id": "a", "url": "https://x/2"}
        out = _filter_cards_used_in_text([c1, c2], "https://x/1 und https://x/2")
        assert out == [c1]


# ══════════════════════════════════════════════════════════════════════════
# _get_used_lp_ids / _add_used_lp_ids
# ══════════════════════════════════════════════════════════════════════════

class TestUsedLpIds:
    def test_get_from_empty_state(self):
        assert _get_used_lp_ids({}) == set()

    def test_get_from_state_without_key(self):
        assert _get_used_lp_ids({"entities": {}}) == set()

    def test_get_empty_string(self):
        assert _get_used_lp_ids({"entities": {"_lp_used_node_ids": ""}}) == set()

    def test_get_valid_json(self):
        state = {"entities": {"_lp_used_node_ids": '["a", "b"]'}}
        assert _get_used_lp_ids(state) == {"a", "b"}

    def test_get_invalid_json_returns_empty(self):
        state = {"entities": {"_lp_used_node_ids": "kein-json{"}}
        assert _get_used_lp_ids(state) == set()

    def test_add_creates_entities_and_filters_falsy(self):
        state = {}
        _add_used_lp_ids(state, ["a", "", "b"])
        assert _get_used_lp_ids(state) == {"a", "b"}
        # Persistiert als JSON-String in entities
        assert isinstance(state["entities"]["_lp_used_node_ids"], str)

    def test_add_accumulates(self):
        state = {"entities": {"_lp_used_node_ids": '["a"]'}}
        _add_used_lp_ids(state, ["b"])
        assert _get_used_lp_ids(state) == {"a", "b"}

    def test_add_bounds_to_100(self):
        state = {}
        ids = [f"id-{i}" for i in range(150)]
        _add_used_lp_ids(state, ids)
        stored = json.loads(state["entities"]["_lp_used_node_ids"])
        # NOTE: pinnt IST-Verhalten — Bound via list(set)[-100:], d.h. WELCHE
        # 100 überleben ist von der Set-Iterationsreihenfolge abhängig
        # (nicht deterministisch über Prozesse) — nur die Anzahl ist stabil.
        assert len(stored) == 100
        assert set(stored) <= set(ids)
