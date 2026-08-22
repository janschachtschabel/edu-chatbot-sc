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


# ── cancel_run + Task-Abbruch (Prod-Befund 3, vom Eval-Weg übertragen) ────
# Dieselbe Lücke wie bei den Eval-Läufen: ``delete_run`` entfernte nur die
# ZEILE, der per ``_spawn_background`` gestartete Lauf-Job feuerte weiter
# echte Chat-Anfragen (Kosten + Last auf derselben Pipeline, die live
# bedient), und einen Stopp gab es gar nicht — der Löschknopf war für
# laufende Zeilen sogar gesperrt. Lasttest-Läufe sind zeitbegrenzt (das
# Profil ist auf 200 Requests gedeckelt), der Schaden also kleiner als beim
# Eval; der Weg ist derselbe.


def _haengender_task(run_id: str):
    """Ein registrierter Hintergrund-Task, der nie von selbst endet."""
    from boerdi.obs.tasks import register_run_task

    async def haengt() -> None:
        await asyncio.Event().wait()

    task = asyncio.get_running_loop().create_task(haengt())
    register_run_task(run_id, task)
    return task


class _EineSitzung:
    """Fabrik-Attrappe für ``_persist``: reicht die Testsitzung durch.

    ``_persist`` ist der Schreibweg des Hintergrund-Läufers und öffnet sonst
    eine eigene Sitzung aus ``app.state.session_factory``. Hier soll er auf
    genau der Sitzung schreiben, die der Test danach liest.
    """

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_exc) -> bool:
        return False


def test_cancel_run_stoppt_task_und_schreibt_cancelled(test_db) -> None:
    from boerdi.obs.tasks import RUN_TASKS
    from boerdi.services.loadtest import cancel_run, create_run, load_run

    async def scenario(session):
        await create_run(session, "lt-c", _PROFILE)
        task = _haengender_task("lt-c")
        stopped = await cancel_run(session, "lt-c")
        run = await load_run(session, "lt-c")
        await asyncio.sleep(0)  # Done-Callback der Registry läuft per call_soon
        return stopped, task.cancelled(), run, "lt-c" in RUN_TASKS

    stopped, cancelled, run, registered = _run(scenario)
    assert stopped is True
    assert cancelled, "der Hintergrund-Task feuerte nach dem Stopp weiter"
    assert run["status"] == "cancelled"
    assert run["finished_at"] is not None
    assert run["error"], "der Grund des Endes gehört in die Zeile"
    assert not registered  # Registry räumt sich selbst


def test_cancel_run_ohne_lebenden_task_schliesst_die_zeile(test_db) -> None:
    # Prozess-Neustart: Zeile 'running', aber kein Task in DIESEM Prozess. Die
    # Zeile wird trotzdem geschlossen — sonst bliebe der Ein-Lauf-Wächter bis
    # zum Start-Sweep blockiert und der Lauf ließe sich nicht einmal löschen.
    from boerdi.services.loadtest import any_run_running, cancel_run, create_run, load_run

    async def scenario(session):
        await create_run(session, "lt-verwaist", _PROFILE)
        stopped = await cancel_run(session, "lt-verwaist")
        return stopped, await load_run(session, "lt-verwaist"), await any_run_running(session)

    stopped, run, running = _run(scenario)
    assert stopped is False
    assert run["status"] == "cancelled"
    assert running is None, "der gestoppte Lauf blockierte weiter jeden Start"


def test_cancel_run_behaelt_die_gemessenen_stufen(test_db) -> None:
    """Ein halber Lasttest ist lesenswert — die Kurve bis zum Stopp bleibt."""
    from boerdi.db.models import LoadtestRun
    from boerdi.services.loadtest import cancel_run, create_run, load_run

    stufe = {"concurrency": 1, "requests": 5, "ok": 5, "errors": 0, "p95_s": 2.0}

    async def scenario(session):
        await create_run(session, "lt-halb", _PROFILE)
        row = await session.get(LoadtestRun, "lt-halb")
        row.result = {"stages": [stufe], "resource_samples": [{"t": 0.0, "rss_mb": 90.0}]}
        await session.commit()
        await cancel_run(session, "lt-halb")
        return await load_run(session, "lt-halb")

    run = _run(scenario)
    assert run["stages"] == [stufe]
    assert run["resource_samples"]
    assert run["summary"] is None  # kein Fazit über einen halben Lauf


def test_delete_run_bricht_den_lebenden_task_ab(test_db) -> None:
    from boerdi.services.loadtest import create_run, delete_run, list_runs

    async def scenario(session):
        await create_run(session, "lt-weg", _PROFILE)
        task = _haengender_task("lt-weg")
        removed = await delete_run(session, "lt-weg")
        return removed, task.cancelled(), await list_runs(session)

    removed, cancelled, listed = _run(scenario)
    assert removed is True
    assert cancelled, "der Hintergrund-Task lief nach dem Löschen weiter"
    assert listed == []


def test_persist_schreibt_einen_gestoppten_lauf_nicht_zurueck(test_db) -> None:
    """Der Läufer schreibt in seinem ``finally`` IMMER einen Endstand.

    Ohne diese Sperre stünde ein gerade gestoppter Lauf Sekunden später als
    „abgeschlossen" da (und bei mehreren Replikas beliebig lange danach) —
    dieselbe Rückwärtsdrehung, die ``_finalize_run`` auf dem Eval-Weg
    verhindert.
    """
    from boerdi.services.loadtest import _persist, cancel_run, create_run, load_run

    async def scenario(session):
        await create_run(session, "lt-spaet", _PROFILE)
        await cancel_run(session, "lt-spaet")
        geschrieben = await _persist(
            _EineSitzung(session), "lt-spaet",
            status="completed", result={"summary": {"stable_concurrency": 8}},
        )
        return geschrieben, await load_run(session, "lt-spaet")

    geschrieben, run = _run(scenario)
    assert geschrieben is False
    assert run["status"] == "cancelled"
    assert run["summary"] is None, "der späte Job überschrieb den Teilstand"


def test_persist_meldet_eine_geloeschte_zeile(test_db) -> None:
    """Der Prüfpunkt des Läufers: ``False`` heißt auch „Zeile ist weg"."""
    from boerdi.services.loadtest import _persist

    async def scenario(session):
        return await _persist(_EineSitzung(session), "lt-gibtsnicht", result={"stages": []})

    assert _run(scenario) is False
