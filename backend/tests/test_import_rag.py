"""6-4 Import-CLI: ALT sqlite rag_chunks -> NEU pg (rag_documents + rag_chunks).

§9.2 RAG-Re-Ingest: read the ALT rows' TEXT only and re-embed via LiteLLM; the ALT
float32 BLOBs are deliberately NOT carried over (NEU's embedding model/dim may
differ). ALT stored flat rows (title/source per chunk); NEU is normalised, so the
migration regroups chunks into documents by (area, source, title).

Guardrail (spec + user 2026-07-17): the sqlite side is opened read-only and never
written — pinned here by hashing the source file before/after, both at the read
level and after a full pg import.

Offline vs pg: the sqlite read, the pure grouping, and the CLI arg/guardrail paths
run everywhere; the two ingest paths (service + CLI end-to-end) are pg-gated and
size their fake embeddings from ``get_embed_dim()`` so the fixture cannot drift
from the column dimension the migration baked in.
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from pathlib import Path

import pytest

from boerdi.services.rag import import_rag
from tests import pg_utils

# ALT rag_chunks rows: (area, title, source, chunk_index, content, embedding_blob).
# BLOBs are non-null on some rows to prove they are never read; grouping by
# (area, source, title) yields 3 documents (klima keeps its 2 chunks).
_ALT_ROWS = [
    ("erdkunde", "Klima", "klima.md", 0, "Eiszeit", b"\x00" * 16),
    ("erdkunde", "Klima", "klima.md", 1, "Gletscher", None),
    ("mathe", "Bruch", "bruch.md", 0, "Zaehler", b"\x01" * 8),
    ("erdkunde", "", "", 0, "Ohne Titel", None),
]


def _make_alt_sqlite(path: Path, rows: list[tuple]) -> None:
    """Build a throwaway sqlite with ALT's rag_chunks schema and the given rows."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE rag_chunks ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, area TEXT NOT NULL,"
            " title TEXT DEFAULT '', source TEXT DEFAULT '', chunk_index INTEGER DEFAULT 0,"
            " content TEXT NOT NULL, embedding BLOB, created_at TEXT)"
        )
        conn.executemany(
            "INSERT INTO rag_chunks"
            " (area, title, source, chunk_index, content, embedding, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, '2026-01-01T00:00:00')",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── offline: read + grouping + guardrail ───────────────────────────────────

def test_read_alt_chunks_returns_text_only_in_document_order(tmp_path) -> None:
    db = tmp_path / "alt.db"
    _make_alt_sqlite(db, _ALT_ROWS)
    rows = import_rag._read_alt_chunks(db)
    # text columns only — the embedding BLOB is never read
    assert all(set(r) == {"area", "title", "source", "chunk_index", "content"} for r in rows)
    # ordered by (area, source, title, chunk_index)
    assert [r["content"] for r in rows] == ["Ohne Titel", "Eiszeit", "Gletscher", "Zaehler"]


def test_read_alt_chunks_leaves_the_source_unchanged(tmp_path) -> None:
    db = tmp_path / "alt.db"
    _make_alt_sqlite(db, _ALT_ROWS)
    before = _sha(db)
    import_rag._read_alt_chunks(db)
    assert _sha(db) == before  # read-only: the ALT DB is never written


def test_group_into_documents_groups_by_area_source_title(tmp_path) -> None:
    db = tmp_path / "alt.db"
    _make_alt_sqlite(db, _ALT_ROWS)
    groups = import_rag._group_into_documents(import_rag._read_alt_chunks(db))
    keys = [key for key, _ in groups]
    assert keys == [
        ("erdkunde", "", ""),
        ("erdkunde", "klima.md", "Klima"),
        ("mathe", "bruch.md", "Bruch"),
    ]
    # chunk order within the klima document is preserved
    klima = next(members for key, members in groups if key[1] == "klima.md")
    assert [m["content"] for m in klima] == ["Eiszeit", "Gletscher"]
    assert [m["chunk_index"] for m in klima] == [0, 1]


def test_cli_requires_the_sqlite_argument() -> None:
    from boerdi.cli import main

    with pytest.raises(SystemExit):  # argparse: --sqlite is required
        main(["import-rag"])


def test_cli_reports_a_missing_sqlite_file(tmp_path, capsys) -> None:
    from boerdi.cli import main

    rc = main(["import-rag", "--sqlite", str(tmp_path / "does-not-exist.db")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


# ── pg: the two ingest paths against real pgvector ─────────────────────────

_DB = "boerdi_p6_importrag_test"


@pytest.fixture(scope="module")
def test_db():
    if not pg_utils.pg_available():
        pytest.skip(pg_utils.SKIP_REASON)
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _dim() -> int:
    from boerdi.services.llm_models import get_embed_dim
    return get_embed_dim()


async def _fake_embed(text: str, *, kind: str = "query") -> list[float]:
    return [0.1] * _dim()


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings
    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


@pytest.mark.pg
def test_import_rag_from_sqlite_populates_pg(tmp_path, monkeypatch, test_db) -> None:
    from sqlalchemy import select

    from boerdi.db.models import RagChunk, RagDocument
    from boerdi.db.session import make_session_factory

    monkeypatch.setattr(import_rag, "embed_text", _fake_embed)
    db = tmp_path / "alt.db"
    _make_alt_sqlite(db, _ALT_ROWS)
    src_hash = _sha(db)

    async def scenario():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                stats = await import_rag.import_rag_from_sqlite(session, db)
            async with factory() as session:
                docs = (await session.execute(
                    select(RagDocument).order_by(RagDocument.id))).scalars().all()
                chunks = (await session.execute(
                    select(RagChunk).order_by(RagChunk.id))).scalars().all()
            return stats, docs, chunks
        finally:
            await engine.dispose()

    stats, docs, chunks = asyncio.run(scenario())

    assert stats == {"documents": 3, "chunks": 4}
    assert _sha(db) == src_hash  # guardrail: the whole import never wrote the ALT DB
    # documents: one per (area, source, title) group, metadata carried over
    assert [(d.area, d.source, d.title) for d in docs] == [
        ("erdkunde", "", ""), ("erdkunde", "klima.md", "Klima"), ("mathe", "bruch.md", "Bruch"),
    ]
    # chunks: content + chunk_index preserved, re-embedded (non-null, right dim), area on each
    assert [c.content for c in chunks] == ["Ohne Titel", "Eiszeit", "Gletscher", "Zaehler"]
    assert [c.chunk_index for c in chunks] == [0, 0, 1, 0]
    assert all(c.embedding is not None and len(c.embedding) == _dim() for c in chunks)
    # the two klima chunks share one document; the others are their own
    klima = [c for c in chunks if c.content in {"Eiszeit", "Gletscher"}]
    assert klima[0].document_id == klima[1].document_id
    assert len({c.document_id for c in chunks}) == 3


@pytest.mark.pg
def test_cli_import_rag_end_to_end(tmp_path, monkeypatch, capsys, test_db) -> None:
    from sqlalchemy import func, select, text

    from boerdi.cli import main
    from boerdi.db.models import RagChunk
    from boerdi.db.session import make_session_factory
    from boerdi.settings import get_settings

    monkeypatch.setattr(import_rag, "embed_text", _fake_embed)
    monkeypatch.setenv("DATABASE_URL", pg_utils.sqlalchemy_url(test_db))
    get_settings.cache_clear()
    db = tmp_path / "alt.db"
    _make_alt_sqlite(db, _ALT_ROWS)

    async def _clean():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text("TRUNCATE rag_chunks, rag_documents RESTART IDENTITY CASCADE")
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def _count():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                result = await session.execute(select(func.count()).select_from(RagChunk))
                return result.scalar_one()
        finally:
            await engine.dispose()

    asyncio.run(_clean())
    rc = main(["import-rag", "--sqlite", str(db)])
    get_settings.cache_clear()

    assert rc == 0
    assert "4 chunks in 3 documents" in capsys.readouterr().out
    assert asyncio.run(_count()) == 4
