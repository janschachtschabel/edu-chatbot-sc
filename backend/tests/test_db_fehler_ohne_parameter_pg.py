"""Paket 18C/D (2.8): Datenbankfehler tragen ihre Parameter nicht ins Log.

SQLAlchemy hängt an jede Fehlermeldung ``[parameters: …]`` an — beim Speichern einer
Nachricht also deren Text. Die Meldung landet über ``logger.exception`` im Log (etwa vor der
Fehlerblase). ``hide_parameters`` lässt die Werte weg; Anweisung und Fehlerart bleiben.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p18_db_fehler_test"


@pytest.fixture(scope="module", autouse=True)
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


def _fremdschluessel_fehler() -> IntegrityError:
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    # Als Variablen: im Traceback stünde sonst die Quelltextzeile samt Werten.
    werte = {"s": "bb-fehlt", "c": "Meine Frage KANARIE7Q"}

    async def szenario() -> IntegrityError:
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))
        try:
            async with engine.connect() as conn:
                # Keine Sitzung „bb-fehlt“ → Fremdschlüssel verletzt.
                await conn.execute(
                    text("INSERT INTO messages (session_id, role, content, cards, debug) "
                         "VALUES (:s, 'user', :c, '[]', '{}')"), werte)
        except IntegrityError as fehler:
            return fehler
        finally:
            await engine.dispose()
        raise AssertionError("kein Fehler")

    return asyncio.run(szenario())


def test_ein_datenbankfehler_nennt_die_nachricht_nicht():
    meldung = str(_fremdschluessel_fehler())
    assert "messages" in meldung                 # Anweisung bleibt
    assert "KANARIE7Q" not in meldung


def test_auch_das_detail_der_datenbank_steht_nicht_im_log():
    """Review Phase 2: Postgres hängt ``DETAIL:`` an — beim Fremdschlüssel den Schlüssel, hier
    die Sitzungs-ID, bei NOT NULL/CHECK die ganze Zeile. ``hide_parameters`` erreicht das nicht;
    die Formatierer schwärzen es in Meldung und Traceback."""
    import logging

    from boerdi.obs.log_format import JsonFormatter, text_formatter

    fehler = _fremdschluessel_fehler()
    assert "bb-fehlt" in str(fehler) and "DETAIL" in str(fehler)   # sonst prüfte der Test nichts
    satz = logging.LogRecord("boerdi.api.chat", logging.ERROR, __file__, 1,
                             "chat endpoint unhandled exception: %s", (fehler,),
                             (type(fehler), fehler, fehler.__traceback__))
    satz.trace_id = "-"  # setzt im Betrieb ``TraceIdFilter``
    for formatierer in (JsonFormatter(), text_formatter()):
        zeile = formatierer.format(satz)
        assert "bb-fehlt" not in zeile and "violates foreign key" in zeile
