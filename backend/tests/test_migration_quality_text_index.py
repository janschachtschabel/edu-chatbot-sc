"""Migration 0013 (Review PR #18, B2): Teilindex für Zeilen, deren Text noch nicht geleert ist.

Der Text-Schritt des Aufbewahrungslaufs (``quality_text``) und sein Überblick suchen Zeilen ohne
Marke ``text_geleert``, die älter als die Gesprächsfrist sind. Geleerte Zeilen bleiben bis zur
Frist des Protokolls (180 Tage) liegen — ohne Index las jeder Lauf ihr ganzes ``data`` erneut.
Im Teilindex stehen nur ungeleerte Zeilen; eine geleerte fällt mit dem Leeren heraus.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_r2_quality_index_test"
_DSN = pg_utils.asyncpg_dsn(_DB)

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]


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


def _index() -> str | None:
    zeilen = asyncio.run(_sql(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_quality_logs_text_offen'"))
    return zeilen[0][0] if zeilen else None


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB, "0012")
    pg_utils.upgrade_db(_DB, "head")
    yield
    pg_utils.drop_db(_DB)


def test_teilindex_nur_fuer_ungeleerte_zeilen(db):
    definition = _index()
    assert definition is not None
    assert "created_at" in definition and "text_geleert" in definition


def test_rueckweg(db):
    command.downgrade(_alembic(), "0012")
    try:
        assert _index() is None
    finally:
        command.upgrade(_alembic(), "head")
