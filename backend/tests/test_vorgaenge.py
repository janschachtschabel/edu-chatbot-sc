"""Paket V1: Vorgänge (Arbeitsstand) — gegen das echte Postgres (Migration 0018).

Besitzerin ist ``aufrufer``; höchstens drei je Person, Frist nach letzter Nutzung, abgelaufen sofort
unlesbar; anonyme Vorgänge gehen mit ihrer Sitzung. Teile der Akte haben eine Version, große Teile
und frühere Fassungen liegen in ``vorgang_ablage``; gleichzeitiges Schreiben fällt auf.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_v1_vorgaenge"
_STRUKTUR = {"name": "Physik 7", "dateien": 1, "alle_dateien": 3, "kinder": []}


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
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            return await ablauf(sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _neu(s, aufrufer="person-a", sid="sitzung-eins-0001", titel="Physik 7"):
    from boerdi.services import vorgaenge

    return vorgaenge.anlegen(s, aufrufer=aufrufer, session_id=sid, titel=titel,
                             zweck="sammlungsstruktur", tage=3)


def test_anlegen_und_lesen_nur_fuer_dieselbe_person(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            await s.commit()
            return (await vorgaenge.lesen(s, v.id, "person-a"),
                    await vorgaenge.lesen(s, v.id, "person-b"))

    gleich, fremd = _lauf(db_url, ablauf)
    assert gleich is not None and gleich.status == "aktiv" and fremd is None
    assert gleich.akte == {"format": "wlo.vorgang@1", "teile": {}, "historie": {}, "lauf": None}


def test_teile_haben_versionen_und_eine_historie(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            v = await vorgaenge.teil_setzen(s, v, "structure", typ="wlo.ordnerbaum@1",
                                            wert=_STRUKTUR, zusammenfassung="3 Ordner", tage=3)
            v = await vorgaenge.teil_setzen(s, v, "draft", typ="wlo.sammlungsstruktur@1",
                                            wert={"titel": "A"}, zusammenfassung="1 Punkt", tage=3)
            v = await vorgaenge.teil_setzen(s, v, "draft", typ="wlo.sammlungsstruktur@1",
                                            wert={"titel": "B"}, zusammenfassung="2 Punkte", tage=3)
            await s.commit()
            frisch = await vorgaenge.lesen(s, v.id, "person-a")
            return (frisch, await vorgaenge.teil_wert(s, frisch, "draft"),
                    await vorgaenge.teil_wert(s, frisch, "structure"),
                    await vorgaenge.historie_wert(s, frisch, "draft", 1))

    v, draft, struktur, alt = _lauf(db_url, ablauf)
    assert v.akte["teile"]["draft"]["version"] == 2 and v.akte_version == 3
    assert v.akte["teile"]["draft"]["zusammenfassung"] == "2 Punkte"
    assert draft == {"titel": "B"} and struktur == _STRUKTUR and alt == {"titel": "A"}


def test_grosse_teile_liegen_in_der_ablage(db_url):
    from boerdi.services import vorgaenge

    gross = {"knoten": [{"id": f"k{i}", "titel": "x" * 50} for i in range(400)]}

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            v = await vorgaenge.teil_setzen(s, v, "draft", typ="t", wert=gross,
                                            zusammenfassung="400", tage=3)
            await s.commit()
            frisch = await vorgaenge.lesen(s, v.id, "person-a")
            return frisch.akte["teile"]["draft"], await vorgaenge.teil_wert(s, frisch, "draft")

    eintrag, wert = _lauf(db_url, ablauf)
    assert "wert" not in eintrag and eintrag["ref"] == "draft@1" and wert == gross


def test_gleichzeitiges_schreiben_faellt_auf(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            await s.commit()
        async with sitzungen() as a, sitzungen() as b:
            va = await vorgaenge.lesen(a, v.id, "person-a")
            vb = await vorgaenge.lesen(b, v.id, "person-a")
            await vorgaenge.teil_setzen(a, va, "draft", typ="t", wert=1, zusammenfassung="", tage=3)
            await a.commit()
            with pytest.raises(vorgaenge.VorgangKonflikt):
                await vorgaenge.teil_setzen(b, vb, "draft", typ="t", wert=2, zusammenfassung="",
                                            tage=3)

    _lauf(db_url, ablauf)


def test_hoechstens_drei_je_person_abgeschlossene_weichen_zuerst(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            ids = []
            for i in range(3):
                ids.append((await _neu(s, titel=f"V{i}")).id)
                await s.commit()
            await s.execute(text("UPDATE vorgaenge SET status = 'fertig' WHERE id = :k"),
                            {"k": ids[1]})
            await s.commit()
            ids.append((await _neu(s, titel="V3")).id)
            andere = (await _neu(s, aufrufer="person-b")).id
            await s.commit()
            da = [await vorgaenge.lesen(s, k, "person-a") is not None for k in ids]
            return da, await vorgaenge.lesen(s, andere, "person-b") is not None

    da, andere = _lauf(db_url, ablauf)
    assert da == [True, False, True, True] and andere is True


def test_abgelaufen_unlesbar_aufgeraeumt_anonyme_gehen_mit_der_sitzung(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            alt = await _neu(s)
            anonym = await _neu(s, aufrufer="sitzung:sitzung-zwei-0002", sid="sitzung-zwei-0002")
            person = await _neu(s, aufrufer="person-c", sid="sitzung-zwei-0002")
            await s.execute(text("UPDATE vorgaenge SET verfaellt_am = now() - interval '1 h' "
                                 "WHERE id = :k"), {"k": alt.id})
            await s.commit()
            lesbar = await vorgaenge.lesen(s, alt.id, "person-a")
        geloescht = await vorgaenge.verfallene_loeschen(sitzungen, datetime.now(UTC))
        async with sitzungen() as s:
            weg = await vorgaenge.anonyme_der_sitzung_loeschen(s, "sitzung-zwei-0002")
            await s.commit()
            return (lesbar, geloescht, weg, await vorgaenge.lesen(s, person.id, "person-c"),
                    await vorgaenge.lesen(s, anonym.id, "sitzung:sitzung-zwei-0002"))

    lesbar, geloescht, weg, rest, anonym_da = _lauf(db_url, ablauf)
    assert lesbar is None and geloescht >= 1 and weg == 1
    assert rest is not None and anonym_da is None


def test_loeschen_nur_fuer_die_besitzerin_und_mit_ablage(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            v = await vorgaenge.teil_setzen(s, v, "draft", typ="t", wert={"a": "x" * 9000},
                                            zusammenfassung="", tage=3)
            await s.commit()
            await vorgaenge.loeschen(s, v.id, "person-b")
            await s.commit()
            bleibt = await vorgaenge.lesen(s, v.id, "person-a")
            await vorgaenge.loeschen(s, v.id, "person-a")
            await s.commit()
            ablage = (await s.execute(text("SELECT count(*) FROM vorgang_ablage "
                                           "WHERE vorgang_id = :k"), {"k": v.id})).scalar_one()
            return bleibt, await vorgaenge.lesen(s, v.id, "person-a"), ablage

    bleibt, weg, ablage = _lauf(db_url, ablauf)
    assert bleibt is not None and weg is None and ablage == 0


def test_juengster_offener_vorgang_und_purge_nimmt_die_anonymen_mit(db_url):
    from boerdi.services import vorgaenge
    from boerdi.services.db_sessions import purge_all

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            alt = await _neu(s, titel="alt")
            await s.commit()
            neu = await _neu(s, titel="neu")
            await s.execute(text("UPDATE vorgaenge SET status = 'fertig' WHERE id = :k"),
                            {"k": neu.id})
            await _neu(s, aufrufer="sitzung:sitzung-zwei-0002", sid="sitzung-zwei-0002")
            await s.commit()
            juengster = await vorgaenge.juengster(s, "person-a")
            counts = await purge_all(s, sessions=True)
            await s.commit()
            rest = (await s.execute(text("SELECT count(*) FROM vorgaenge"))).scalar_one()
            return alt.id, juengster.id, counts, rest

    alt, juengster, counts, rest = _lauf(db_url, ablauf)
    assert juengster == alt                       # der abgeschlossene zählt nicht
    assert counts["vorgaenge"] == 1 and rest == 2  # die der Person überdauern


def test_ein_gescheitertes_update_hinterlaesst_kein_phantom(db_url):
    """Review V1, Befund 3: nach einem Konflikt liest dieselbe Sitzung den gespeicherten Stand."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            await s.commit()
        async with sitzungen() as a, sitzungen() as b:
            va = await vorgaenge.lesen(a, v.id, "person-a")
            vb = await vorgaenge.lesen(b, v.id, "person-a")
            await vorgaenge.teil_setzen(a, va, "draft", typ="t", wert=1, zusammenfassung="", tage=3)
            await a.commit()
            with pytest.raises(vorgaenge.VorgangKonflikt):
                await vorgaenge.teil_setzen(b, vb, "draft", typ="t", wert=2, zusammenfassung="",
                                            tage=3)
            frisch = await vorgaenge.lesen(b, v.id, "person-a")
            return frisch.akte_version, await vorgaenge.teil_wert(b, frisch, "draft")

    version, wert = _lauf(db_url, ablauf)
    assert (version, wert) == (1, 1)


def test_der_lauf_steht_in_der_akte_und_setzt_den_status(db_url):
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            lauf = {"ablauf": "probe", "schritt": "frage", "status": "wartet_person"}
            v = await vorgaenge.lauf_setzen(s, v, lauf, status="wartet_person", tage=3)
            await s.commit()
            frisch = await vorgaenge.lesen(s, v.id, "person-a")
            with pytest.raises(vorgaenge.VorgangKonflikt):
                alt = type(frisch)(**{c: getattr(frisch, c) for c in ("id", "akte")},
                                   akte_version=0)
                await vorgaenge.lauf_setzen(s, alt, None, status="fertig", tage=3)
            return frisch

    v = _lauf(db_url, ablauf)
    assert v.akte["lauf"]["schritt"] == "frage" and v.status == "wartet_person"


def test_nur_der_entwurf_behaelt_fruehere_fassungen(db_url):
    """Querschnitts-Review 2026-11-06 (Datensparsamkeit): eine Historie hat nur ``draft`` einen
    Leser — für ``ablage`` (je Datei eine neue Fassung mit Titeln) bleibt keine liegen, auch keine
    große in der Ablage."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            for i in range(3):
                v = await vorgaenge.teil_setzen(s, v, "ablage", typ="wlo.ablage@1",
                                                wert={"titel": f"T{i}", "x": "y" * 9000},
                                                zusammenfassung="", tage=3)
            v = await vorgaenge.teil_setzen(s, v, "draft", typ="t", wert={"a": 1},
                                            zusammenfassung="", tage=3)
            v = await vorgaenge.teil_setzen(s, v, "draft", typ="t", wert={"a": 2},
                                            zusammenfassung="", tage=3)
            await s.commit()
            frisch = await vorgaenge.lesen(s, v.id, "person-a")
            zeilen = (await s.execute(text("SELECT schluessel FROM vorgang_ablage WHERE "
                                           "vorgang_id = :k ORDER BY schluessel"),
                                      {"k": v.id})).scalars().all()
            return frisch, zeilen

    v, zeilen = _lauf(db_url, ablauf)
    assert "ablage" not in v.akte["historie"] and v.akte["historie"]["draft"] == ["draft@1"]
    assert zeilen == ["ablage@3", "draft@1"]


def test_sperren_haelt_die_zeile_bis_zum_ende_der_transaktion(db_url):
    """Review Q1, Befund 3: ``sperren`` ist ``FOR UPDATE`` — ein zweiter Schreiber wartet."""
    import asyncio as _asyncio

    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            v = await _neu(s)
            await s.commit()
        folge: list[str] = []
        async with sitzungen() as a, sitzungen() as b:
            await vorgaenge.sperren(a, v.id, "person-a")
            folge.append("a sperrt")

            async def zweiter():
                await vorgaenge.sperren(b, v.id, "person-a")
                folge.append("b sperrt")
                await b.commit()

            aufgabe = _asyncio.create_task(zweiter())
            await _asyncio.sleep(0.3)
            folge.append("a fertig")
            await a.commit()
            await aufgabe
        return folge

    assert _lauf(db_url, ablauf) == ["a sperrt", "a fertig", "b sperrt"]


def test_eigene_nicht_abgeschlossene_vorgaenge_anderer_gespraeche(db_url):
    """AS-Ud (Plan 2026-11-09 §5j, Ud-1): „Meine Vorgänge“ — aktiv und wartend, nur die eigenen,
    nie abgeschlossene, ohne das aktuelle Gespräch, die jüngsten zuerst."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            hier = await _neu(s, titel="hier")
            await s.commit()
            dort = await _neu(s, sid="sitzung-zwei-0002", titel="dort")
            await s.execute(text("UPDATE vorgaenge SET status = 'wartet_person' WHERE id = :k"),
                            {"k": dort.id})
            await s.commit()
            fertig = await _neu(s, sid="sitzung-zwei-0002", titel="fertig")
            await s.execute(text("UPDATE vorgaenge SET status = 'fertig' WHERE id = :k"),
                            {"k": fertig.id})
            await _neu(s, aufrufer="person-b", sid="sitzung-zwei-0002", titel="fremd")
            await s.commit()
            ohne = [v.titel for v in
                    await vorgaenge.eigene(s, "person-a", ohne="sitzung-eins-0001")]
            alle = [v.titel for v in await vorgaenge.eigene(s, "person-a")]
            return ohne, alle, hier.id

    ohne, alle, _ = _lauf(db_url, ablauf)
    assert ohne == ["dort"]
    assert alle == ["dort", "hier"]


def test_eigene_zeigt_auch_mehr_als_drei_und_schliesst_vor_der_grenze_aus(db_url):
    """Review AS-Ud, Befund 3: wartende Vorgänge weichen nie (``anlegen``) — eine Person kann mehr
    als drei haben; keiner darf aus der Liste fallen. Der Vorgang, auf den das aktuelle Gespräch
    verweist (``ohne_id``), fällt in der Abfrage weg, nicht erst danach."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            ids = []
            for i in range(4):
                v = await _neu(s, sid="sitzung-zwei-0002", titel=f"v{i}")
                if i < 3:          # drei warten — der vierte verdrängt keinen
                    await s.execute(text("UPDATE vorgaenge SET status = 'wartet_auftrag' "
                                         "WHERE id = :k"), {"k": v.id})
                await s.commit()
                ids.append(v.id)
            alle = [v.titel for v in await vorgaenge.eigene(s, "person-a")]
            ohne = [v.titel for v in await vorgaenge.eigene(s, "person-a", ohne_id=ids[3])]
            return alle, ohne

    alle, ohne = _lauf(db_url, ablauf)
    assert sorted(alle) == ["v0", "v1", "v2", "v3"]
    assert sorted(ohne) == ["v0", "v1", "v2"]


def test_alle_sperren_laeuft_auf_postgres(db_url):
    """Q-5: die Sperre vor „Arbeitsstand löschen“ ist gültiges SQL und sperrt nur Zeilen."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            await _neu(s)
            await s.commit()
            await vorgaenge.alle_sperren(s, ["person-a", "sitzung:sitzung-eins-0001"])
            zahl = await vorgaenge.alle_loeschen(s, "person-a")
            await s.commit()
            return zahl

    assert _lauf(db_url, ablauf) == 1



def test_zweites_review_as8a_4_vorgaenge_der_probe_gehen_mit_der_sitzung(db_url):
    """Zweites Review AS-8a, Befund 4: ``probe:<sitzung>`` gehört der Sitzung wie ``sitzung:…``."""
    from boerdi.services import vorgaenge

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            for sid in ("sitzung-drei-0003", "sitzung-vier-0004", "sitzung-fuenf-0005"):
                await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                     "ON CONFLICT DO NOTHING"), {"s": sid})
            eine = await _neu(s, aufrufer="probe:sitzung-drei-0003", sid="sitzung-drei-0003")
            alle = await _neu(s, aufrufer="probe:sitzung-vier-0004", sid="sitzung-vier-0004")
            waise = await _neu(s, aufrufer="probe:sitzung-fuenf-0005", sid="sitzung-fuenf-0005")
            await s.execute(text("UPDATE vorgaenge SET session_id = NULL WHERE id = :k"),
                            {"k": waise.id})
            await s.commit()
            weg_eine = await vorgaenge.anonyme_der_sitzung_loeschen(s, "sitzung-drei-0003")
            weg_alle = await vorgaenge.alle_anonymen_loeschen(s)
            await s.commit()
        await vorgaenge.verfallene_loeschen(sitzungen, datetime.now(UTC))
        async with sitzungen() as s:
            return (weg_eine, weg_alle,
                    [await vorgaenge.lesen(s, v.id, v.aufrufer) for v in (eine, alle, waise)])

    weg_eine, weg_alle, rest = _lauf(db_url, ablauf)
    assert weg_eine == 1 and weg_alle >= 1 and rest == [None, None, None]
