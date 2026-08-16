"""Behavior pins for domain/inline_rendering.py (whole-module verbatim port of ALT
``chat_inline_rendering.py``). Every expected value is traced against the ALT source —
these are behavior pins, not a re-derivation. Pure formatting logic, no mocks needed.
"""

from __future__ import annotations

import pytest

from boerdi.domain import inline_rendering as ir
from boerdi.i18n import BOT_TEXT, SUPPORTED

# --- _inline_doc_title_for_pattern -----------------------------------------

def test_title_m09_bold_lernpfad_header_wins():
    md = "**Lernpfad: Bruchrechnung**\n\nText"
    assert ir._inline_doc_title_for_pattern("M09", md, "Egal") == "Lernpfad: Bruchrechnung"


def test_title_m09_topic_fallback_when_no_bold():
    # Nutzer-Entscheid 2026-08-16: der Rückfall nennt NUR das Thema, ohne das
    # Wort „Lernpfad". Grund: seit ein freigegebener Skill sein eigenes Format
    # vorgeben darf, ist der Inhalt dieser Box nicht mehr zwingend ein
    # Lernpfad — live gemessen stand „Lernpfad: Optik" über einem
    # Stundenentwurf. Die ART der Box zeigt ohnehin das Symbol
    # (``inline-documents.component.ts``:37 aus ``doc.kind``); das Wort im
    # Titel war Doppelung und im Skill-Fall schlicht falsch.
    assert ir._inline_doc_title_for_pattern("M09", "# Kapitel", "Bruch") == "Bruch"


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
    # ``kind`` trägt die Art der Box (das Widget zeichnet daraus sein Symbol),
    # der Titel nur noch das Thema — siehe test_title_m09_topic_fallback_when_no_bold.
    assert docs[0]["kind"] == "lernpfad"
    assert docs[0]["title"] == "Bruch"
    assert docs[0]["content"] == "# Body-Head\nRest"
    assert docs[0]["meta"] == {"pattern": "M09"}


def test_build_doc_extra_meta_merged():
    dr = {"inline_documents": {"per_pattern": {"M11": True}}}
    docs, _ = ir._build_inline_document("M11", "# H\nB", dr, extra_meta={"src": "x"})
    assert docs[0]["kind"] == "edit"
    assert docs[0]["meta"] == {"pattern": "M11", "src": "x"}


# --- Ohne Überschrift keine Kachel (Nutzer-Befund 2026-08-16) --------------
# Gemessen: der freigegebene Skill „Stunde planen" stellte seine Rückfrage
# („Für welchen Jahrgang und welche Dauer … 45 oder 90 Minuten?"). Die Antwort
# hatte 222 Zeichen und keine Überschrift. ``_split_lead_and_body`` gibt in dem
# Fall alles als Body zurück — die Frage landete in der Material-Kachel mit dem
# Titel „Optik" und der Art ``lernpfad``, die Sprechblase blieb LEER.
#
# Die drei Kachel-Muster verlangen alle ein H1 (M09 „1-Satz-Bubble-Lead VOR dem
# H1 … dann ab H1 das Markdown", M10 dieselbe Formel je Materialtyp, M11 „der
# KOMPLETTE editierte Markdown ab H1"). Fehlt es ganz, hat das Modell kein
# Dokument geliefert, sondern Prosa — und Prosa gehört in die Blase.
#
# Der Längen-Wächter in ``turn_persist`` (``>= 200``) sollte genau das fangen
# und griff nicht: 222 > 200. Länge ist das falsche Signal, die Struktur das
# richtige.

_RUECKFRAGE = (
    "Für welchen Jahrgang und welche Dauer soll der Stundenentwurf gelten: "
    "**45 oder 90 Minuten**? Außerdem: Ist die Stunde eine **Einführung**, "
    "**Durcharbeitung**, **Übung** oder **Anwendung** innerhalb Ihrer "
    "Unterrichtsreihe?"
)


def test_build_doc_rueckfrage_ohne_ueberschrift_bleibt_in_der_blase():
    dr = {"inline_documents": {"per_pattern": {"M09": True}}}
    docs, text = ir._build_inline_document("M09", _RUECKFRAGE, dr, topic="Optik")
    assert docs == []
    assert text == _RUECKFRAGE


@pytest.mark.parametrize("pattern_id", ["M09", "M10", "M11"])
def test_build_doc_ohne_ueberschrift_keine_kachel(pattern_id):
    """Gilt für alle drei Kachel-Muster — jedes von ihnen schreibt ein H1 vor."""
    dr = {"inline_documents": {"per_pattern": {pattern_id: True}}}
    assert ir._build_inline_document(pattern_id, "Nur Fliesstext.", dr) == (
        [], "Nur Fliesstext.")


def test_build_doc_ueberschrift_mitten_im_text_zaehlt_weiter():
    """Gegenrichtung: die Überschrift muss nicht am Anfang stehen. Genau dafür
    gibt es den Lead — er steht davor und geht in die Blase."""
    dr = {"inline_documents": {"per_pattern": {"M09": True}}}
    docs, intro = ir._build_inline_document("M09", "Lead.\n\n# Kopf\nRest", dr)
    assert intro == "Lead."
    assert docs[0]["content"] == "# Kopf\nRest"


# --- C1-f2b5: dieselbe Box auf Englisch ------------------------------------
# Die deutschen Pins oben bleiben unverändert stehen — sie sind der Beleg, dass
# der deutsche Weg byte-genau derselbe geblieben ist.

def test_title_m09_english_bold_header_wins():
    md = "**Learning path: Fractions**\n\nText"
    assert ir._inline_doc_title_for_pattern("M09", md, "Egal", lang="en") == \
        "Learning path: Fractions"


def test_title_m09_english_topic_fallback_when_no_bold():
    # Der neutrale Rückfall ist sprachunabhängig — ein blosses Thema braucht
    # kein Label und damit auch keine Übersetzung.
    assert ir._inline_doc_title_for_pattern("M09", "# Chapter", "Fractions", lang="en") == \
        "Fractions"


def test_title_m10_english_material_type_bold():
    md = "**Worksheet: Photosynthesis**"
    assert ir._inline_doc_title_for_pattern("M10", md, "", lang="en") == \
        "Worksheet: Photosynthesis"


def test_title_english_pattern_default_with_topic():
    assert ir._inline_doc_title_for_pattern("M11", "plain no markers", "Algebra", lang="en") == \
        "Edited version: Algebra"


def test_title_english_unknown_pattern_no_topic():
    assert ir._inline_doc_title_for_pattern("XX", "plain no markers", "", lang="en") == "Content"


def test_strip_english_generic_only_line_dropped():
    assert ir._strip_generic_lead_lines("Here is your material", lang="en") == ""


def test_strip_english_generic_but_substantive_kept():
    # Dieselbe Schutzregel wie auf Deutsch: ein Inhalts-Marker rettet die Zeile.
    line = "Here is your material *Topic*"
    assert ir._strip_generic_lead_lines(line, lang="en") == line


def test_strip_english_non_generic_kept():
    line = "I created a quiz for you"
    assert ir._strip_generic_lead_lines(line, lang="en") == line


def test_strip_german_phrase_still_dropped_in_english_mode():
    # Die englische Liste enthält die deutschen Floskeln mit (Vereinigung, wie
    # in C1-f2b4): eine deutsche Zeile in einer englischen Antwort ist eine
    # Floskel und soll fliegen, nicht überleben.
    assert ir._strip_generic_lead_lines("Hier ist dein Material", lang="en") == ""


def test_build_doc_english_end_to_end():
    dr = {"inline_documents": {"per_pattern": {"M09": True}}}
    docs, intro = ir._build_inline_document(
        "M09", "Lead.\n\n# Body-Head\nRest", dr, topic="Fractions", lang="en")
    assert intro == "Lead."
    assert docs[0]["title"] == "Fractions"


def test_jede_sprachtabelle_kennt_jede_unterstuetzte_sprache():
    # Der Wächter aus C1-f2b4: eine Tabelle mit nur deutschem Eintrag fällt am
    # Aufrufort still auf DEFAULT zurück — der Fehler bliebe sonst unsichtbar.
    for name in ("_LP_TITLE_WORDS", "_MATERIAL_TITLE_WORDS",
                 "_GENERIC_LEAD_PHRASES", "_SUBSTANTIVE_MARKERS"):
        table = getattr(ir, name)
        assert set(table) == set(SUPPORTED), name


def test_jeder_titel_schluessel_steht_in_beiden_katalogen():
    for key in list(ir._TITLE_LABEL_KEY.values()) + [ir._TITLE_LABEL_FALLBACK_KEY]:
        for lang in SUPPORTED:
            assert key in BOT_TEXT[lang], (lang, key)


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
