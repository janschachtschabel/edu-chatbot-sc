"""P1-1: alembic migration 0001 == spec §6 DDL — verified against the live
Compose-Postgres (fresh throwaway database per test module).

Skips with a clear hint when the compose PG is not running.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from tests import pg_utils

_TEST_DB = "boerdi_p1_test"
_TEST_DSN = pg_utils.asyncpg_dsn(_TEST_DB)
_TEST_URL_SQLA = pg_utils.sqlalchemy_url(_TEST_DB)

SPEC_TABLES = {
    "sessions", "messages", "memory", "safety_logs", "quality_logs",
    "eval_runs", "loadtest_runs", "config_areas", "config_history",
    "config_snapshots", "rag_documents", "rag_chunks",
}
SPEC_INDEXES = {
    "idx_sessions_updated", "idx_messages_session", "idx_safety_created",
    "idx_safety_risk", "idx_quality_created", "idx_quality_pattern",
    "idx_rag_area", "idx_rag_embedding",
}


pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def migrated_db():
    pg_utils.create_migrated_db(_TEST_DB)
    yield _TEST_DSN
    pg_utils.drop_db(_TEST_DB)


async def _fetch_set(dsn: str, sql: str) -> set[str]:
    conn = await asyncpg.connect(dsn)
    try:
        return {r[0] for r in await conn.fetch(sql)}
    finally:
        await conn.close()


def test_all_spec_tables_exist(migrated_db) -> None:
    tables = _run(_fetch_set(
        migrated_db,
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'",
    ))
    missing = SPEC_TABLES - tables
    assert missing == set(), f"missing tables: {sorted(missing)}"


def test_spec_indexes_exist(migrated_db) -> None:
    indexes = _run(_fetch_set(
        migrated_db, "SELECT indexname FROM pg_indexes WHERE schemaname='public'"
    ))
    missing = SPEC_INDEXES - indexes
    assert missing == set(), f"missing indexes: {sorted(missing)}"


def test_config_notify_trigger_installed(migrated_db) -> None:
    triggers = _run(_fetch_set(migrated_db, "SELECT tgname FROM pg_trigger"))
    assert "trg_config_notify" in triggers


def test_embedding_column_is_vector_with_dim(migrated_db) -> None:
    async def fetch() -> str:
        conn = await asyncpg.connect(migrated_db)
        try:
            return await conn.fetchval(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid='rag_chunks'::regclass AND attname='embedding'"
            )
        finally:
            await conn.close()

    assert _run(fetch()) == "vector(1536)"


def test_memory_unique_and_fk_cascade(migrated_db) -> None:
    async def scenario() -> int:
        conn = await asyncpg.connect(migrated_db)
        try:
            await conn.execute("INSERT INTO sessions (session_id) VALUES ('bb-t1')")
            await conn.execute(
                "INSERT INTO memory (session_id, key, value, memory_type) "
                "VALUES ('bb-t1','fach','mathe','short')"
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    "INSERT INTO memory (session_id, key, value, memory_type) "
                    "VALUES ('bb-t1','fach','bio','short')"
                )
            await conn.execute(
                "INSERT INTO messages (session_id, role, content) "
                "VALUES ('bb-t1','user','hi')"
            )
            await conn.execute("DELETE FROM sessions WHERE session_id='bb-t1'")
            return await conn.fetchval(
                "SELECT count(*) FROM messages WHERE session_id='bb-t1'"
            )
        finally:
            await conn.close()

    assert _run(scenario()) == 0  # ON DELETE CASCADE


def test_orm_models_map_to_real_schema(migrated_db) -> None:
    """One ORM round-trip proves the models match the migrated DDL
    (JSONB mapping, server defaults, asyncpg driver)."""

    async def roundtrip() -> None:
        from boerdi.db.models import ConfigArea
        from boerdi.db.session import make_engine, make_session_factory
        from boerdi.settings import Settings

        engine = make_engine(Settings(_env_file=None, database_url=_TEST_URL_SQLA))
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                s.add(ConfigArea(area="01-base/welcome-config", data={"greeting": "hi"}))
                await s.commit()
            async with factory() as s:
                row = await s.get(ConfigArea, "01-base/welcome-config")
                assert row is not None
                assert row.data["greeting"] == "hi"
                assert row.version == 1  # server default from DDL
                assert row.updated_at is not None
        finally:
            await engine.dispose()

    _run(roundtrip())


def test_messages_role_check_constraint(migrated_db) -> None:
    async def bad_role() -> None:
        conn = await asyncpg.connect(migrated_db)
        try:
            await conn.execute("INSERT INTO sessions (session_id) VALUES ('bb-t2')")
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO messages (session_id, role, content) "
                    "VALUES ('bb-t2','system','x')"
                )
        finally:
            await conn.close()

    _run(bad_role())
