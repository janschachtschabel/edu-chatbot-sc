"""Migration 0011 (Paket 12, W1): Werksfassung und eigene Fassung je Bereich.

``config_areas`` bekommt ``werk_hash`` (Prüfsumme der Werksfassung, auf der der Bereich steht) und
``eigene_fassung`` (die stillgelegte eigene Fassung); ``config_werk_entfernt`` merkt sich im Studio
gelöschte Werksbereiche; ``config_snapshots.art`` unterscheidet „von Hand“ und „automatisch“.
Bestehende Zeilen bleiben, wie sie sind — die Zuordnung zur Werksfassung macht der Werksabgleich.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_w1_test"
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
    pg_utils.create_migrated_db(_DB, "0010")
    asyncio.run(_sql("INSERT INTO config_areas (area, data) VALUES ('01-base/x', '{\"a\": 1}')"))
    asyncio.run(_sql(
        "INSERT INTO config_snapshots (id, label, blob) VALUES ('snap-1', 'alt', '\\x00')"))
    pg_utils.upgrade_db(_DB, "head")
    yield
    pg_utils.drop_db(_DB)


def test_neue_spalten_und_tabelle(db):
    bereiche = _spalten("config_areas")
    assert bereiche["werk_hash"] == "text"
    assert bereiche["eigene_fassung"] == "jsonb"
    assert bereiche["eigene_basis"] == "text"
    assert set(_spalten("config_werk_entfernt")) >= {"area", "entfernt_am"}
    assert _spalten("config_snapshots")["art"] == "text"


def test_bestand_bleibt_unberuehrt(db):
    zeile = asyncio.run(_sql(
        "SELECT data::text, werk_hash, eigene_fassung FROM config_areas WHERE area='01-base/x'"))[0]
    assert zeile[0] == '{"a": 1}'
    assert zeile[1] is None and zeile[2] is None
    art = asyncio.run(_sql("SELECT art FROM config_snapshots WHERE id='snap-1'"))[0][0]
    assert art == "hand"


def test_rueckweg(db):
    command.downgrade(_alembic(), "0010")
    try:
        assert "werk_hash" not in _spalten("config_areas")
        assert "art" not in _spalten("config_snapshots")
        assert _spalten("config_werk_entfernt") == {}
    finally:
        command.upgrade(_alembic(), "head")
