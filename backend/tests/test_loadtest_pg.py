"""P7/V9: loadtest_runs persistence against the REAL Postgres.

Mirrors ``test_db_sessions_pg.py``: a fresh migrated throwaway DB, every scenario
runs against a truncated-then-used ``loadtest_runs``. These pins prove what a fake
cannot — that the profile round-trips as native JSONB in ``config``, that the ALT
run dict is reconstructed from the ``config``/``result`` split, that the
one-run-at-a-time guard really keys on ``status``, that delete reports found vs.
not-found, and that the orphan sweep flips leftover ``running`` rows to ``failed``.
Skipped unless the Compose-Postgres is up.
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

_DB = "boerdi_p7_loadtest_test"

_PROFILE = {
    "stages": [1, 2],
    "requests_per_stage": 5,
    "mix": {"wissen": 1, "suche": 1},
    "p95_threshold_s": 20.0,
    "total_requests": 10,
}


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
    """Run ``fn(session)`` against a freshly truncated ``loadtest_runs``."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text("TRUNCATE loadtest_runs RESTART IDENTITY CASCADE")
                )
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def test_create_then_load_roundtrips_profile_and_defaults(test_db) -> None:
    from boerdi.services.loadtest import create_run, load_run

    async def scenario(session):
        await create_run(session, "lt-1", _PROFILE)
        return await load_run(session, "lt-1")

    run = _run(scenario)
    assert run["id"] == "lt-1"
    assert run["status"] == "running"
    assert run["profile"] == _PROFILE  # config JSONB parsed back to a dict
    assert run["created_at"] is not None
    # nothing has run yet → the result-side fields degrade to ALT's empties
    assert run["finished_at"] is None
    assert run["stages"] == [] and run["resource_samples"] == []
    assert run["summary"] is None and run["error"] is None


def test_load_run_reconstructs_full_dict_from_result_column(test_db) -> None:
    from boerdi.db.models import LoadtestRun
    from boerdi.services.loadtest import create_run, load_run

    result = {
        "finished_at": "2026-07-24T10:00:00+00:00",
        "stages": [{"concurrency": 1, "requests": 5, "errors": 0, "p95_s": 3.1}],
        "resource_samples": [],
        "summary": {"stable_concurrency": 2, "total_requests": 10, "total_errors": 0},
        "error": None,
    }

    async def scenario(session):
        await create_run(session, "lt-2", _PROFILE)
        row = await session.get(LoadtestRun, "lt-2")
        row.status = "completed"
        row.result = result
        await session.commit()
        return await load_run(session, "lt-2")

    run = _run(scenario)
    assert run["status"] == "completed"
    assert run["profile"] == _PROFILE
    assert run["finished_at"] == "2026-07-24T10:00:00+00:00"
    assert run["stages"] == result["stages"]
    assert run["summary"] == result["summary"]


def test_list_runs_is_newest_first_and_compact(test_db) -> None:
    from boerdi.services.loadtest import create_run, list_runs

    async def scenario(session):
        await create_run(session, "lt-a", _PROFILE)  # separate commits → distinct now()
        await create_run(session, "lt-b", _PROFILE)
        return await list_runs(session)

    runs = _run(scenario)
    assert [r["id"] for r in runs] == ["lt-b", "lt-a"]  # created_at DESC
    # compact shape: no per-stage detail, but summary/error/profile present
    assert set(runs[0]) == {"id", "status", "created_at", "finished_at",
                            "profile", "summary", "error"}


def test_any_run_running_detects_and_clears(test_db) -> None:
    from boerdi.db.models import LoadtestRun
    from boerdi.services.loadtest import any_run_running, create_run

    async def scenario(session):
        await create_run(session, "lt-live", _PROFILE)
        while_running = await any_run_running(session)
        row = await session.get(LoadtestRun, "lt-live")
        row.status = "completed"
        await session.commit()
        after_done = await any_run_running(session)
        return while_running, after_done

    while_running, after_done = _run(scenario)
    assert while_running == "lt-live"
    assert after_done is None  # completed run no longer blocks new runs


def test_delete_run_reports_found_then_missing(test_db) -> None:
    from boerdi.services.loadtest import create_run, delete_run, load_run

    async def scenario(session):
        await create_run(session, "lt-del", _PROFILE)
        first = await delete_run(session, "lt-del")
        gone = await load_run(session, "lt-del")
        second = await delete_run(session, "lt-del")
        return first, gone, second

    first, gone, second = _run(scenario)
    assert first is True  # a row was removed
    assert gone is None
    assert second is False  # nothing left to remove


def test_sweep_marks_running_failed_leaves_others(test_db) -> None:
    from boerdi.db.models import LoadtestRun
    from boerdi.services.loadtest import (
        any_run_running,
        create_run,
        load_run,
        sweep_orphaned_loadtests,
    )

    async def scenario(session):
        await create_run(session, "lt-orphan1", _PROFILE)
        await create_run(session, "lt-orphan2", _PROFILE)
        await create_run(session, "lt-done", _PROFILE)
        done = await session.get(LoadtestRun, "lt-done")
        done.status = "completed"
        await session.commit()

        swept = await sweep_orphaned_loadtests(session)
        return (
            swept,
            await load_run(session, "lt-orphan1"),
            await load_run(session, "lt-done"),
            await any_run_running(session),
        )

    swept, orphan1, done, running = _run(scenario)
    assert swept == 2  # both running rows flipped, the completed one untouched
    assert orphan1["status"] == "failed"
    assert orphan1["error"]  # error message set
    assert orphan1["finished_at"] is not None
    assert done["status"] == "completed"  # untouched
    assert running is None  # deadlock lifted — new runs possible again
