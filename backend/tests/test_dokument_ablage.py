"""Paket U3-2a: Ablage hochgeladener Dokumente — gegen das echte Postgres (Migration 0017)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_u32_dokument_ablage"


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
                for sid in ("sitzung-eins-0001", "sitzung-zwei-0002"):
                    await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                         "ON CONFLICT DO NOTHING"), {"s": sid})
                await s.commit()
            return await ablauf(sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _neu(s: AsyncSession, sid="sitzung-eins-0001", aufrufer=None, name="Lehrplan.pdf"):
    from boerdi.services.dokumente import ablage

    return ablage.speichern(s, session_id=sid, block_id="b0000001", aufrufer=aufrufer, name=name,
                            format="pdf", groesse=10, befund={"seiten": 1}, gliederung=[],
                            markdown="# A", ttl_h=24)


def test_speichern_lesen_nur_in_derselben_sitzung_und_fuer_denselben_aufrufer(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _neu(s, aufrufer="person-a")
            await s.commit()
        async with sitzungen() as s:
            gleich = await ablage.lesen(s, "sitzung-eins-0001", kennung, "person-a")
            fremd = await ablage.lesen(s, "sitzung-zwei-0002", kennung, "person-a")
            andere = await ablage.lesen(s, "sitzung-eins-0001", kennung, "person-b")
            aktuell = await ablage.aktuelles(s, "sitzung-eins-0001", "person-a")
        return gleich, fremd, andere, aktuell

    gleich, fremd, andere, aktuell = _lauf(db_url, ablauf)
    assert gleich is not None and gleich.markdown == "# A"
    assert fremd is None and andere is None
    assert aktuell is not None and aktuell.id == gleich.id


def test_ein_neues_dokument_ersetzt_das_alte_der_sitzung(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            alt = await _neu(s, sid="sitzung-zwei-0002", name="alt.pdf")
            await s.commit()
            neu = await _neu(s, sid="sitzung-zwei-0002", name="neu.pdf")
            await s.commit()
            return (await ablage.lesen(s, "sitzung-zwei-0002", alt, None),
                    await ablage.lesen(s, "sitzung-zwei-0002", neu, None))

    alt, neu = _lauf(db_url, ablauf)
    assert alt is None and neu is not None and neu.name == "neu.pdf"


def test_abgelaufen_ist_sofort_unlesbar_und_wird_aufgeraeumt(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _neu(s)
            await s.execute(text("UPDATE dokument_uploads SET verfaellt_am = now() - "
                                 "interval '1 h' WHERE id = :k"), {"k": kennung})
            await s.commit()
            lesbar = await ablage.lesen(s, "sitzung-eins-0001", kennung, None)
        geloescht = await ablage.verfallene_loeschen(sitzungen, datetime.now(UTC))
        async with sitzungen() as s:
            rest = (await s.execute(text("SELECT count(*) FROM dokument_uploads WHERE id = :k"),
                                    {"k": kennung})).scalar_one()
        return lesbar, geloescht, rest

    lesbar, geloescht, rest = _lauf(db_url, ablauf)
    assert lesbar is None and geloescht >= 1 and rest == 0


def test_beruehren_verlaengert_und_loeschen_entfernt(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _neu(s)
            await s.commit()
            vorher = (await ablage.lesen(s, "sitzung-eins-0001", kennung, None)).verfaellt_am
            await ablage.beruehren(s, kennung, ttl_h=48)
            await s.commit()
            nachher = (await ablage.lesen(s, "sitzung-eins-0001", kennung, None)).verfaellt_am
            await ablage.loeschen(s, "sitzung-zwei-0002", kennung)   # fremde Sitzung: nichts
            await s.commit()
            bleibt = await ablage.lesen(s, "sitzung-eins-0001", kennung, None)
            await ablage.loeschen(s, "sitzung-eins-0001", kennung)
            await s.commit()
            weg = await ablage.lesen(s, "sitzung-eins-0001", kennung, None)
        return vorher, nachher, bleibt, weg

    vorher, nachher, bleibt, weg = _lauf(db_url, ablauf)
    assert nachher - vorher > timedelta(hours=20)
    assert bleibt is not None and weg is None


def test_mit_der_sitzung_verschwindet_das_dokument(db_url):
    async def ablauf(sitzungen):
        async with sitzungen() as s:
            await s.execute(text("INSERT INTO sessions (session_id) VALUES ('sitzung-weg-00003')"))
            kennung = await _neu(s, sid="sitzung-weg-00003")
            await s.commit()
            await s.execute(text("DELETE FROM sessions WHERE session_id = 'sitzung-weg-00003'"))
            await s.commit()
            return (await s.execute(text("SELECT count(*) FROM dokument_uploads WHERE id = :k"),
                                    {"k": kennung})).scalar_one()

    assert _lauf(db_url, ablauf) == 0


def _vorgang_mit_dokument(s, kennung, sid="sitzung-eins-0001", gross=False):
    from boerdi.services import vorgaenge

    async def anlegen():
        v = await vorgaenge.anlegen(s, aufrufer=f"sitzung:{sid}", session_id=sid, titel="T",
                                    zweck="sammlungsstruktur", tage=3)
        wert = {"ref": f"dokument:{kennung}", "name": "Lehrplan.pdf", "format": "pdf",
                "befund": {"seiten": 1, **({"x": "y" * 9000} if gross else {})}}
        v = await vorgaenge.teil_setzen(s, v, "document", typ="wlo.dokument@1", wert=wert,
                                        zusammenfassung="Lehrplan.pdf, 3 Abschnitte", tage=3)
        return await vorgaenge.teil_setzen(s, v, "draft", typ="t", wert={"a": 1},
                                           zusammenfassung="", tage=3)
    return anlegen()


def _teile(s, vid):
    return s.execute(text("SELECT akte->'teile' FROM vorgaenge WHERE id = :k"), {"k": vid})


def test_querschnitt_mit_dem_dokument_geht_sein_teil_im_vorgang(db_url):
    """Querschnitts-Review 2026-11-06 (Datenschutz): Name und Befund des Dokuments überdauerten im
    Teil ``document`` dessen 24 h und das Löschen — jetzt gehen sie mit (der Entwurf bleibt)."""
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            geloescht_k = await _neu(s)
            v1 = await _vorgang_mit_dokument(s, geloescht_k)
            await s.commit()
            await ablage.loeschen(s, "sitzung-eins-0001", geloescht_k)
            await s.commit()
            nach_loeschen = (await _teile(s, v1.id)).scalar_one()
        async with sitzungen() as s:
            verfallen_k = await _neu(s, sid="sitzung-zwei-0002")
            v2 = await _vorgang_mit_dokument(s, verfallen_k, sid="sitzung-zwei-0002", gross=True)
            await s.execute(text("UPDATE dokument_uploads SET verfaellt_am = now() - "
                                 "interval '1 h' WHERE id = :k"), {"k": verfallen_k})
            await s.commit()
        await ablage.verfallene_loeschen(sitzungen, datetime.now(UTC))
        async with sitzungen() as s:
            nach_verfall = (await _teile(s, v2.id)).scalar_one()
            reste = (await s.execute(text("SELECT count(*) FROM vorgang_ablage WHERE "
                                          "vorgang_id = :k AND schluessel LIKE 'document@%'"),
                                     {"k": v2.id})).scalar_one()
        return nach_loeschen, nach_verfall, reste

    nach_loeschen, nach_verfall, reste = _lauf(db_url, ablauf)
    assert "document" not in nach_loeschen and "draft" in nach_loeschen
    assert "document" not in nach_verfall and "draft" in nach_verfall and reste == 0


def test_ein_ersetztes_dokument_nimmt_seinen_teil_mit(db_url):
    """Review Q3, Befund 7: ein neues Dokument der Sitzung löscht das alte — dessen Name und Befund
    im Teil ``document`` gehen mit."""

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            alt = await _neu(s)
            v = await _vorgang_mit_dokument(s, alt)
            await s.commit()
            await _neu(s, name="Neu.pdf")
            await s.commit()
            return (await _teile(s, v.id)).scalar_one()

    teile = _lauf(db_url, ablauf)
    assert "document" not in teile and "draft" in teile


def test_ein_inzwischen_neues_dokument_bleibt_beim_entfernen(db_url):
    """Nachprüfung, Befund 5: unter der Sperre geht ``document`` nur, wenn es noch auf eines der
    entfernten Dokumente zeigt."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            neu = await _neu(s, name="Neu.pdf")
            v = await _vorgang_mit_dokument(s, neu)
            await s.commit()
            # gewählt für ein altes Dokument, unter der Sperre trägt der Vorgang schon das neue
            zahl = await vorgaenge._entfernen_unter_sperre(s, v.id, {"dokument:alt-weg"})
            await s.commit()
            return zahl, (await _teile(s, v.id)).scalar_one()

    zahl, teile = _lauf(db_url, ablauf)
    assert zahl is False and "document" in teile


def test_der_aufbewahrungslauf_raeumt_verwaiste_dokument_teile(db_url):
    """Review Q3, Befund 7: ein Teil, dessen Dokument auf anderem Weg ging (Sitzung gelöscht,
    Kaskade), bleibt nicht stehen."""
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            klein = await _vorgang_mit_dokument(s, "00000000-0000-0000-0000-000000000000")
            gross = await _vorgang_mit_dokument(s, "00000000-0000-0000-0000-000000000001",
                                                gross=True)
            await s.commit()
        await ablage.verfallene_loeschen(sitzungen, datetime.now(UTC))
        async with sitzungen() as s:
            reste = (await s.execute(text("SELECT count(*) FROM vorgang_ablage WHERE "
                                          "vorgang_id = :k AND schluessel LIKE 'document@%'"),
                                     {"k": gross.id})).scalar_one()
            return ((await _teile(s, klein.id)).scalar_one(),
                    (await _teile(s, gross.id)).scalar_one(), reste)

    klein, gross, reste = _lauf(db_url, ablauf)
    assert "document" not in klein and "draft" in klein
    assert "document" not in gross and reste == 0
