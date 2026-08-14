"""Characterization tests for the card-build helpers (port of the relevant
classes from ALT ``tests/test_chat_card_helpers.py``): ``_norm_words``,
``_collection_matches_topic``, ``_sort_topic_pages``, ``_build_cards``.

These pin ALT's IST behaviour 1:1 (including quirks marked ``# NOTE: pinnt
IST-Verhalten``). The other ALT classes cover functions already ported
elsewhere (``lp_diversity``, ``inline_grouping``) or outside this slice — not
duplicated here. Offline, deterministic, pure.
"""

from __future__ import annotations

from boerdi.api.schemas import WloCard
from boerdi.domain.cards.build import (
    _apply_llm_card_selection,
    _build_cards,
    _collection_matches_topic,
    _norm_words,
    _sort_topic_pages,
)

# ══════════════════════════════════════════════════════════════════════════
# _norm_words
# ══════════════════════════════════════════════════════════════════════════

class TestNormWords:
    def test_lowercases_and_splits(self):
        assert _norm_words("Eiszeit und Klimawandel") == ["eiszeit", "und", "klimawandel"]

    def test_strips_punctuation(self):
        assert _norm_words("Mathe, Physik & Chemie!") == ["mathe", "physik", "chemie"]

    def test_keeps_hyphen_inside_word(self):
        # Bindestrich steht in der Keep-Klasse der Regex → bleibt Teil des Tokens.
        assert _norm_words("Eisen-Erzeugung, Teil 2") == ["eisen-erzeugung", "teil", "2"]

    def test_keeps_umlauts_and_eszett(self):
        assert _norm_words("Grüße & Öl") == ["grüße", "öl"]

    def test_empty_string(self):
        assert _norm_words("") == []

    def test_none_input(self):
        # `if not s` fängt None ab, bevor die Regex läuft.
        assert _norm_words(None) == []

    def test_whitespace_only(self):
        assert _norm_words("   \t ") == []


# ══════════════════════════════════════════════════════════════════════════
# _collection_matches_topic
# ══════════════════════════════════════════════════════════════════════════

def _card(title: str) -> WloCard:
    return WloCard(title=title)


class TestCollectionMatchesTopic:
    def test_exact_word_match(self):
        assert _collection_matches_topic([_card("Eiszeit und Klimawandel")], "Eiszeit") is True

    def test_no_substring_false_positive(self):
        # 'Eiszeit' darf NICHT über Substring in 'Eisen…' matchen.
        assert _collection_matches_topic([_card("Eisen und Stahl")], "Eiszeit") is False

    def test_morphological_prefix_title_longer(self):
        # Titel-Token 'eiszeiten' beginnt mit key 'eiszeit' (≥5 Zeichen).
        assert _collection_matches_topic([_card("Eiszeiten in Europa")], "Eiszeit") is True

    def test_morphological_prefix_topic_longer(self):
        # key 'eiszeitalter' beginnt mit Titel-Token 'eiszeit'.
        assert _collection_matches_topic([_card("Die Eiszeit")], "Eiszeitalter") is True

    def test_multiword_topic_uses_longest_token(self):
        # key = 'pythagoras' (längstes Token ≥4) — 'Satzbau' matcht nicht.
        assert _collection_matches_topic(
            [_card("Pythagoras verstehen")], "Satz des Pythagoras"
        ) is True
        assert _collection_matches_topic(
            [_card("Satzbau im Deutschen")], "Satz des Pythagoras"
        ) is False

    def test_short_only_topic_accepts_conservatively(self):
        # NOTE: pinnt IST-Verhalten — Topic besteht nur aus Tokens < 4 Zeichen
        # ('Eis' hat 3) → Funktion gibt True zurück, OHNE die Titel überhaupt
        # anzusehen (konservatives Akzeptieren).
        assert _collection_matches_topic([_card("Völlig anderes Thema")], "Eis") is True

    def test_empty_topic_returns_false(self):
        assert _collection_matches_topic([_card("Eiszeit")], "") is False

    def test_empty_cards_returns_false(self):
        assert _collection_matches_topic([], "Eiszeit") is False

    def test_card_without_title(self):
        assert _collection_matches_topic([_card("")], "Eiszeit") is False


# ══════════════════════════════════════════════════════════════════════════
# _sort_topic_pages
# ══════════════════════════════════════════════════════════════════════════

PAGE_T = {"url": "t", "target_group": "teacher", "label": "Lehrkräfte"}
PAGE_L = {"url": "l", "target_group": "learner", "label": "Lernende"}
PAGE_G = {"url": "g", "target_group": "general", "label": "Alle"}
PAGE_U = {"url": "u", "label": "ohne target_group"}


class TestSortTopicPages:
    def test_empty_and_single_returned_as_is(self):
        assert _sort_topic_pages([], "P-LEH") == []
        single = [dict(PAGE_L)]
        assert _sort_topic_pages(single, "P-LEH") is single  # kein Kopieren

    def test_teacher_persona_rank_order(self):
        pages = [dict(PAGE_L), dict(PAGE_G), dict(PAGE_T), dict(PAGE_U)]
        out = _sort_topic_pages(pages, "P-LEH")
        assert [p["url"] for p in out] == ["t", "g", "u", "l"]

    def test_learner_persona(self):
        pages = [dict(PAGE_T), dict(PAGE_G), dict(PAGE_L)]
        out = _sort_topic_pages(pages, "P-LER")
        assert [p["url"] for p in out] == ["l", "g", "t"]

    def test_unknown_persona_prefers_general(self):
        pages = [dict(PAGE_T), dict(PAGE_G)]
        out = _sort_topic_pages(pages, "")
        assert [p["url"] for p in out] == ["g", "t"]

    def test_target_group_case_insensitive(self):
        pages = [dict(PAGE_G), {"url": "t2", "target_group": "Teacher"}]
        out = _sort_topic_pages(pages, "P-LEH")
        assert [p["url"] for p in out] == ["t2", "g"]

    def test_stable_sort_within_rank(self):
        t1 = {"url": "t1", "target_group": "teacher"}
        t2 = {"url": "t2", "target_group": "teacher"}
        out = _sort_topic_pages([t1, t2], "P-LEH")
        assert [p["url"] for p in out] == ["t1", "t2"]


# ══════════════════════════════════════════════════════════════════════════
# _build_cards
# ══════════════════════════════════════════════════════════════════════════

class TestBuildCards:
    def test_basic_mapping_and_defaults(self):
        out = _build_cards([{"node_id": "n1", "title": "T", "description": "D"}])
        assert len(out) == 1
        c = out[0]
        assert isinstance(c, WloCard)
        assert (c.node_id, c.title, c.description) == ("n1", "T", "D")
        assert c.node_type == "content"  # Default, wenn nicht gesetzt
        assert c.disciplines == [] and c.topic_pages == []

    def test_empty_input(self):
        assert _build_cards([]) == []

    def test_cards_without_node_id_are_not_deduped(self):
        out = _build_cards([{"title": "A"}, {"title": "B"}])
        assert [c.title for c in out] == ["A", "B"]

    def test_merge_same_node_id_metadata_inheritance(self):
        raw = [
            {  # Themenseiten-Karte: arm an Metadaten
                "node_id": "n1", "title": "Thema", "node_type": "topic_page",
                "topic_pages": [
                    {"variant_id": "v1", "url": "u1", "target_group": "teacher"},
                ],
            },
            {  # Sammlungs-Karte: reichere Metadaten, gleiche node_id
                "node_id": "n1", "title": "Thema", "node_type": "collection",
                "preview_url": "p.jpg", "disciplines": ["Mathematik"],
                "topic_pages": [
                    {"variant_id": "v2", "url": "u2", "target_group": "learner"},
                    {"variant_id": "v1", "url": "dup", "target_group": "teacher"},
                ],
            },
        ]
        out = _build_cards(raw, persona_id="P-LER")
        assert len(out) == 1  # dedupliziert nach node_id
        c = out[0]
        # Reichere Felder des zweiten Partners füllen Lücken des ersten:
        assert c.preview_url == "p.jpg"
        assert c.disciplines == ["Mathematik"]
        # topic_pages nach variant_id gemerged (v1-Duplikat verworfen):
        vids = sorted(tp["variant_id"] for tp in c.topic_pages)
        assert vids == ["v1", "v2"]
        # Merged Card mit topic_pages wird zwingend zur collection:
        assert c.node_type == "collection"
        # Persona P-LER → learner-Variante zuerst sortiert:
        assert c.topic_pages[0]["target_group"] == "learner"

    def test_first_occurrence_wins_position_and_scalar_fields(self):
        # NOTE: pinnt IST-Verhalten — bei Duplikaten ohne topic_pages gewinnt
        # der ERSTE Eintrag für alle bereits gesetzten Felder (auch node_type,
        # das nicht in der Gap-Fill-Liste steht).
        raw = [
            {"node_id": "n2", "node_type": "content", "title": "Erster"},
            {"node_id": "n2", "node_type": "collection", "title": "Zweiter"},
        ]
        out = _build_cards(raw)
        assert len(out) == 1
        assert out[0].title == "Erster"
        assert out[0].node_type == "content"

    def test_order_preserved_first_occurrence(self):
        raw = [
            {"node_id": "a", "title": "A"},
            {"node_id": "b", "title": "B"},
            {"node_id": "a", "title": "A-dup"},
        ]
        out = _build_cards(raw)
        assert [c.node_id for c in out] == ["a", "b"]

    # ── skill_count: die Naht Parser → WloCard (Befund 2026-08-14) ────────
    # Diese Funktion ist die EINZIGE Stelle, an der eine WloCard gebaut wird,
    # und sie zaehlt ihre Felder einzeln auf. Ein Feld, das der Parser setzt
    # und das Schema fuehrt, ist ohne diese Zeile trotzdem weg — Parser-Test
    # und Kachel-Test bleiben dabei gruen, weil beide neben der Naht liegen.

    def test_skill_count_ueberlebt_die_kartenkonstruktion(self):
        out = _build_cards([{
            "node_id": "n1", "title": "Optik",
            "node_type": "collection", "skill_count": 28,
        }])
        assert out[0].skill_count == 28

    def test_ohne_freigabeliste_bleibt_der_zaehler_null(self):
        assert _build_cards([{"node_id": "n1", "title": "T"}])[0].skill_count == 0

    def test_skill_count_wird_vom_reicheren_partner_geerbt(self):
        # Dieselbe Sammlung aus zwei Quellen: die Freigabeliste haengt am
        # Treffer der Sammlungssuche, die Themenseiten-Karte kennt sie nicht.
        # Ohne Vererbung gewinnt der Erstfund — mit 0.
        raw = [
            {"node_id": "n1", "title": "Optik", "node_type": "topic_page",
             "topic_pages": [
                 {"variant_id": "v1", "url": "u1", "target_group": "teacher"},
             ]},
            {"node_id": "n1", "title": "Optik", "node_type": "collection",
             "skill_count": 28},
        ]
        assert _build_cards(raw)[0].skill_count == 28


# ══════════════════════════════════════════════════════════════════════════
# _apply_llm_card_selection
# ══════════════════════════════════════════════════════════════════════════

class TestSammlungNachziehen:
    """Nutzer-Vorgabe 2026-08-14: „Die Optiksammlung muss gefunden werden, wenn
    der MCP diese liefern kann."

    #193 hat das strukturelle Aushungern beseitigt (harter Deckel 5) und der
    Prompt bittet um die Sammlung — eine Bitte ist aber keine Zusage. Enthielt
    der Pool eine passende Sammlung und die Modell-Auswahl keine, sah der User
    sie trotzdem nie. Diese Stufe ist deterministisch: genau EINE Sammlung wird
    nachgezogen, ans Ende, damit die Reihenfolge des Modells erhalten bleibt.
    """

    @staticmethod
    def _karte(nid: str, node_type: str = "content", **kw):
        return WloCard(node_id=nid, title=nid, node_type=node_type, **kw)

    def test_sammlung_wird_nachgezogen_wenn_die_auswahl_keine_hat(self):
        pool = [
            self._karte("v1"), self._karte("v2"),
            self._karte("optik", "collection"),
        ]
        out = _apply_llm_card_selection(pool, ["v1", "v2"])
        assert [c.node_id for c in out] == ["v1", "v2", "optik"]

    def test_die_reihenfolge_des_modells_bleibt_vorn(self):
        pool = [self._karte("optik", "collection"), self._karte("v1")]
        out = _apply_llm_card_selection(pool, ["v1"])
        assert out[0].node_id == "v1"

    def test_hat_die_auswahl_schon_eine_sammlung_aendert_sich_nichts(self):
        pool = [self._karte("s1", "collection"), self._karte("s2", "collection")]
        out = _apply_llm_card_selection(pool, ["s1"])
        assert [c.node_id for c in out] == ["s1"]

    def test_ohne_sammlung_im_pool_aendert_sich_nichts(self):
        pool = [self._karte("v1"), self._karte("v2")]
        out = _apply_llm_card_selection(pool, ["v1"])
        assert [c.node_id for c in out] == ["v1"]

    def test_eine_themenseite_zaehlt_nicht_als_sammlung(self):
        # Themenseiten haben ihre EIGENE Box; eine davon in der Auswahl belegt
        # nicht, dass die Sammlungs-Box gefuellt ist.
        tp = self._karte("thema", "collection", topic_pages=[
            {"url": "u", "target_group": "teacher", "label": "L", "variant_id": "v"},
        ])
        pool = [tp, self._karte("optik", "collection")]
        out = _apply_llm_card_selection(pool, ["thema"])
        assert [c.node_id for c in out] == ["thema", "optik"]

    def test_es_wird_hoechstens_eine_nachgezogen(self):
        pool = [self._karte("v1")] + [
            self._karte(f"s{i}", "collection") for i in range(4)
        ]
        out = _apply_llm_card_selection(pool, ["v1"])
        assert len(out) == 2

    def test_ohne_auswahl_bleibt_alles_wie_es_war(self):
        # Keine Modell-Auswahl → der Caller sortiert selbst; hier darf nichts
        # umgestellt werden.
        pool = [self._karte("v1"), self._karte("s1", "collection")]
        assert _apply_llm_card_selection(pool, []) == pool


class _ObjCard:
    """Minimal object-form card (getattr path, not dict)."""

    def __init__(self, node_id: str):
        self.node_id = node_id


class TestApplyLlmCardSelection:
    def test_none_selection_returns_copy(self):
        cards = [{"node_id": "a"}]
        out = _apply_llm_card_selection(cards, None)
        assert out == [{"node_id": "a"}]
        assert out is not cards  # neue Liste, kein Aliasing

    def test_empty_selection_returns_copy(self):
        cards = [{"node_id": "a"}, {"node_id": "b"}]
        assert _apply_llm_card_selection(cards, []) == cards
        assert _apply_llm_card_selection(cards, []) is not cards

    def test_empty_cards_with_selection(self):
        assert _apply_llm_card_selection([], ["a"]) == []

    def test_filters_and_orders_by_llm_choice(self):
        a, b, c = {"node_id": "a"}, {"node_id": "b"}, {"node_id": "c"}
        # LLM order c,a — b was deselected and drops out
        assert _apply_llm_card_selection([a, b, c], ["c", "a"]) == [c, a]

    def test_skips_nonmatching_ids(self):
        a = {"node_id": "a"}
        assert _apply_llm_card_selection([a], ["x", "a"]) == [a]

    def test_salvage_returns_unfiltered_on_zero_matches(self):
        # alle selected IDs verfehlen → lieber ungefilterte Liste als leer
        cards = [{"node_id": "a"}, {"node_id": "b"}]
        assert _apply_llm_card_selection(cards, ["x", "y"]) == cards

    def test_object_cards_via_getattr(self):
        a, b = _ObjCard("a"), _ObjCard("b")
        assert _apply_llm_card_selection([a, b], ["b"]) == [b]

    def test_card_without_node_id_is_salvaged(self):
        # kein node_id → nichts landet im Lookup → 0 Matches → Salvage
        cards = [{"title": "x"}]
        assert _apply_llm_card_selection(cards, ["a"]) == cards
