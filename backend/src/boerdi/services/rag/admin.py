"""RAG administration (P6-2c): area/document listing + deletion for the Studio.

pg-**REWRITES, not ports**: ALT ran raw sqlite inside the router
(``routers/rag.py`` Z. 134-307) against a flat ``rag_chunks`` table that carried
title/source/created_at on every chunk. NEU is normalised (``rag_documents``
1:N ``rag_chunks``) and keeps DB access in the service layer (spec rule 4), so
the router stays HTTP-only. The dict shapes the router returns are ALT-identical.

ALT's ``rag_vec`` sweeps after every delete are **dropped without replacement**:
sqlite-vec kept embeddings in a separate table behind its own connection that
could not join the same transaction, so orphaned vector rows were a real risk
worth sweeping for. pgvector stores the embedding as a column ON ``rag_chunks``
— deleting the chunk deletes the vector. There is nothing left to sweep, and
nothing left to fail non-fatally.
"""

from __future__ import annotations

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import RagChunk, RagDocument


async def list_areas(session: AsyncSession) -> list[dict]:
    """All knowledge areas with chunk + document counts, area-sorted.

    ALT's dict shape ``{area, chunks, documents}``. ``documents`` counts DISTINCT
    titles — kept verbatim although it disagrees with ``get_rag_chunks``-based
    grouping, which keys on ``(title, source)``: two same-titled documents from
    different sources count as one here but list as two there. That inconsistency
    is ALT's and is not in scope to fix.
    """
    stmt = (
        select(
            RagChunk.area,
            func.count().label("count"),
            func.count(distinct(RagDocument.title)).label("docs"),
        )
        .select_from(RagChunk)
        .outerjoin(RagDocument, RagChunk.document_id == RagDocument.id)
        .group_by(RagChunk.area)
        .order_by(RagChunk.area)
    )
    rows = (await session.execute(stmt)).all()
    return [{"area": r.area, "chunks": r.count, "documents": r.docs} for r in rows]


async def delete_area(session: AsyncSession, area: str) -> None:
    """Delete every chunk of a knowledge area, and its document rows.

    ALT deleted from ``rag_chunks`` only — that was the only table it had. NEU
    must drop the ``rag_documents`` rows too, or the area's documents linger as
    empty shells. Chunks go first so rows with a NULL ``document_id`` (the FK is
    nullable) are covered as well; the document delete then cascades over the
    rest. Both in one transaction.
    """
    await session.execute(delete(RagChunk).where(RagChunk.area == area))
    await session.execute(delete(RagDocument).where(RagDocument.area == area))
    await session.commit()


async def get_document_chunks(
    session: AsyncSession, area: str, title: str, source: str
) -> list[dict]:
    """All chunks of ONE document, ordered by chunk_index then id (ALT's order).

    Identified by the exact triple ``(area, title, source)`` — empty strings are
    valid values, not wildcards (ALT semantics). Inner join: a chunk without a
    document has no title/source and can never match.

    ``created_at`` lives on ``rag_documents`` in NEU (ALT stored it per chunk), so
    every chunk reports the document's stamp — which is what ALT effectively
    returned anyway, since all chunks of one ingest were written within the same
    second. Serialised to an ISO string here so the router body stays ALT-verbatim;
    the format differs from ALT's sqlite ``CURRENT_TIMESTAMP`` text by stack.
    """
    stmt = (
        select(RagChunk.chunk_index, RagChunk.content, RagDocument.created_at)
        .select_from(RagChunk)
        .join(RagDocument, RagChunk.document_id == RagDocument.id)
        .where(
            RagChunk.area == area,
            RagDocument.title == title,
            RagDocument.source == source,
        )
        .order_by(RagChunk.chunk_index.asc(), RagChunk.id.asc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "chunk_index": r.chunk_index,
            "content": r.content,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def delete_document(
    session: AsyncSession, area: str, title: str, source: str
) -> int:
    """Delete one document (exact ``area``+``title``+``source``) and its chunks.

    Returns the number of CHUNKS removed — ALT's ``deleted`` count. It is read
    before the delete because the ``ON DELETE CASCADE`` that removes the chunks
    does not report how many it touched. A count of 0 leaves the database
    untouched (ALT's ``noop`` branch).
    """
    count_stmt = (
        select(func.count())
        .select_from(RagChunk)
        .join(RagDocument, RagChunk.document_id == RagDocument.id)
        .where(
            RagChunk.area == area,
            RagDocument.title == title,
            RagDocument.source == source,
        )
    )
    n = (await session.execute(count_stmt)).scalar_one()
    if not n:
        return 0

    await session.execute(
        delete(RagDocument).where(
            RagDocument.area == area,
            RagDocument.title == title,
            RagDocument.source == source,
        )
    )
    await session.commit()
    return n
