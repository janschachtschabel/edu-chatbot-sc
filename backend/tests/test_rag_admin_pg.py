"""P6-2c: RAG admin service against the REAL Postgres (fresh throwaway DB).

test_rag_admin.py fakes the DB boundary and asserts the compiled SQL. This file
proves what a fake cannot: that deleting a `rag_documents` row really cascades
its chunks away, that the DISTINCT-title count behaves as ALT's did, and that the
area filter really isolates. Skipped unless the Compose-Postgres is up.

Every test re-seeds (these functions DELETE) — no shared mutable state.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p6_ragadmin_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


async def _seed(session) -> None:
    """Two 'bio' documents that SHARE a title but differ in source (this is what
    makes ALT's DISTINCT-title count disagree with (title, source) grouping),
    plus an orphan chunk and an untouched 'mathe' document."""
    await session.execute(text(
        "INSERT INTO rag_documents (id, area, title, source) VALUES "
        "(1, 'bio', 'Zelle', 'z.md'), "
        "(2, 'bio', 'Zelle', 'andere.md'), "
        "(3, 'mathe', 'Bruch', 'b.md')"
    ))
    rows = [
        (1, 1, "bio", 0, "Zelle Teil 1"),
        (2, 1, "bio", 1, "Zelle Teil 2"),
        (3, 2, "bio", 0, "Andere Quelle"),
        (4, None, "bio", 0, "Waise ohne Dokument"),  # document_id is nullable
        (5, 3, "mathe", 0, "Bruchrechnung"),
    ]
    for cid, doc, area, idx, content in rows:
        await session.execute(
            text(
                "INSERT INTO rag_chunks (id, document_id, area, chunk_index, content) "
                "VALUES (:i, :d, :a, :x, :c)"
            ),
            {"i": cid, "d": doc, "a": area, "x": idx, "c": content},
        )
    await session.commit()


def _run(fn):
    """Run `fn(session)` against a freshly seeded database."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text("TRUNCATE rag_chunks, rag_documents RESTART IDENTITY CASCADE")
                )
                await _seed(session)
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


async def _count(session, table: str, where: str = "TRUE") -> int:
    return (await session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"))).scalar_one()


def test_list_areas_counts_chunks_and_distinct_titles(test_db) -> None:
    from boerdi.services.rag.admin import list_areas

    out = _run(list_areas)
    by_area = {r["area"]: r for r in out}
    assert [r["area"] for r in out] == ["bio", "mathe"]  # ORDER BY area
    # 3 doc-backed chunks + 1 orphan; the LEFT JOIN keeps the orphan counted
    assert by_area["bio"]["chunks"] == 4
    # ALT quirk, kept: two documents titled 'Zelle' collapse to ONE here, while
    # GET /area/{area} groups by (title, source) and would show two.
    assert by_area["bio"]["documents"] == 1
    assert by_area["mathe"] == {"area": "mathe", "chunks": 1, "documents": 1}


def test_get_document_chunks_isolates_one_document_in_order(test_db) -> None:
    from boerdi.services.rag.admin import get_document_chunks

    out = _run(lambda s: get_document_chunks(s, "bio", "Zelle", "z.md"))
    assert [c["chunk_index"] for c in out] == [0, 1]  # ORDER BY chunk_index
    assert [c["content"] for c in out] == ["Zelle Teil 1", "Zelle Teil 2"]
    # same title, different source -> must NOT leak in
    assert all("Andere Quelle" != c["content"] for c in out)
    # created_at comes from the document row and is a non-empty ISO string
    assert out[0]["created_at"] and out[0]["created_at"] == out[1]["created_at"]


def test_get_document_chunks_never_returns_orphans(test_db) -> None:
    from boerdi.services.rag.admin import get_document_chunks

    # The orphan chunk has no document, so no (title, source) can address it.
    assert _run(lambda s: get_document_chunks(s, "bio", "", "")) == []


def test_delete_document_cascades_chunks_and_spares_its_siblings(test_db) -> None:
    from boerdi.services.rag.admin import delete_document

    async def scenario(session):
        n = await delete_document(session, "bio", "Zelle", "z.md")
        return (
            n,
            await _count(session, "rag_chunks", "document_id = 1"),
            await _count(session, "rag_documents", "id = 1"),
            await _count(session, "rag_chunks", "document_id = 2"),  # sibling doc
            await _count(session, "rag_chunks", "area = 'mathe'"),
        )

    n, orphaned_chunks, doc_rows, sibling_chunks, mathe = _run(scenario)
    assert n == 2  # ALT's `deleted` = chunk count
    assert orphaned_chunks == 0  # ON DELETE CASCADE really removed them
    assert doc_rows == 0
    assert sibling_chunks == 1  # same title, other source: untouched
    assert mathe == 1


def test_delete_document_unknown_leaves_everything(test_db) -> None:
    from boerdi.services.rag.admin import delete_document

    async def scenario(session):
        n = await delete_document(session, "bio", "Gibt", "es.nicht")
        return n, await _count(session, "rag_chunks"), await _count(session, "rag_documents")

    assert _run(scenario) == (0, 5, 3)


def test_delete_area_removes_chunks_documents_and_orphans(test_db) -> None:
    from boerdi.services.rag.admin import delete_area

    async def scenario(session):
        await delete_area(session, "bio")
        return (
            await _count(session, "rag_chunks", "area = 'bio'"),
            await _count(session, "rag_documents", "area = 'bio'"),
            await _count(session, "rag_chunks", "area = 'mathe'"),
            await _count(session, "rag_documents", "area = 'mathe'"),
        )

    bio_chunks, bio_docs, mathe_chunks, mathe_docs = _run(scenario)
    assert bio_chunks == 0  # includes the orphan ALT-style chunk delete catches
    assert bio_docs == 0  # ALT had no document table; leaving shells would be a leak
    assert (mathe_chunks, mathe_docs) == (1, 1)  # other areas untouched
