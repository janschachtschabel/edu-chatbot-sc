"""domain.facets — deterministic UX hints from MCP ``_queryMeta`` (persist prereq).

Verbatim port of ALT ``chat_facets``: ``narrowing_quick_replies_from_metas`` builds
"Nur <Typ> (N)" narrowing pills from the richest facet bucket-list, and
``unresolved_filter_note`` builds an honest note when the MCP silently dropped a
filter it could not resolve. Both are pure and LLM-free.
"""

from __future__ import annotations

from boerdi.domain.facets import (
    narrowing_quick_replies_from_metas,
    unresolved_filter_note,
)

# ── narrowing_quick_replies_from_metas ───────────────────────────

def test_narrowing_builds_type_pills():
    metas = [{"facets": {"learningResourceType": [
        {"label": "Video", "count": 1203},
        {"label": "Arbeitsblatt", "count": 50},
    ]}}]
    assert narrowing_quick_replies_from_metas(metas) == [
        "Nur Video (1203)", "Nur Arbeitsblatt (50)"
    ]


def test_narrowing_empty_on_single_bucket():
    metas = [{"facets": {"learningResourceType": [{"label": "Video", "count": 5}]}}]
    assert narrowing_quick_replies_from_metas(metas) == []


def test_narrowing_empty_on_none():
    assert narrowing_quick_replies_from_metas(None) == []


def test_narrowing_sorts_desc_and_caps_max_options():
    metas = [{"facets": {"learningResourceType": [
        {"label": "A", "count": 10},
        {"label": "B", "count": 100},
        {"label": "C", "count": 50},
        {"label": "D", "count": 5},
    ]}}]
    assert narrowing_quick_replies_from_metas(metas, max_options=2) == [
        "Nur B (100)", "Nur C (50)"
    ]


def test_narrowing_filters_blank_label_and_low_count():
    metas = [{"facets": {"learningResourceType": [
        {"label": "Video", "count": 10},
        {"label": "   ", "count": 99},   # blank label → dropped
        {"label": "Quiz", "count": 0},   # count < min_count(1) → dropped
        {"label": "Audio", "count": 3},
    ]}}]
    assert narrowing_quick_replies_from_metas(metas) == [
        "Nur Video (10)", "Nur Audio (3)"
    ]


def test_narrowing_picks_richest_bucket_across_metas():
    metas = [
        {"facets": {"learningResourceType": [{"label": "Video", "count": 5}]}},
        {"facets": {"learningResourceType": [
            {"label": "Video", "count": 5}, {"label": "Audio", "count": 2},
        ]}},
    ]
    assert narrowing_quick_replies_from_metas(metas) == ["Nur Video (5)", "Nur Audio (2)"]


# ── unresolved_filter_note ───────────────────────────────────────

def test_unresolved_note_built():
    metas = [{"unresolvedFilters": [{"field": "discipline", "value": "Nonsens"}]}]
    note = unresolved_filter_note(metas)
    assert note.startswith("Hinweis:")
    assert "Nonsens" in note


def test_unresolved_note_empty_when_resolved():
    assert unresolved_filter_note([{"unresolvedFilters": []}]) == ""
    assert unresolved_filter_note(None) == ""


# ── C1-f2b6a: dieselben zwei Ausgaben auf Englisch ───────────────

def test_narrowing_pills_english():
    metas = [{"facets": {"learningResourceType": [
        {"label": "Video", "count": 1203},
        {"label": "Arbeitsblatt", "count": 50},
    ]}}]
    # Das Label kommt aus dem WLO-Vokabular und bleibt, wie WLO es liefert —
    # uebersetzt wird nur das Wort, das WIR davorsetzen.
    assert narrowing_quick_replies_from_metas(metas, lang="en") == [
        "Only Video (1203)", "Only Arbeitsblatt (50)"
    ]


def test_unresolved_note_english():
    metas = [{"unresolvedFilters": [{"field": "discipline", "value": "Nonsens"}]}]
    note = unresolved_filter_note(metas, lang="en")
    assert note == ('Note: I could not filter by “Nonsens” and searched '
                    'more broadly instead.')


def test_unresolved_note_dedups_and_caps():
    metas = [
        {"unresolvedFilters": [{"field": "d", "value": "X"}, {"field": "d", "value": "Y"}]},
        {"unresolvedFilters": [{"field": "d", "value": "X"}, {"field": "d", "value": "Z"}]},
    ]
    note = unresolved_filter_note(metas, max_shown=2)
    assert "X" in note and "Y" in note  # first two distinct values
    assert "Z" not in note  # capped at max_shown=2
