"""Config-change LISTEN/NOTIFY listener (spec §6, improvement V2).

A dedicated asyncpg connection LISTENs on ``config_changed`` (fired by the
``trg_config_notify`` trigger with the area name as payload) and dispatches
to a callback — P2's config_store drops its process cache per area.

Dedicated raw connection on purpose: LISTEN must outlive pooled checkouts.
The background task reconnects with backoff when the connection drops and then
reports the reconnect (``on_reconnect``), because notifications sent in between
are lost; callback errors are logged and never kill the listener.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

import asyncpg
from sqlalchemy.engine import make_url

from boerdi.obs.tasks import cancel_and_drain

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_S = 2.0
_HEALTH_POLL_S = 1.0


def asyncpg_dsn(sqlalchemy_url: str) -> str:
    """The same URL for asyncpg: ``postgresql+asyncpg://…`` -> ``postgresql://…``.

    Rebuilt through SQLAlchemy's own parser rather than a string replace
    (Audit 2026-09-29): ``POSTGRES_PASSWORD`` goes into ``DATABASE_URL`` raw,
    and SQLAlchemy reads a ``/`` (or ``@``, ``#``, ``?``) in the password
    fine — asyncpg splits the URL with ``urllib.parse`` and cut the host at the
    first ``/``. The listener never connected and startup aborted. Rendering
    percent-encodes the credentials, which asyncpg decodes again.
    """
    url = make_url(sqlalchemy_url)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


class ConfigChangeListener:
    def __init__(self, dsn: str, channel: str = "config_changed") -> None:
        self._dsn = dsn
        self._channel = channel
        self._on_change: Callable[[str], None] | None = None
        self._on_reconnect: Callable[[], None] | None = None
        self._task: asyncio.Task | None = None
        self._stopped = False
        self._connected = asyncio.Event()

    async def start(
        self,
        on_change: Callable[[str], None],
        on_reconnect: Callable[[], None] | None = None,
    ) -> None:
        """``on_reconnect`` runs after every RE-connect, not the first connect.

        Notifications sent while the connection was down are lost, so the owner
        has to reload what it caches (audit 2026-09-29, C-M NOTIFY). It runs
        after ``LISTEN`` is back, so no change can slip between the two.
        """
        self._on_change = on_change
        self._on_reconnect = on_reconnect
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name="config-notify-listener")

    async def wait_connected(self, timeout: float = 5.0) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def stop(self) -> None:
        self._stopped = True
        try:
            if self._task is not None:
                # Paket 18E: mit Frist, und ohne den eigenen Abbruch zu verschlucken.
                await cancel_and_drain([self._task], bezeichnung="config-notify")
        finally:
            self._task = None
            self._connected.clear()

    def _dispatch(self, _conn, _pid, _channel, payload: str) -> None:
        try:
            if self._on_change is not None:
                self._on_change(payload)
        except Exception:
            logger.exception("config-change callback failed for area %r", payload)

    def _report_reconnect(self) -> None:
        try:
            if self._on_reconnect is not None:
                self._on_reconnect()
        except Exception:
            logger.exception("config reconnect callback failed")

    async def _run(self) -> None:
        connected_before = False
        while not self._stopped:
            conn: asyncpg.Connection | None = None
            try:
                conn = await asyncpg.connect(self._dsn)
                await conn.add_listener(self._channel, self._dispatch)
                self._connected.set()
                logger.info("LISTEN %s established", self._channel)
                if connected_before:
                    self._report_reconnect()
                connected_before = True
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
