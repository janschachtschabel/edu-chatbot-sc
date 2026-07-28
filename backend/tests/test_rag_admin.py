"""P6-2c: RAG administration service (area/document listing + deletion).

These are pg-REWRITES, not ports: ALT ran raw sqlite inside the router against a
flat `rag_chunks` table that carried title/source/created_at per chunk. So there
is nothing to AST-compare against — the contract is pinned by behaviour instead.

Local strategy as in test_rag_retrieval.py: a fake session captures the statement
(compiled against the real postgresql dialect, so a bad statement fails here and
not only in the pg-gated tests) and returns canned rows. The pg-gated
test_rag_admin_pg.py drives the same functions against a real database.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

import boerdi.services.rag.admin as admin


class _FakeResult:
    def __init__(self, rows=(), scalar=None):
        self._rows, self._scalar = list(rows), scalar

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class _FakeSession:
    """Captures executed statements; returns canned rows/scalars in order."""

    def __init__(self, results=()):
        self.results = list(results)
        self.stmts: list = []
        self.commits = 0

    async def execute(self, stmt):
        self.stmts.append(stmt)
        return self.results.pop(0) if self.results else _FakeResult()

    async def commit(self):
        self.commits += 1


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _params(stmt) -> dict:
    return stmt.compile(dialect=postgresql.dialect()).params


# ── list_areas ───────────────────────────────────────────────────────────
def test_list_areas_counts_chunks_and_distinct_titles_grouped_by_area():
    sess = _FakeSession()
    asyncio.run(admin.list_areas(sess))
    sql = _sql(sess.stmts[0])
    assert "count(DISTINCT rag_documents.title)" in sql  # title lives on the document
    assert "LEFT OUTER JOIN rag_documents" in sql  # chunks without a doc still count
    assert "GROUP BY rag_chunks.area" in sql
    assert "ORDER BY rag_chunks.area" in sql


def test_list_areas_maps_rows_to_the_alt_contract():
    sess = _FakeSession([_FakeResult([
        SimpleNamespace(area="bio", count=7, docs=2),
        SimpleNamespace(area="erdkunde", count=3, docs=1),
    ])])
    out = asyncio.run(admin.list_areas(sess))
    assert out == [
        {"area": "bio", "chunks": 7, "documents": 2},
        {"area": "erdkunde", "chunks": 3, "documents": 1},
    ]


def test_list_areas_empty_returns_empty_list():
    assert asyncio.run(admin.list_areas(_FakeSession())) == []


def test_list_areas_does_not_write():
    sess = _FakeSession()
    asyncio.run(admin.list_areas(sess))
    assert sess.commits == 0


# ── delete_area ──────────────────────────────────────────────────────────
def test_delete_area_removes_chunks_and_documents_in_one_transaction():
    sess = _FakeSession()
    asyncio.run(admin.delete_area(sess, "bio"))
    sqls = [_sql(s) for s in sess.stmts]
    assert len(sqls) == 2
    assert "DELETE FROM rag_chunks" in sqls[0]  # covers orphans (document_id NULL)
    assert "DELETE FROM rag_documents" in sqls[1]  # ALT had no such table to clean
    assert all("area = " in s for s in sqls)
    assert sess.commits == 1  # one transaction, not one per statement


def test_delete_area_filters_by_the_requested_area_only():
    sess = _FakeSession()
    asyncio.run(admin.delete_area(sess, "erdkunde"))
    for stmt in sess.stmts:
        assert "erdkunde" in _params(stmt).values()


# ── get_document_chunks ──────────────────────────────────────────────────
def test_get_document_chunks_joins_and_filters_on_area_title_source():
    sess = _FakeSession()
    asyncio.run(admin.get_document_chunks(sess, "bio", "Zelle", "z.md"))
    sql = _sql(sess.stmts[0])
    assert "JOIN rag_documents" in sql and "LEFT OUTER JOIN" not in sql  # inner: needs a doc
    assert "rag_chunks.area = " in sql
    assert "rag_documents.title = " in sql
    assert "rag_documents.source = " in sql
    assert "ORDER BY rag_chunks.chunk_index ASC, rag_chunks.id ASC" in sql  # ALT order
    assert set(_params(sess.stmts[0]).values()) >= {"bio", "Zelle", "z.md"}


def test_get_document_chunks_maps_rows_and_isoformats_created_at():
    ts = datetime(2026, 7, 17, 12, 30, 0, tzinfo=UTC)
    sess = _FakeSession([_FakeResult([
        SimpleNamespace(chunk_index=0, content="Erst", created_at=ts),
        SimpleNamespace(chunk_index=1, content="Zweit", created_at=ts),
    ])])
    out = asyncio.run(admin.get_document_chunks(sess, "bio", "Zelle", "z.md"))
    # created_at sits on the DOCUMENT in NEU -> every chunk reports the same
    # stamp. ALT stored it per chunk, but all chunks of one ingest shared a
    # second anyway. Serialized as a string so the router body stays ALT-verbatim.
    assert out == [
        {"chunk_index": 0, "content": "Erst", "created_at": "2026-07-17T12:30:00+00:00"},
        {"chunk_index": 1, "content": "Zweit", "created_at": "2026-07-17T12:30:00+00:00"},
    ]


def test_get_document_chunks_empty_document_returns_empty_list():
    assert asyncio.run(admin.get_document_chunks(_FakeSession(), "bio", "x", "y")) == []


def test_get_document_chunks_accepts_empty_title_and_source_as_exact_match():
    # ALT: "Empty strings are valid (the match is exact)".
    sess = _FakeSession()
    asyncio.run(admin.get_document_chunks(sess, "bio", "", ""))
    vals = list(_params(sess.stmts[0]).values())
    assert vals.count("") == 2  # both bound as '', not dropped or coerced to NULL


def test_get_document_chunks_does_not_write():
    sess = _FakeSession()
    asyncio.run(admin.get_document_chunks(sess, "bio", "t", "s"))
    assert sess.commits == 0


# ── delete_document ──────────────────────────────────────────────────────
def test_delete_document_counts_chunks_then_cascades_via_the_document():
    sess = _FakeSession([_FakeResult(scalar=4)])
    n = asyncio.run(admin.delete_document(sess, "bio", "Zelle", "z.md"))
    assert n == 4  # ALT's `deleted` is the CHUNK count, not the document count
    sqls = [_sql(s) for s in sess.stmts]
    assert len(sqls) == 2
    assert sqls[0].startswith("SELECT count(")  # counted BEFORE the delete
    assert "DELETE FROM rag_documents" in sqls[1]  # chunks follow via ON DELETE CASCADE
    assert sess.commits == 1


def test_delete_document_unknown_document_is_a_noop_without_delete_or_commit():
    sess = _FakeSession([_FakeResult(scalar=0)])
    n = asyncio.run(admin.delete_document(sess, "bio", "weg", "x.md"))
    assert n == 0
    assert len(sess.stmts) == 1  # only the count ran
    assert sess.commits == 0  # nothing to commit -> ALT's "noop" branch


def test_delete_document_filters_by_area_title_and_source():
    sess = _FakeSession([_FakeResult(scalar=1)])
    asyncio.run(admin.delete_document(sess, "bio", "Zelle", "z.md"))
    for stmt in sess.stmts:
        assert set(_params(stmt).values()) >= {"bio", "Zelle", "z.md"}
