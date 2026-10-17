"""Shared helpers for tests that need the live Compose-Postgres."""

from __future__ import annotations

import asyncio
import functools
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[1]
# 127.0.0.1 statt localhost (Paket 7, gemessen 2026-10-09): unter Windows versucht
# „localhost“ zuerst IPv6 ::1 und kostet je frischer Verbindung ~2,1 s statt ~0,06 s —
# bei Hunderten PG-Tests der Großteil der Suite-Laufzeit. In der CI gleichwertig.
HOST = "127.0.0.1:5432"
ADMIN_DSN = f"postgresql://boerdi:boerdi@{HOST}/postgres"

SKIP_REASON = (
    "Compose-PG nicht erreichbar — docker compose -f deploy/compose.dev.yml up -d postgres"
)

#: Frist der beiden Proben. Sie liefen je Modul beim Einsammeln mit 3 s, und
#: unter Last fiel ein ganzes Modul still aus (Paket 6, B3). Jetzt einmal je
#: Prozess, am Anfang des Laufs, mit mehr Luft — ein Fehlen kostet lokal nur
#: diese eine Wartezeit.
PROBE_TIMEOUT_S = 10


@functools.cache
def pg_available() -> bool:
    async def probe() -> None:
        conn = await asyncpg.connect(ADMIN_DSN, timeout=PROBE_TIMEOUT_S)
        await conn.close()

    try:
        asyncio.run(probe())
        return True
    except Exception:
        return False


DEV_DB_SKIP_REASON = (
    "Standard-DB nicht migriert/geseedet — "
    "uv run alembic upgrade head && uv run boerdi import-config --from seeds"
)


@functools.cache
def dev_db_ready() -> bool:
    """Ist die STANDARD-Datenbank migriert *und* befüllt?

    ``pg_available`` beantwortet eine schwächere Frage: nimmt Postgres eine
    Verbindung an. Tests, die die echte App gegen die Settings-Standard-URL
    hochfahren, brauchen mehr — beim Start liest ``config_areas``, und sie
    prüfen auf geseedete Inhalte. Auf einem frischen Postgres (CI ohne den
    Bereitstellungs-Schritt) gelingt die Verbindung, und die Abfrage stirbt
    danach mit ``UndefinedTableError``. Das liest sich wie ein Code-Fehler und
    ist keiner — deshalb fragt dieses Tor nach dem, was wirklich gebraucht wird.
    """

    async def probe() -> bool:
        from boerdi.settings import get_settings

        url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(url, timeout=PROBE_TIMEOUT_S)
        try:
            if await conn.fetchval("SELECT to_regclass('public.config_areas')") is None:
                return False
            return bool(await conn.fetchval("SELECT count(*) FROM config_areas"))
        finally:
            await conn.close()

    try:
        return asyncio.run(probe())
    except Exception:
        return False


def asyncpg_dsn(db: str) -> str:
    return f"postgresql://boerdi:boerdi@{HOST}/{db}"


def sqlalchemy_url(db: str) -> str:
    return f"postgresql+asyncpg://boerdi:boerdi@{HOST}/{db}"


async def _admin_exec(sql: str) -> None:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


def create_migrated_db(db: str, revision: str = "head") -> None:
    """Fresh throwaway database migrated to ``revision`` (default: head)."""
    asyncio.run(_admin_exec(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)'))
    asyncio.run(_admin_exec(f'CREATE DATABASE {db}'))
    upgrade_db(db, revision)


def upgrade_db(db: str, revision: str) -> None:
    """Migrate an existing test database on to ``revision`` — for data
    migrations, which need rows written in between."""
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url(db))
    command.upgrade(cfg, revision)


def drop_db(db: str) -> None:
    asyncio.run(_admin_exec(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)'))
