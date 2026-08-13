"""P7: eval_service persistence + analytics against the REAL Postgres.

Mirrors test_db_sessions_pg.py: a fresh migrated throwaway DB, every scenario runs
against a truncated-then-used session. These pins prove what a fake cannot — that
ALT's flat response shapes reconstruct from the NEU JSONB layout, that the
running-guard's stale-sweep + 409 really fire, that ``_finalize_run`` writes the
terminal row, and that the quality_logs analytics read ``data->>...`` correctly.
Skipped unless the Compose-Postgres is up.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p7_eval_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine():
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))


def _run(fn):
    """Run ``fn(session)`` against a freshly truncated database."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine()
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text("TRUNCATE eval_runs, quality_logs RESTART IDENTITY CASCADE")
                )
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


async def _add_run(session, run_id, **kw):
    from boerdi.db.models import EvalRun

    session.add(EvalRun(id=run_id, **kw))
    await session.commit()


async def _add_qlog(session, session_id, pattern_id, intent_id, data):
    from boerdi.db.models import QualityLog

    session.add(QualityLog(
        session_id=session_id, pattern_id=pattern_id, intent_id=intent_id, data=data,
    ))
    await session.commit()


# ── list_runs + get_run round-trip (JSONB → ALT shape) ────────────────────


def test_list_and_get_run_reconstruct_alt_shape_from_jsonb(test_db) -> None:
    from boerdi.services.eval_service import get_run, list_runs

    async def scenario(session):
        await _add_run(
            session, "eval-a", status="done", mode="golden",
            config={"config_slug": "wlo", "personas": ["P-LEH"], "intents": ["I03"],
                    "turns_per_conv": 0, "judge_model": "", "simulator_model": ""},
            totals={"total_turns": 3, "avg_score": 0.75},
            summary={"target_turns": 3, "current_activity": "Fertig",
                     "golden_metrics": {"overall_pass_rate": 0.75}},
            conversations=[{"kind": "golden", "flow_id": "GS-1", "turns": []}],
        )
        return await list_runs(session, 50), await get_run(session, "eval-a")

    listed, detail = _run(scenario)
    assert len(listed["runs"]) == 1
    row = listed["runs"][0]
    assert row["id"] == "eval-a" and row["status"] == "done" and row["mode"] == "golden"
    assert row["config_slug"] == "wlo"
    assert row["personas"] == ["P-LEH"] and row["intents"] == ["I03"]
    assert row["total_turns"] == 3 and row["avg_score"] == 0.75
    assert row["target_turns"] == 3 and row["current_activity"] == "Fertig"
    # full detail expands summary + conversations natively
    assert detail["summary"]["golden_metrics"] == {"overall_pass_rate": 0.75}
    assert detail["conversations"] == [{"kind": "golden", "flow_id": "GS-1", "turns": []}]
    assert detail["turns_per_conv"] == 0


def test_get_run_404_for_missing_id(test_db) -> None:
    from boerdi.services.eval_service import get_run

    async def scenario(session):
        with pytest.raises(HTTPException) as ei:
            await get_run(session, "eval-nope")
        return ei.value.status_code

    assert _run(scenario) == 404


# ── running-guard: stale sweep + 409 ──────────────────────────────────────


def test_ensure_no_running_run_sweeps_stale_and_raises_on_fresh(test_db) -> None:
    from boerdi.services.eval_service import _ensure_no_running_run

    async def stale(session):
        # created_at far in the past → swept to 'failed', no raise
        await _add_run(session, "eval-stale", status="running",
                       created_at=datetime(2020, 1, 1, tzinfo=UTC))
        await _ensure_no_running_run(session)
        status = (await session.execute(
            text("SELECT status FROM eval_runs WHERE id='eval-stale'")
        )).scalar_one()
        return status

    async def fresh(session):
        await _add_run(session, "eval-live", status="running",
                       created_at=datetime.now(UTC))
        with pytest.raises(HTTPException) as ei:
            await _ensure_no_running_run(session)
        return ei.value.status_code

    assert _run(stale) == "failed"
    assert _run(fresh) == 409


# ── _finalize_run terminal write ──────────────────────────────────────────


def test_finalize_run_writes_terminal_row(test_db) -> None:
    from boerdi.services.eval_service import _finalize_run, get_run

    async def scenario(session):
        await _add_run(session, "eval-f", status="running", mode="golden",
                       config={"personas": [], "intents": []},
                       totals={"total_turns": 0, "avg_score": None},
                       summary={"current_activity": "Starte …"})
        await _finalize_run(
            session, "eval-f", status="done", total_turns=5, avg_score=0.9,
            summary={"current_activity": "Fertig", "golden_metrics": {"turns": 5}},
            conversations=[{"flow_id": "GS-1"}],
        )
        return await get_run(session, "eval-f")

    detail = _run(scenario)
    assert detail["status"] == "done"
    assert detail["total_turns"] == 5 and detail["avg_score"] == 0.9
    assert detail["summary"]["current_activity"] == "Fertig"
    assert detail["conversations"] == [{"flow_id": "GS-1"}]


# ── delete_run + bulk delete_runs ─────────────────────────────────────────


def test_delete_run_removes_row(test_db) -> None:
    from boerdi.services.eval_service import delete_run, list_runs

    async def scenario(session):
        await _add_run(session, "eval-d", status="done", mode="golden")
        out = await delete_run(session, "eval-d")
        return out, await list_runs(session, 50)

    out, listed = _run(scenario)
    assert out == {"deleted": "eval-d"}
    assert listed["runs"] == []


def test_delete_runs_filters_by_status_and_mode(test_db) -> None:
    from boerdi.services.eval_service import delete_runs, list_runs

    async def scenario(session):
        await _add_run(session, "g-done", status="done", mode="golden")
        await _add_run(session, "g-fail", status="failed", mode="golden")
        await _add_run(session, "gen-done", status="done", mode="generative")
        # delete only golden runs
        golden_del = await delete_runs(session, None, "golden", False)
        remaining = await list_runs(session, 50)
        return golden_del, {r["id"] for r in remaining["runs"]}

    golden_del, remaining_ids = _run(scenario)
    assert golden_del["deleted"] == 2
    assert golden_del["filter"] == {"status": None, "mode": "golden"}
    assert remaining_ids == {"gen-done"}


def test_delete_runs_generative_means_not_golden(test_db) -> None:
    from boerdi.services.eval_service import delete_runs, list_runs

    async def scenario(session):
        await _add_run(session, "g1", status="done", mode="golden")
        await _add_run(session, "gen1", status="done", mode="generative")
        deleted = await delete_runs(session, None, "generative", False)
        remaining = await list_runs(session, 50)
        return deleted["deleted"], {r["id"] for r in remaining["runs"]}

    count, remaining_ids = _run(scenario)
    assert count == 1 and remaining_ids == {"g1"}


# ── clear_eval_quality_logs ───────────────────────────────────────────────


def test_clear_eval_quality_logs_only_touches_eval_rows(test_db) -> None:
    from boerdi.services.eval_service import clear_eval_quality_logs

    async def scenario(session):
        await _add_qlog(session, "eval-1", "M04", "I01", {"persona_id": "P-AND"})
        await _add_qlog(session, "eval-2", "M05", "I03", {"persona_id": "P-LEH"})
        await _add_qlog(session, "bb-prod", "M04", "I01", {"persona_id": "P-AND"})
        out = await clear_eval_quality_logs(session)
        left = (await session.execute(
            text("SELECT COUNT(*) FROM quality_logs")
        )).scalar_one()
        prod_left = (await session.execute(
            text("SELECT session_id FROM quality_logs")
        )).scalar_one()
        return out, left, prod_left

    out, left, prod_left = _run(scenario)
    assert out == {"deleted_eval_log_rows": 2}
    assert left == 1 and prod_left == "bb-prod"  # production traffic preserved


# ── pattern_usage_stats (reads data->>...) ────────────────────────────────


def test_pattern_usage_groups_and_scopes(test_db) -> None:
    from boerdi.services.eval_service import pattern_usage_stats

    async def seed(session):
        await _add_qlog(session, "eval-1", "M04", "I01 (Suche)",
                        {"persona_id": "P-AND", "final_confidence": 0.8})
        await _add_qlog(session, "eval-2", "M04", "I01 (Suche)",
                        {"persona_id": "P-AND", "final_confidence": 0.6})
        await _add_qlog(session, "bb-prod", "M05", "I03 (Lernpfad)",
                        {"persona_id": "P-LEH", "final_confidence": 1.0})

    async def scenario_all(session):
        await seed(session)
        return await pattern_usage_stats(session, None, "all")

    async def scenario_eval(session):
        await seed(session)
        return await pattern_usage_stats(session, None, "eval")

    async def scenario_prod(session):
        await seed(session)
        return await pattern_usage_stats(session, None, "production")

    all_ = _run(scenario_all)
    assert all_["total"] == 3 and all_["scope"] == "all"
    # M04/I01/P-AND appears twice — top triple; avg_conf = (0.8+0.6)/2 = 0.7
    top = all_["triples"][0]
    assert top["pattern_id"] == "M04" and top["persona_id"] == "P-AND"
    assert top["count"] == 2 and round(top["avg_conf"], 3) == 0.7
    assert {p["pattern_id"] for p in all_["by_pattern"]} == {"M04", "M05"}

    ev = _run(scenario_eval)
    assert ev["total"] == 2  # only eval-% sessions
    assert all(p["pattern_id"] == "M04" for p in ev["by_pattern"])

    prod = _run(scenario_prod)
    assert prod["total"] == 1 and prod["triples"][0]["persona_id"] == "P-LEH"


def test_pattern_usage_since_floor(test_db) -> None:
    from boerdi.services.eval_service import pattern_usage_stats

    async def scenario(session):
        await _add_qlog(session, "eval-1", "M04", "I01", {"persona_id": "P-AND"})
        future = await pattern_usage_stats(session, "2999-01-01T00:00:00+00:00", "all")
        past = await pattern_usage_stats(session, "2000-01-01T00:00:00+00:00", "all")
        return future["total"], past["total"]

    future_total, past_total = _run(scenario)
    assert future_total == 0  # nothing after year 2999
    assert past_total == 1  # everything after year 2000


# ── start_golden_eval_run persists a real running row (spawn stubbed) ──────


def test_start_golden_eval_run_persists_running_row(test_db, monkeypatch) -> None:
    import boerdi.services.eval.golden_run as golden_run
    import boerdi.services.eval_service as svc

    flows = [{"id": "GS-1", "persona": "P-LEH", "intents": ["I03"],
              "turns": [{"message": "hallo"}]}]
    # Patched where the caller lives: ``start_golden_eval_run`` resolves both
    # names in ``golden_run``'s globals; the facade only re-exports them.
    monkeypatch.setattr(golden_run, "load_gold_flows", lambda: flows)

    spawned: list = []

    def fake_spawn(coro):
        spawned.append(coro)
        coro.close()

    monkeypatch.setattr(golden_run, "_spawn_background", fake_spawn)

    async def scenario(session):
        out = await svc.start_golden_eval_run(
            session, None, svc_golden_req(judge=False)
        )
        detail = await svc.get_run(session, out["run_id"])
        return out, detail

    out, detail = _run(scenario)
    assert out["status"] == "running" and out["mode"] == "golden"
    assert out["flows_used"] == ["GS-1"] and out["turns_total"] == 1
    assert detail["status"] == "running" and detail["mode"] == "golden"
    assert detail["personas"] == ["P-LEH"]
    assert len(spawned) == 1  # background job was scheduled (and stubbed)


def svc_golden_req(*, judge: bool):
    from boerdi.api.eval import GoldenRunRequest

    return GoldenRunRequest(judge=judge)
