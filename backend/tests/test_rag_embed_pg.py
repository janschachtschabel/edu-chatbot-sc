"""P6-2d: embed_missing_chunks against the REAL Postgres/pgvector.

test_rag_ingest.py fakes the session — which means the per-chunk SAVEPOINT is
pinned against a fake ``begin_nested``, i.e. against the very thing it claims to
handle. Only a real transaction can prove that claim: that a real dimension
mismatch really aborts it, and that the savepoint really keeps the surviving
chunks and the final commit alive. Skipped unless the Compose-Postgres is up.

Vectors come from the faked embedder and are sized from ``get_embed_dim()``, the
same source the migration bakes into the column — so the fixture cannot drift
from the schema.
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

_DB = "boerdi_p6_ragembed_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


def _dim() -> int:
    """The dimension the migration baked into the column."""
    from boerdi.services.llm_models import get_embed_dim

    return get_embed_dim()


async def _seed(session) -> None:
    """Two chunks without a vector — what a seed import or a restored dump
    leaves behind — plus one that already has one."""
    await session.execute(text(
        "INSERT INTO rag_documents (id, area, title, source) "
        "VALUES (1, 'bio', 'Zelle', 'z.md')"
    ))
    for cid, idx, content in [(1, 0, "Zelle Teil 1"), (2, 1, "Zelle Teil 2")]:
        await session.execute(
            text("INSERT INTO rag_chunks (id, document_id, area, chunk_index, content, "
                 "embedding) VALUES (:i, 1, 'bio', :x, :c, NULL)"),
            {"i": cid, "x": idx, "c": content},
        )
    await session.execute(
        text("INSERT INTO rag_chunks (id, document_id, area, chunk_index, content, "
             "embedding) VALUES (3, 1, 'bio', 2, 'Schon fertig', CAST(:v AS vector))"),
        {"v": "[" + ",".join(["0.5"] * _dim()) + "]"},
    )
    await session.commit()


def _run(fn, monkeypatch, embedder):
    """Run `fn(session)` against a freshly seeded database with `embedder` wired
    in as the network boundary."""
    import boerdi.services.rag.ingest as ri
    from boerdi.db.session import make_session_factory

    monkeypatch.setattr(ri, "embedding", embedder)

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


async def _count(session, where: str) -> int:
    return (await session.execute(
        text(f"SELECT COUNT(*) FROM rag_chunks WHERE {where}")
    )).scalar_one()


def test_embed_missing_fills_every_null_vector(test_db, monkeypatch) -> None:
    import boerdi.services.rag.ingest as ri

    async def good(_text):
        return [0.25] * _dim()

    async def scenario(session):
        result = await ri.embed_missing_chunks(session)
        return result, await _count(session, "embedding IS NULL")

    result, nulls = _run(scenario, monkeypatch, good)
    assert result == (2, 2)  # the already-embedded chunk is not re-embedded
    assert nulls == 0


def test_embed_missing_savepoint_survives_a_real_dimension_mismatch(test_db, monkeypatch) -> None:
    import boerdi.services.rag.ingest as ri

    async def one_bad(text_):
        if text_ == "Zelle Teil 1":
            return [1.0, 2.0]  # wrong dim -> pgvector raises, aborting the tx
        return [0.25] * _dim()

    async def scenario(session):
        result = await ri.embed_missing_chunks(session)
        return (result,
                await _count(session, "embedding IS NULL"),
                await _count(session, "id = 2 AND embedding IS NOT NULL"))

    result, nulls, chunk2_written = _run(scenario, monkeypatch, one_bad)
    # Without the savepoint the aborted statement would take chunk 2 AND the
    # commit down with it (500); ALT's sqlite simply carried on, and so must we.
    assert result == (1, 2)
    assert nulls == 1  # the bad chunk stays NULL -> a later run retries it
    assert chunk2_written == 1  # the survivor really committed


def test_embed_missing_leaves_existing_vectors_untouched(test_db, monkeypatch) -> None:
    import boerdi.services.rag.ingest as ri

    async def good(_text):
        return [0.25] * _dim()

    async def scenario(session):
        await ri.embed_missing_chunks(session)
        return (await session.execute(
            text("SELECT embedding FROM rag_chunks WHERE id = 3")
        )).scalar_one()

    kept = _run(scenario, monkeypatch, good)
    assert "0.5" in str(kept)  # never re-embedded to 0.25


def test_embed_missing_reports_nothing_to_do_on_a_fully_embedded_table(
    test_db, monkeypatch
) -> None:
    import boerdi.services.rag.ingest as ri

    calls: list[str] = []

    async def good(text_):
        calls.append(text_)
        return [0.25] * _dim()

    async def scenario(session):
        await ri.embed_missing_chunks(session)  # first pass fills 1 and 2
        return await ri.embed_missing_chunks(session)  # second finds nothing

    assert _run(scenario, monkeypatch, good) == (0, 0)
    assert len(calls) == 2  # the second pass never reached the embedder
