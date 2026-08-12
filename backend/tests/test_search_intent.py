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


# ── C1-f2c-b: die Meta-Frage-Ausnahme kannte nur Deutsch ─────────────
# Der Welle-C-Hotfix im Modul beschreibt, was eine durchgewischte
# Meta-Frage anrichtet: das Sicherheitsnetz startet eine MCP-Suche und
# schmuggelt Karten in eine RAG-Antwort. Genau das passierte auf
# Englisch — „what can you do?" galt als echte Suchanfrage.

def test_english_meta_questions_are_not_searches():
    assert q("what can you do?") is False
    assert q("how do i use this") is False
    assert q("who are you?") is False


def test_english_greetings_are_not_searches():
    assert q("hello there") is False
    assert q("good morning") is False


def test_hey_is_deliberately_absent_from_the_list():
    """``hey`` ist als Teilzeichenkette unbrauchbar: es steckt in ``they``,
    auch mit angehaengtem Leerzeichen (``they `` enthaelt ``hey ``). Mit dem
    Eintrag waere „why do they matter" (unter 25 Zeichen) still keine
    Suchanfrage mehr. Gemessen, nicht vermutet."""
    assert q("why do they matter") is True


def test_the_german_exceptions_are_unchanged():
    assert q("was kannst du?") is False
    assert q("hallo, wer bist du") is False


def test_a_real_english_search_still_passes():
    assert q("climate change teaching material") is True
    assert q("worksheets about photosynthesis") is True


def test_the_length_limit_still_guards_the_short_list():
    """Die kurzen Ausnahmen greifen nur unter 25 Zeichen — sonst faellt
    „Hi, kannst du mir helfen mit Mathe?" faelschlich raus. Der englische
    Spiegel erbt dieselbe Schranke."""
    assert q("hello, can you help me find worksheets on maths") is True
