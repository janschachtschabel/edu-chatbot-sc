"""Review Q3 (Nachprüfung), gegen das echte Postgres: Arbeitsstand-Schreibwege mit Savepoint.

- Befund 1: der Rückruf ``neu`` liest über den Lader — dessen Freigabe der Verbindung schrieb bisher
  mitten im Savepoint fest (Sperre weg, danach ``InvalidRequestError``); jeder Dateistand und jeder
  Abschluss einer Ablage ging so verloren.
- ``nur_dieser``: ein abgeschlossener Vorgang nimmt den Stand nicht, und es entsteht kein neuer.
- ``alle_loeschen`` lässt die Vorgänge einer anderen Besitzerin stehen.
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

_DB = "boerdi_q3_vorgang_pg"
_SID = "sitzung-q3-pg-0001"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


@pytest.fixture(autouse=True)
def anonym(monkeypatch):
    from boerdi.services import arbeitsstand

    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: False)


def _lauf(db_url, ablauf):
    async def huelle():
        engine = create_async_engine(db_url)
        sitzungen = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sitzungen() as s:
                await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                     "ON CONFLICT DO NOTHING"), {"s": _SID})
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            async with sitzungen() as s:
                return await ablauf(s)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def test_neu_rechnen_ueber_den_lader_speichert(db_url):
    from boerdi.services import arbeitsstand, vorgaenge

    async def ablauf(s):
        entities: dict = {}
        ok1 = await arbeitsstand.teile_speichern(s, _SID, entities,
                                                 [("ablage", "t", {"n": 1}, "z")])

        async def neu():
            wert = await arbeitsstand.teil_lader(s, _SID, entities)("ablage")
            return [("ablage", "t", {"n": wert["n"] + 1}, "z")]

        ok2 = await arbeitsstand.teile_speichern(s, _SID, entities, [], neu=neu)
        v = await vorgaenge.lesen(s, entities[arbeitsstand.VERWEIS]["id"], f"sitzung:{_SID}")
        return ok1, ok2, await vorgaenge.teil_wert(s, v, "ablage")

    assert _lauf(db_url, ablauf) == (True, True, {"n": 2})


def test_nur_dieser_schreibt_nicht_in_einen_neuen_vorgang(db_url):
    from boerdi.services import arbeitsstand

    async def ablauf(s):
        entities: dict = {}
        await arbeitsstand.teile_speichern(s, _SID, entities, [("ablage", "t", {"n": 1}, "z")])
        await s.execute(text("UPDATE vorgaenge SET status = 'fertig'"))
        await s.commit()

        async def neu():
            return [("ablage", "t", {"n": 2}, "z")]

        ok = await arbeitsstand.teile_speichern(s, _SID, entities, [], neu=neu, nur_dieser=True)
        zahl = (await s.execute(text("SELECT count(*) FROM vorgaenge"))).scalar_one()
        return ok, zahl

    assert _lauf(db_url, ablauf) == (False, 1)


def test_alle_loeschen_nur_fuer_die_eigene_besitzerin(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(s):
        for wer in ("person-a", "person-a", "person-b"):
            await vorgaenge.anlegen(s, aufrufer=wer, session_id=None, titel="T", zweck="z", tage=3)
        await s.commit()
        zahl = await vorgaenge.alle_loeschen(s, "person-a")
        await s.commit()
        rest = (await s.execute(text("SELECT aufrufer FROM vorgaenge"))).scalars().all()
        return zahl, rest

    assert _lauf(db_url, ablauf) == (2, ["person-b"])
