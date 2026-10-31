"""Async engine/session factories (P1-1).

No module-global engine (spec rule 3): the app builds ONE engine in its
lifespan when the first DB consumer arrives (P2 config_store) and stores it
on ``app.state``; tests and CLIs build their own against their URL.

Paket 19 (Audit 2026-10-31, M-10): every connection carries time limits — the server
ends a runaway statement, a forgotten transaction and a long lock wait; asyncpg's
``command_timeout`` ends a call that never hears back (network partition without RST).
The server limits are ``SET`` right after connecting (:func:`fristen_anweisungen`), NOT
sent as startup parameters: PgBouncer rejects unknown startup parameters ("unsupported
startup parameter", Review 19-4), and no pod would start. The CLI builds its engines
with ``fristen=False``: one-off operator runs, watched, some of them long.

Review 19-4: a long wait for a pooled connection (or the pool timeout) is logged —
before, an exhausted pool showed only as the error bubble.
"""

import logging
import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, Pool

from boerdi.obs.drossel import gedrosselt
from boerdi.settings import Settings, get_settings

logger = logging.getLogger(__name__)

#: Ab dieser Wartezeit auf eine Verbindung aus dem Pool eine (gedrosselte) Warnung.
POOL_WARTE_WARNUNG_S = 1.0


def _ms(sekunden: float) -> int:
    return max(1, round(sekunden * 1000))


def verbindungs_fristen(cfg: Settings) -> dict[str, Any]:
    """``connect_args``: nur die Clientfrist ``command_timeout`` (0 = aus). Die
    Server-Fristen stehen in :func:`fristen_anweisungen` — nie im Startpaket."""
    if cfg.db_command_timeout_s > 0:
        return {"command_timeout": float(cfg.db_command_timeout_s)}
    return {}


def fristen_anweisungen(cfg: Settings) -> list[str]:
    """Die ``SET``-Anweisungen der Server-Fristen nach dem Verbindungsaufbau; 0 = aus."""
    werte = (("statement_timeout", cfg.db_statement_timeout_s),
             ("idle_in_transaction_session_timeout", cfg.db_idle_in_transaction_timeout_s),
             ("lock_timeout", cfg.db_lock_timeout_s))
    return [f"SET {name} = {_ms(s)}" for name, s in werte if s > 0]


def _fristen_beim_verbinden(engine: AsyncEngine, anweisungen: list[str]) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _setzen(dbapi_connection: Any, _record: Any) -> None:
        async def _ausfuehren(verbindung: Any) -> None:
            for anweisung in anweisungen:
                await verbindung.execute(anweisung)

        dbapi_connection.run_async(_ausfuehren)


class _MessenderPool(AsyncAdaptedQueuePool):
    """Der Pool der App, mit Meldung bei langer Wartezeit und bei ``pool_timeout``."""

    def _do_get(self) -> Any:
        beginn = time.monotonic()
        try:
            return super()._do_get()
        except PoolTimeout:
            gedrosselt(logger, logging.WARNING, "db-pool-timeout", 60.0,
                       "DB-Pool erschöpft: keine Verbindung binnen %.0f s (Pool %d + %d)",
                       self._timeout, self.size(), self._max_overflow)
            raise
        finally:
            gewartet = time.monotonic() - beginn
            if POOL_WARTE_WARNUNG_S <= gewartet < self._timeout:
                gedrosselt(logger, logging.WARNING, "db-pool-warten", 60.0,
                           "DB-Pool: %.1f s auf eine Verbindung gewartet", gewartet)


def make_engine(
    settings: Settings | None = None, *, echo: bool = False,
    poolclass: type[Pool] | None = None, fristen: bool = True,
    pool_size: int | None = None, max_overflow: int | None = None,
    pool_timeout: float | None = None,
) -> AsyncEngine:
    """Async engine. ``poolclass=NullPool`` avoids cross-event-loop connection
    reuse — needed when a test mixes asyncio.run() with a TestClient loop.

    ``pool_size``/``max_overflow``/``pool_timeout`` override the settings for a
    small dedicated engine (the session lock, Paket 19 H-5); ``fristen=False``
    builds without connection time limits (CLI)."""
    cfg = settings or get_settings()
    # Paket 18C/D: SQLAlchemy hängt an jede Fehlermeldung ``[parameters: …]`` an — beim
    # Speichern einer Nachricht deren Text, und die Meldung landet über ``logger.exception``
    # im Log. Anweisung und Fehlerart bleiben.
    kwargs: dict = {"echo": echo, "hide_parameters": True}
    if fristen and (connect_args := verbindungs_fristen(cfg)):
        kwargs["connect_args"] = connect_args
    if poolclass is not None:
        kwargs["poolclass"] = poolclass  # NullPool: no pre-ping, no size
    else:
        kwargs.update(poolclass=_MessenderPool, pool_pre_ping=True,
                      pool_size=cfg.db_pool_size if pool_size is None else pool_size,
                      max_overflow=cfg.db_max_overflow if max_overflow is None else max_overflow)
        if pool_timeout is not None:
            kwargs["pool_timeout"] = pool_timeout
    engine = create_async_engine(cfg.database_url, **kwargs)
    if fristen and (anweisungen := fristen_anweisungen(cfg)):
        _fristen_beim_verbinden(engine, anweisungen)
    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
