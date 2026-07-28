"""Markdown chunking primitives (verbatim port of ALT ``rag_service.py``:
``chunk_markdown`` + ``_merge_sections`` + ``_split_by_sentences``).

The first P6-RAG leaf. Pure, framework-free text splitting for RAG ingestion —
no I/O, no DB, no network, only ``re`` — so it lives in ``domain/``. The three
functions are byte-for-byte ALT (no app imports → no import swaps).

Multi-strategy split: (1) at markdown headings H1-H3, (2) else at paragraph
boundaries, (3) else at sentence boundaries with overlap. ``_merge_sections``
packs small sections up to ``max_chunk`` and sentence-splits any oversized one;
``_split_by_sentences`` carries an ``overlap`` suffix into the next chunk for
context continuity.

Deliberately NOT ported here: ``embedding_to_bytes`` (a sqlite-vec ``struct.pack``
artifact — pgvector takes float arrays) and the ONNX reranker block (superseded by
``services/card_reranker`` V13). Those are enumerated NEU changes, not parity ports.
"""

from __future__ import annotations

import re


def chunk_markdown(text: str, max_chunk: int = 1000, overlap: int = 150) -> list[str]:
    """Split text into chunks using a multi-strategy approach.

    Strategy priority:
    1. Split at markdown headings (H1-H3)
    2. If that produces too few chunks, split at paragraph boundaries (double newline)
    3. Final fallback: split at sentence boundaries with overlap
    """
    # ── Strategy 1: heading-based split ─────────────────────
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    heading_sections = [s.strip() for s in sections if s.strip()]

    # If headings produce good granularity, use them
    if len(heading_sections) > 1:
        return _merge_sections(heading_sections, max_chunk)

    # ── Strategy 2: paragraph-based split ───────────────────
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if len(paragraphs) > 1:
        return _merge_sections(paragraphs, max_chunk)

    # ── Strategy 3: sentence-based split with overlap ───────
    # For texts without headings or paragraph breaks (e.g. raw PDF text)
    return _split_by_sentences(text, max_chunk, overlap)


def _merge_sections(sections: list[str], max_chunk: int) -> list[str]:
    """Merge small sections into chunks up to max_chunk size."""
    chunks: list[str] = []
    current = ""

    for section in sections:
        if not section:
            continue
        if len(current) + len(section) + 2 > max_chunk and current:
            chunks.append(current.strip())
            current = section
        else:
            current = (current + "\n\n" + section) if current else section

    if current.strip():
        chunks.append(current.strip())

    # Post-process: split any oversized chunks
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chunk:
            final.append(chunk)
        else:
            final.extend(_split_by_sentences(chunk, max_chunk, 100))

    return final if final else [sections[0][:max_chunk]]


def _split_by_sentences(text: str, max_chunk: int, overlap: int) -> list[str]:
    """Split text at sentence boundaries with overlap for context continuity."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        # Absolute fallback: hard split at max_chunk
        return [text[i:i + max_chunk] for i in range(0, len(text), max_chunk - overlap)]

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chunk and current:
            chunks.append(current.strip())
            # Overlap: keep last ~overlap chars for context continuity
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:].lstrip() + " " + sentence
            else:
                current = sentence
        else:
            current = (current + " " + sentence) if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_chunk]]
