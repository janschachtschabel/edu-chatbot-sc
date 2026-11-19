"""Paket U1/U2 (Plan 2026-11-17): Grenzen je Sitzung und Rolle der Sitzungsdokumente — gegen das
echte Postgres. Inhalte (Rolle ``inhalt``) liegen in derselben Tabelle wie Strukturdokumente; ihre
Kurzangaben stehen im Befund (keine Migration). Strukturdokument-Lesewege sehen nur Rolle
``struktur``; die Grenze zählt beide."""

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

_DB = "boerdi_paket_u_ablage"
_SID = "sitzung-u-0001"


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
                await s.commit()
            async with sitzungen() as s:
                from boerdi.services.dokumente import ablage

                await ablage.der_sitzung_loeschen(s, _SID)
                await s.commit()
            return await ablauf(sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _neu(s, name, *, rolle="struktur", groesse=10, angaben=None, markdown=None):
    from boerdi.services.dokumente import ablage

    return ablage.speichern(s, session_id=_SID, block_id="b0000001", aufrufer=None, name=name,
                            format="pdf", groesse=groesse, befund={"seiten": 1}, gliederung=[],
                            markdown=markdown or f"# {name}", ttl_h=24, rolle=rolle,
                            angaben=angaben)


@pytest.fixture
def grenzen(monkeypatch):
    from boerdi.services.config_loader import upload as lader

    def setzen(dateien=10, mb=50):
        monkeypatch.setattr(lader, "area", lambda key: {
            "upload": {"lokal_max_dateien": dateien, "lokal_max_mb_gesamt": mb}})
    setzen()
    return setzen


def test_ueber_der_anzahl_wird_abgewiesen_statt_verdraengt(db_url, grenzen):
    from boerdi.services.dokumente import ablage

    grenzen(dateien=2)

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            await _neu(s, "a.pdf")
            await _neu(s, "b.pdf", rolle="inhalt")
            await s.commit()
        async with sitzungen() as s:
            with pytest.raises(ablage.GrenzeErreicht) as fehler:
                await _neu(s, "c.pdf")
            await s.rollback()
            namen = [z.name for z in await ablage.alle_lesbaren(s, _SID, None, rolle=None)]
        return fehler.value.code, namen

    code, namen = _lauf(db_url, ablauf)
    assert code == "grenze_anzahl"
    assert sorted(namen) == ["a.pdf", "b.pdf"]


def test_ueber_der_gesamtgroesse_wird_abgewiesen(db_url, grenzen):
    from boerdi.services.dokumente import ablage

    grenzen(mb=1)
    mib = 1024 * 1024

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            await _neu(s, "a.pdf", groesse=mib // 2)
            await s.commit()
        async with sitzungen() as s:
            with pytest.raises(ablage.GrenzeErreicht) as fehler:
                await _neu(s, "b.pdf", groesse=mib // 2 + 1)
            await s.rollback()
            await _neu(s, "c.pdf", groesse=mib // 2)   # genau bis zur Grenze geht
            await s.commit()
        return fehler.value.code

    assert _lauf(db_url, ablauf) == "grenze_gesamt"


def test_erneutes_hochladen_desselben_dokuments_geht_auch_an_der_grenze(db_url, grenzen):
    from boerdi.services.dokumente import ablage

    grenzen(dateien=1)

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            await _neu(s, "a.pdf")
            await s.commit()
            neu = await _neu(s, "a.pdf")
            await s.commit()
            return neu, [z.id for z in await ablage.alle_lesbaren(s, _SID, None)]

    neu, ids = _lauf(db_url, ablauf)
    assert ids == [neu]


def test_inhalte_tragen_rolle_und_angaben_und_fehlen_in_strukturdokument_wegen(db_url, grenzen):
    from boerdi.services.dokumente import ablage

    angaben = {"titel": "Linsen", "beschreibung": "Sammellinsen", "schlagworte": ["Optik"]}

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            struktur = await _neu(s, "Lehrplan.pdf")
            inhalt = await _neu(s, "Linsen.pdf", rolle="inhalt", angaben=angaben)
            await s.commit()
        async with sitzungen() as s:
            nur_struktur = [z.id for z in await ablage.alle_fuer_aufrufer(s, _SID, None)]
            alle = await ablage.alle_lesbaren(s, _SID, None, rolle=None)
            inhalte = await ablage.alle_lesbaren(s, _SID, None, rolle="inhalt")
            juengstes = await ablage.aktuelles(s, _SID, None)
        return struktur, inhalt, nur_struktur, alle, inhalte, juengstes

    struktur, inhalt, nur_struktur, alle, inhalte, juengstes = _lauf(db_url, ablauf)
    assert nur_struktur == [struktur]
    assert {z.id for z in alle} == {struktur, inhalt}
    assert [z.id for z in inhalte] == [inhalt]
    assert ablage.rolle(inhalte[0]) == "inhalt" and ablage.angaben(inhalte[0]) == angaben
    assert ablage.rolle(next(z for z in alle if z.id == struktur)) == "struktur"
    assert ablage.angaben(next(z for z in alle if z.id == struktur)) is None
    # „das Dokument der Sitzung“ bleibt ein Strukturdokument, auch wenn ein Inhalt jünger ist
    assert juengstes is not None and juengstes.id == struktur
