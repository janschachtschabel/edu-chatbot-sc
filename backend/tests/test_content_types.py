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
