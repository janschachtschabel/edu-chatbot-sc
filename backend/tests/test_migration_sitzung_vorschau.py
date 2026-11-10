"""Migration 0022 (Plan 2026-11-10, TB-E2): ``sessions.vorschau`` — vorhandene Marken in
``entities`` (``_probe``, ``_vorschau``) werden übernommen, der Rückweg entfernt die Spalte."""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_tbe2_sitzung_vorschau_test"

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]


def _sql(sql: str) -> list[asyncpg.Record]:
    async def lauf():
        conn = await asyncpg.connect(pg_utils.asyncpg_dsn(_DB))
        try:
            return await conn.fetch(sql)
        finally:
            await conn.close()
    return asyncio.run(lauf())


@pytest.fixture()
def db():
    pg_utils.create_migrated_db(_DB, "0021")
    yield
    pg_utils.drop_db(_DB)


def test_vorhandene_marken_werden_uebernommen(db):
    _sql("INSERT INTO sessions (session_id, entities) VALUES "
         "('bb-probe', '{\"_probe\": true}'), ('bb-vorschau', '{\"_vorschau\": true}'), "
         "('bb-echt', '{}'), ('bb-falsch', '{\"_probe\": \"ja\"}')")
    pg_utils.upgrade_db(_DB, "0022")
    zeilen = {r["session_id"]: r["vorschau"] for r in _sql(
        "SELECT session_id, vorschau FROM sessions")}
    assert zeilen == {"bb-probe": True, "bb-vorschau": True, "bb-echt": False, "bb-falsch": False}
    [index] = _sql("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_sessions_vorschau'")
    assert "WHERE vorschau" in index["indexdef"]


def test_der_rueckweg_entfernt_spalte_und_index(db):
    pg_utils.upgrade_db(_DB, "0022")
    cfg = Config(str(pg_utils.BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(pg_utils.BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_utils.sqlalchemy_url(_DB))
    command.downgrade(cfg, "0021")
    assert not _sql("SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'sessions' AND column_name = 'vorschau'")
