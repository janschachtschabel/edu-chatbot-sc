"""DB-backed config area store (P2-2, spec §6 / improvement V2).

``put()`` upserts the area with version++ and appends the config_history row
in ONE transaction. ``get()`` serves from a process cache; the NOTIFY listener
(P1-2, fed by ``trg_config_notify``) drops cache entries when ANY replica
writes — propagation target < 2 s (spec §8). Subscribers (loader facade) get
the area name on every change, own writes included.

The cache never falls back to an older state (Paket 4, D1; external audit F08):
it holds each area's version next to its data and drops a fetch that brings an
older one, and per area only one fetch runs at a time — a NOTIFY arriving
meanwhile triggers exactly one more fetch afterwards. Before, every NOTIFY
started its own fetch, and a slow old one overwrote a faster new one or the
write-through from ``put``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.db.notify import ConfigChangeListener
from boerdi.services.config_conflict import (
    FIRST_VERSION,
    als_bereichsfehler,
    als_json,
    write_checked,
)

logger = logging.getLogger(__name__)

_UPSERT = text(f"""
    INSERT INTO config_areas (area, data, updated_by, version)
    VALUES (:area, CAST(:data AS jsonb), :updated_by, {FIRST_VERSION})
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

_SELECT_DATA = text("SELECT data, version FROM config_areas WHERE area = :area")

_SELECT_HISTORY = text("""
    SELECT version, data, updated_at, updated_by
    FROM config_history WHERE area = :area
    ORDER BY version DESC LIMIT :limit
""")

_SELECT_AREAS = text("SELECT area, version, updated_at, updated_by FROM config_areas ORDER BY area")

_SELECT_ALL_DATA = text("SELECT area, data FROM config_areas ORDER BY area")

_DELETE_AREA = text("DELETE FROM config_areas WHERE area = :area RETURNING area")


class ConfigStore:
    def __init__(self, engine: AsyncEngine, listen_dsn: str) -> None:
        self._engine = engine
        self._cache: dict[str, dict[str, Any]] = {}
        # Version of each cached entry; both dicts always change together.
        self._versions: dict[str, int] = {}
        # Single-flight per area: the running fetch, and areas changed meanwhile.
        self._fetching: dict[str, asyncio.Task[None]] = {}
        self._changed_again: set[str] = set()
        self._listener = ConfigChangeListener(listen_dsn)
        self._subscribers: list[Callable[[str], None]] = []

    @property
    def engine(self) -> AsyncEngine:
        """Shared async engine — snapshots (P2-7) run their own table SQL on it."""
        return self._engine

    async def start(self) -> None:
        """Attach the NOTIFY listener (call once in app lifespan)."""
        await self._listener.start(self._on_area_changed, on_reconnect=self._on_reconnect)
        await self._listener.wait_connected()

    def _on_reconnect(self) -> None:
        # Notifications sent while LISTEN was down are lost: reload everything
        # this process may hold, or a replica keeps stale config — privacy
        # switches included — until restart (audit 2026-09-29, C-M NOTIFY).
        try:
            asyncio.get_running_loop().create_task(self._resync())
        except RuntimeError:  # no loop — listener callbacks run on the loop
            logger.warning("config resync after reconnect skipped: no running loop")

    async def _resync(self) -> None:
        # Cached areas AND the database list: an area created during the
        # outage is not in the cache yet.
        areas = set(self._cache)
        try:
            areas |= {meta["area"] for meta in await self.list_areas()}
        except Exception as e:
            logger.warning("config resync could not list areas: %s", e)
        logger.info("config resync after reconnect: %d areas", len(areas))
        for area in sorted(areas):
            self._on_area_changed(area)

    async def stop(self) -> None:
        await self._listener.stop()

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Register for area-change events (loader caches etc.)."""
        self._subscribers.append(callback)

    def _on_area_changed(self, area: str) -> None:
        # refetch-and-overwrite (no pop first) so SYNC readers of the loader
        # facade (get_cached) never see an empty window between drop and refill
        if area in self._fetching:
            self._changed_again.add(area)
        else:
            try:
                task = asyncio.get_running_loop().create_task(self._refresh_until_quiet(area))
            except RuntimeError:  # no loop — listener callbacks run on the loop
                logger.warning("config refresh for %r skipped: no running loop", area)
            else:
                self._fetching[area] = task
        for cb in self._subscribers:
            try:
                cb(area)
            except Exception:
                logger.exception("config subscriber failed for area %r", area)

    async def _refresh_until_quiet(self, area: str) -> None:
        """Fetch again as long as a change was reported during the last fetch."""
        try:
            while True:
                self._changed_again.discard(area)
                await self._refresh(area)
                if area not in self._changed_again:
                    return
        finally:
            self._fetching.pop(area, None)

    async def _refresh(self, area: str) -> None:
        try:
            row = await self._fetch(area)
        except Exception as e:
            logger.warning("config refresh for %r failed: %s", area, e)
            return
        if row is None:
            self._forget(area)  # row gone -> drop
        else:
            self._remember(area, *row)

    def _remember(self, area: str, data: dict[str, Any], version: int) -> None:
        """Cache ``data`` unless the cache already holds a newer version."""
        if version < self._versions.get(area, 0):
            return
        self._cache[area] = data
        self._versions[area] = version

    def _forget(self, area: str) -> None:
        # The area is gone; a re-created row continues its count (FIRST_VERSION).
        self._cache.pop(area, None)
        self._versions.pop(area, None)

    async def preload(self, areas: list[str]) -> None:
        """Warm the cache so the sync loader facade never misses (P2-3)."""
        for area in areas:
            row = await self._fetch(area)
            if row is not None:
                self._remember(area, *row)

    def get_cached(self, area: str) -> dict[str, Any] | None:
        """Sync cache lookup for the loader facade — never touches the DB."""
        return self._cache.get(area)

    def cached_areas(self) -> list[str]:
        return list(self._cache)

    def clear_cache(self, area: str | None = None) -> None:
        """Facade invalidate_yaml_cache equivalent (None = drop everything)."""
        if area is None:
            self._cache.clear()
            self._versions.clear()
        else:
            self._forget(area)

    async def get(self, area: str) -> dict[str, Any] | None:
        if area in self._cache:
            return self._cache[area]
        row = await self._fetch(area)
        if row is None:
            return None
        self._remember(area, *row)
        return row[0]

    async def _fetch(self, area: str) -> tuple[dict[str, Any], int] | None:
        """``(data, version)`` of the area, or ``None`` when the row is gone."""
        async with self._engine.connect() as conn:
            row = (await conn.execute(_SELECT_DATA, {"area": area})).first()
        return None if row is None else (row[0], row[1])

    async def read(self, area: str) -> tuple[dict[str, Any], int] | None:
        """``(data, version)`` straight from the database; refreshes the cache.

        For editors (Paket 4, D5): the version they save against must be the
        stored one, not what the cache holds until another replica's NOTIFY
        lands — or "reload" after a conflict would show the same stale state.
        """
        row = await self._fetch(area)
        if row is None:
            self._forget(area)
        else:
            self._remember(area, *row)
        return row

    async def put(
        self, area: str, data: dict[str, Any], updated_by: str = "", *,
        expected_version: int | None = None, create_only: bool = False,
    ) -> int:
        """Upsert + history in one transaction; returns the new version.

        With ``expected_version`` or ``create_only`` the write is conditional
        and raises ``ConfigConflict`` when the stored row does not match
        (``services/config_conflict.py``).
        """
        if expected_version is None and not create_only:
            return (await self.put_many({area: data}, updated_by=updated_by))[area]
        payload = als_json(area, data)
        async with self._engine.begin() as conn:
            with als_bereichsfehler(area):
                version = await write_checked(
                    conn, area=area, payload=payload, updated_by=updated_by,
                    expected_version=expected_version, create_only=create_only,
                )
            await conn.execute(
                _HISTORY_INSERT,
                {"area": area, "version": version, "data": payload, "updated_by": updated_by},
            )
        self._remember(area, data, version)
        return version

    async def put_many(
        self, items: dict[str, dict[str, Any]], updated_by: str = "",
        delete: Iterable[str] = (),
    ) -> dict[str, int]:
        """Upserts + history rows, then deletions — all in ONE transaction.

        A restore or seed run lands whole or not at all (Paket 4, D4; external
        audit F07): one transaction per area left the first two new when the
        third failed. Returns the new version per written area. The NOTIFY
        trigger fires per row; Postgres delivers at commit.
        """
        gone = list(delete)
        ganz = len(items) + len(gone) > 1  # mehr als ein Bereich: alles fällt zurück
        payloads = {area: als_json(area, data, ganzer_vorgang=ganz) for area, data in items.items()}
        versions: dict[str, int] = {}
        async with self._engine.begin() as conn:
            for area, payload in payloads.items():
                with als_bereichsfehler(area, ganzer_vorgang=ganz):
                    versions[area] = (
                        await conn.execute(
                            _UPSERT, {"area": area, "data": payload, "updated_by": updated_by}
                        )
                    ).scalar_one()
                await conn.execute(
                    _HISTORY_INSERT,
                    {"area": area, "version": versions[area], "data": payload,
                     "updated_by": updated_by},
                )
            for area in gone:
                await conn.execute(_DELETE_AREA, {"area": area})
        # write-through, only after the commit: warm the cache with what we just
        # wrote so an immediate SYNC loader re-read (typed PUT endpoints) sees
        # the fresh value; the self-NOTIFY refetch lands the same value
        # idempotently. A newer version another replica wrote meanwhile stays.
        for area, version in versions.items():
            self._remember(area, items[area], version)
        for area in gone:
            self._forget(area)
        return versions

    async def delete(self, area: str) -> bool:
        """Delete an area (config file DELETE, P2-5). Returns False if absent."""
        async with self._engine.begin() as conn:
            row = (await conn.execute(_DELETE_AREA, {"area": area})).first()
        self._forget(area)
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

    async def all_data(self) -> dict[str, dict[str, Any]]:
        """Every stored area as ``{area: data}``, read from the database.

        The source of snapshots, backups and the seed comparison (Paket 4, D2):
        the process cache may trail another replica's write until its NOTIFY
        arrives, and a backup must hold what is actually stored.
        """
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_SELECT_ALL_DATA)).all()
        return {area: data for area, data in rows}
