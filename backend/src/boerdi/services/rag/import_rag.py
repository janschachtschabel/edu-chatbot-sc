"""Migrate ALT sqlite ``rag_chunks`` -> NEU pg (``rag_documents`` + ``rag_chunks``).

Spec §9.2 (RAG-Re-Ingest): read the ALT rows' TEXT only and re-embed via LiteLLM.
The ALT float32 embedding BLOBs are deliberately NOT carried over — NEU's embedding
model/dimension may differ, so a binary copy would land vectors the pgvector column
rejects (or silently mis-scores). Re-embedding is the price of the model swap.

Read-only on the source: the sqlite is opened ``mode=ro`` and only ever SELECTed,
so the ALT DB (a *copy* per the runbook) is never mutated. The CLI requires an
explicit ``--sqlite`` path — there is no default pointing at the real ALT DB.

ALT stored flat rows (title/source duplicated per chunk); NEU is normalised, so
chunks are regrouped into one ``rag_documents`` row per ``(area, source, title)``
with their ``chunk_index`` order preserved. The whole import runs in one
transaction: a mid-run embed failure rolls everything back, leaving no partial
migration to clean up before a re-run.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import RagChunk, RagDocument
from boerdi.services.llm import embedding

logger = logging.getLogger(__name__)


def _read_alt_chunks(sqlite_path: Path) -> list[dict]:
    """ALT ``rag_chunks`` rows (text columns only) read-only, in document order.

    The ``embedding`` BLOB is never selected — it is re-embedded downstream. Opened
    ``mode=ro`` so a mistaken path to the real ALT DB still cannot be written.
    """
    uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT area, title, source, chunk_index, content FROM rag_chunks "
            "ORDER BY area, source, title, chunk_index"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _group_into_documents(
    rows: list[dict],
) -> list[tuple[tuple[str, str, str], list[dict]]]:
    """Regroup flat ALT chunks into (``(area, source, title)``, chunks) documents.

    Insertion order is preserved (so the read's document ordering carries through),
    and within a group the chunks keep their read order (= ``chunk_index``).
    """
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        key = (r["area"], r["source"] or "", r["title"] or "")
        groups.setdefault(key, []).append(r)
    return list(groups.items())


async def import_rag_from_sqlite(session: AsyncSession, sqlite_path: Path) -> dict[str, int]:
    """Re-ingest ALT ``rag_chunks`` into pg. Returns ``{"documents", "chunks"}``.

    One ``rag_documents`` row + N re-embedded ``rag_chunks`` per group, all in a
    single transaction (see module docstring).
    """
    docs = 0
    chunks = 0
    for (area, source, title), members in _group_into_documents(_read_alt_chunks(sqlite_path)):
        doc = RagDocument(area=area, title=title, source=source)
        session.add(doc)
        await session.flush()  # assigns doc.id for the FK
        for m in members:
            emb = await embedding(m["content"])
            session.add(RagChunk(
                document_id=doc.id, area=area,
                chunk_index=m["chunk_index"], content=m["content"], embedding=emb,
            ))
        docs += 1
        chunks += len(members)
    # simplify: one transaction across all (network) embed calls — atomic and fine
    # for a one-time migration; for a very large ALT DB, batch the embeds or commit
    # per document to avoid holding a single transaction open for the whole run.
    await session.commit()
    logger.info("import-rag: %d chunks in %d documents from %s", chunks, docs, sqlite_path)
    return {"documents": docs, "chunks": chunks}
