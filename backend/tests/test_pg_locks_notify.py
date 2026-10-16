"""P1-2: config NOTIFY listener against the live Compose-Postgres (fresh throwaway DB).

The session-serialisation half (``db/locks.acquire_session_lock``, an xact
advisory lock no endpoint ever called) is gone: since Paket 7 (P1) the chat
endpoints take a lock row in ``session_locks`` — ``test_sitzungssperre.py``.

Timing margins are deliberately generous (hold 0.6s vs. start offset 0.15s)
— concurrency semantics cannot be tested without real parallel waits.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p1_locks_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


def test_notify_listener_receives_area_names(test_db) -> None:
    from boerdi.db.notify import ConfigChangeListener

    async def scenario() -> list[str]:
        received: list[str] = []
        listener = ConfigChangeListener(pg_utils.asyncpg_dsn(test_db))
        await listener.start(received.append)
        await listener.wait_connected(timeout=5.0)

        conn = await asyncpg.connect(pg_utils.asyncpg_dsn(test_db))
        try:
            await conn.execute(
                "INSERT INTO config_areas (area, data) "
                "VALUES ('01-base/welcome-config', '{}'::jsonb)"
            )
            await conn.execute(
                "UPDATE config_areas SET data='{\"x\":1}'::jsonb "
                "WHERE area='01-base/welcome-config'"
            )
        finally:
            await conn.close()

        for _ in range(100):  # up to 5s
            if len(received) >= 2:
                break
            await asyncio.sleep(0.05)
        await listener.stop()
        return received

    received = asyncio.run(scenario())
    assert received == ["01-base/welcome-config", "01-base/welcome-config"]


def test_listener_survives_callback_errors(test_db) -> None:
    from boerdi.db.notify import ConfigChangeListener

    async def scenario() -> list[str]:
        seen: list[str] = []

        def flaky(area: str) -> None:
            if not seen:
                seen.append(f"boom:{area}")
                raise RuntimeError("callback bug")
            seen.append(area)

        listener = ConfigChangeListener(pg_utils.asyncpg_dsn(test_db))
        await listener.start(flaky)
        await listener.wait_connected(timeout=5.0)

        conn = await asyncpg.connect(pg_utils.asyncpg_dsn(test_db))
        try:
            await conn.execute("SELECT pg_notify('config_changed', 'a1')")
            await conn.execute("SELECT pg_notify('config_changed', 'a2')")
        finally:
            await conn.close()

        for _ in range(100):
            if len(seen) >= 2:
                break
            await asyncio.sleep(0.05)
        await listener.stop()
        return seen

    assert asyncio.run(scenario()) == ["boom:a1", "a2"]  # error didn't kill the listener
