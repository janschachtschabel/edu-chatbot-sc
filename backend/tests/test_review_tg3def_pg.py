"""Review TG-3d–f gegen das echte Postgres: M1 (anonym lesen, anmelden, der Lader mit Vorgang findet
die Dokumente), MINOR 5 (Verdrängung: abgelaufene zuerst, nur desselben Aufrufers, erneutes
Hochladen ersetzt) und zwei gleichzeitige ``speichern`` (Sperre je Sitzung)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_review_tg3def"
_MD = "# A\nx\n# B\ny\n# C\nz"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _lauf(db_url, ablauf, sid: str):
    async def huelle():
        engine = create_async_engine(db_url)
        sitzungen = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sitzungen() as s:
                await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                     "ON CONFLICT DO NOTHING"), {"s": sid})
                await s.execute(text("DELETE FROM dokument_uploads WHERE session_id = :s"),
                                {"s": sid})
                await s.commit()
            return await ablauf(sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _speichern(s, sid, *, name="a.pdf", groesse=10, aufrufer=None):
    from boerdi.domain.dokument_gliederung import gliederung
    from boerdi.services.dokumente import ablage

    abschnitte, _ = gliederung(_MD)
    return ablage.speichern(s, session_id=sid, block_id="b0000001", aufrufer=aufrufer,
                            name=name, format="md", groesse=groesse, befund={},
                            gliederung=[a.__dict__ for a in abschnitte], markdown=_MD, ttl_h=24)


def test_m1_anonym_gelesen_dann_angemeldet_der_lader_mit_vorgang_findet_es(db_url, monkeypatch):
    from boerdi.services.dokumente import stand
    from boerdi.services.dokumente import strukturdokument as leser
    from boerdi.services.dokumente import strukturdokument_teil as sd
    from boerdi.ui_module import dienst_upload

    sid = "sitzung-m1-00001"
    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _speichern(s, sid, name="Lehrplan.md")       # anonym
            await s.commit()
        teil = sd.wert([sd.chatbot(kennung, "Lehrplan.md")])

        async def teile(name):
            return teil if name == sd.TEIL else None

        # jetzt angemeldet
        monkeypatch.setattr(leser, "has_personal_auth", lambda: True)
        monkeypatch.setattr(leser, "aufrufer_kennung", lambda: "person-m1")
        async with sitzungen() as s:
            erg = await stand.laden(s, sid, teile)
        async with sitzungen() as s:
            besitz = (await s.execute(text("SELECT aufrufer FROM dokument_uploads WHERE id = :k"),
                                      {"k": kennung})).scalar_one()
        return erg, besitz

    erg, besitz = _lauf(db_url, ablauf, sid)
    assert isinstance(erg, stand.DokumentStand) and erg.name == "Lehrplan.md"
    assert besitz == "person-m1"                          # TB-E1: übernommen


def test_minor5_abgelaufene_zuerst_und_nur_desselben_aufrufers(db_url):
    from boerdi.db.models import DokumentUpload
    from boerdi.services.dokumente import ablage

    sid = "sitzung-m5-00001"

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            person = await _speichern(s, sid, name="person.md", aufrufer="person-a")
            anonym = [await _speichern(s, sid, name=f"a{n}.md") for n in range(5)]
            await s.commit()
            # das älteste anonyme ist abgelaufen — es geht, keins der lesbaren
            await s.execute(update(DokumentUpload).where(DokumentUpload.id == anonym[0])
                            .values(verfaellt_am=datetime.now(UTC) - timedelta(minutes=1)))
            await s.commit()
            neu = await _speichern(s, sid, name="a5.md")
            await s.commit()
            lesbar = [z.id for z in await ablage.alle_lesbaren(s, sid, None)]
            fuer_person = [z.id for z in await ablage.alle_lesbaren(s, sid, "person-a")]
        return person, anonym, neu, lesbar, fuer_person

    person, anonym, neu, lesbar, fuer_person = _lauf(db_url, ablauf, sid)
    assert lesbar == [*anonym[1:], neu]                    # fünf, keins verdrängt
    assert fuer_person == [person]                          # das der Person bleibt


def test_minor5_erneutes_hochladen_nach_netzfehler_ersetzt_statt_zu_verdraengen(db_url):
    from boerdi.services.dokumente import ablage

    sid = "sitzung-m5-00002"

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            alle = [await _speichern(s, sid, name=f"d{n}.md") for n in range(5)]
            await s.commit()
            # die Antwort zu d4 ging verloren, das Widget lädt dieselbe Datei noch einmal
            wieder = await _speichern(s, sid, name="d4.md")
            await s.commit()
            lesbar = [z.id for z in await ablage.alle_lesbaren(s, sid, None)]
        return alle, wieder, lesbar

    alle, wieder, lesbar = _lauf(db_url, ablauf, sid)
    assert lesbar == [*alle[:4], wieder]                   # d0 bleibt, d4 ist ersetzt


def test_zwei_gleichzeitige_speichern_halten_die_grenze(db_url):
    from boerdi.services.dokumente import ablage

    sid = "sitzung-gl-00001"

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            for n in range(ablage.max_je_sitzung() - 1):
                await _speichern(s, sid, name=f"d{n}.md")
            await s.commit()

        async def einer(name):
            async with sitzungen() as s:
                try:
                    await _speichern(s, sid, name=name)
                except ablage.GrenzeErreicht:
                    await s.rollback()
                    return "abgewiesen"
                await asyncio.sleep(0.05)                   # die Sperre hält bis zum Festschreiben
                await s.commit()
                return "gespeichert"

        ausgang = await asyncio.gather(einer("x.md"), einer("y.md"))
        async with sitzungen() as s:
            return ausgang, [z.name for z in await ablage.alle_lesbaren(s, sid, None)]

    # Paket U1 (altes Soll: beide gespeichert, das älteste verdrängt): unter der Sperre gewinnt
    # einer, der andere wird abgewiesen — nichts wird verdrängt
    ausgang, namen = _lauf(db_url, ablauf, sid)
    assert sorted(ausgang) == ["abgewiesen", "gespeichert"]
    assert len(namen) == ablage.max_je_sitzung() and "d0.md" in namen


def test_nachpruefung_minor3_verschiedene_dokumente_gleichen_namens_bleiben_beide(db_url):
    """Gleicher Name und gleiche Größe, aber anderer Text: kein erneutes Hochladen — beide
    bleiben (Nachprüfung TG-3d–f, MINOR 3)."""
    from boerdi.domain.dokument_gliederung import gliederung
    from boerdi.services.dokumente import ablage

    sid = "sitzung-np3-0001"

    async def ablauf(sitzungen):
        abschnitte, _ = gliederung("# A\nx")
        async with sitzungen() as s:
            ids = []
            for text_ in ("# A\nx", "# B\ny"):                 # gleich lang
                ids.append(await ablage.speichern(
                    s, session_id=sid, block_id="b0000001", aufrufer=None, name="Plan.md",
                    format="md", groesse=6, befund={},
                    gliederung=[a.__dict__ for a in abschnitte], markdown=text_, ttl_h=24))
            await s.commit()
            return ids, [z.id for z in await ablage.alle_lesbaren(s, sid, None)]

    ids, lesbar = _lauf(db_url, ablauf, sid)
    assert lesbar == ids
