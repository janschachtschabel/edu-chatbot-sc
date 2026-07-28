"""Async engine/session factories (P1-1).

No module-global engine (spec rule 3): the app builds ONE engine in its
lifespan when the first DB consumer arrives (P2 config_store) and stores it
on ``app.state``; tests and CLIs build their own against their URL.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import Pool

from boerdi.settings import Settings, get_settings


def make_engine(
    settings: Settings | None = None, *, echo: bool = False,
    poolclass: type[Pool] | None = None,
) -> AsyncEngine:
    """Async engine. ``poolclass=NullPool`` avoids cross-event-loop connection
    reuse — needed when a test mixes asyncio.run() with a TestClient loop."""
    cfg = settings or get_settings()
    kwargs: dict = {"echo": echo, "pool_pre_ping": True}
    if poolclass is not None:
        kwargs["poolclass"] = poolclass
        kwargs.pop("pool_pre_ping")  # NullPool has no pre-ping
    return create_async_engine(cfg.database_url, **kwargs)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
