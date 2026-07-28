"""P2-2: config_store — DB-backed area store with versioning, history,
process cache and NOTIFY-driven invalidation (spec §6 / improvement V2).
Runs against the live Compose-Postgres (fresh throwaway DB).
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p2_store_test"
_AREA = "01-base/welcome-config"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _make_store(db: str):
    from boerdi.db.session import make_engine
    from boerdi.services.config_store import ConfigStore
    from boerdi.settings import Settings

    engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))
    return ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(db)), engine


def test_get_missing_area_returns_none(test_db) -> None:
    async def scenario():
        store, engine = _make_store(test_db)
        try:
            return await store.get("does/not-exist")
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) is None


def test_put_get_roundtrip_with_version_and_history(test_db) -> None:
    async def scenario():
        store, engine = _make_store(test_db)
        try:
            v1 = await store.put(_AREA, {"greeting": "Moin"}, updated_by="test")
            first = await store.get(_AREA)
            v2 = await store.put(_AREA, {"greeting": "Servus"}, updated_by="editor")
            second = await store.get(_AREA)
            history = await store.history(_AREA)
            return v1, first, v2, second, history
        finally:
            await engine.dispose()

    v1, first, v2, second, history = asyncio.run(scenario())
    assert v1 == 1 and first == {"greeting": "Moin"}
    assert v2 == 2 and second == {"greeting": "Servus"}
    assert [h["version"] for h in history] == [2, 1]  # newest first
    assert history[0]["updated_by"] == "editor"
    assert history[1]["data"] == {"greeting": "Moin"}


def test_put_is_write_through(test_db) -> None:
    """put warms the cache with the written value — an immediate SYNC read
    (loader facade get_cached) sees it without any DB fetch."""

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/policy", {"x": 1})
            calls = 0
            original = store._fetch

            async def counting_fetch(area: str):
                nonlocal calls
                calls += 1
                return await original(area)

            store._fetch = counting_fetch
            assert store.get_cached("01-base/policy") == {"x": 1}  # sync, no fetch
            await store.get("01-base/policy")  # cache hit
            return calls
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) == 0  # write-through -> no fetch needed


def test_cold_get_fetches_once_then_caches(test_db) -> None:
    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/states", {"y": 2})
            store.clear_cache()  # simulate a cold process cache
            calls = 0
            original = store._fetch

            async def counting_fetch(area: str):
                nonlocal calls
                calls += 1
                return await original(area)

            store._fetch = counting_fetch
            await store.get("01-base/states")
            await store.get("01-base/states")
            await store.get("01-base/states")
            return calls
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) == 1  # one DB hit, two cache hits


def test_delete_removes_area(test_db) -> None:
    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/device-config", {"z": 3})
            deleted = await store.delete("01-base/device-config")
            absent = await store.delete("01-base/device-config")
            return deleted, absent, store.get_cached("01-base/device-config")
        finally:
            await engine.dispose()

    deleted, absent, cached = asyncio.run(scenario())
    assert deleted is True and absent is False and cached is None


def test_preload_fills_cache_for_sync_reads(test_db) -> None:
    """The loader facade (P2-3) reads synchronously via get_cached() —
    preload() must warm the cache and get_cached() must not touch the DB."""

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/intents", {"intents": [{"id": "I01"}]})
            await store.put("01-base/states", {"states": [{"id": "S1"}]})
            await store.preload(["01-base/intents", "01-base/states", "does/not-exist"])
            return (
                store.get_cached("01-base/intents"),
                store.get_cached("01-base/states"),
                store.get_cached("does/not-exist"),
            )
        finally:
            await engine.dispose()

    intents, states, missing = asyncio.run(scenario())
    assert intents == {"intents": [{"id": "I01"}]}
    assert states == {"states": [{"id": "S1"}]}
    assert missing is None


def test_notify_refreshes_cache_in_place(test_db) -> None:
    """After a foreign write, the cached entry is REFRESHED (not just
    dropped) so sync get_cached() readers see the new value without a
    DB round-trip of their own."""

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.start()
            await store.put("01-base/welcome-r", {"v": "old"})
            await store.preload(["01-base/welcome-r"])

            conn = await asyncpg.connect(pg_utils.asyncpg_dsn(test_db))
            try:
                await conn.execute(
                    "UPDATE config_areas SET data=$1::jsonb, version=version+1 "
                    "WHERE area=$2",
                    json.dumps({"v": "new"}), "01-base/welcome-r",
                )
            finally:
                await conn.close()

            for _ in range(40):  # < 2s (spec §8)
                if store.get_cached("01-base/welcome-r") == {"v": "new"}:
                    return True
                await asyncio.sleep(0.05)
            return False
        finally:
            await store.stop()
            await engine.dispose()

    assert asyncio.run(scenario()) is True


def test_notify_from_other_writer_drops_cache(test_db) -> None:
    """Acceptance (spec P2-2): a foreign write (other replica) must reach
    this process' reads via the real trigger->NOTIFY->listener chain."""

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.start()  # listener on
            await store.put(_AREA + "-x", {"v": "old"})
            assert (await store.get(_AREA + "-x")) == {"v": "old"}  # now cached

            conn = await asyncpg.connect(pg_utils.asyncpg_dsn(test_db))
            try:
                await conn.execute(
                    "UPDATE config_areas SET data=$1::jsonb, version=version+1 "
                    "WHERE area=$2",
                    json.dumps({"v": "new"}), _AREA + "-x",
                )
            finally:
                await conn.close()

            for _ in range(40):  # up to 2s (spec: propagation < 2s)
                if (await store.get(_AREA + "-x")) == {"v": "new"}:
                    return True
                await asyncio.sleep(0.05)
            return False
        finally:
            await store.stop()
            await engine.dispose()

    assert asyncio.run(scenario()) is True
