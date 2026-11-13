"""Paket R2-d (Plan 2026-11-12), gegen das echte Postgres: ein anonym begonnener Vorgang geht nach
der Anmeldung auf die Person über — wie das Dokument der Sitzung seit TB-E1. Sonst verlor die
Person beim Anmelden ihren Entwurf, und ein Ablauf mit Voraussetzung ``anmeldung`` begann neu.

- Nur der Vorgang des Verweises DIESER Sitzung (Besitz ``sitzung:<id>``), nur ein offener.
- Ein Verweis einer anderen Person bleibt verborgen stehen (Review Q3, Befund 11).
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

_DB = "boerdi_r2d_vorgang_pg"
_SID = "sitzung-r2d-pg-0001"


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
                await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                     "ON CONFLICT DO NOTHING"), {"s": _SID})
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            async with sitzungen() as s:
                return await ablauf(s)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _anmelden(monkeypatch, person: bool):
    from boerdi.services import arbeitsstand

    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: person)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")


def test_r2d_der_anonyme_vorgang_geht_auf_die_person_ueber(db_url, monkeypatch):
    from boerdi.services import arbeitsstand

    async def ablauf(s):
        entities: dict = {}
        _anmelden(monkeypatch, False)
        await arbeitsstand.teile_speichern(s, _SID, entities, [("draft", "t", {"n": 1}, "z")])
        await s.commit()
        anonym = arbeitsstand.verweis(entities, f"sitzung:{_SID}")
        _anmelden(monkeypatch, True)
        await arbeitsstand.auffrischen(s, _SID, entities)
        person = arbeitsstand.verweis(entities, "person-a")
        besitz = (await s.execute(text("SELECT aufrufer FROM vorgaenge"))).scalars().all()
        return anonym, person, besitz

    anonym, person, besitz = _lauf(db_url, ablauf)
    assert anonym is not None and person is not None and person["id"] == anonym["id"]
    assert besitz == ["person-a"]


def test_r2d_ein_abgeschlossener_oder_fremder_vorgang_bleibt(db_url, monkeypatch):
    from boerdi.services import arbeitsstand

    async def ablauf(s):
        entities: dict = {}
        _anmelden(monkeypatch, False)
        await arbeitsstand.teile_speichern(s, _SID, entities, [("draft", "t", {"n": 1}, "z")])
        await s.execute(text("UPDATE vorgaenge SET status = 'fertig'"))
        await s.commit()
        _anmelden(monkeypatch, True)
        await arbeitsstand.auffrischen(s, _SID, entities)
        return (await s.execute(text("SELECT aufrufer FROM vorgaenge"))).scalars().all()

    assert _lauf(db_url, ablauf) == [f"sitzung:{_SID}"]


def test_review_r2_8_der_vorgang_einer_anderen_sitzung_bleibt(db_url, monkeypatch):
    """Review R2, Befund 8: zeigen die Entities auf den Vorgang einer ANDEREN Sitzung
    (untergeschoben), geht nichts über — ``uebernehmen`` verlangt den Besitz dieser Sitzung."""
    from boerdi.services import arbeitsstand

    async def ablauf(s):
        fremd: dict = {}
        _anmelden(monkeypatch, False)
        await s.execute(text("INSERT INTO sessions (session_id) VALUES ('sitzung-andere-0001') "
                             "ON CONFLICT DO NOTHING"))
        await s.commit()
        await arbeitsstand.teile_speichern(s, "sitzung-andere-0001", fremd,
                                           [("draft", "t", {"n": 1}, "z")])
        await s.commit()
        _anmelden(monkeypatch, True)
        await arbeitsstand.auffrischen(s, _SID, fremd)
        return (await s.execute(text("SELECT aufrufer FROM vorgaenge"))).scalars().all()

    assert _lauf(db_url, ablauf) == ["sitzung:sitzung-andere-0001"]
