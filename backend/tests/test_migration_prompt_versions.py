"""Migration 0012 (Paket 13, A4): Ablage der festen Prompt-Bausteine.

``prompt_versions`` hält jede Fassung eines festen Systemteils genau einmal (Schlüssel: die
Prüfsumme). Läufe tragen nur die Prüfsummen; ein Vergleich zweier Läufe holt die Texte von hier.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_p13_prompts_test"
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


def _spalten(tabelle: str) -> dict[str, str]:
    zeilen = asyncio.run(_sql(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name=$1",
        tabelle))
    return {z[0]: z[1] for z in zeilen}


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB, "0011")
    pg_utils.upgrade_db(_DB, "head")
    yield
    pg_utils.drop_db(_DB)


def test_tabelle_mit_pruefsumme_als_schluessel(db):
    assert _spalten("prompt_versions") == {
        "hash": "text", "art": "text", "text": "text",
        "erstmals": "timestamp with time zone", "zuletzt": "timestamp with time zone"}
    asyncio.run(_sql("INSERT INTO prompt_versions (hash, art, text) VALUES ('h1', 'agent', 'A')"))
    with pytest.raises(asyncpg.UniqueViolationError):
        asyncio.run(_sql(
            "INSERT INTO prompt_versions (hash, art, text) VALUES ('h1', 'agent', 'B')"))


def test_rueckweg(db):
    command.downgrade(_alembic(), "0011")
    try:
        assert _spalten("prompt_versions") == {}
    finally:
        command.upgrade(_alembic(), "head")
