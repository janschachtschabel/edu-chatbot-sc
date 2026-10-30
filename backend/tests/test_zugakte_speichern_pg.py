"""Paket 18C/D, Phase 1 (1.7): die Zugakte landet im Diagnoseteil der gespeicherten Antwort.

Gelesen aus dem Kontext wie die Trace-ID: jeder Weg, der eine Antwort speichert (Normalweg,
früh endende Züge, Fehlerblase), bekommt sie ohne eigenen Code. Auch der zweite Schreibvorgang
(``finalize_message``) behält sie — er ersetzt den Diagnoseteil ganz.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text

from boerdi.services import zugakte as za
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p18_zugakte_speichern_test"


@pytest.fixture(scope="module", autouse=True)
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


def _lauf(fn):
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.services.db_sessions import get_or_create_session
    from boerdi.settings import Settings

    async def szenario():
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))
        try:
            async with make_session_factory(engine)() as session:
                await session.execute(text("TRUNCATE messages, sessions RESTART IDENTITY CASCADE"))
                await session.commit()
                await get_or_create_session(session, "bb-z")
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(szenario())


async def _debug_von(session, message_id):
    from boerdi.db.models import ChatMessage

    return (await session.execute(
        select(ChatMessage.debug).where(ChatMessage.id == message_id))).scalar_one()


def _akte_mit_aufruf() -> za.Zugakte:
    akte = za.binde_zugakte()
    akte.werkzeug("search_wlo_content", argumente_eingang={"query": "Optik"},
                  argumente_gesendet={"query": "Optik"}, status="ok", aus_cache=False,
                  dauer_ms=5, zeichen=10)
    return akte


def test_die_antwort_traegt_die_zugakte_neben_dem_uebrigen_diagnoseteil():
    from boerdi.services.db_sessions import save_message

    async def fn(session):
        akte = _akte_mit_aufruf()
        debug = {"pattern": "PAT-01"}
        mid = await save_message(session, "bb-z", "assistant", "Antwort", debug=debug)
        return debug, await _debug_von(session, mid), akte.als_dict()

    debug_des_aufrufers, gespeichert, erwartet = _lauf(fn)
    assert gespeichert == {"pattern": "PAT-01", za.SCHLUESSEL: erwartet}
    assert debug_des_aufrufers == {"pattern": "PAT-01"}  # sein Dict bleibt, wie es war


def test_die_frage_der_person_traegt_keine():
    from boerdi.services.db_sessions import save_message

    async def fn(session):
        _akte_mit_aufruf()
        return await _debug_von(session, await save_message(session, "bb-z", "user", "hallo"))

    assert _lauf(fn) == {}


def test_eine_leere_akte_laesst_den_diagnoseteil_wie_er_ist():
    from boerdi.services.db_sessions import save_message

    async def fn(session):
        za.binde_zugakte()
        mid = await save_message(session, "bb-z", "assistant", "A", debug={"pattern": "P"})
        return await _debug_von(session, mid)

    assert _lauf(fn) == {"pattern": "P"}


def test_der_abschluss_behaelt_die_akte_samt_spaeteren_eintraegen():
    from boerdi.services.db_sessions import finalize_message, save_message

    async def fn(session):
        akte = _akte_mit_aufruf()
        mid = await save_message(session, "bb-z", "assistant", "A", debug={"pattern": "P"})
        akte.umschreibung("waechter", original="o", ersatz="e", grund="g")
        assert await finalize_message(session, mid, cards=[], debug={"pattern": "P", "x": 1})
        return await _debug_von(session, mid), akte.als_dict()

    gespeichert, erwartet = _lauf(fn)
    assert gespeichert == {"pattern": "P", "x": 1, za.SCHLUESSEL: erwartet}
    assert gespeichert[za.SCHLUESSEL]["umschreibungen"][0]["art"] == "waechter"


def test_der_verlauf_gibt_die_akte_nur_auf_wunsch_heraus():
    """Ohne Schalter nimmt sie schon die Datenbank heraus: der öffentliche Verlauf zeigt sie
    nicht, und ``setup`` lädt je Zug zwanzig Nachrichten ohne sie (Review Phase 1)."""
    from boerdi.services.db_sessions import get_messages, save_message

    async def fn(session):
        _akte_mit_aufruf()
        await save_message(session, "bb-z", "assistant", "A", debug={"pattern": "P"})
        return (await get_messages(session, "bb-z"),
                await get_messages(session, "bb-z", zugakte=True))

    ohne, mit = _lauf(fn)
    assert ohne[0]["debug"] == {"pattern": "P"}
    assert mit[0]["debug"]["pattern"] == "P" and za.SCHLUESSEL in mit[0]["debug"]
