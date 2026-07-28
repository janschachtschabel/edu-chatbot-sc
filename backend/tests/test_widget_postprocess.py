"""Characterization pins for domain/widget_postprocess._apply_widget_modes_postprocess
(verbatim port of ALT chat_postprocess._apply_widget_modes_postprocess). Every value is
traced against the ALT source.

Note: with NEU's compat-echo ``_widget_modes`` (all-True) the ``not modes[...]`` disable
branches are dead at runtime, but ``modes`` is a *parameter* — so these tests still pin the
full branch behaviour (live + toggle paths) by passing modes dicts explicitly, which is
exactly what the verbatim port must preserve.
"""

from __future__ import annotations

from boerdi.domain.widget_postprocess import _apply_widget_modes_postprocess as pp

ALL_TRUE = {
    "canvas_enabled": True,
    "cards_enabled": True,
    "quick_replies_enabled": True,
    "inline_result_grouping": True,
}


# --- live paths (all-True modes) -------------------------------------------

def test_plain_passthrough():
    qrs, cards, pa, txt = pp(dict(ALL_TRUE), ["Weiter?"], [], None, "Hallo", False)
    assert (qrs, cards, pa, txt) == (["Weiter?"], [], None, "Hallo")


def test_guide_qr_extracted_to_inline_when_text_only():
    qrs, cards, pa, txt = pp(
        dict(ALL_TRUE),
        ["__guide__|Zur FAQ|https://faq.example", "Mehr?"],
        [], None, "Text", False,
    )
    assert qrs == ["Mehr?"]  # guide QR pulled out, plain QR kept
    assert txt == "Text\n\n- [Zur FAQ](https://faq.example)"
    assert cards == []


def test_malformed_guide_qr_is_kept():
    # no "|url" part → not extractable → stays a quick reply
    qrs, cards, pa, txt = pp(dict(ALL_TRUE), ["__guide__|OnlyLabel"], [], None, "T", False)
    assert qrs == ["__guide__|OnlyLabel"]
    assert txt == "T"


def test_substantive_content_strips_guide_qrs_without_appending():
    card = {"node_id": "n1", "title": "T", "url": "", "wlo_url": ""}
    qrs, cards, pa, txt = pp(
        dict(ALL_TRUE), ["__guide__|X|https://x", "Mehr?"], [card], None, "Text", False,
    )
    assert qrs == ["Mehr?"]        # guide QR dropped (cards cover the info)
    assert txt == "Text"           # NOT appended as inline link
    assert cards == [card]


# --- toggle paths (disable branches, exercised via the modes param) --------

def test_canvas_disabled_inlines_markdown_with_sentinel():
    modes = {**ALL_TRUE, "canvas_enabled": False}
    pa_in = {
        "action": "canvas_open",
        "payload": {"markdown": "# Doc\nBody", "material_type": "lernpfad", "title": "Mein Pfad"},
    }
    qrs, cards, pa, txt = pp(modes, [], [], pa_in, "Intro", False)
    assert pa is None
    assert txt == "Intro\n\n<!-- boerdi:printable-canvas|lernpfad|Mein Pfad -->\n\n# Doc\nBody"


def test_canvas_show_cards_lifts_inner_cards():
    modes = {**ALL_TRUE, "canvas_enabled": False}
    inner = {"node_id": "c1"}
    pa_in = {"action": "canvas_show_cards", "payload": {"cards": [inner]}}
    qrs, cards, pa, txt = pp(modes, [], [], pa_in, "Text", False)
    assert cards == [inner]
    assert pa is None


def test_cards_disabled_appends_inline_links_and_keeps_cards():
    modes = {**ALL_TRUE, "cards_enabled": False, "inline_result_grouping": False}
    card = {
        "node_id": "n1", "title": "Mein Video", "link": "https://x",
        "node_type": "video", "learning_resource_types": ["Video"],
    }
    qrs, cards, pa, txt = pp(modes, [], [card], None, "Text", False)
    # inline markdown link appended; cards retained (frontend gates tiles, not the array)
    assert txt.endswith("- [@@ICON:play_circle@@Mein Video](https://x)")
    assert txt.startswith("Text\n\n")
    assert cards == [card]


def test_canvas_material_skips_extra_inline_card_list():
    modes = {**ALL_TRUE, "cards_enabled": False, "inline_result_grouping": False}
    card = {"node_id": "n1", "title": "T", "link": "https://x"}
    txt_in = "Intro <!-- boerdi:printable-canvas|lernpfad|X --> Body"
    qrs, cards, pa, txt = pp(modes, ["Q"], [card], None, txt_in, False)
    assert cards == []          # cleared — material carries the references
    assert txt == txt_in        # no inline card list appended
    assert qrs == ["Q"]


def test_quick_replies_disabled_empties_them():
    modes = {**ALL_TRUE, "quick_replies_enabled": False}
    qrs, cards, pa, txt = pp(modes, ["A", "B"], [], None, "Text", False)
    assert qrs == []
