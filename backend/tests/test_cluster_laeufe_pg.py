"""Paket 17 (C1/C2): Lasttest- und Eval-Läufe bei mehreren Repliken — gegen echtes Postgres.

Bis Paket 17 galt „eine ``running``-Zeile nach einem Prozessstart ist verwaist“. Bei N Repliken
stimmt das nicht: ein neuer Pod (Rollout, Hochskalieren) brach so den laufenden Lasttest eines
anderen ab, und ein beendeter Pod hinterließ einen Eval-Lauf, der neue Läufe bis zu 2 h
blockierte. Seither trägt jeder Lauf einen Herzschlag (``heartbeat_at``, alle 15 s); verwaist
ist nur, wessen Herzschlag ausbleibt. Ein Unique-Teilindex lässt höchstens einen laufenden
Lasttest zu (wie 0006 für Eval).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p17_cluster_laeufe_test"
_PROFIL = {"stages": [1], "requests_per_stage": 1, "mix": {"wissen": 1},
           "p95_threshold_s": 20.0, "total_requests": 1}


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _lauf(fn):
    """``fn(factory)`` gegen frisch geleerte Lauf-Tabellen."""
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.settings import Settings

    async def szenario():
        engine = make_engine(Settings(_env_file=None,
                                      database_url=pg_utils.sqlalchemy_url(_DB)))
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                await s.execute(text("TRUNCATE loadtest_runs, eval_runs RESTART IDENTITY CASCADE"))
                await s.commit()
            return await fn(factory)
        finally:
            await engine.dispose()

    return asyncio.run(szenario())


async def _herzschlag(factory, tabelle: str, run_id: str, vor: timedelta) -> None:
    async with factory() as s:
        await s.execute(text(f"UPDATE {tabelle} SET heartbeat_at = :t WHERE id = :id"),
                        {"t": datetime.now(UTC) - vor, "id": run_id})
        await s.commit()


async def _status(factory, tabelle: str, run_id: str) -> str:
    async with factory() as s:
        return (await s.execute(text(f"SELECT status FROM {tabelle} WHERE id = :id"),
                                {"id": run_id})).scalar_one()


# ── C1: Lasttest ────────────────────────────────────────────────────────────

def test_der_lauf_eines_anderen_pods_ueberlebt_den_start(test_db) -> None:
    from boerdi.services.loadtest import create_run, sweep_orphaned_loadtests

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-anderer-pod", _PROFIL)
        await _herzschlag(factory, "loadtest_runs", "lt-anderer-pod", timedelta(seconds=5))
        async with factory() as s:
            await sweep_orphaned_loadtests(s)
        return await _status(factory, "loadtest_runs", "lt-anderer-pod")

    assert _lauf(szenario) == "running"


def test_ein_lauf_ohne_herzschlag_wird_abgeraeumt(test_db) -> None:
    from boerdi.services.loadtest import any_run_running, create_run, sweep_orphaned_loadtests

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-tot", _PROFIL)
        await _herzschlag(factory, "loadtest_runs", "lt-tot", timedelta(minutes=5))
        async with factory() as s:
            await sweep_orphaned_loadtests(s)
            return await _status(factory, "loadtest_runs", "lt-tot"), await any_run_running(s)

    status, laufend = _lauf(szenario)
    assert status == "failed"
    assert laufend is None


def test_der_start_raeumt_einen_toten_lauf_ohne_neustart_ab(test_db) -> None:
    """Der Start-Wächter prüft selbst — sonst blockierte der tote Lauf bis zum nächsten
    Prozessstart irgendeines Pods."""
    from boerdi.services.loadtest import any_run_running, create_run

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-tot", _PROFIL)
        await _herzschlag(factory, "loadtest_runs", "lt-tot", timedelta(minutes=5))
        async with factory() as s:
            return await any_run_running(s)

    assert _lauf(szenario) is None


def test_zwei_gleichzeitige_lasttests_scheitern_an_der_datenbank(test_db) -> None:
    from boerdi.services.loadtest import LastTestLaeuftSchon, create_run

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-erster", _PROFIL)
        async with factory() as s:
            with pytest.raises(LastTestLaeuftSchon) as fehler:
                await create_run(s, "lt-zweiter", _PROFIL)
            return fehler.value.laufend

    assert _lauf(szenario) == "lt-erster"


# ── C2: Eval ────────────────────────────────────────────────────────────────

async def _eval_zeile(factory, run_id: str, *, erstellt: datetime) -> None:
    async with factory() as s:
        await s.execute(text(
            "INSERT INTO eval_runs (id, mode, status, created_at, config, totals, summary) "
            "VALUES (:id, 'golden', 'running', :t, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)"),
            {"id": run_id, "t": erstellt})
        await s.commit()


def test_eval_ohne_herzschlag_gibt_den_weg_nach_minuten_frei(test_db) -> None:
    from boerdi.services.eval.run_store import _ensure_no_running_run

    async def szenario(factory):
        await _eval_zeile(factory, "eval-tot", erstellt=datetime.now(UTC) - timedelta(minutes=10))
        await _herzschlag(factory, "eval_runs", "eval-tot", timedelta(minutes=5))
        async with factory() as s:
            await _ensure_no_running_run(s)  # keine 409
        return await _status(factory, "eval_runs", "eval-tot")

    assert _lauf(szenario) == "failed"


def test_eval_mit_herzschlag_blockiert_weiter(test_db) -> None:
    from fastapi import HTTPException

    from boerdi.services.eval.run_store import _ensure_no_running_run

    async def szenario(factory):
        await _eval_zeile(factory, "eval-lebt", erstellt=datetime.now(UTC) - timedelta(hours=3))
        await _herzschlag(factory, "eval_runs", "eval-lebt", timedelta(seconds=10))
        async with factory() as s:
            with pytest.raises(HTTPException) as fehler:
                await _ensure_no_running_run(s)
            return fehler.value.status_code

    assert _lauf(szenario) == 409  # lange Läufe mit Herzschlag sind nicht „veraltet“


# ── Herzschlag ──────────────────────────────────────────────────────────────

def test_der_herzschlag_schlaegt_solange_der_lauf_lebt(test_db, monkeypatch) -> None:
    from boerdi.obs import herzschlag
    from boerdi.services.loadtest import create_run

    monkeypatch.setattr(herzschlag, "TAKT_S", 0.05)

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-lebt", _PROFIL)

        async def arbeit():
            await asyncio.sleep(0.2)
            return "fertig"

        # Eine Stunde alt: nur ein echter Schlag kann ihn nach vorn holen (Review C, 3).
        await _herzschlag(factory, "loadtest_runs", "lt-lebt", timedelta(hours=1))
        ergebnis = await herzschlag.mit_herzschlag(factory, "loadtest_runs", "lt-lebt", arbeit())
        nach_dem_lauf = await _schlag(factory, "lt-lebt")
        await asyncio.sleep(0.2)  # vier Takte: ein weiterlaufender Schlag fiele auf
        return ergebnis, nach_dem_lauf, await _schlag(factory, "lt-lebt")

    ergebnis, nach_dem_lauf, spaeter = _lauf(szenario)
    assert ergebnis == "fertig"
    assert datetime.now(UTC) - nach_dem_lauf < timedelta(seconds=5)
    assert spaeter == nach_dem_lauf  # mit der Arbeit endet der Herzschlag


async def _schlag(factory, run_id: str) -> datetime:
    async with factory() as s:
        return (await s.execute(text("SELECT heartbeat_at FROM loadtest_runs WHERE id = :id"),
                                {"id": run_id})).scalar_one()


def test_nur_die_bekannten_tabellen() -> None:
    from boerdi.obs import herzschlag

    with pytest.raises(ValueError):
        asyncio.run(herzschlag.mit_herzschlag(None, "users; DROP TABLE x", "id", asyncio.sleep(0)))


# ── Review Phase C ──────────────────────────────────────────────────────────

def test_ein_abgeraeumter_lasttest_bleibt_abgeraeumt(test_db) -> None:
    """Befund 2: lebt der Läufer noch (Herzschlag nur ausgesetzt), darf er die Zeile nicht auf
    ``completed`` zurückdrehen — sonst liefen zwei Lasttests, obwohl der Start-Wächter den Weg
    freigab."""
    from boerdi.services.loadtest import _persist, create_run, sweep_orphaned_loadtests

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-haengt", _PROFIL)
        await _herzschlag(factory, "loadtest_runs", "lt-haengt", timedelta(minutes=5))
        async with factory() as s:
            await sweep_orphaned_loadtests(s)
        zwischen = await _persist(factory, "lt-haengt", result={"stages": [1]})
        ende = await _persist(factory, "lt-haengt", status="completed", result={"stages": [1]})
        return zwischen, ende, await _status(factory, "loadtest_runs", "lt-haengt")

    assert _lauf(szenario) == (False, False, "failed")


def test_ein_abgeraeumter_eval_lauf_bleibt_abgeraeumt(test_db) -> None:
    """Befund 2 und 7 auf dem Eval-Weg: Endstand bleibt ``failed``, mit Endzeit."""
    from boerdi.services.eval.run_store import _ensure_no_running_run, _finalize_run

    async def szenario(factory):
        await _eval_zeile(factory, "eval-haengt", erstellt=datetime.now(UTC) - timedelta(hours=1))
        async with factory() as s:
            await _ensure_no_running_run(s)
        async with factory() as s:
            geschrieben = await _finalize_run(s, "eval-haengt", status="done")
        async with factory() as s:
            status, ende = (await s.execute(text(
                "SELECT status, completed_at FROM eval_runs WHERE id = 'eval-haengt'"))).one()
        return geschrieben, status, ende

    geschrieben, status, ende = _lauf(szenario)
    assert (geschrieben, status) == (False, "failed")
    assert ende is not None


class _VorgehendeUhr(datetime):
    """Die Uhr des Pods geht zehn Minuten vor."""

    @classmethod
    def now(cls, tz=None):
        return datetime.now(tz) + timedelta(minutes=10)


def test_eine_vorgehende_pod_uhr_raeumt_keinen_lebenden_lauf_ab(test_db, monkeypatch) -> None:
    """Befund 5: die Grenze rechnet die Datenbank — wie den Herzschlag."""
    from fastapi import HTTPException

    from boerdi.services import loadtest
    from boerdi.services.eval import run_store

    monkeypatch.setattr(loadtest, "datetime", _VorgehendeUhr)
    monkeypatch.setattr(run_store, "datetime", _VorgehendeUhr)

    async def szenario(factory):
        async with factory() as s:
            await loadtest.create_run(s, "lt-lebt", _PROFIL)
            await loadtest.sweep_orphaned_loadtests(s)
        await _eval_zeile(factory, "eval-lebt", erstellt=datetime.now(UTC))
        await _herzschlag(factory, "eval_runs", "eval-lebt", timedelta(seconds=1))
        async with factory() as s:
            with pytest.raises(HTTPException) as fehler:  # der Lauf lebt
                await run_store._ensure_no_running_run(s)
            assert fehler.value.status_code == 409
        return (await _status(factory, "loadtest_runs", "lt-lebt"),
                await _status(factory, "eval_runs", "eval-lebt"))

    assert _lauf(szenario) == ("running", "running")


_DB_MIGRATION = "boerdi_p17_migration_0014_test"


def test_0014_laesst_den_juengsten_laufenden_lasttest_stehen() -> None:
    """Befund 6: vor dem Unique-Index gehen überzählige Läufe auf ``failed`` — mit Grund."""
    pg_utils.create_migrated_db(_DB_MIGRATION, revision="0013")
    try:
        async def zeilen_anlegen():
            import asyncpg
            conn = await asyncpg.connect(pg_utils.asyncpg_dsn(_DB_MIGRATION))
            try:
                for rid, alter in (("lt-alt", "2 hours"), ("lt-neu", "1 minute")):
                    await conn.execute(
                        "INSERT INTO loadtest_runs (id, status, config, result, created_at) "
                        f"VALUES ($1, 'running', '{{}}', '{{}}', now() - interval '{alter}')", rid)
            finally:
                await conn.close()

        async def lesen():
            import asyncpg
            conn = await asyncpg.connect(pg_utils.asyncpg_dsn(_DB_MIGRATION))
            try:
                return {r["id"]: (r["status"], r["fehler"]) for r in await conn.fetch(
                    "SELECT id, status, result->>'error' AS fehler FROM loadtest_runs")}
            finally:
                await conn.close()

        asyncio.run(zeilen_anlegen())
        pg_utils.upgrade_db(_DB_MIGRATION, "head")
        zeilen = asyncio.run(lesen())
    finally:
        pg_utils.drop_db(_DB_MIGRATION)
    assert zeilen["lt-neu"] == ("running", None)
    assert zeilen["lt-alt"][0] == "failed" and zeilen["lt-alt"][1]


def test_beim_herunterfahren_enden_die_eigenen_laeufe_als_failed(test_db) -> None:
    """Gesamt-Review Paket 17 (C2): Zeile zuerst, dann der Task — wie beim Stoppen-Knopf.
    Nur, was in DIESEM Pod registriert ist: ein fremder Lauf läuft weiter."""
    from boerdi.obs.tasks import RUN_TASKS, register_run_task
    from boerdi.services import laeufe_beenden
    from boerdi.services.loadtest import create_run

    async def beende_mit(factory, run_id):
        aufgabe = asyncio.create_task(asyncio.sleep(60))
        register_run_task(run_id, aufgabe)
        try:
            zahl = await laeufe_beenden.beende(factory.kw["bind"])
            await asyncio.gather(aufgabe, return_exceptions=True)
            return zahl, aufgabe.cancelled()
        finally:
            aufgabe.cancel()
            RUN_TASKS.clear()

    async def szenario(factory):
        async with factory() as s:
            await create_run(s, "lt-eigen", _PROFIL)
        await _eval_zeile(factory, "eval-x", erstellt=datetime.now(UTC))
        erste = await beende_mit(factory, "lt-eigen")        # eval-x gehört einem anderen Pod
        eval_dazwischen = await _status(factory, "eval_runs", "eval-x")
        zweite = await beende_mit(factory, "eval-x")
        async with factory() as s:
            lt = tuple((await s.execute(text(
                "SELECT status, result->>'error' FROM loadtest_runs WHERE id = 'lt-eigen'"))).one())
            ev = tuple((await s.execute(text(
                "SELECT status, error_message, completed_at FROM eval_runs "
                "WHERE id = 'eval-x'"))).one())
        return erste, eval_dazwischen, zweite, lt, ev

    erste, eval_dazwischen, zweite, lt, ev = _lauf(szenario)
    assert erste == (1, True) and zweite == (1, True)
    assert eval_dazwischen == "running"
    assert lt[0] == "failed" and "Pod beendet" in lt[1]
    assert ev[0] == "failed" and "Pod beendet" in ev[1] and ev[2] is not None
