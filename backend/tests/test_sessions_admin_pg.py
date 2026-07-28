"""P7: session-admin queries against the REAL Postgres (skips if Compose-PG down).

Mirrors test_db_sessions_pg.py: a fresh migrated throwaway DB, each scenario runs
against a truncated-then-used session. These pins prove what a fake cannot — that
``list_sessions_admin`` orders newest-first with the right columns, that
``db_stats`` reports a live ``pg_database_size`` plus tuple counts, and above all
that ``optimize_database`` really runs ``VACUUM`` on an AUTOCOMMIT checkout without
raising (the SQLite→Postgres rewrite's riskiest seam).
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

_DB = "boerdi_p7_sessions_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


def _run(fn):
    """Run ``fn(session)`` against a freshly truncated database."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text(
                        "TRUNCATE sessions, messages, memory, safety_logs, quality_logs "
                        "RESTART IDENTITY CASCADE"
                    )
                )
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def test_list_sessions_admin_orders_newest_first_with_alt_columns(test_db) -> None:
    from boerdi.services.db_sessions import get_or_create_session, update_session
    from boerdi.services.session_admin import list_sessions_admin

    async def scenario(session):
        await get_or_create_session(session, "bb-old")
        await get_or_create_session(session, "bb-new")
        # bump bb-new's updated_at last → it is unambiguously the newest.
        await update_session(session, "bb-new", turn_count=1)
        return await list_sessions_admin(session)

    rows = _run(scenario)
    assert [r["session_id"] for r in rows] == ["bb-new", "bb-old"]
    # ALT column set — no entities/signal_history/tour_state in the list view.
    assert set(rows[0]) == {
        "session_id", "persona_id", "state_id", "turn_count", "created_at", "updated_at",
    }
    assert rows[0]["turn_count"] == 1
    assert isinstance(rows[0]["created_at"], str)  # timestamptz serialised to ISO


def test_list_sessions_admin_caps_at_100(test_db) -> None:
    from boerdi.services.db_sessions import get_or_create_session
    from boerdi.services.session_admin import list_sessions_admin

    async def scenario(session):
        for i in range(105):
            await get_or_create_session(session, f"bb-{i:03d}")
        return await list_sessions_admin(session)

    rows = _run(scenario)
    assert len(rows) == 100  # LIMIT 100


def test_db_stats_reports_size_and_tuple_counts(test_db) -> None:
    from boerdi.services.db_sessions import get_or_create_session
    from boerdi.services.session_admin import db_stats

    async def scenario(session):
        await get_or_create_session(session, "bb-1")
        return await db_stats(session)

    stats = _run(scenario)
    assert set(stats) == {"size_bytes", "live_tuples", "dead_tuples", "reclaimable_bytes"}
    assert stats["size_bytes"] > 0  # a real database has a size
    assert all(isinstance(stats[k], int) for k in stats)
    assert stats["dead_tuples"] >= 0 and stats["reclaimable_bytes"] >= 0


def test_optimize_database_runs_vacuum_without_raising(test_db) -> None:
    from boerdi.services.db_sessions import (
        delete_messages_for_session,
        get_or_create_session,
        save_message,
    )
    from boerdi.services.session_admin import optimize_database

    async def scenario(session):
        # Create then delete rows so VACUUM has dead tuples to process.
        await get_or_create_session(session, "bb-1")
        await save_message(session, "bb-1", "user", "x")
        await delete_messages_for_session(session, "bb-1")
        return await optimize_database(session)

    result = _run(scenario)
    assert set(result) == {"before_bytes", "after_bytes", "reclaimed_bytes"}
    assert all(isinstance(result[k], int) for k in result)
    assert result["before_bytes"] > 0 and result["after_bytes"] > 0
    assert result["reclaimed_bytes"] >= 0  # plain VACUUM: typically 0 (no OS shrink)
