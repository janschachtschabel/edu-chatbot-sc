"""Migration 0023 (Plan 2026-11-16, TG-3e): ``dokument_uploads.session_id`` ist nicht mehr
eindeutig, nur indiziert; der Rückweg behält je Sitzung das jüngste Dokument."""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from tests import pg_utils

_DB = "boerdi_tg3e_dokumente_je_sitzung_test"

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
    pg_utils.create_migrated_db(_DB, "0022")
    yield
    pg_utils.drop_db(_DB)


def _dokument(kennung: str, erstellt: str) -> str:
    return ("INSERT INTO dokument_uploads (id, session_id, block_id, name, format, groesse, "
            "befund, gliederung, markdown, erstellt, verfaellt_am) VALUES "
            f"('{kennung}', 'bb-tg3e', 'b0000001', '{kennung}.pdf', 'pdf', 1, '{{}}', '[]', '#', "
            f"'{erstellt}', now() + interval '1 day')")


def test_nach_0023_traegt_eine_sitzung_mehrere_dokumente(db):
    _sql("INSERT INTO sessions (session_id) VALUES ('bb-tg3e')")
    pg_utils.upgrade_db(_DB, "0023")
    _sql(_dokument("eins", "2026-11-16 10:00+00"))
    _sql(_dokument("zwei", "2026-11-16 11:00+00"))
    assert len(_sql("SELECT id FROM dokument_uploads WHERE session_id = 'bb-tg3e'")) == 2
    [index] = _sql("SELECT indexdef FROM pg_indexes "
                   "WHERE indexname = 'ix_dokument_uploads_session_id'")
    assert "(session_id)" in index["indexdef"]
    assert not _sql("SELECT 1 FROM pg_constraint "
                    "WHERE conname = 'dokument_uploads_session_id_key'")


def test_der_rueckweg_behaelt_das_juengste_und_die_eindeutigkeit(db):
    _sql("INSERT INTO sessions (session_id) VALUES ('bb-tg3e')")
    pg_utils.upgrade_db(_DB, "0023")
    _sql(_dokument("alt", "2026-11-16 10:00+00"))
    _sql(_dokument("neu", "2026-11-16 11:00+00"))
    cfg = Config(str(pg_utils.BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(pg_utils.BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_utils.sqlalchemy_url(_DB))
    command.downgrade(cfg, "0022")
    assert [r["id"] for r in _sql("SELECT id FROM dokument_uploads")] == ["neu"]
    assert _sql("SELECT 1 FROM pg_constraint WHERE conname = 'dokument_uploads_session_id_key'")
    assert not _sql("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_dokument_uploads_session_id'")
