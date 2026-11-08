"""Paket K1a: Aufträge eines Vorgangs — gegen das echte Postgres (Migration 0019).

Je Vorgang höchstens ein offener Auftrag (ein neuer ersetzt den offenen: ``abgebrochen``); der Stand
wechselt nur von ``laeuft`` weg; mit dem Vorgang gehen seine Aufträge.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_k1_auftraege"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _lauf(db_url, ablauf):
    async def huelle():
        engine = create_async_engine(db_url)
        sitzungen = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sitzungen() as s:
                await s.execute(text("INSERT INTO sessions (session_id) VALUES ('sitzung-k1-0001') "
                                     "ON CONFLICT DO NOTHING"))
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            return await ablauf(sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


async def _vorgang(s):
    from boerdi.services import vorgaenge

    v = await vorgaenge.anlegen(s, aufrufer="person-a", session_id="sitzung-k1-0001",
                                titel="Probe", zweck="probe", tage=3)
    await s.commit()
    return v


def test_anlegen_und_offen_lesen(db_url):
    from boerdi.services.auftraege import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _vorgang(s)
            await ablage.anlegen(s, v.id, job_id="job-1", flow="wlo/volltext", schritt="lesen")
            await s.commit()
            offen = await ablage.offen(s, v.id)
            return offen.job_id, offen.status, offen.schritt

    assert _lauf(db_url, ablauf) == ("job-1", "laeuft", "lesen")


def test_ein_neuer_auftrag_ersetzt_den_offenen(db_url):
    from boerdi.services.auftraege import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _vorgang(s)
            await ablage.anlegen(s, v.id, job_id="job-1", flow="f", schritt="a")
            await ablage.anlegen(s, v.id, job_id="job-2", flow="f", schritt="b")
            await s.commit()
            alle = (await s.execute(text(
                "SELECT job_id, status FROM vorgang_auftraege ORDER BY job_id"))).all()
            return [tuple(r) for r in alle], (await ablage.offen(s, v.id)).job_id

    alle, offen = _lauf(db_url, ablauf)
    assert alle == [("job-1", "abgebrochen"), ("job-2", "laeuft")] and offen == "job-2"


def test_abschliessen_und_mit_dem_vorgang_geloescht(db_url):
    from boerdi.services import vorgaenge
    from boerdi.services.auftraege import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _vorgang(s)
            a = await ablage.anlegen(s, v.id, job_id="job-1", flow="f", schritt="a")
            await ablage.abschliessen(s, a, "fertig")
            await s.commit()
            nach = await ablage.offen(s, v.id)
            await vorgaenge.loeschen(s, v.id, "person-a")
            await s.commit()
            rest = (await s.execute(text("SELECT count(*) FROM vorgang_auftraege"))).scalar()
            return nach, rest

    nach, rest = _lauf(db_url, ablauf)
    assert nach is None and rest == 0


def test_abschliessen_eines_inzwischen_geloeschten_auftrags_wirft_nicht(db_url):
    """Review Q3 (Nachprüfung), Befund 6: „Arbeitsstand löschen“ in einem zweiten Tab nimmt den
    Auftrag per Kaskade mit — das Abschließen im laufenden Zug traf sonst 0 Zeilen
    (``StaleDataError``, 500)."""
    from boerdi.services.auftraege import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _vorgang(s)
            a = await ablage.anlegen(s, v.id, job_id="job-weg", flow="f", schritt="a")
            await s.commit()
            async with sitzungen() as zweiter:
                await zweiter.execute(text("DELETE FROM vorgaenge WHERE id = :v"), {"v": v.id})
                await zweiter.commit()
            await ablage.abschliessen(s, a, "fertig")
            await s.commit()
            return a.status

    assert _lauf(db_url, ablauf) == "fertig"


def test_offene_job_ids_der_besitzerinnen(db_url):
    """Job-Vertrag 2026-11-07: für „Arbeitsstand löschen“ — nur laufende, nur eigene Vorgänge."""
    from boerdi.services import vorgaenge
    from boerdi.services.auftraege import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _vorgang(s)
            fremd = await vorgaenge.anlegen(s, aufrufer="person-b", session_id="sitzung-k1-0001",
                                            titel="Fremd", zweck="probe", tage=3)
            fertig = await ablage.anlegen(s, v.id, job_id="job-alt", flow="f", schritt="a")
            await ablage.abschliessen(s, fertig, "fertig")
            await ablage.anlegen(s, v.id, job_id="job-offen", flow="f", schritt="a")
            await ablage.anlegen(s, fremd.id, job_id="job-fremd", flow="f", schritt="a")
            await s.commit()
            return await ablage.offene_job_ids(s, ["person-a", "sitzung:sitzung-k1-0001"])

    assert _lauf(db_url, ablauf) == ["job-offen"]
