"""Migration 0016 (Paket 18C/D, Phase 1): die Trace-ID je Zug in der Datenbank.

Aus einer Logzeile und aus der Fehlernummer einer Blase soll der Weg zum Zug im Studio führen.
Dafür tragen Nachricht, Qualitäts- und Sicherheitsprotokoll die Trace-ID der Anfrage; gesucht
wird nach dem Präfix der Fehlernummer, deshalb ``text_pattern_ops`` (``LIKE 'abc%'`` nutzt den
Index auch unter einer Sortierfolge, die nicht ``C`` ist).
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_p18_trace_id_test"
_DSN = pg_utils.asyncpg_dsn(_DB)

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_TABELLEN = ("messages", "quality_logs", "safety_logs")


def _alembic() -> Config:
    cfg = Config(str(pg_utils.BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(pg_utils.BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_utils.sqlalchemy_url(_DB))
    return cfg


async def _sql(sql: str, *args):
    conn = await asyncpg.connect(_DSN)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def _spalten() -> dict[str, str]:
    zeilen = asyncio.run(_sql(
        "SELECT table_name, is_nullable FROM information_schema.columns "
        "WHERE column_name = 'trace_id' AND table_name = ANY($1::text[])", list(_TABELLEN)))
    return {z[0]: z[1] for z in zeilen}


def _index() -> str | None:
    zeilen = asyncio.run(_sql(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_messages_trace_id'"))
    return zeilen[0][0] if zeilen else None


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB, "0015")
    pg_utils.upgrade_db(_DB, "head")
    yield
    pg_utils.drop_db(_DB)


def test_drei_tabellen_tragen_die_trace_id_nullable(db):
    # NULL bleibt erlaubt: Hintergrundläufe und Altbestand haben keine Anfrage.
    assert _spalten() == {t: "YES" for t in _TABELLEN}


def test_praefixsuche_hat_ihren_index(db):
    definition = _index()
    assert definition is not None
    assert "messages" in definition and "text_pattern_ops" in definition


def test_rueckweg(db):
    command.downgrade(_alembic(), "0015")
    try:
        assert _spalten() == {}
        assert _index() is None
    finally:
        command.upgrade(_alembic(), "head")
