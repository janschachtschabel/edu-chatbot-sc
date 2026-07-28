"""Behavior pins for domain/search_intent._looks_like_search_query (verbatim port of
ALT chat_prefetch._looks_like_search_query). Every expected value is traced against the
ALT heuristic. Pure, offline, deterministic.
"""

from __future__ import annotations

from boerdi.domain.search_intent import _looks_like_search_query as q


def test_empty_and_none_are_false():
    assert q("") is False
    assert q(None) is False


def test_too_short_is_false():
    # < 5 chars after strip
    assert q("Math") is False
    assert q("  hi ") is False


def test_substantive_query_is_true():
    assert q("Materialien zur Photosynthese") is True


def test_exact_no_search_phrases_are_false():
    assert q("Was ist WLO?") is False
    assert q("Was ist OER?") is False
    assert q("Was ist WirLernenOnline?") is False


def test_short_meta_phrases_are_false():
    assert q("Was kannst du?") is False
    assert q("Hilfe") is False


def test_length_guard_lets_long_meta_phrase_through():
    # contains "wie kann ich" but len >= 25 → guard does not fire → True
    assert q("wie kann ich Bruchrechnung üben?") is True


def test_short_meta_phrase_under_limit_stays_false():
    assert q("wie kann ich?") is False
