"""Review TG-3a–c, Testlücke: ein großer Teil ``struktur`` (500 lange Dateinamen, weit über 8 KB)
gegen das echte Postgres — er liegt in der Ablage des Vorgangs (``vorgang_ablage``), wird ganz
gelesen und geht beim Start eines Ablaufs mit (``BEREITSTELLUNG``, ``zug._bereitstellung``)."""

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

_DB = "boerdi_r3_struktur_gross"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _gross() -> dict:
    dateien = [{"i": i, "name": f"{i:04d}" + "n" * 100 + ".pdf", "endung": "pdf",
                "groesse": 10, "rolle": "inhalt"} for i in range(500)]
    return {"struktur": {"name": "P", "dateien": 500, "alle_dateien": 500, "kinder": [],
                         "dateiliste": dateien},
            "zahlen": {"ordner": 1, "dateien": 500}, "warnungen": [], "block_id": "b0000001"}


def test_ein_grosser_teil_struktur_liegt_in_der_ablage_und_geht_beim_start_mit(db_url):
    from boerdi.services import vorgaenge
    from boerdi.services.ablauf import zug

    async def ablauf():
        engine = create_async_engine(db_url)
        sitzungen = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sitzungen() as s:
                v = await vorgaenge.anlegen(s, aufrufer="sitzung:s-gross-0001",
                                            session_id=None, titel="T",
                                            zweck="bereitstellen", tage=3)
                v = await vorgaenge.teil_setzen(s, v, "struktur", typ="wlo.auswahl@1",
                                                wert=_gross(), zusammenfassung="500 Dateien",
                                                tage=3)
                await s.commit()
                eintrag = v.akte["teile"]["struktur"]
                abgelegt = (await s.execute(text(
                    "SELECT count(*) FROM vorgang_ablage WHERE vorgang_id = :v "
                    "AND schluessel LIKE 'struktur@%'"), {"v": v.id})).scalar_one()
                gelesen = await vorgaenge.teil_wert(s, v, "struktur")
                mit = await zug._bereitstellung(s, v)
                neu = await vorgaenge.anlegen(s, aufrufer="sitzung:s-gross-0001",
                                              session_id=None, titel="Neu",
                                              zweck="bereitstellen", tage=3)
                for name, typ, wert, kurz in mit:
                    neu = await vorgaenge.teil_setzen(s, neu, name, typ=typ, wert=wert,
                                                      zusammenfassung=kurz, tage=3)
                await s.commit()
                im_neuen = await vorgaenge.teil_wert(s, neu, "struktur")
            return eintrag, abgelegt, gelesen, mit, im_neuen
        finally:
            await engine.dispose()

    eintrag, abgelegt, gelesen, mit, im_neuen = asyncio.run(ablauf())
    assert "ref" in eintrag and "wert" not in eintrag       # über 8 KB: in der Ablage
    assert abgelegt == 1
    assert gelesen == _gross()
    assert [m[0] for m in mit] == ["struktur"] and mit[0][1] == "wlo.auswahl@1"
    assert im_neuen == _gross()
