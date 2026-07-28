"""DB-backed config area store (P2-2, spec §6 / improvement V2).

``put()`` upserts the area with version++ and appends the config_history row
in ONE transaction. ``get()`` serves from a process cache; the NOTIFY listener
(P1-2, fed by ``trg_config_notify``) drops cache entries when ANY replica
writes — propagation target < 2 s (spec §8). Subscribers (loader facade) get
the area name on every change, own writes included.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.db.notify import ConfigChangeListener

logger = logging.getLogger(__name__)

_UPSERT = text("""
    INSERT INTO config_areas (area, data, updated_by)
    VALUES (:area, CAST(:data AS jsonb), :updated_by)
    ON CONFLICT (area) DO UPDATE
      SET data = EXCLUDED.data,
          version = config_areas.version + 1,
          updated_at = now(),
          updated_by = EXCLUDED.updated_by
    RETURNING version
""")

_HISTORY_INSERT = text("""
    INSERT INTO config_history (area, version, data, updated_by)
    VALUES (:area, :version, CAST(:data AS jsonb), :updated_by)
""")

_SELECT_DATA = text("SELECT data FROM config_areas WHERE area = :area")

_SELECT_HISTORY = text("""
    SELECT version, data, updated_at, updated_by
    FROM config_history WHERE area = :area
    ORDER BY version DESC LIMIT :limit
""")

_SELECT_AREAS = text("SELECT area, version, updated_at, updated_by FROM config_areas ORDER BY area")

_DELETE_AREA = text("DELETE FROM config_areas WHERE area = :area RETURNING area")


class ConfigStore:
    def __init__(self, engine: AsyncEngine, listen_dsn: str) -> None:
        self._engine = engine
        self._cache: dict[str, dict[str, Any]] = {}
        self._listener = ConfigChangeListener(listen_dsn)
        self._subscribers: list[Callable[[str], None]] = []

    @property
    def engine(self) -> AsyncEngine:
        """Shared async engine — snapshots (P2-7) run their own table SQL on it."""
        return self._engine

    async def start(self) -> None:
        """Attach the NOTIFY listener (call once in app lifespan)."""
        await self._listener.start(self._on_area_changed)
        await self._listener.wait_connected()

    async def stop(self) -> None:
        await self._listener.stop()

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Register for area-change events (loader caches etc.)."""
        self._subscribers.append(callback)

    def _on_area_changed(self, area: str) -> None:
        # refetch-and-overwrite (no pop first) so SYNC readers of the loader
        # facade (get_cached) never see an empty window between drop and refill
        try:
            asyncio.get_running_loop().create_task(self._refresh(area))
        except RuntimeError:  # no loop — listener callbacks run on the loop
            logger.warning("config refresh for %r skipped: no running loop", area)
        for cb in self._subscribers:
            try:
                cb(area)
            except Exception:
                logger.exception("config subscriber failed for area %r", area)

    async def _refresh(self, area: str) -> None:
        try:
            data = await self._fetch(area)
            if data is None:
                self._cache.pop(area, None)  # row gone -> drop
            else:
                self._cache[area] = data
        except Exception as e:
            logger.warning("config refresh for %r failed: %s", area, e)

    async def preload(self, areas: list[str]) -> None:
        """Warm the cache so the sync loader facade never misses (P2-3)."""
        for area in areas:
            data = await self._fetch(area)
            if data is not None:
                self._cache[area] = data

    def get_cached(self, area: str) -> dict[str, Any] | None:
        """Sync cache lookup for the loader facade — never touches the DB."""
        return self._cache.get(area)

    def cached_areas(self) -> list[str]:
        return list(self._cache)

    def clear_cache(self, area: str | None = None) -> None:
        """Facade invalidate_yaml_cache equivalent (None = drop everything)."""
        if area is None:
            self._cache.clear()
        else:
            self._cache.pop(area, None)

    async def get(self, area: str) -> dict[str, Any] | None:
        if area in self._cache:
            return self._cache[area]
        data = await self._fetch(area)
        if data is not None:
            self._cache[area] = data
        return data

    async def _fetch(self, area: str) -> dict[str, Any] | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(_SELECT_DATA, {"area": area})).first()
        return None if row is None else row[0]

    async def put(self, area: str, data: dict[str, Any], updated_by: str = "") -> int:
        """Upsert + history in one transaction; returns the new version."""
        payload = json.dumps(data, ensure_ascii=False)
        async with self._engine.begin() as conn:
            version = (
                await conn.execute(
                    _UPSERT, {"area": area, "data": payload, "updated_by": updated_by}
                )
            ).scalar_one()
            await conn.execute(
                _HISTORY_INSERT,
                {"area": area, "version": version, "data": payload, "updated_by": updated_by},
            )
        # write-through: warm the cache with what we just wrote so an immediate
        # SYNC loader re-read (typed PUT endpoints) sees the fresh value; the
        # self-NOTIFY refetch lands the same value idempotently.
        self._cache[area] = data
        return version

    async def delete(self, area: str) -> bool:
        """Delete an area (config file DELETE, P2-5). Returns False if absent."""
        async with self._engine.begin() as conn:
            row = (await conn.execute(_DELETE_AREA, {"area": area})).first()
        self._cache.pop(area, None)
        return row is not None

    async def history(self, area: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(_SELECT_HISTORY, {"area": area, "limit": limit})
            ).mappings().all()
        return [dict(r) for r in rows]

    async def list_areas(self) -> list[dict[str, Any]]:
        """All areas with meta (endpoint /api/config/files, P2-5)."""
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_SELECT_AREAS)).mappings().all()
        return [dict(r) for r in rows]
