"""Shared helpers for tests that need the live Compose-Postgres."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[1]
HOST = "localhost:5432"
ADMIN_DSN = f"postgresql://boerdi:boerdi@{HOST}/postgres"

SKIP_REASON = (
    "Compose-PG nicht erreichbar — docker compose -f deploy/compose.dev.yml up -d postgres"
)


def pg_available() -> bool:
    async def probe() -> None:
        conn = await asyncpg.connect(ADMIN_DSN, timeout=3)
        await conn.close()

    try:
        asyncio.run(probe())
        return True
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


def create_migrated_db(db: str) -> None:
    """Fresh throwaway database migrated to head."""
    asyncio.run(_admin_exec(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)'))
    asyncio.run(_admin_exec(f'CREATE DATABASE {db}'))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url(db))
    command.upgrade(cfg, "head")


def drop_db(db: str) -> None:
    asyncio.run(_admin_exec(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)'))
