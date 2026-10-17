"""Aufbewahrungsfristen (Paket 8, A — P5-4, Nutzer-Entscheide 2026-10-09).

Zwei Bereiche führten ``retention_days`` (Sicherheitsprotokoll in
``01-base/safety-config``, Qualitätsprotokoll in ``01-base/quality-log-config``),
und kein Code las sie: die Einstellung versprach eine Frist, die niemand durchsetzte
(Audit 2026-09-29, §1.5). Dazu kam die Frist der Gesprächsverläufe — Nachrichten und
Sitzungsgedächtnis, ``01-base/privacy-config``, Vorgabe 30 Tage (Nutzer). Gegen die
echte Compose-Postgres, weil das Löschen die SQL ist.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p8_aufbewahrung"


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _fristen(monkeypatch, *, gespraeche=30, sicherheit=90, qualitaet=180):
    """Die drei Bereiche, wie der Config-Store sie liefert (``None`` = Feld fehlt)."""
    from boerdi.services import aufbewahrung

    def _bereich(tage):
        return {"logging": {} if tage is None else {"retention_days": tage}}

    def _area(schluessel):
        assert schluessel == "01-base/privacy-config", schluessel
        return _bereich(gespraeche)

    monkeypatch.setattr(aufbewahrung, "area", _area)
    monkeypatch.setattr(aufbewahrung, "load_safety_config", lambda: _bereich(sicherheit))
    monkeypatch.setattr(aufbewahrung, "load_quality_log_config", lambda: _bereich(qualitaet))


def _lauf(db, szenario):
    async def wrapper():
        from boerdi.db.session import make_engine, make_session_factory
        from boerdi.settings import Settings

        engine = make_engine(Settings(_env_file=None, database_url=db))
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                from sqlalchemy import text
                await s.execute(text("DELETE FROM safety_logs"))
                await s.execute(text("DELETE FROM quality_logs"))
                await s.execute(text("DELETE FROM session_locks"))
                await s.execute(text("DELETE FROM sessions"))
                await s.commit()
            return await szenario(engine, factory)
        finally:
            await engine.dispose()
    return asyncio.run(wrapper())


async def _zeilen(factory, sicherheit_tage: list[int], qualitaet_tage: list[int]) -> None:
    from boerdi.db.models import QualityLog, SafetyLog

    jetzt = datetime.now(UTC)
    async with factory() as s:
        for tage in sicherheit_tage:
            s.add(SafetyLog(data={}, created_at=jetzt - timedelta(days=tage)))
        for tage in qualitaet_tage:
            s.add(QualityLog(data={}, created_at=jetzt - timedelta(days=tage)))
        await s.commit()


async def _anzahl(factory) -> tuple[int, int]:
    from sqlalchemy import func, select

    from boerdi.db.models import QualityLog, SafetyLog

    async with factory() as s:
        return (
            (await s.execute(select(func.count()).select_from(SafetyLog))).scalar_one(),
            (await s.execute(select(func.count()).select_from(QualityLog))).scalar_one(),
        )


def test_der_ueberblick_zaehlt_was_faellig_ist(db, monkeypatch):
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch)

    async def szenario(engine, factory):
        await _zeilen(factory, [100, 95, 10], [200, 10])
        async with factory() as s:
            return await aufbewahrung.ueberblick(s)

    zeilen = {z["bereich"]: z for z in _lauf(db, szenario)}
    assert zeilen["safety_logs"]["tage"] == 90 and zeilen["safety_logs"]["faellig"] == 2
    assert zeilen["quality_logs"]["tage"] == 180 and zeilen["quality_logs"]["faellig"] == 1
    assert zeilen["safety_logs"]["aeltester"] is not None


def test_bereinigen_loescht_nur_was_aelter_als_die_frist_ist(db, monkeypatch):
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch)

    async def szenario(engine, factory):
        await _zeilen(factory, [100, 95, 10], [200, 10])
        geloescht = await aufbewahrung.lauf(engine, factory)
        return geloescht, await _anzahl(factory)

    geloescht, uebrig = _lauf(db, szenario)
    assert geloescht == {"messages": 0, "memory": 0, "session_state": 0,
                         "safety_logs": 2, "quality_logs": 1}
    assert uebrig == (1, 1)


def test_null_tage_heisst_unbegrenzt(db, monkeypatch):
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch, sicherheit=0, qualitaet=0)

    async def szenario(engine, factory):
        await _zeilen(factory, [1000], [1000])
        geloescht = await aufbewahrung.lauf(engine, factory)
        async with factory() as s:
            return geloescht, await aufbewahrung.ueberblick(s), await _anzahl(factory)

    geloescht, ueberblick, uebrig = _lauf(db, szenario)
    assert geloescht == {"messages": 0, "memory": 0, "session_state": 0,
                         "safety_logs": 0, "quality_logs": 0}
    assert all(z["faellig"] == 0 for z in ueberblick)
    assert uebrig == (1, 1)


def test_ohne_eintrag_gilt_die_vorgabe_des_bereichs(db, monkeypatch):
    """Was das Studio als Wert zeigt, gilt auch: fehlt das Feld, die Vorgabe des Modells
    — seit Paket 9 dieselbe wie im Auslieferungsstand (90 bzw. 180 Tage)."""
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch, gespraeche=None, sicherheit=None, qualitaet=None)
    assert [(f.bereich, f.tage) for f in aufbewahrung.fristen()] == [
        ("messages", 30), ("memory", 30), ("session_state", 30), ("safety_logs", 90),
        ("quality_logs", 180),
    ]


def test_in_stapeln_bis_nichts_mehr_faellig_ist(db, monkeypatch):
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch)
    monkeypatch.setattr(aufbewahrung, "STAPEL", 2)

    async def szenario(engine, factory):
        await _zeilen(factory, [100] * 5, [])
        return await aufbewahrung.lauf(engine, factory), await _anzahl(factory)

    geloescht, uebrig = _lauf(db, szenario)
    assert geloescht["safety_logs"] == 5
    assert uebrig == (0, 0)


def test_nur_eine_kopie_bereinigt_zugleich(db, monkeypatch):
    """Läuft der Lauf schon (auf einer anderen Kopie), meldet ``lauf`` ``None``."""
    from boerdi.services import aufbewahrung
    from boerdi.services.sitzungssperre import sitzungssperre

    _fristen(monkeypatch)

    async def szenario(engine, factory):
        await _zeilen(factory, [100], [])
        async with sitzungssperre(engine, aufbewahrung.SPERRE, warten_s=0.0):
            ergebnis = await aufbewahrung.lauf(engine, factory)
        return ergebnis, await _anzahl(factory)

    ergebnis, uebrig = _lauf(db, szenario)
    assert ergebnis is None
    assert uebrig == (1, 0)


async def _gespraech(factory, nachrichten_tage: list[int], gedaechtnis_tage: list[int]) -> None:
    """Eine Sitzung mit Nachrichten und Gedächtnis-Einträgen des genannten Alters."""
    from boerdi.db.models import ChatMessage, ChatSession, MemoryItem, UsageEvent

    jetzt = datetime.now(UTC)
    async with factory() as s:
        s.add(ChatSession(session_id="bb-alt", created_at=jetzt - timedelta(days=400)))
        await s.flush()
        for tage in nachrichten_tage:
            s.add(ChatMessage(session_id="bb-alt", role="user", content="Hallo",
                              created_at=jetzt - timedelta(days=tage)))
        for i, tage in enumerate(gedaechtnis_tage):
            s.add(MemoryItem(session_id="bb-alt", key=f"k{i}", value="v", memory_type="short",
                             created_at=jetzt - timedelta(days=tage)))
        s.add(UsageEvent(session_id="bb-alt", model="m", created_at=jetzt - timedelta(days=200)))
        await s.commit()


async def _gespraech_anzahl(factory) -> dict[str, int]:
    from sqlalchemy import func, select

    from boerdi.db.models import ChatMessage, ChatSession, MemoryItem, UsageEvent

    async with factory() as s:
        return {
            name: (await s.execute(select(func.count()).select_from(modell))).scalar_one()
            for name, modell in (("messages", ChatMessage), ("memory", MemoryItem),
                                 ("sessions", ChatSession), ("usage", UsageEvent))
        }


def test_gespraechsverlaeufe_verfallen_nach_ihrer_frist(db, monkeypatch):
    """Nutzer 2026-10-09: Vorgabe 30 Tage. Nachrichten und Gedächtnis gehen, die Sitzung
    und ihre Verbrauchszahlen bleiben — mit der Sitzung verschwänden die Kosten."""
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch)

    async def szenario(engine, factory):
        await _gespraech(factory, [45, 31, 2], [60, 1])
        async with factory() as s:
            vorher = {z["bereich"]: z["faellig"] for z in await aufbewahrung.ueberblick(s)}
        geloescht = await aufbewahrung.lauf(engine, factory)
        return vorher, geloescht, await _gespraech_anzahl(factory)

    vorher, geloescht, uebrig = _lauf(db, szenario)
    assert vorher["messages"] == 2 and vorher["memory"] == 1
    assert geloescht["messages"] == 2 and geloescht["memory"] == 1
    assert uebrig == {"messages": 1, "memory": 1, "sessions": 1, "usage": 1}


def test_gespraechsverlaeufe_mit_null_tagen_bleiben(db, monkeypatch):
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch, gespraeche=0)

    async def szenario(engine, factory):
        await _gespraech(factory, [500], [500])
        geloescht = await aufbewahrung.lauf(engine, factory)
        return geloescht, await _gespraech_anzahl(factory)

    geloescht, uebrig = _lauf(db, szenario)
    assert geloescht["messages"] == 0 and geloescht["memory"] == 0
    assert uebrig["messages"] == 1 and uebrig["memory"] == 1


def test_der_gespraechsstand_ruhender_sitzungen_verfaellt_mit(db, monkeypatch):
    """Paket 9 (V7, Review Paket 7): Thema, Seitentitel und Suchbegriffe aus dem Gespräch
    standen in ``sessions.entities`` — sie überdauerten die Frist der Verläufe. Mit ihr
    geleert werden jetzt Entities, Signale und Tour-Stand einer Sitzung, die so lange
    ruht; die Sitzung und ihre Verbrauchszahlen bleiben (Nutzer-Entscheid Paket 8)."""
    from sqlalchemy import select

    from boerdi.db.models import ChatSession
    from boerdi.services import aufbewahrung

    _fristen(monkeypatch)
    jetzt = datetime.now(UTC)
    stand = {"entities": {"thema": "Optik", "document_title": "Linsen"},
             "signal_history": ["neugierig"], "tour_state": {"step": "2"}}

    async def szenario(engine, factory):
        async with factory() as s:
            s.add(ChatSession(session_id="bb-ruht", updated_at=jetzt - timedelta(days=40), **stand))
            s.add(ChatSession(session_id="bb-aktiv", updated_at=jetzt - timedelta(days=3), **stand))
            await s.commit()
        async with factory() as s:
            vorher = {z["bereich"]: z["faellig"] for z in await aufbewahrung.ueberblick(s)}
        geloescht = await aufbewahrung.lauf(engine, factory)
        async with factory() as s:
            zeilen = {z.session_id: z for z in (await s.execute(select(ChatSession))).scalars()}
        return vorher, geloescht, zeilen

    vorher, geloescht, zeilen = _lauf(db, szenario)
    assert vorher["session_state"] == 1 and geloescht["session_state"] == 1
    ruht, aktiv = zeilen["bb-ruht"], zeilen["bb-aktiv"]
    assert (ruht.entities, ruht.signal_history, ruht.tour_state) == ({}, [], {})
    assert aktiv.entities == stand["entities"]
    assert set(zeilen) == {"bb-ruht", "bb-aktiv"}


async def _bis_einer_auf_eine_zeile_wartet(factory) -> None:
    """Wartet, bis eine andere Verbindung an einer Zeilensperre hängt — statt einer Pause."""
    from sqlalchemy import text

    for _ in range(200):
        async with factory() as s:
            wartende = (await s.execute(text(
                "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' "
                "AND datname = current_database()"))).scalar_one()
        if wartende:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("das Leeren hat nie auf die Zeile gewartet")


def test_ein_zug_waehrend_des_leerens_behaelt_seinen_stand(db, monkeypatch):
    """Review Paket 9 (MINOR 12): das äußere UPDATE prüfte nur ``session_id IN (…)``.
    Schrieb ein Zug dieselbe Sitzung, während der Stapel auf ihre Zeile wartete, prüfte
    Postgres danach nur diese Bedingung neu — und leerte den frischen Stand, auch einen
    offenen Schreibvorgang."""
    from sqlalchemy import select, update

    from boerdi.db.models import ChatSession
    from boerdi.services import aufbewahrung

    jetzt = datetime.now(UTC)
    frisch = {"_pending_write": {"tool": "wlo_add_to_collection"}}

    async def szenario(engine, factory):
        async with factory() as s:
            s.add(ChatSession(session_id="bb-wacht-auf", updated_at=jetzt - timedelta(days=40),
                              entities={"thema": "Optik"}))
            await s.commit()
        async with factory() as zug:          # der Zug schreibt — und hält die Zeile
            await zug.execute(update(ChatSession)
                              .where(ChatSession.session_id == "bb-wacht-auf")
                              .values(entities=frisch, updated_at=datetime.now(UTC)))
            leeren = asyncio.create_task(aufbewahrung._stand_leeren(
                factory, aufbewahrung.Frist(aufbewahrung.SITZUNGSSTAND, 30), jetzt))
            await _bis_einer_auf_eine_zeile_wartet(factory)
            await zug.commit()
        await leeren
        async with factory() as s:
            return (await s.execute(select(ChatSession.entities)
                                    .where(ChatSession.session_id == "bb-wacht-auf"))).scalar_one()

    assert _lauf(db, szenario) == frisch
