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
from sqlalchemy import select, text

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


def test_maschinen_filter_liest_die_aufgeloeste_maschine_vor_der_wahl(test_db) -> None:
    """ST-7a: die SQL-Bedingung folgt derselben Reihenfolge wie ``run_engine``
    — erst ``engine_effective``, dann die ausdrückliche Wahl älterer Läufe.
    Ein „default"-Lauf ohne Auflösung gehört zu keiner Maschine."""
    from boerdi.services.eval_service import get_trends, list_runs

    async def scenario(session):
        laeufe = {
            "eval-neu-agent": {"engine": "default", "engine_effective": "agent"},
            "eval-neu-muster": {"engine": "pattern", "engine_effective": "pattern"},
            "eval-alt-agent": {"engine": "agent"},
            "eval-alt-vorgabe": {"engine": "default"},
            "eval-alt-generativ": {},
        }
        for run_id, config in laeufe.items():
            await _add_run(session, run_id, status="done", mode="golden", config=config,
                           totals={"total_turns": 1, "avg_score": 1.0}, summary={})
        return (await list_runs(session, 50, "agent"), await list_runs(session, 50, None),
                await get_trends(session, 10, "agent"))

    agent, alle, verlauf = _run(scenario)
    assert sorted(r["id"] for r in agent["runs"]) == ["eval-alt-agent", "eval-neu-agent"]
    assert len(alle["runs"]) == 5
    assert sorted(m["id"] for m in verlauf["runs"]) == ["eval-alt-agent", "eval-neu-agent"]


def test_vergleich_liest_genau_die_gewaehlten_laeufe(test_db) -> None:
    """ST-7c: die Auswahl ist SQL (``id IN …``) — ein nicht gewählter Lauf darf
    in keiner Maschine mitzählen, eine unbekannte Kennung wird genannt."""
    from boerdi.services.eval_service import compare_runs

    zug = {"user": "u", "bot": "Antwort", "latency_ms": 1000, "debug": {},
           "golden": {"checks": {"qr": True}, "observed": {"content_len": 7}}}

    async def scenario(session):
        for run_id, engine in (("eval-m1", "pattern"), ("eval-a1", "agent"),
                               ("eval-a2", "agent"), ("eval-fremd", "agent")):
            await _add_run(session, run_id, status="done", mode="golden",
                           config={"engine": engine, "engine_effective": engine},
                           totals={"total_turns": 1, "avg_score": 1.0}, summary={},
                           conversations=[{"flow_id": "GV-LEH-1", "turns": [zug]}])
        return await compare_runs(session, ["eval-m1", "eval-a1", "eval-a2", "eval-weg"])

    out = _run(scenario)
    assert out["engines"]["agent"]["runs"] == 2
    assert out["engines"]["pattern"]["runs"] == 1
    assert [r["id"] for r in out["runs"]] == ["eval-m1", "eval-a1", "eval-a2"]
    assert {"code": "not_found", "run": "eval-weg"} in out["warnings"]


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


# ── cancel_run + Task-Abbruch beim Löschen (Nutzer-Befund 2026-08-22) ─────
# „Alle Läufe löschen" entfernte nur die ZEILE eines laufenden Laufs: der
# Hintergrund-Task feuerte weiter Chat- und Judge-Aufrufe (Kosten!), seine
# Zwischenstände liefen ins Leere, und ohne running-Zeile hätte der
# Parallel-Wächter einen zweiten Lauf zugelassen. Abbrechen gab es gar nicht.


def _haengender_task(run_id: str):
    """Ein registrierter Hintergrund-Task, der nie von selbst endet."""
    from boerdi.obs.tasks import register_run_task

    async def haengt() -> None:
        await asyncio.Event().wait()

    task = asyncio.get_running_loop().create_task(haengt())
    register_run_task(run_id, task)
    return task


def test_cancel_run_stoppt_task_und_schreibt_cancelled(test_db) -> None:
    # Die Registry liegt in ``obs/tasks``, seit der Lasttest als zweiter
    # Aufrufer dazukam; ``run_store`` führt sie nur noch unter seinen alten
    # Namen weiter. Der Test prüft den kanonischen Ort.
    from boerdi.obs.tasks import RUN_TASKS
    from boerdi.services.eval_service import cancel_run, get_run

    async def scenario(session):
        await _add_run(session, "eval-c", status="running", mode="golden",
                       summary={"current_activity": "Judge bewertet 39 Züge …"})
        task = _haengender_task("eval-c")
        out = await cancel_run(session, "eval-c")
        detail = await get_run(session, "eval-c")
        await asyncio.sleep(0)  # Done-Callback der Registry läuft per call_soon
        return out, task.cancelled(), detail, "eval-c" in RUN_TASKS

    out, cancelled, detail, registered = _run(scenario)
    assert out == {"cancelled": "eval-c", "task_stopped": True}
    assert cancelled
    assert detail["status"] == "cancelled"
    assert detail["completed_at"] is not None
    assert detail["summary"]["current_activity"] == "Abgebrochen"
    assert not registered


def test_cancel_run_ohne_lebenden_task_schliesst_die_zeile(test_db) -> None:
    # Prozess-Neustart: Zeile 'running', aber kein Task in DIESEM Prozess. Die
    # Zeile wird trotzdem abgeschlossen — sonst bliebe der Parallel-Wächter bis
    # zum Stale-Sweep (2 h) blockiert.
    from boerdi.services.eval_service import cancel_run, get_run

    async def scenario(session):
        await _add_run(session, "eval-verwaist", status="running", mode="generative")
        out = await cancel_run(session, "eval-verwaist")
        return out, await get_run(session, "eval-verwaist")

    out, detail = _run(scenario)
    assert out == {"cancelled": "eval-verwaist", "task_stopped": False}
    assert detail["status"] == "cancelled"


def test_cancel_run_409_wenn_nicht_running_und_404_wenn_fehlt(test_db) -> None:
    from boerdi.services.eval_service import cancel_run

    async def fertig(session):
        await _add_run(session, "eval-fertig", status="done", mode="golden")
        with pytest.raises(HTTPException) as ei:
            await cancel_run(session, "eval-fertig")
        return ei.value.status_code, ei.value.detail

    async def fehlt(session):
        with pytest.raises(HTTPException) as ei:
            await cancel_run(session, "eval-nix")
        return ei.value.status_code

    code, detail = _run(fertig)
    assert code == 409 and "done" in detail
    assert _run(fehlt) == 404


def test_delete_run_bricht_den_lebenden_task_ab(test_db) -> None:
    from boerdi.services.eval_service import delete_run, list_runs

    async def scenario(session):
        await _add_run(session, "eval-weg", status="running", mode="generative")
        task = _haengender_task("eval-weg")
        out = await delete_run(session, "eval-weg")
        return out, task.cancelled(), await list_runs(session, 50)

    out, cancelled, listed = _run(scenario)
    assert out == {"deleted": "eval-weg"}
    assert cancelled, "der Hintergrund-Task lief nach dem Löschen weiter"
    assert listed["runs"] == []


def test_finalize_run_dreht_einen_gestoppten_lauf_nicht_zurueck(test_db) -> None:
    """Review-Befund 2026-08-22: ``_finalize_run`` schrieb den Status
    bedingungslos. Ein Job, der die Cancellation erst am nächsten Prüfpunkt
    bemerkt — oder in einer ANDEREN Replika läuft — drehte den gestoppten Lauf
    damit auf ``done`` zurück: die Oberfläche meldete „gestoppt", der Lauf
    stand danach als „fertig" da, und der Parallel-Wächter war die ganze Zeit
    offen."""
    from boerdi.services.eval_service import _finalize_run, get_run

    async def scenario(session):
        await _add_run(session, "eval-terminal", status="cancelled", mode="golden",
                       summary={"current_activity": "Abgebrochen"})
        geschrieben = await _finalize_run(
            session, "eval-terminal", status="done", total_turns=39,
            avg_score=0.95, summary={"current_activity": "Fertig"},
        )
        return geschrieben, await get_run(session, "eval-terminal")

    geschrieben, detail = _run(scenario)
    assert geschrieben is False
    assert detail["status"] == "cancelled"
    assert detail["summary"]["current_activity"] == "Abgebrochen"
    assert detail["total_turns"] == 0, "der späte Job überschrieb die Zähler"


def test_cancel_run_trifft_keinen_lauf_der_gerade_fertig_wurde(
    test_db, monkeypatch,
) -> None:
    """Die Gegenrichtung: wird der Lauf WÄHREND des Abbruchs regulär fertig,
    darf der Stopp ihn nicht nachträglich umetikettieren."""
    import boerdi.services.eval.mutations as mut
    from boerdi.services.eval_service import cancel_run, get_run

    async def scenario(session):
        await _add_run(session, "eval-knapp", status="running", mode="golden")

        async def wird_fertig(run_id: str) -> bool:
            # Simuliert das Zeitfenster: der Job schließt sich selbst ab,
            # während der Abbruch auf ihn wartet.
            await session.execute(
                text("UPDATE eval_runs SET status='done' WHERE id=:i"),
                {"i": run_id},
            )
            await session.commit()
            return False

        monkeypatch.setattr(mut, "_cancel_run_task", wird_fertig)
        with pytest.raises(HTTPException) as ei:
            await cancel_run(session, "eval-knapp")
        return ei.value.status_code, await get_run(session, "eval-knapp")

    code, detail = _run(scenario)
    assert code == 409
    assert detail["status"] == "done", "ein fertiger Lauf wurde als gestoppt geführt"


def test_golden_lauf_haelt_am_pruefpunkt_an_wenn_die_zeile_gestoppt_ist(
    test_db, monkeypatch,
) -> None:
    """Der eigentliche Schutz gegen den Replika-Fall (Review 2026-08-22).

    Der In-Prozess-Abbruch erreicht nur den Task DIESES Prozesses. Deshalb
    liest der Lauf an seinen eigenen Prüfpunkten (je Flow) mit, ob seine Zeile
    noch ``running`` ist — und hört sonst auf. Ohne das lief ein Lauf nach dem
    Stopp auf jeder anderen Replika weiter und verbrannte Züge.
    """
    import boerdi.services.eval.golden_run as golden_run

    flows = [{"id": "GS-1", "turns": [{"message": "a"}]},
             {"id": "GS-2", "turns": [{"message": "b"}]}]
    gefeuert: list[str] = []

    async def scenario(session):
        from boerdi.db.session import make_session_factory
        engine = _engine()
        factory = make_session_factory(engine)

        async def run_flows(_url, flow_liste, *, headers=None):
            from boerdi.db.models import EvalRun
            fid = str(flow_liste[0]["id"])
            gefeuert.append(fid)
            # Nach dem ERSTEN Flow stoppt jemand den Lauf (anderer Prozess) —
            # genau so, wie ``cancel_run`` es täte: Status UND Schlusswort.
            async with factory() as s:
                r = (
                    await s.execute(select(EvalRun).where(EvalRun.id == "eval-stop"))
                ).scalar_one()
                r.status = "cancelled"
                r.summary = {**(r.summary or {}), "current_activity": "Abgebrochen"}
                await s.commit()
            return [{"flow_id": fid, "turns": [{"user": "a", "bot": "b"}]}]

        monkeypatch.setattr(golden_run, "_load_golden_runner",
                            lambda: type("R", (), {"run_flows": staticmethod(run_flows)}))

        async def offline_conditions(*, judge_enabled):
            return {}  # K0-2: sonst holte der Job den Master-Skill per MCP

        monkeypatch.setattr(golden_run, "run_conditions", offline_conditions)
        await _add_run(session, "eval-stop", status="running", mode="golden",
                       summary={"current_activity": "Starte Gold-Flows …"})
        try:
            await golden_run._execute_golden_run(
                factory, "eval-stop", flows, False, engine="pattern",
            )
        finally:
            await engine.dispose()
        from boerdi.services.eval_service import get_run
        return await get_run(session, "eval-stop")

    detail = _run(scenario)
    assert gefeuert == ["GS-1"], f"Lauf feuerte nach dem Stopp weiter: {gefeuert}"
    assert detail["status"] == "cancelled"
    # Der Zwischenstand rettet weiter Zahlen und Transkripte des Flows, der noch
    # fertig geworden ist — nur das Schlusswort gehört dem Abbrecher.
    assert [c["flow_id"] for c in detail["conversations"]] == ["GS-1"]
    assert detail["total_turns"] == 1
    assert detail["summary"]["current_activity"] == "Abgebrochen"


def test_generativer_fortschritt_meldet_den_abbruch(test_db) -> None:
    """Dieselbe Wache für die generative Familie — ihr Prüfpunkt ist der
    Fortschritts-Rückruf, den der Runner an vier Stellen aufruft."""
    from boerdi.db.models import EvalRun
    from boerdi.services.eval.cancel import RunCancelled
    from boerdi.services.eval_service import _progress_writer, get_run

    async def scenario(session):
        from boerdi.db.session import make_session_factory
        engine = _engine()
        factory = make_session_factory(engine)
        try:
            await _add_run(session, "eval-gen", status="running", mode="generative",
                           summary={"current_activity": "Wartet …"})
            progress = _progress_writer(factory, "eval-gen", 10)
            await progress([], "Dialog 1/4 …")  # läuft noch → kein Abbruch
            # Stopp aus einem anderen Prozess, wie ``cancel_run`` ihn schreibt.
            r = (
                await session.execute(select(EvalRun).where(EvalRun.id == "eval-gen"))
            ).scalar_one()
            r.status = "cancelled"
            r.summary = {**(r.summary or {}), "current_activity": "Abgebrochen"}
            await session.commit()
            with pytest.raises(RunCancelled):
                await progress([{"turns": [{"judge": {"total": 1.0}}]}], "Dialog 2/4 …")
            # Frische Sitzung zum Nachlesen: die Test-Sitzung hält die Zeile aus
            # ihrer EIGENEN Änderung im Speicher und zeigte sonst deren Stand
            # statt den, den der Fortschritts-Schreiber nebenan geschrieben hat.
            async with factory() as pruef:
                return await get_run(pruef, "eval-gen")
        finally:
            await engine.dispose()

    detail = _run(scenario)
    # Zahlen des letzten Zuges kommen noch an, das Schlusswort bleibt stehen.
    assert detail["total_turns"] == 1
    assert detail["summary"]["current_activity"] == "Abgebrochen"


def test_delete_runs_bricht_lebende_tasks_ab(test_db) -> None:
    from boerdi.services.eval_service import delete_runs

    async def scenario(session):
        await _add_run(session, "eval-bulk", status="running", mode="golden")
        task = _haengender_task("eval-bulk")
        out = await delete_runs(session, None, None, True)
        return out["deleted"], task.cancelled()

    count, cancelled = _run(scenario)
    assert count == 1
    assert cancelled, "die Sammel-Löschung ließ den Hintergrund-Task weiterlaufen"


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
    assert {t["pattern_id"] for t in all_["triples"]} == {"M04", "M05"}
    # Review-Runde 3 (2026-08-22, Nutzer-Entscheid): die Betriebsart-blinden
    # Server-Aggregate by_pattern/by_intent sind entfernt — das Studio leitet
    # beide Verteilungen seit dem Betriebsart-Filter aus den Kombinationen ab,
    # und einen weiteren Konsumenten gab es nie.
    assert "by_pattern" not in all_ and "by_intent" not in all_

    ev = _run(scenario_eval)
    assert ev["total"] == 2  # only eval-% sessions
    assert all(t["pattern_id"] == "M04" for t in ev["triples"])

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
        # Der echte _spawn_background gibt den Task zurück (Abbruch-Registry
        # 2026-08-22) — der Fake erfüllt den Vertrag mit einem No-op-Task.
        return asyncio.create_task(asyncio.sleep(0))

    monkeypatch.setattr(golden_run, "_spawn_background", fake_spawn)

    async def reachable():
        return None

    # Preflight (Review-Nachlauf 2026-08-22): im Test läuft kein Chat — der
    # echte Erreichbarkeits-Check bräche den Start mit 502 ab.
    monkeypatch.setattr(golden_run, "_ensure_chat_reachable", reachable)

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


# ── Paket 4, E2 (externes Audit F22): der Start ist atomar ────────────────────

def test_zwei_gleichzeitige_starts_ergeben_genau_einen_lauf_und_eine_409(
    test_db, monkeypatch,
) -> None:
    """`_ensure_no_running_run` prüfte, angelegt wurde danach — ohne Index und
    ohne Sperre. Zwei Starts zur selben Zeit sahen beide keinen laufenden Lauf
    und legten beide einen an. Die Schranke lässt beide Starts die Prüfung
    bestehen, bevor einer anlegt: genau der Fall, den nur die Datenbank
    entscheiden kann (Index aus Migration 0006)."""
    import boerdi.services.eval.golden_run as golden_run
    from boerdi.db.models import EvalRun

    flows = [{"id": "GS-1", "turns": [{"message": "a"}]}]
    monkeypatch.setattr(golden_run, "load_gold_flows", lambda: flows)
    monkeypatch.setattr(golden_run, "_load_golden_runner", lambda: type(
        "R", (), {"validate_flows": staticmethod(lambda _flows: None)}))

    async def erreichbar():
        return None

    monkeypatch.setattr(golden_run, "_ensure_chat_reachable", erreichbar)

    def ohne_hintergrund(coro):
        coro.close()  # der Lauf selbst ist hier nicht Gegenstand

        async def nichts():
            return None

        return asyncio.ensure_future(nichts())

    monkeypatch.setattr(golden_run, "_spawn_background", ohne_hintergrund)
    echt = golden_run._ensure_no_running_run

    async def scenario(session):
        from boerdi.db.session import make_session_factory

        schranke = asyncio.Barrier(2)

        async def beide_bestehen(s):
            await echt(s)
            await schranke.wait()

        monkeypatch.setattr(golden_run, "_ensure_no_running_run", beide_bestehen)
        engine = _engine()
        factory = make_session_factory(engine)
        req = type("Req", (), {"flow_ids": [], "judge": False, "engine": "pattern",
                               "config_slug": "test"})()
        try:
            async with factory() as a, factory() as b:
                ergebnisse = await asyncio.gather(
                    golden_run.start_golden_eval_run(a, factory, req),
                    golden_run.start_golden_eval_run(b, factory, req),
                    return_exceptions=True,
                )
        finally:
            await engine.dispose()
        laufend = (await session.execute(
            select(EvalRun.id).where(EvalRun.status == "running"))).scalars().all()
        return ergebnisse, laufend

    ergebnisse, laufend = _run(scenario)
    abgewiesen = [e for e in ergebnisse if isinstance(e, HTTPException)]
    angelegt = [e for e in ergebnisse if isinstance(e, dict)]
    assert len(laufend) == 1
    assert len(angelegt) == 1 and angelegt[0]["run_id"] == laufend[0]
    assert [e.status_code for e in abgewiesen] == [409]
    assert laufend[0] in abgewiesen[0].detail  # dieselbe Meldung wie bisher
