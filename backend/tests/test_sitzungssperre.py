"""Sitzungssperre über alle Kopien (Paket 7, P1 — P5-1, Audit C-H1).

Zwei Züge derselben Sitzung auf zwei Kopien lasen und schrieben
``session_state`` parallel; der letzte gewann (``_pending_write``,
``turn_count``). Die Sperre ist ein Eintrag in ``session_locks`` mit Ablaufzeit:
keine gehaltene Verbindung je Zug, und nach einem Absturz gibt sie sich selbst
frei. Wer sie nicht bekommt, wartet kurz und erfährt dann „beschäftigt“.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from boerdi.services.sitzungssperre import SitzungBeschaeftigt, sitzungssperre
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p1_sperre"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _run(coro):
    """Je Test eine Schleife und darin ein Pool wie im Betrieb: ein frischer
    Verbindungsaufbau dauert hier (Windows, ``localhost``) rund 2 s und spränge
    jedes der kurzen Zeitfenster unten."""
    return asyncio.run(coro)


def test_eine_zweite_sperre_derselben_sitzung_ist_beschaeftigt(db_url):
    async def _ablauf():
        engine = create_async_engine(db_url)
        try:
            async with sitzungssperre(engine, "s-1", warten_s=0.0):
                with pytest.raises(SitzungBeschaeftigt):
                    async with sitzungssperre(engine, "s-1", warten_s=0.3, abfrage_s=0.1):
                        pass
                # Eine andere Sitzung läuft daneben.
                async with sitzungssperre(engine, "s-2", warten_s=0.0):
                    pass
            # Freigegeben: dieselbe Sitzung ist wieder zu haben.
            async with sitzungssperre(engine, "s-1", warten_s=0.0):
                pass
        finally:
            await engine.dispose()
    _run(_ablauf())


def test_wer_wartet_bekommt_die_sperre_nach_der_freigabe(db_url):
    async def _ablauf():
        engine = create_async_engine(db_url)
        reihenfolge: list[str] = []

        async def _erster():
            async with sitzungssperre(engine, "s-3", warten_s=0.0):
                reihenfolge.append("erster an")
                await asyncio.sleep(0.4)
                reihenfolge.append("erster aus")

        async def _zweiter():
            await asyncio.sleep(0.1)
            async with sitzungssperre(engine, "s-3", warten_s=3.0, abfrage_s=0.05):
                reihenfolge.append("zweiter an")

        try:
            await asyncio.gather(_erster(), _zweiter())
        finally:
            await engine.dispose()
        assert reihenfolge == ["erster an", "erster aus", "zweiter an"]
    _run(_ablauf())


def test_eine_verfallene_sperre_wird_uebernommen(db_url):
    """Ein abgestürzter Zug verlängert nicht mehr — nach Ablauf ist sie frei."""
    async def _ablauf():
        engine = create_async_engine(db_url)
        try:
            from sqlalchemy import text
            async with engine.begin() as conn:
                await conn.execute(text(
                    "INSERT INTO session_locks (session_id, owner, expires_at) "
                    "VALUES ('s-4', 'tot', now() - interval '1 second')"))
            async with sitzungssperre(engine, "s-4", warten_s=0.0):
                pass
        finally:
            await engine.dispose()
    _run(_ablauf())


def test_die_verlaengerung_haelt_die_sperre_ueber_den_ablauf_hinaus(db_url):
    async def _ablauf():
        engine = create_async_engine(db_url)
        try:
            async with sitzungssperre(engine, "s-5", warten_s=0.0, ttl_s=1, takt_s=0.2):
                await asyncio.sleep(1.5)   # länger als ttl_s
                with pytest.raises(SitzungBeschaeftigt):
                    async with sitzungssperre(engine, "s-5", warten_s=0.0):
                        pass
        finally:
            await engine.dispose()
    _run(_ablauf())


def test_eine_verlorene_sperre_meldet_die_verlaengerung(db_url, caplog):
    """Review Paket 7, A-8: hing ein Zug länger als ``ttl_s`` ohne Verlängerung
    und eine andere Kopie übernahm, fand die Verlängerung 0 Zeilen — und schwieg."""
    async def _ablauf():
        engine = create_async_engine(db_url)
        try:
            async with sitzungssperre(engine, "s-6", warten_s=0.0, ttl_s=5, takt_s=0.1):
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "UPDATE session_locks SET owner = 'andere-kopie' WHERE session_id = 's-6'"))
                await asyncio.sleep(0.5)
        finally:
            await engine.dispose()
    with caplog.at_level(logging.WARNING, logger="boerdi.services.sitzungssperre"):
        _run(_ablauf())
    # Paket 18C/D: die Sitzung erscheint im Log nur als Kurzkennung.
    from boerdi.obs.log_inhalt import kennung

    meldungen = [r.getMessage() for r in caplog.records if kennung("s-6") in r.getMessage()]
    assert all("s-6" not in m for m in meldungen)
    assert len(meldungen) == 1 and "verloren" in meldungen[0], meldungen
