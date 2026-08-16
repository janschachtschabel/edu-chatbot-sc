"""Behaviour pins for ``domain/content_types`` (whole-module verbatim port of ALT
``chat_content_types.py``): the stateless content-type intent classifier that turns
a user message (plus accumulated entities) into the ``wanted_content_types`` set the
card pipeline already consumes, and matches cards against it.

Pure keyword/string logic — no boundaries to mock. The pins nail each function's
branches: intent detection, extraction (incl. umlaut variants + case), the 3-source
resolver (message + classification + session entities, with canonical-map and raw
fallback), and card matching over both dict and object cards.
"""

from __future__ import annotations

from boerdi.domain import content_types as ct


# ── _user_wants_specific_content_type ───────────────────────────
def test_wants_type_true_when_format_keyword_present():
    assert ct._user_wants_specific_content_type("Hast du Videos zu Mathe?") is True


def test_wants_type_false_without_format_keyword():
    assert ct._user_wants_specific_content_type("Erklär mir Bruchrechnung") is False


def test_wants_type_handles_empty_and_none():
    assert ct._user_wants_specific_content_type("") is False
    assert ct._user_wants_specific_content_type(None) is False


# ── _extract_wanted_content_types ───────────────────────────────
def test_extract_multiple_canonical_types():
    assert ct._extract_wanted_content_types(
        "Such mir Arbeitsblätter und Videos"
    ) == {"arbeitsblatt", "video"}


def test_extract_empty_without_type_focus():
    assert ct._extract_wanted_content_types("Erklär mir X") == set()


def test_extract_is_case_insensitive():
    assert ct._extract_wanted_content_types("VIDEO bitte") == {"video"}


def test_extract_maps_umlaut_variants_to_canonical():
    # "uebungen" / "übungen" both collapse to the canonical "übung".
    assert ct._extract_wanted_content_types("zeig mir uebungen") == {"übung"}
    assert ct._extract_wanted_content_types("zeig mir Übungen") == {"übung"}


# ── _resolve_wanted_content_types (3 sources) ───────────────────
def test_resolve_from_message_only():
    assert ct._resolve_wanted_content_types("nur videos zeigen") == {"video"}


def test_resolve_from_classification_medientyp_canonical():
    assert ct._resolve_wanted_content_types(
        "", classification_entities={"medientyp": "Video"}
    ) == {"video"}


def test_resolve_accumulates_from_session_entities():
    # A follow-up without a fresh medientyp still filters via prior session knowledge.
    assert ct._resolve_wanted_content_types(
        "", session_entities={"medientyp": "Arbeitsblatt"}
    ) == {"arbeitsblatt"}


def test_resolve_reads_material_typ_fallback_key():
    assert ct._resolve_wanted_content_types(
        "", classification_entities={"material_typ": "Quiz"}
    ) == {"quiz"}


def test_resolve_raw_fallback_for_unknown_type():
    # An entity value that maps to no canonical keyword is used raw (lower-cased).
    assert ct._resolve_wanted_content_types(
        "", classification_entities={"medientyp": "Hörbuch"}
    ) == {"hörbuch"}


def test_resolve_unions_message_and_entities():
    assert ct._resolve_wanted_content_types(
        "videos", classification_entities={"medientyp": "Arbeitsblatt"}
    ) == {"video", "arbeitsblatt"}


def test_resolve_ignores_non_dict_and_empty_entities():
    assert ct._resolve_wanted_content_types(
        "quiz", session_entities=None, classification_entities="notadict"
    ) == {"quiz"}
    assert ct._resolve_wanted_content_types(
        "", classification_entities={"medientyp": "  "}
    ) == set()


# ── _card_matches_wanted_types ──────────────────────────────────
def test_card_match_true_when_wanted_empty():
    assert ct._card_matches_wanted_types({"learning_resource_types": ["Video"]}, set()) is True


def test_card_match_dict_card_substring():
    assert ct._card_matches_wanted_types(
        {"learning_resource_types": ["Video"]}, {"video"}
    ) is True


def test_card_match_object_card_via_getattr():
    card = type("Card", (), {"learning_resource_types": ["Arbeitsblatt"]})()
    assert ct._card_matches_wanted_types(card, {"video"}) is False
    assert ct._card_matches_wanted_types(card, {"arbeitsblatt"}) is True


def test_card_match_false_when_card_has_no_types():
    assert ct._card_matches_wanted_types({"learning_resource_types": None}, {"video"}) is False


def test_card_match_substring_within_type_label():
    # wanted "video" matches the label "Erklärvideo" as a substring.
    assert ct._card_matches_wanted_types(
        {"learning_resource_types": ["Erklärvideo"]}, {"video"}
    ) is True


# ── C1-f2c-b: die Typ-Erkennung liest jetzt auch englische Nachrichten ──
# Vor dieser Scheibe traf nur, was in beiden Sprachen gleich heißt (video,
# quiz, audio, podcast). Alles andere fiel durch: kein Typ-Filter, keine
# Typ-Fokus-CTA, keine gefilterte Such-URL.
#
# **Der kanonische Schlüssel bleibt deutsch.** Er ist nicht nur ein Name: er
# geht als ``learningResourceType`` in die WLO-Suche (``prefetch.py:250``) und
# wird in ``_card_matches_wanted_types`` als Teilzeichenkette gegen die
# deutschen ``learning_resource_types`` der Karte gehalten. Übersetzt träfe er
# nie — dieselbe Doppelrolle wie das Typ-Label in C1-f2b3.
_EN_TYP = [
    ("find me worksheets", "arbeitsblatt"),
    ("I need exercises", "übung"),
    ("show me presentations", "präsentation"),
    ("are there learning games", "spiel"),
    ("I am looking for a tutorial", "kurs"),
    ("any infographics on this", "grafik"),
]


def test_english_type_words_resolve_to_the_german_canonical():
    for nachricht, kanonisch in _EN_TYP:
        assert kanonisch in ct._extract_wanted_content_types(nachricht), nachricht


def test_english_request_still_filters_german_cards():
    """Der Beleg, dass der Schlüssel deutsch bleiben MUSS: die Karte trägt das
    deutsche WLO-Label, die Anfrage ist englisch.

    Die leere Menge matcht ALLES — ohne die erste Zusicherung wäre dieser Test
    auch ohne die englischen Stichwörter grün, und zwar aus dem falschen Grund.
    """
    wanted = ct._extract_wanted_content_types("find me worksheets")
    assert wanted, "ohne Treffer prüft der Rest nichts"
    treffer = type("Card", (), {"learning_resource_types": ["Arbeitsblatt"]})()
    daneben = type("Card", (), {"learning_resource_types": ["Video"]})()
    assert ct._card_matches_wanted_types(treffer, wanted) is True
    assert ct._card_matches_wanted_types(daneben, wanted) is False


def test_english_type_word_marks_a_specific_type_wish():
    assert ct._user_wants_specific_content_type("do you have any worksheets?") is True
    assert ct._user_wants_specific_content_type("explain photosynthesis to me") is False


# ── „Sammlung" ist kein Inhaltstyp (Nutzer-Befund 2026-08-16) ──────────────
# Live gemessen: „Suche mir Sammlungen zum Thema Optik" → der Klassifikator
# schrieb ``medientyp='Sammlung'``, und ``response_tool_selection`` nahm
# daraufhin ``search_wlo_all``, ``search_wlo_collections`` und
# ``search_wlo_topic_pages`` aus der Werkzeugliste, „um eine Inhaltssuche zu
# erzwingen". Ergebnis: keine Sammlungskarte, keine Notiz, kein Skill-Vorrang.
#
# Die Begründung des Strips („Sammlungen lassen sich nicht nach resourceType
# filtern, also ist die Inhaltssuche der einzig richtige Weg") trägt nur,
# solange der Medientyp ein INHALT ist. Meint er die Sammlung selbst, dreht sie
# sich um: dann ist die Sammlungssuche der einzig richtige Weg.

def test_sammlung_und_themenseite_meinen_die_sammlung_selbst():
    for wort in ("Sammlung", "sammlungen", "Themenseite", " THEMENSEITEN "):
        assert ct.medientyp_meint_sammlungen(wort) is True, wort


def test_echte_inhaltstypen_meinen_die_sammlung_nicht():
    for wort in ("Video", "Arbeitsblatt", "Quiz", "", None, 42, "Sammelband"):
        assert ct.medientyp_meint_sammlungen(wort) is False, wort


def test_kein_inhaltstyp_heisst_sammlung():
    """Gegenprobe am Katalog selbst: stünde „sammlung" dort, wäre die neue
    Regel ein Widerspruch zur Filterung statt eine Ergänzung."""
    assert "sammlung" not in ct._CONTENT_TYPE_KEYWORDS


def test_sammlung_wird_kein_wunsch_typ():
    """Der Rohwort-Rueckfall in ``_resolve_wanted_content_types`` nimmt jeden
    unbekannten Medientyp als Filterwort. Bei „Sammlung" filtert der
    Karten-Filter danach gegen ``learning_resource_types`` — und dort steht es
    nie. Live gemessen 2026-08-16: „universal type-filter: 3 -> 0 cards
    (medientyp=['sammlung'])", also alle Sammlungskarten weg, obwohl die Suche
    sie gerade gefunden hatte."""
    assert ct._resolve_wanted_content_types(
        "Suche mir Sammlungen zum Thema Optik",
        classification_entities={"medientyp": "Sammlung"},
    ) == set()


def test_ein_echter_medientyp_bleibt_ein_wunsch_typ():
    """Gegenrichtung — der Filter ist fuer genau diesen Fall gebaut."""
    assert ct._resolve_wanted_content_types(
        "nur Videos", classification_entities={"medientyp": "Video"}) == {"video"}


def test_ein_unbekannter_medientyp_faellt_weiter_aufs_rohwort_zurueck():
    """Der Rueckfall bleibt: er faengt Typen, die der Katalog nicht kennt.
    Nur die Sammlung ist ausgenommen — sie ist kein Inhaltstyp."""
    assert "lehrfilmreihe" in ct._resolve_wanted_content_types(
        "", classification_entities={"medientyp": "Lehrfilmreihe"})
