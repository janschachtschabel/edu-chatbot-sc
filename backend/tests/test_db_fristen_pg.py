"""DB-Fristen je Verbindung (Paket 19, Audit 2026-10-31, M-10).

Es gab kein ``statement_timeout``, kein ``idle_in_transaction_session_timeout``, kein
``lock_timeout`` und kein ``command_timeout``; ``pool_pre_ping`` greift nur beim Ausleihen.
Bei einer Netzpartition ohne RST hing ein Zug unbegrenzt, und eine vergessene Transaktion
hielt ihre Verbindung (und Sperren) bis zum Ende des Prozesses.

Gegen das echte Postgres: die Werte kommen in der Sitzung an, der Server beendet eine
hängende Transaktion, und der lange Lauf (``VACUUM``) bekommt seine eigene Frist.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p19_db_fristen"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _engine(url: str, *, fristen: bool = True, **werte):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=url, **werte), fristen=fristen)


async def _zeige(engine, *namen: str) -> list[str]:
    async with engine.connect() as conn:
        return [(await conn.execute(text(f"SHOW {n}"))).scalar_one() for n in namen]


_NAMEN = ("statement_timeout", "idle_in_transaction_session_timeout", "lock_timeout")


def test_die_fristen_gelten_in_jeder_sitzung(db_url):
    async def ablauf():
        engine = _engine(db_url, db_statement_timeout_s=7, db_idle_in_transaction_timeout_s=11,
                         db_lock_timeout_s=3)
        try:
            return await _zeige(engine, *_NAMEN)
        finally:
            await engine.dispose()

    assert asyncio.run(ablauf()) == ["7s", "11s", "3s"]


def test_ohne_fristen_fuer_die_kommandozeile(db_url):
    async def ablauf():
        engine = _engine(db_url, fristen=False, db_statement_timeout_s=7)
        try:
            return await _zeige(engine, *_NAMEN)
        finally:
            await engine.dispose()

    assert asyncio.run(ablauf()) == ["0", "0", "0"]


def test_der_server_beendet_eine_haengende_transaktion(db_url):
    async def ablauf():
        engine = _engine(db_url, db_idle_in_transaction_timeout_s=0.5)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))  # Transaktion offen
                await asyncio.sleep(1.2)
                with pytest.raises(Exception):  # noqa: B017,PT011 — der Server hat beendet
                    await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    asyncio.run(ablauf())


def test_eine_lange_wartezeit_auf_den_pool_wird_gemeldet(db_url, caplog):
    """Review 19-4: ein ausgeschöpfter Pool war nur an der Fehlerblase zu erkennen."""
    from sqlalchemy.exc import TimeoutError as PoolTimeout

    async def ablauf():
        engine = _engine(db_url, db_pool_size=1, db_max_overflow=0)
        engine.sync_engine.pool._timeout = 0.2
        try:
            async with engine.connect() as erste:
                await erste.execute(text("SELECT 1"))
                with pytest.raises(PoolTimeout):
                    async with engine.connect():
                        pass
        finally:
            await engine.dispose()

    with caplog.at_level("WARNING", logger="boerdi.db.session"):
        asyncio.run(ablauf())
    assert any("Pool" in r.getMessage() and r.levelname == "WARNING" for r in caplog.records)


def test_vacuum_laeuft_ueber_die_anweisungsfrist_hinaus(db_url):
    from boerdi.db.session import make_session_factory
    from boerdi.services.session_admin import optimize_database

    async def ablauf():
        # 100 ms: gemessen 2026-10-31 brauchte VACUUM (ANALYZE) auf der frisch migrierten
        # Datenbank 300–400 ms, die übrigen Abfragen hier je unter 5 ms.
        engine = _engine(db_url, db_statement_timeout_s=0.1, db_lock_timeout_s=3,
                         db_pool_size=1, db_max_overflow=0)
        try:
            async with make_session_factory(engine)() as session:
                ergebnis = await optimize_database(session)
            # Danach gelten wieder die Fristen der Verbindung (dieselbe Verbindung, Pool 1).
            return ergebnis, await _zeige(engine, "statement_timeout", "lock_timeout")
        finally:
            await engine.dispose()

    ergebnis, danach = asyncio.run(ablauf())
    assert ergebnis["after_bytes"] > 0
    assert danach == ["100ms", "3s"]
