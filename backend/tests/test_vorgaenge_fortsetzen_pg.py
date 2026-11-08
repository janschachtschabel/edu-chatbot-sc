"""Paket K2a gegen das echte Postgres: Frist, Verdrängen und Gespräch eines wartenden Auftrags.

- **Frist (V-4):** Wartet der Lauf auf einen Auftrag, hält der Vorgang bis :data:`vorgaenge.
  WARTET_AUFTRAG_TAGE` (Job bis 24 h, danach 7 Tage Ein- und Ausgaben bei der b-api), höchstens
  :data:`vorgaenge.HOECHSTENS_TAGE` — auch wenn ein Lesen oder ein neuer Teil die Frist neu setzt.
- **Verdrängen** lässt wartende Aufträge aus (ihr Job liefe bei der b-api sonst besitzerlos weiter).
- **Gespräch:** Startet ein Auftrag, merkt sich der Vorgang das Gespräch, in dem er lief; ``offene``
  nennt es der Besitzerin, außer dem aktuellen.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from boerdi.services import vorgaenge
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_k2a_vorgaenge_pg"
_A = "sitzung-k2a-pg-aaaa"
_B = "sitzung-k2a-pg-bbbb"
_WER = "person-k2a"


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
                for sid in (_A, _B):
                    await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                         "ON CONFLICT DO NOTHING"), {"s": sid})
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            async with sitzungen() as s:
                return await ablauf(s)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


async def _neu(s, *, sitzung=_A, status="aktiv", lauf=None):
    v = await vorgaenge.anlegen(s, aufrufer=_WER, session_id=sitzung, titel="Lesen",
                                zweck="ablauf", tage=3)
    return await vorgaenge.lauf_setzen(s, v, lauf, status=status, tage=3)


def _tage(v) -> float:
    return (v.verfaellt_am - datetime.now(UTC)) / timedelta(days=1)


_WARTET = {"ablauf": "lesen", "status": "wartet_auftrag"}


def test_ein_wartender_auftrag_haelt_den_vorgang_laenger(db_url):
    async def ablauf(s):
        v = await _neu(s, status="wartet_auftrag", lauf=_WARTET)
        nach_start = _tage(v)
        await vorgaenge.beruehren(s, v.id, tage=3)              # ein Lesen setzt die Frist neu
        nach_lesen = _tage(await vorgaenge.lesen(s, v.id, _WER))
        v = await vorgaenge.teil_setzen(s, v, "notiz", typ="text", wert="x",
                                        zusammenfassung="x", tage=3)
        nach_teil = _tage(v)
        v = await vorgaenge.lauf_setzen(s, v, {**_WARTET, "status": "fertig"}, status="aktiv",
                                        tage=3)
        return nach_start, nach_lesen, nach_teil, _tage(v)

    nach_start, nach_lesen, nach_teil, nach_ende = _lauf(db_url, ablauf)
    for wert in (nach_start, nach_lesen, nach_teil):
        assert vorgaenge.WARTET_AUFTRAG_TAGE - 0.1 < wert <= vorgaenge.WARTET_AUFTRAG_TAGE
    assert 2.9 < nach_ende <= 3                     # abgeholt: wieder die gewöhnliche Frist


def test_die_frist_bleibt_unter_der_obergrenze(db_url):
    async def ablauf(s):
        v = await _neu(s)
        v = await vorgaenge.lauf_setzen(s, v, _WARTET, status="wartet_auftrag", tage=60)
        return _tage(v)

    assert _lauf(db_url, ablauf) <= vorgaenge.HOECHSTENS_TAGE


def test_verdraengen_laesst_wartende_auftraege_aus(db_url):
    async def ablauf(s):
        wartend = await _neu(s, status="wartet_auftrag", lauf=_WARTET)
        for _ in range(vorgaenge.MAX_JE_PERSON + 1):
            await _neu(s)
        zeilen = await s.execute(text("SELECT id, status FROM vorgaenge"))
        return wartend.id, {z.id: z.status for z in zeilen}

    wartend, alle = _lauf(db_url, ablauf)
    assert wartend in alle and len(alle) == vorgaenge.MAX_JE_PERSON


def test_offene_nennen_das_gespraech_des_auftrags(db_url):
    async def ablauf(s):
        v = await _neu(s, sitzung=_A, status="wartet_auftrag", lauf=_WARTET)
        await vorgaenge.sitzung_setzen(s, v.id, _B)             # der Auftrag lief in Gespräch B
        await _neu(s, sitzung=_A)                               # aktiv, wartet auf nichts
        await _neu(s, sitzung=None, status="wartet_person", lauf={"status": "wartet"})
        von_a = await vorgaenge.offene(s, _WER, ohne=_A)
        von_b = await vorgaenge.offene(s, _WER, ohne=_B)
        fremd = await vorgaenge.offene(s, "jemand-anderes", ohne=_A)
        return [(o.session_id, o.status) for o in von_a], von_b, fremd

    von_a, von_b, fremd = _lauf(db_url, ablauf)
    assert von_a == [(_B, "wartet_auftrag")]
    assert von_b == [] and fremd == []
