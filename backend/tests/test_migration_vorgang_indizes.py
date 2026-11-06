"""Migration 0020 (Querschnitts-Review 2026-11-06): Indizes der Vorgänge.

- ``ix_vorgaenge_session_id``: der Fremdschlüssel ``session_id … ON DELETE SET NULL`` prüfte sonst
  bei jedem gelöschten Sitzungs-Datensatz alle Vorgänge (die Aufbewahrung löscht in Stapeln).
- ``ix_vorgaenge_aufrufer_muster`` (``text_pattern_ops``): die Suche nach anonymen Vorgängen
  (``aufrufer LIKE 'sitzung:%'``) nutzt den Index auch unter einer Sortierfolge, die nicht ``C``
  ist.
- ``ix_vorgaenge_aufrufer`` (0018) fällt weg: der Muster-Index trägt auch die Gleichheit.
- ``ix_vorgang_auftraege_vorgang_id``: der Name, den das Modell erzeugt (0019 hieß er anders).
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_q3_vorgang_indizes_test"
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


def _indizes() -> dict[str, str]:
    async def lesen():
        conn = await asyncpg.connect(_DSN)
        try:
            return await conn.fetch(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename IN ('vorgaenge', 'vorgang_auftraege')")
        finally:
            await conn.close()
    return {z[0]: z[1] for z in asyncio.run(lesen())}


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB, "0019")
    pg_utils.upgrade_db(_DB, "head")
    yield
    pg_utils.drop_db(_DB)


def test_die_indizes_sind_da(db):
    ix = _indizes()
    assert "session_id" in ix["ix_vorgaenge_session_id"]
    assert "text_pattern_ops" in ix["ix_vorgaenge_aufrufer_muster"]
    assert "ix_vorgaenge_aufrufer" not in ix
    assert "ix_vorgang_auftraege_vorgang_id" in ix and "ix_vorgang_auftraege_vorgang" not in ix


def test_rueckweg(db):
    command.downgrade(_alembic(), "0019")
    try:
        ix = _indizes()
        assert "ix_vorgaenge_session_id" not in ix and "ix_vorgaenge_aufrufer_muster" not in ix
        assert "ix_vorgang_auftraege_vorgang" in ix and "ix_vorgaenge_aufrufer" in ix
    finally:
        command.upgrade(_alembic(), "head")
