"""P6-1: search_rag_chunks against the REAL pgvector (fresh throwaway DB).

The unit tests in test_rag_retrieval.py fake the DB boundary and assert the
compiled SQL; this file proves the query actually runs on pgvector and that the
cosine ordering / area filter / LEFT JOIN behave as intended. Skipped unless the
Compose-Postgres is up.

Seed AND query vectors are sized from ``get_embed_dim()``, the same source the
migration bakes into the column — so the fixture cannot drift from the schema
(same rule as the sibling test_rag_embed_pg.py). A hardcoded literal here is a
silent ``expected 1536 dimensions, not 3`` the moment this file is run for real.
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

_DB = "boerdi_p6_ragsearch_test"


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


def _unit(axis: int) -> list[float]:
    """One-hot vector of the column's dimension.

    The same axis twice is identical (cosine distance 0), two different axes are
    orthogonal (distance 1) — the [1,0,0]/[0,1,0] semantics this fixture is
    written around, at whatever dimension the schema actually has.
    """
    vec = [0.0] * _dim()
    vec[axis] = 1.0
    return vec


def _literal(vec: list[float]) -> str:
    """pgvector text literal for ``CAST(:v AS vector)``."""
    return "[" + ",".join(str(x) for x in vec) + "]"


async def _seed(session) -> None:
    """One document + 3 chunks in 'erdkunde' (near/far) and 1 in 'mathe'.
    Vectors are unit-ish so cosine distance is easy to reason about."""
    await session.execute(text(
        "INSERT INTO rag_documents (id, area, title, source) "
        "VALUES (1, 'erdkunde', 'Klima', 'klima.md')"
    ))
    rows = [
        (1, 1, "erdkunde", 0, "Eiszeit-Text", _unit(0)),     # identical to query -> dist 0
        (2, 1, "erdkunde", 1, "Gletscher-Text", _unit(1)),   # orthogonal         -> dist 1
        (3, None, "erdkunde", 2, "Waise ohne Dokument", _unit(0)),  # no document row
        (4, 1, "mathe", 0, "Bruchrechnung", _unit(0)),       # other area -> filtered out
    ]
    for cid, doc, area, idx, content, vec in rows:
        await session.execute(
            text(
                "INSERT INTO rag_chunks (id, document_id, area, chunk_index, content, embedding) "
                "VALUES (:i, :d, :a, :x, :c, CAST(:v AS vector))"
            ),
            {"i": cid, "d": doc, "a": area, "x": idx, "c": content, "v": _literal(vec)},
        )
    # a chunk without an embedding must never surface
    await session.execute(text(
        "INSERT INTO rag_chunks (id, document_id, area, chunk_index, content, embedding) "
        "VALUES (5, 1, 'erdkunde', 3, 'Ohne Embedding', NULL)"
    ))
    await session.commit()


def test_cosine_search_orders_filters_and_joins(test_db) -> None:
    from boerdi.db.session import make_session_factory
    from boerdi.services.rag.retrieval import search_rag_chunks

    async def scenario():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await _seed(session)
                return await search_rag_chunks(session, "erdkunde", _unit(0), top_k=10)
        finally:
            await engine.dispose()

    out = asyncio.run(scenario())
    chunks = [r["chunk"] for r in out]

    # area filter: nothing from 'mathe'; NULL embedding never surfaces
    assert "Bruchrechnung" not in chunks
    assert "Ohne Embedding" not in chunks
    # cosine ordering: identical vector first, orthogonal last
    assert chunks[0] in {"Eiszeit-Text", "Waise ohne Dokument"}
    assert chunks[-1] == "Gletscher-Text"
    # score = 1 - cosine_distance
    by_chunk = {r["chunk"]: r for r in out}
    assert by_chunk["Eiszeit-Text"]["score"] == pytest.approx(1.0, abs=1e-6)
    assert by_chunk["Gletscher-Text"]["score"] == pytest.approx(0.0, abs=1e-6)
    # LEFT JOIN: document fields present, orphan chunk yields NULLs
    assert by_chunk["Eiszeit-Text"]["title"] == "Klima"
    assert by_chunk["Eiszeit-Text"]["source"] == "klima.md"
    assert by_chunk["Waise ohne Dokument"]["title"] is None
    assert by_chunk["Waise ohne Dokument"]["source"] is None


def test_top_k_limits_the_result(test_db) -> None:
    from boerdi.db.session import make_session_factory
    from boerdi.services.rag.retrieval import search_rag_chunks

    async def scenario():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                return await search_rag_chunks(session, "erdkunde", _unit(0), top_k=1)
        finally:
            await engine.dispose()

    assert len(asyncio.run(scenario())) == 1
