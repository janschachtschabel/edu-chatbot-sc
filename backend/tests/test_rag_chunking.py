"""Behavior pins for domain/rag_chunking (verbatim port of ALT rag_service.py
chunk_markdown + _merge_sections + _split_by_sentences). Every expected value is
locked against the ALT functions (executed in isolation). Pure, offline, deterministic.
"""

from __future__ import annotations

from boerdi.domain.rag_chunking import (
    _merge_sections,
    _split_by_sentences,
    chunk_markdown,
)


# ── chunk_markdown: the 3-strategy dispatcher ────────────────────────────
def test_single_short_text_returns_one_chunk():
    # No headings, one paragraph, one sentence -> Strategy 3 returns it whole.
    assert chunk_markdown("Just one short line.") == ["Just one short line."]


def test_paragraph_strategy_splits_on_blank_lines():
    # No headings, 2 paragraphs, small cap -> Strategy 2 (paragraph split).
    assert chunk_markdown("Para one text.\n\nPara two text.", 15) == [
        "Para one text.",
        "Para two text.",
    ]


def test_heading_strategy_splits_on_headings():
    # Two H1/H2 headings, small cap -> Strategy 1 (heading split).
    assert chunk_markdown("# Alpha Alpha\n\n## Beta Beta", 15) == [
        "# Alpha Alpha",
        "## Beta Beta",
    ]


def test_heading_strategy_preserves_every_section_title():
    out = chunk_markdown(
        "# H1 title\n\nlong body aaa\n\n# H2 title\n\nlong body bbb", 18
    )
    assert out == ["# H1 title\n\nlong body aaa", "# H2 title\n\nlong body bbb"]


# ── _merge_sections: pack small, split oversized ─────────────────────────
def test_merge_packs_small_sections_together():
    assert _merge_sections(["aa", "bb"], 1000) == ["aa\n\nbb"]


def test_merge_keeps_single_fitting_section():
    assert _merge_sections(["only"], 5) == ["only"]


def test_merge_splits_oversized_section_by_sentences():
    # One section longer than the cap -> post-process sentence-splits it.
    assert _merge_sections(
        ["Sentence one. Sentence two. Sentence three."], 20
    ) == ["Sentence one.", "Sentence two.", "Sentence three."]


# ── _split_by_sentences: sentence boundaries + overlap ───────────────────
def test_sentence_split_carries_overlap_prefix():
    # After emitting chunk 1, the last `overlap` chars are prepended to chunk 2.
    assert _split_by_sentences("First sentence. Second sentence.", 20, 5) == [
        "First sentence.",
        "ence. Second sentence.",
    ]
