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
from collections.abc import Callable, Collection, Iterable, Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.db.notify import ConfigChangeListener
from boerdi.domain.config_models.schalter import normalisiere_schalter
from boerdi.obs.tasks import ABBRUCH_FRIST_S
from boerdi.services.config_conflict import (
    FIRST_VERSION,
    ConfigConflict,
    als_bereichsfehler,
    als_json,
    delete_checked,
    write_checked,
)
from boerdi.services.werkfassung import Fassung

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
# Paket 12, Review 2 #1: eine stillgelegte eigene Fassung steht in keinem Schnappschuss — ein
# Bereich, der eine trägt, wird nie mitgelöscht.
_DELETE_OHNE_EIGENE = text(
    "DELETE FROM config_areas WHERE area = :area AND eigene_fassung IS NULL RETURNING area")
_HAT_EIGENE = text(
    "SELECT eigene_fassung IS NOT NULL FROM config_areas WHERE area = :area FOR UPDATE")

# Paket 12: Werksfassung und eigene Fassung (``services/werkfassung``). Ein gelöschter
# Werksbereich wird vermerkt, damit der Werksabgleich ihn nicht wieder anlegt; jedes Schreiben
# trägt ihn aus. Werksbereich heißt: er hat eine Werksbasis — oder der Aufrufer weiß es aus dem
# Seed (Review 2 #2: vor 0011 angepasste Bereiche haben keine Basis). Läuft VOR dem Löschen in
# derselben Transaktion; schlägt das Löschen fehl, fällt der Vermerk mit zurück.
_ENTFERNT_EINTRAGEN = text("""
    INSERT INTO config_werk_entfernt (area)
    SELECT area FROM config_areas
     WHERE area = :area AND eigene_fassung IS NULL
       AND (werk_hash IS NOT NULL OR :werksbereich)
    ON CONFLICT (area) DO NOTHING
""")
_ENTFERNT_AUSTRAGEN = text("DELETE FROM config_werk_entfernt WHERE area = :area")
_SELECT_ENTFERNT = text("SELECT area FROM config_werk_entfernt ORDER BY area")
_WERK_HASH_SETZEN = text("UPDATE config_areas SET werk_hash = :werk_hash WHERE area = :area")
# Umschalten in EINEM Schreibvorgang, bedingt auf die Version (Review #13: vorher zwei UPDATEs
# und damit zwei Benachrichtigungen je Umschalten).
_UMSCHALTEN = text("""
    UPDATE config_areas
       SET data = CAST(:data AS jsonb), version = version + 1, updated_at = now(),
           updated_by = :updated_by, werk_hash = :werk_hash,
           eigene_fassung = CAST(:eigene AS jsonb), eigene_basis = :eigene_basis
     WHERE area = :area AND version = :expected
    RETURNING version
""")
# Werksabgleich und Wiederherstellen schreiben nur, was sie gelesen haben (Review #2/#5): ein
# vorhandener Bereich nur in der gelesenen Version, ein fehlender nur, wenn er noch fehlt und
# (außer beim ausdrücklichen Wiederherstellen) nicht im Studio gelöscht wurde.
_WERK_AKTUALISIEREN = text("""
    UPDATE config_areas
       SET data = CAST(:data AS jsonb), version = version + 1, updated_at = now(),
           updated_by = :updated_by, werk_hash = :werk_hash,
           eigene_fassung = COALESCE(eigene_fassung, CAST(:parken AS jsonb))
     WHERE area = :area AND version = :expected
    RETURNING version
""")
_WERK_ANLEGEN = text(f"""
    INSERT INTO config_areas (area, data, updated_by, version, werk_hash)
    SELECT :area, CAST(:data AS jsonb), :updated_by, {FIRST_VERSION}, :werk_hash
     WHERE :trotz_entfernt OR NOT EXISTS (
           SELECT 1 FROM config_werk_entfernt WHERE area = :area)
    ON CONFLICT (area) DO NOTHING
    RETURNING version
""")
_SELECT_META = text("SELECT version, updated_at, updated_by FROM config_areas WHERE area = :area")
_SELECT_FASSUNG = text("""
    SELECT data, version, werk_hash, eigene_fassung, eigene_basis
    FROM config_areas WHERE area = :area
""")
_SELECT_FASSUNGEN = text("""
    SELECT area, data, version, updated_by, werk_hash,
           eigene_fassung IS NOT NULL AS hat_eigene_fassung
    FROM config_areas ORDER BY area
""")


class EigeneFassungLiegtStill(Exception):
    """Der Bereich trägt eine stillgelegte eigene Fassung — Löschen nähme sie mit (Review 2 #1)."""

    def __init__(self, area: str) -> None:
        super().__init__(f"config area {area!r} has an own version set aside")
        self.area = area


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

    async def stop(self, *, frist_s: float = ABBRUCH_FRIST_S) -> None:
        """Den Listener anhalten, höchstens ``frist_s`` (der Rest der Frist beim Herunterfahren)."""
        await self._listener.stop(frist_s=frist_s)

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Register for area-change events (loader caches etc.)."""
        self._subscribers.append(callback)

    def _on_area_changed(self, area: str) -> None:
        # Paket 17 (C3): a ``__`` payload is a signal on the same channel (e.g. the shared
        # master-skill state), not an area — nothing to fetch, only the subscribers hear it.
        if area.startswith("__"):
            pass
        # refetch-and-overwrite (no pop first) so SYNC readers of the loader
        # facade (get_cached) never see an empty window between drop and refill
        elif area in self._fetching:
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
        """Cache ``data`` unless the cache already holds a newer version.

        Switches the area model types as ``bool`` are read the way the gate reads them
        (Paket 18E: ``"false"`` stored from the raw-text editor is off for every reader,
        not only the loaders); the database row stays as stored."""
        if version < self._versions.get(area, 0):
            return
        self._cache[area] = normalisiere_schalter(area, data)
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
        return self._cache.get(area, row[0])

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
            await conn.execute(_ENTFERNT_AUSTRAGEN, {"area": area})
        self._remember(area, data, version)
        return version

    async def put_many(
        self, items: dict[str, dict[str, Any]], updated_by: str = "",
        delete: Iterable[str] = (), *, werk_hashes: Mapping[str, str] | None = None,
        werk_bereiche: Collection[str] = (),
    ) -> dict[str, int]:
        """Upserts + history rows, then deletions — all in ONE transaction.

        ``werk_hashes`` (Paket 12): für Bereiche, die aus der Werksfassung geschrieben werden, deren
        Prüfsumme — der Bereich steht danach nachweislich auf dieser Werksfassung. Andere Schreiber
        lassen die gemerkte Basis, wie sie ist. ``werk_bereiche``: welche der gelöschten Bereiche
        laut Seed zur Werksfassung gehören (Löschvermerk). Ein Bereich mit stillgelegter eigener
        Fassung wird nie gelöscht — die Aufrufer filtern ihn vorher heraus und melden ihn.

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
                await conn.execute(_ENTFERNT_AUSTRAGEN, {"area": area})
                if werk_hashes and area in werk_hashes:
                    await conn.execute(
                        _WERK_HASH_SETZEN, {"area": area, "werk_hash": werk_hashes[area]})
            for area in gone:
                await conn.execute(_ENTFERNT_EINTRAGEN,
                                   {"area": area, "werksbereich": area in werk_bereiche})
                await conn.execute(_DELETE_OHNE_EIGENE, {"area": area})
        # write-through, only after the commit: warm the cache with what we just
        # wrote so an immediate SYNC loader re-read (typed PUT endpoints) sees
        # the fresh value; the self-NOTIFY refetch lands the same value
        # idempotently. A newer version another replica wrote meanwhile stays.
        for area, version in versions.items():
            self._remember(area, items[area], version)
        for area in gone:
            self._forget(area)
        return versions

    async def delete(
        self, area: str, *, expected_version: int | None = None, werksbereich: bool = False,
    ) -> bool:
        """Delete an area (config file DELETE, P2-5). Returns False if absent;
        with ``expected_version`` only that version (``delete_checked``)."""
        async with self._engine.begin() as conn:
            zeile = (await conn.execute(_HAT_EIGENE, {"area": area})).first()
            if zeile is not None and zeile[0]:
                raise EigeneFassungLiegtStill(area)
            await conn.execute(_ENTFERNT_EINTRAGEN, {"area": area, "werksbereich": werksbereich})
            if expected_version is not None:
                geloescht = await delete_checked(conn, area=area, expected_version=expected_version)
            else:
                geloescht = (await conn.execute(_DELETE_AREA, {"area": area})).first() is not None
        self._forget(area)
        return geloescht

    async def umschalten(
        self, area: str, neu: Fassung, *, expected_version: int, updated_by: str,
    ) -> int:
        """Zwischen Werksfassung und eigener Fassung wechseln (Paket 12) — ``neu`` kommt aus
        ``werkfassung.umschalten``. Bedingt auf die gelesene Version wie jedes Studio-Speichern
        (``ConfigConflict``), ein UPDATE plus Verlaufszeile in einer Transaktion."""
        if neu.data is None:
            raise ValueError("umschalten braucht einen Inhalt")
        payload = als_json(area, neu.data)
        params = {
            "area": area, "data": payload, "updated_by": updated_by,
            "werk_hash": neu.werk_hash, "expected": expected_version,
            "eigene": None if neu.eigene is None else als_json(area, neu.eigene),
            "eigene_basis": neu.eigene_basis,
        }
        async with self._engine.begin() as conn:
            with als_bereichsfehler(area):
                row = (await conn.execute(_UMSCHALTEN, params)).first()
            if row is None:
                meta = (await conn.execute(_SELECT_META, {"area": area})).mappings().first()
                raise ConfigConflict(area, dict(meta) if meta is not None else None)
            version = int(row[0])
            await conn.execute(
                _HISTORY_INSERT,
                {"area": area, "version": version, "data": payload, "updated_by": updated_by},
            )
        self._remember(area, neu.data, version)
        return version

    async def werk_schreiben(
        self, eintraege: Mapping[
            str, tuple[dict[str, Any], str, int | None, dict[str, Any] | None]], *,
        updated_by: str, trotz_entfernt: bool = False,
    ) -> dict[str, int]:
        """Werksfassungen bedingt schreiben — ``{area: (data, werk_hash, gelesene Version,
        parken)}``. ``parken``: alter Inhalt, der stillgelegt wird, sofern noch keine eigene
        Fassung stillliegt (Review 2 #4); eine vorhandene wird nie verdrängt.

        Version ``None`` heißt „fehlte beim Lesen“: dann nur anlegen, wenn er noch fehlt und nicht
        im Studio gelöscht wurde (``trotz_entfernt`` für „Werksfassung wiederherstellen“). Gibt nur
        die geschriebenen Bereiche zurück; was sich seit dem Lesen geändert hat, bleibt stehen.
        Eine Transaktion für alle."""
        versionen: dict[str, int] = {}
        async with self._engine.begin() as conn:
            for area, (data, werk_hash, gelesen, parken) in eintraege.items():
                payload = als_json(area, data, ganzer_vorgang=len(eintraege) > 1)
                params = {"area": area, "data": payload, "updated_by": updated_by,
                          "werk_hash": werk_hash}
                with als_bereichsfehler(area, ganzer_vorgang=len(eintraege) > 1):
                    if gelesen is None:
                        row = (await conn.execute(
                            _WERK_ANLEGEN, {**params, "trotz_entfernt": trotz_entfernt})).first()
                    else:
                        row = (await conn.execute(_WERK_AKTUALISIEREN, {
                            **params, "expected": gelesen,
                            "parken": None if parken is None else als_json(area, parken),
                        })).first()
                if row is None:
                    continue
                versionen[area] = int(row[0])
                await conn.execute(
                    _HISTORY_INSERT,
                    {"area": area, "version": versionen[area], "data": payload,
                     "updated_by": updated_by},
                )
                await conn.execute(_ENTFERNT_AUSTRAGEN, {"area": area})
        for area, version in versionen.items():
            self._remember(area, eintraege[area][0], version)
        return versionen

    async def werk_hashes_setzen(self, hashes: Mapping[str, str]) -> None:
        """Nur die Basis merken; Inhalt und Version bleiben (Erstzuordnung des Bestands)."""
        if not hashes:
            return
        async with self._engine.begin() as conn:
            for area, werk_hash in hashes.items():
                await conn.execute(_WERK_HASH_SETZEN, {"area": area, "werk_hash": werk_hash})

    async def fassung(self, area: str) -> dict[str, Any] | None:
        """Inhalt, Version, Werks-Prüfsumme und stillgelegte eigene Fassung — aus der Datenbank."""
        async with self._engine.connect() as conn:
            row = (await conn.execute(_SELECT_FASSUNG, {"area": area})).mappings().first()
        return None if row is None else dict(row)

    async def fassungen(self) -> list[dict[str, Any]]:
        """Alle Bereiche mit Inhalt und Fassungs-Metadaten (ohne die stillgelegten Inhalte)."""
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_SELECT_FASSUNGEN)).mappings().all()
        return [dict(r) for r in rows]

    async def entfernte(self) -> set[str]:
        """Im Studio gelöschte Bereiche (``config_werk_entfernt``)."""
        async with self._engine.connect() as conn:
            return {r[0] for r in (await conn.execute(_SELECT_ENTFERNT)).all()}

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
