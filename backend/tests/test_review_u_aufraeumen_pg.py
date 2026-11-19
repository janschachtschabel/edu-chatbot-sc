"""Review Paket U (19.11.), MAJOR 2 (Datenschutz) und MAJOR 3 (Belegung) — gegen das echte Postgres.

Löschen, Ersetzen und Ablauf eines hier im Chat gelesenen Inhalts setzen seine Einträge im Teil
``metadaten`` jedes Vorgangs (auch eines mitgenommenen) auf „nur Name“ zurück: ohne die
Kurzangaben des LLM, ohne ``upload_id``, ``lesbar: false`` — inline und in der Ablage (groß).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_review_u_aufraeumen"
_SID = "sitzung-review-u-01"
_GEHEIM = "Sammellinsen in der Brille"


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
                # jeder Test beginnt leer (die Datenbank gilt je Modul; je Person höchstens drei
                # Vorgänge — ältere wichen sonst mitten im Test)
                for tabelle in ("dokument_uploads", "vorgaenge"):
                    await s.execute(text(f"DELETE FROM {tabelle} WHERE session_id = :s"),
                                    {"s": _SID})
                await s.commit()
            return await ablauf(sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _inhalt(s, name="Linsen.pdf"):
    from boerdi.services.dokumente import ablage

    return ablage.speichern(s, session_id=_SID, block_id="b0000001", aufrufer=None, name=name,
                            format="pdf", groesse=10, befund={"seiten": 1}, gliederung=[],
                            markdown=f"# {name}", ttl_h=24, rolle="inhalt",
                            angaben={"titel": "Linsen im Alltag", "beschreibung": _GEHEIM,
                                     "schlagworte": ["Optik"], "fach": "Physik"})


def _metadaten(kennung: str, viele: int = 0) -> dict:
    """Ein Teil wie nach ``arbeitsstand._speichern`` — mit ``viele`` weiteren, nicht gelesenen
    Einträgen wird er groß (Ablage statt Akte)."""
    inhalte = [{"i": 0, "rolle": "inhalt", "titel": "Linsen im Alltag", "beschreibung": _GEHEIM,
                "schlagworte": ["Optik"], "faecher": ["Physik"], "lesbar": True,
                "upload_id": kennung}]
    inhalte += [{"i": n, "rolle": "inhalt", "titel": f"Datei mit langem Namen {n}" * 3,
                 "lesbar": False} for n in range(1, viele + 1)]
    return {"format": "wlo.metadaten@1", "quelle": "chatbot", "block_id": "b0000001",
            "titel": f"Inhalte aus {len(inhalte)} Dateien (1 gelesen)", "fehlend": [],
            "inhalte": inhalte}


_STRUKTUR = {"block_id": "b0000001", "zahlen": {"ordner": 1, "dateien": 1, "inhalte": 1},
             "warnungen": [], "struktur": {"name": "Unterlagen", "dateien": 1, "kinder": [],
                                           "dateiliste": [{"i": 0, "name": "Linsen_Gesetz.pdf",
                                                           "endung": "pdf", "groesse": 10,
                                                           "rolle": "inhalt"}]}}


async def _vorgang(s, kennung: str, viele: int = 0):
    from boerdi.services import vorgaenge

    v = await vorgaenge.anlegen(s, aufrufer=f"sitzung:{_SID}", session_id=_SID, titel="T",
                                zweck="bereitstellen", tage=3)
    v = await vorgaenge.teil_setzen(s, v, "struktur", typ="wlo.auswahl@1", wert=_STRUKTUR,
                                    zusammenfassung="1 Datei", tage=3)
    return await vorgaenge.teil_setzen(s, v, "metadaten", typ="wlo.metadaten@1",
                                       wert=_metadaten(kennung, viele),
                                       zusammenfassung="1 Inhalte, 1 gelesen", tage=3)


async def _metadaten_wert(s, vid):
    from boerdi.db.models import Vorgang
    from boerdi.services import vorgaenge

    v = await s.get(Vorgang, vid, populate_existing=True)
    return v.akte["teile"]["metadaten"], await vorgaenge.teil_wert(s, v, "metadaten")


def _nur_name(eintrag: dict, wert: dict) -> None:
    assert eintrag["version"] == 2
    e = wert["inhalte"][0]
    assert e == {"i": 0, "rolle": "inhalt", "titel": "Linsen Gesetz", "lesbar": False,
                 "beschreibung": "Ordner: Unterlagen"}
    assert _GEHEIM not in str(wert) and "Linsen im Alltag" not in str(wert)
    assert "upload_id" not in str(wert)


def test_loeschen_setzt_den_eintrag_auf_nur_name_auch_im_mitgenommenen_vorgang(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _inhalt(s)
            v1 = await _vorgang(s, kennung)
            v2 = await _vorgang(s, kennung)          # wie von ``zug._bereitstellung`` mitgenommen
            await s.commit()
            await ablage.loeschen(s, _SID, kennung)
            await s.commit()
            return [await _metadaten_wert(s, v.id) for v in (v1, v2)]

    for eintrag, wert in _lauf(db_url, ablauf):
        _nur_name(eintrag, wert)
        assert eintrag["zusammenfassung"] == "1 Inhalte, 0 gelesen"


def test_ein_grosser_teil_in_der_ablage_wird_ebenso_bereinigt(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _inhalt(s)
            v = await _vorgang(s, kennung, viele=120)
            assert "ref" in v.akte["teile"]["metadaten"]          # groß: in der Ablage
            await s.commit()
            await ablage.loeschen(s, _SID, kennung)
            await s.commit()
            eintrag, wert = await _metadaten_wert(s, v.id)
            alte = (await s.execute(text(
                "SELECT count(*) FROM vorgang_ablage WHERE vorgang_id = :v "
                "AND schluessel = 'metadaten@1'"), {"v": v.id})).scalar_one()
            return eintrag, wert, alte

    eintrag, wert, alte = _lauf(db_url, ablauf)
    assert alte == 0                                  # die alte Fassung ist weg
    assert eintrag["version"] == 2 and len(wert["inhalte"]) == 121
    assert wert["inhalte"][0]["lesbar"] is False and _GEHEIM not in str(wert)


def test_ersetzen_raeumt_die_angaben_des_alten_dokuments(db_url):
    async def ablauf(sitzungen):
        async with sitzungen() as s:
            alt = await _inhalt(s)
            v = await _vorgang(s, alt)
            await s.commit()
            await _inhalt(s)                                  # dasselbe Dokument noch einmal
            await s.commit()
            return await _metadaten_wert(s, v.id)

    _nur_name(*_lauf(db_url, ablauf))


def test_der_aufbewahrungslauf_raeumt_abgelaufene_und_verwaiste(db_url):
    from boerdi.services.dokumente import ablage

    verwaist = "00000000-0000-4000-8000-0000000000bb"

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            kennung = await _inhalt(s)
            v1 = await _vorgang(s, kennung)
            v2 = await _vorgang(s, verwaist)                  # Dokument nie (mehr) da
            await s.execute(text("UPDATE dokument_uploads SET verfaellt_am = :t WHERE id = :k"),
                            {"t": datetime.now(UTC) - timedelta(minutes=1), "k": kennung})
            await s.commit()
        await ablage.verfallene_loeschen(sitzungen, datetime.now(UTC))
        async with sitzungen() as s:
            return [await _metadaten_wert(s, v.id) for v in (v1, v2)]

    for eintrag, wert in _lauf(db_url, ablauf):
        _nur_name(eintrag, wert)


def test_ein_anderer_inhalt_bleibt_gelesen(db_url):
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            weg = await _inhalt(s, "a.pdf")
            bleibt = await _inhalt(s, "b.pdf")
            v = await _vorgang(s, bleibt)
            await s.commit()
            await ablage.loeschen(s, _SID, weg)
            await s.commit()
            return bleibt, await _metadaten_wert(s, v.id)

    bleibt, (eintrag, wert) = _lauf(db_url, ablauf)
    assert eintrag["version"] == 1 and wert["inhalte"][0]["upload_id"] == bleibt


def test_major3_die_belegung_zaehlt_nur_nicht_abgelaufene(db_url):
    """Review U, MAJOR 3: was die Sitzung für „Hier im Chat“ schon hält (beide Rollen)."""
    from boerdi.services.dokumente import ablage

    async def ablauf(sitzungen):
        async with sitzungen() as s:
            leer = await ablage.belegung(s, _SID)
            a = await _inhalt(s, "a.pdf")
            await _inhalt(s, "b.pdf")
            await s.execute(text("UPDATE dokument_uploads SET verfaellt_am = :t WHERE id = :k"),
                            {"t": datetime.now(UTC) - timedelta(minutes=1), "k": a})
            await s.commit()
            return leer, await ablage.belegung_lader(s, _SID)()

    leer, danach = _lauf(db_url, ablauf)
    assert leer == (0, 0) and danach == (1, 10)
