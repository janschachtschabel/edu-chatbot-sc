"""Config-change LISTEN/NOTIFY listener (spec §6, improvement V2).

A dedicated asyncpg connection LISTENs on ``config_changed`` (fired by the
``trg_config_notify`` trigger with the area name as payload) and dispatches
to a callback — P2's config_store drops its process cache per area.

Dedicated raw connection on purpose: LISTEN must outlive pooled checkouts.
The background task reconnects with backoff when the connection drops;
callback errors are logged and never kill the listener.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

import asyncpg

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_S = 2.0
_HEALTH_POLL_S = 1.0


def asyncpg_dsn(sqlalchemy_url: str) -> str:
    """Strip the SQLAlchemy driver suffix: postgresql+asyncpg://... -> postgresql://..."""
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


class ConfigChangeListener:
    def __init__(self, dsn: str, channel: str = "config_changed") -> None:
        self._dsn = dsn
        self._channel = channel
        self._on_change: Callable[[str], None] | None = None
        self._task: asyncio.Task | None = None
        self._stopped = False
        self._connected = asyncio.Event()

    async def start(self, on_change: Callable[[str], None]) -> None:
        self._on_change = on_change
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name="config-notify-listener")

    async def wait_connected(self, timeout: float = 5.0) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._connected.clear()

    def _dispatch(self, _conn, _pid, _channel, payload: str) -> None:
        try:
            if self._on_change is not None:
                self._on_change(payload)
        except Exception:
            logger.exception("config-change callback failed for area %r", payload)

    async def _run(self) -> None:
        while not self._stopped:
            conn: asyncpg.Connection | None = None
            try:
                conn = await asyncpg.connect(self._dsn)
                await conn.add_listener(self._channel, self._dispatch)
                self._connected.set()
                logger.info("LISTEN %s established", self._channel)
                while not self._stopped and not conn.is_closed():
                    await asyncio.sleep(_HEALTH_POLL_S)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("config-notify listener error: %s — reconnecting", e)
            finally:
                self._connected.clear()
                if conn is not None and not conn.is_closed():
                    with contextlib.suppress(Exception):
                        await conn.close()
            if not self._stopped:
                await asyncio.sleep(_RECONNECT_DELAY_S)
