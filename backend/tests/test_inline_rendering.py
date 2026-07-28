"""Behavior pins for domain/inline_rendering.py (whole-module verbatim port of ALT
``chat_inline_rendering.py``). Every expected value is traced against the ALT source —
these are behavior pins, not a re-derivation. Pure formatting logic, no mocks needed.
"""

from __future__ import annotations

from boerdi.domain import inline_rendering as ir

# --- _inline_doc_title_for_pattern -----------------------------------------

def test_title_m09_bold_lernpfad_header_wins():
    md = "**Lernpfad: Bruchrechnung**\n\nText"
    assert ir._inline_doc_title_for_pattern("M09", md, "Egal") == "Lernpfad: Bruchrechnung"


def test_title_m09_topic_fallback_when_no_bold():
    assert ir._inline_doc_title_for_pattern("M09", "# Kapitel", "Bruch") == "Lernpfad: Bruch"


def test_title_m10_material_type_bold():
    md = "**Arbeitsblatt: Photosynthese**"
    assert ir._inline_doc_title_for_pattern("M10", md, "") == "Arbeitsblatt: Photosynthese"


def test_title_atx_heading():
    assert ir._inline_doc_title_for_pattern("M11", "# Mein Titel\nBody", "") == "Mein Titel"


def test_title_bold_header_fallback():
    got = ir._inline_doc_title_for_pattern("M11", "**Wichtiger Hinweis**", "")
    assert got == "Wichtiger Hinweis"


def test_title_pattern_default_with_topic():
    assert ir._inline_doc_title_for_pattern("M11", "plain no markers", "Algebra") == \
        "Bearbeitete Version: Algebra"


def test_title_unknown_pattern_no_topic():
    assert ir._inline_doc_title_for_pattern("XX", "plain no markers", "") == "Inhalt"


# --- _format_inline_doc_intro ----------------------------------------------

def test_intro_with_topic_suffix():
    assert ir._format_inline_doc_intro("Hier{topic_suffix}.", "Mathe") == \
        "Hier zum Thema *Mathe*."


def test_intro_empty_topic_drops_suffix():
    assert ir._format_inline_doc_intro("Hier{topic_suffix}.", "") == "Hier."


def test_intro_unknown_placeholder_returns_template_unchanged():
    assert ir._format_inline_doc_intro("Hi {other}", "T") == "Hi {other}"


# --- _strip_generic_lead_lines ---------------------------------------------

def test_strip_empty_lead():
    assert ir._strip_generic_lead_lines("") == ""


def test_strip_generic_only_line_dropped():
    assert ir._strip_generic_lead_lines("Hier ist dein Material") == ""


def test_strip_generic_but_substantive_kept():
    # generic phrase present, but a substantive marker ("*") guards it from the drop
    assert ir._strip_generic_lead_lines("Hier ist dein Material *Thema*") == \
        "Hier ist dein Material *Thema*"


def test_strip_non_generic_kept():
    line = "Ich habe dir ein Quiz erstellt"
    assert ir._strip_generic_lead_lines(line) == line


# --- _split_lead_and_body --------------------------------------------------

def test_split_empty():
    assert ir._split_lead_and_body("") == ("", "")


def test_split_lead_before_heading():
    assert ir._split_lead_and_body("Lead-Satz.\n\n# Heading\nBody") == \
        ("Lead-Satz.", "# Heading\nBody")


def test_split_no_heading_all_body():
    assert ir._split_lead_and_body("No heading here") == ("", "No heading here")


# --- _build_inline_document ------------------------------------------------

def test_build_doc_empty_markdown():
    assert ir._build_inline_document("M09", "", {}) == ([], "")


def test_build_doc_inline_documents_disabled():
    dr = {"inline_documents": {"enabled": False}}
    assert ir._build_inline_document("M09", "# X", dr) == ([], "# X")


def test_build_doc_pattern_not_enabled():
    dr = {"inline_documents": {"per_pattern": {"M09": False}}}
    assert ir._build_inline_document("M09", "# X", dr) == ([], "# X")


def test_build_doc_template_intro_wins_over_llm_lead():
    dr = {
        "inline_documents": {
            "per_pattern": {"M10": True},
            "intro_text": {"M10": "Dein Material{topic_suffix}:"},
        }
    }
    docs, intro = ir._build_inline_document("M10", "# Arbeitsblatt\nText", dr, topic="Zellen")
    assert intro == "Dein Material zum Thema *Zellen*:"
    assert docs == [{
        "kind": "ki_material",
        "title": "Arbeitsblatt",
        "content": "# Arbeitsblatt\nText",
        "meta": {"pattern": "M10"},
    }]


def test_build_doc_llm_lead_when_no_template():
    dr = {"inline_documents": {"per_pattern": {"M09": True}}}
    docs, intro = ir._build_inline_document("M09", "Lead.\n\n# Body-Head\nRest", dr, topic="Bruch")
    assert intro == "Lead."
    assert docs[0]["kind"] == "lernpfad"
    assert docs[0]["title"] == "Lernpfad: Bruch"
    assert docs[0]["content"] == "# Body-Head\nRest"
    assert docs[0]["meta"] == {"pattern": "M09"}


def test_build_doc_extra_meta_merged():
    dr = {"inline_documents": {"per_pattern": {"M11": True}}}
    docs, _ = ir._build_inline_document("M11", "# H\nB", dr, extra_meta={"src": "x"})
    assert docs[0]["kind"] == "edit"
    assert docs[0]["meta"] == {"pattern": "M11", "src": "x"}


# --- _truncate_title -------------------------------------------------------

def test_truncate_fits():
    assert ir._truncate_title("Kurz", 10) == "Kurz"


def test_truncate_word_boundary():
    assert ir._truncate_title("Dies ist ein langer Titel hier", 15) == "Dies ist ein…"


def test_truncate_single_long_word_hard_cut():
    assert ir._truncate_title("Supercalifragilistic", 10) == "Supercalif…"


# --- _inline_card_url ------------------------------------------------------

def test_card_url_guide_mode_prefers_guide_url():
    assert ir._inline_card_url({"guide_url": "g", "wlo_url": "w"}, True) == "g"


def test_card_url_guide_mode_falls_back_when_no_guide_url():
    assert ir._inline_card_url({"wlo_url": "w"}, True) == "w"


def test_card_url_non_guide_uses_wlo_url():
    assert ir._inline_card_url({"guide_url": "g", "wlo_url": "w"}, False) == "w"


def test_card_url_fallback_chain_to_url():
    assert ir._inline_card_url({"url": "u"}, False) == "u"


def test_card_url_object_access():
    class C:
        wlo_url = "obj-w"
    assert ir._inline_card_url(C(), False) == "obj-w"


# --- _sort_cards_for_inline ------------------------------------------------

def test_sort_default_topic_coll_content():
    t = {"node_type": "topic_page"}
    cl = {"node_type": "collection"}
    ct = {"node_type": "video"}
    assert ir._sort_cards_for_inline([ct, t, cl], False) == [t, cl, ct]


def test_sort_prefer_content_first():
    t = {"node_type": "topic_page"}
    cl = {"node_type": "collection"}
    ct = {"node_type": "video"}
    assert ir._sort_cards_for_inline([t, cl, ct], True) == [ct, t, cl]


def test_sort_collection_with_topic_pages_counts_as_topic():
    coll_tp = {"node_type": "collection", "topic_pages": [1]}
    ct = {"node_type": "video"}
    assert ir._sort_cards_for_inline([ct, coll_tp], False) == [coll_tp, ct]


# --- _icon_name_for_card ---------------------------------------------------

def test_icon_topic_page():
    assert ir._icon_name_for_card({"node_type": "topic_page"}) == "topic"


def test_icon_collection_plain():
    assert ir._icon_name_for_card({"node_type": "collection"}) == "auto_stories"


def test_icon_collection_with_topic_pages():
    assert ir._icon_name_for_card({"node_type": "collection", "topic_pages": [1]}) == "topic"


def test_icon_content_video():
    assert ir._icon_name_for_card(
        {"node_type": "", "learning_resource_types": ["Video"]}) == "play_circle"


def test_icon_content_arbeitsblatt():
    assert ir._icon_name_for_card(
        {"node_type": "", "learning_resource_types": ["Arbeitsblatt"]}) == "article"


def test_icon_content_default():
    assert ir._icon_name_for_card(
        {"node_type": "", "learning_resource_types": ["Unbekannt"]}) == "menu_book"


# --- _build_inline_card_links ----------------------------------------------

def test_links_empty_cards():
    assert ir._build_inline_card_links([], False, 5, 50) == ""


def test_links_single_card_with_link_field():
    card = {"node_type": "video", "link": "http://x",
            "title": "Mein Video", "learning_resource_types": ["Video"]}
    assert ir._build_inline_card_links([card], False, 5, 50) == \
        "- [@@ICON:play_circle@@Mein Video](http://x)"


def test_links_dedup_same_url():
    # no learning_resource_types → icon falls back to menu_book (node_type "video"
    # only matters for topic_page/collection in _icon_name_for_card)
    a = {"node_type": "video", "link": "http://x", "title": "A"}
    b = {"node_type": "video", "link": "http://x", "title": "B"}
    assert ir._build_inline_card_links([a, b], False, 5, 50) == \
        "- [@@ICON:menu_book@@A](http://x)"


def test_links_limit_cap():
    cards = [{"node_type": "video", "link": f"http://x/{i}", "title": f"T{i}"} for i in range(5)]
    out = ir._build_inline_card_links(cards, False, 2, 50)
    assert len(out.splitlines()) == 2


def test_links_title_falls_back_to_url_when_missing():
    # no title and no learning_resource_types → url is the label, icon is menu_book
    card = {"node_type": "video", "link": "http://only-url"}
    assert ir._build_inline_card_links([card], False, 5, 50) == \
        "- [@@ICON:menu_book@@http://only-url](http://only-url)"
