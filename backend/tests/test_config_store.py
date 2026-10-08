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


# ── Paket 4, D4 (externes Audit F07): mehrere Bereiche in EINER Transaktion ──
# Postgres weist ``\u0000`` in jsonb ab — ein Fehler der Datenbank selbst, im
# dritten Bereich, nach zwei gelungenen Schreibvorgängen.

def test_put_many_schreibt_alles_oder_nichts(test_db) -> None:
    # Paket 4b, A4: der Datenfehler nennt seinen Bereich, statt als 500 zu enden.
    from boerdi.services.config_conflict import BereichNichtSpeicherbar

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/d4-a", {"v": 1})
            with pytest.raises(BereichNichtSpeicherbar) as fehler:
                await store.put_many({
                    "01-base/d4-a": {"v": 2},
                    "01-base/d4-b": {"v": 2},
                    "01-base/d4-kaputt": {"x": "\x00"},
                }, updated_by="restore")
            gespeichert = (await store._fetch("01-base/d4-a"), await store._fetch("01-base/d4-b"))
            im_cache = (store.get_cached("01-base/d4-a"), store.get_cached("01-base/d4-b"))
            return gespeichert, im_cache, fehler.value
        finally:
            await engine.dispose()

    gespeichert, im_cache, fehler = asyncio.run(scenario())
    assert gespeichert == (({"v": 1}, 1), None)
    assert im_cache == ({"v": 1}, None)
    assert fehler.area == "01-base/d4-kaputt"
    assert fehler.ganzer_vorgang is True  # drei Bereiche, eine Transaktion: alle verworfen


def test_ein_bedingter_put_meldet_den_datenfehler_mit_bereich(test_db) -> None:
    from boerdi.services.config_conflict import BereichNichtSpeicherbar

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            v1 = await store.put("01-base/d4-c", {"v": 1})
            with pytest.raises(BereichNichtSpeicherbar) as fehler:
                await store.put("01-base/d4-c", {"x": "\x00"}, expected_version=v1)
            return fehler.value, await store._fetch("01-base/d4-c")
        finally:
            await engine.dispose()

    fehler, gespeichert = asyncio.run(scenario())
    assert fehler.area == "01-base/d4-c"
    assert fehler.ganzer_vorgang is False  # nur dieser eine Bereich
    assert gespeichert == ({"v": 1}, 1)


def test_ein_einzelner_put_ist_kein_ganzer_vorgang(test_db) -> None:
    """Review 4b: ``put`` läuft über ``put_many`` mit einem Bereich — eine
    Route, die je Bereich ``put`` ruft, hat davor schon geschrieben."""
    from boerdi.services.config_conflict import BereichNichtSpeicherbar

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            with pytest.raises(BereichNichtSpeicherbar) as fehler:
                await store.put("01-base/d4-d", {"x": "\x00"})
            return fehler.value
        finally:
            await engine.dispose()

    fehler = asyncio.run(scenario())
    assert (fehler.area, fehler.ganzer_vorgang) == ("01-base/d4-d", False)


def test_put_many_loescht_in_derselben_transaktion(test_db) -> None:
    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/d4-weg", {"alt": True})
            versionen = await store.put_many({"01-base/d4-neu": {"neu": True}},
                                             updated_by="seed-apply", delete=["01-base/d4-weg"])
            return (versionen, await store._fetch("01-base/d4-weg"),
                    store.get_cached("01-base/d4-weg"), store.get_cached("01-base/d4-neu"),
                    await store.history("01-base/d4-neu"))
        finally:
            await engine.dispose()

    versionen, weg, weg_im_cache, neu_im_cache, verlauf = asyncio.run(scenario())
    assert versionen == {"01-base/d4-neu": 1}
    assert weg is None and weg_im_cache is None
    assert neu_im_cache == {"neu": True}
    assert [h["updated_by"] for h in verlauf] == ["seed-apply"]


# ── Paket 4, D5 (externes Audit F14): Speichern mit Konfliktschutz ─────────────

def test_put_mit_alter_version_ist_ein_konflikt_und_schreibt_nichts(test_db) -> None:
    from boerdi.services.config_conflict import ConfigConflict

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            v1 = await store.put("01-base/d5-a", {"v": 1}, updated_by="erste")
            await store.put("01-base/d5-a", {"v": 2}, updated_by="zweite", expected_version=v1)
            with pytest.raises(ConfigConflict) as err:
                await store.put("01-base/d5-a", {"v": 3}, updated_by="dritte",
                                expected_version=v1)
            return err.value, await store._fetch("01-base/d5-a"), store.get_cached("01-base/d5-a")
        finally:
            await engine.dispose()

    konflikt, gespeichert, im_cache = asyncio.run(scenario())
    assert konflikt.current is not None
    assert konflikt.current["version"] == 2
    assert konflikt.current["updated_by"] == "zweite"
    assert gespeichert == ({"v": 2}, 2)
    assert im_cache == {"v": 2}


def test_anlegen_ueber_bestehendes_ist_ein_konflikt(test_db) -> None:
    from boerdi.services.config_conflict import ConfigConflict

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/d5-b", {"da": True}, updated_by="erste")
            with pytest.raises(ConfigConflict):
                await store.put("01-base/d5-b", {"neu": True}, create_only=True)
            frei = await store.put("01-base/d5-frei", {"neu": True}, create_only=True)
            return await store._fetch("01-base/d5-b"), frei
        finally:
            await engine.dispose()

    gespeichert, frei = asyncio.run(scenario())
    assert gespeichert == ({"da": True}, 1)
    assert frei == 1


def test_eine_geloeschte_zeile_ist_ein_konflikt_ohne_stand(test_db) -> None:
    from boerdi.services.config_conflict import ConfigConflict

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            v1 = await store.put("01-base/d5-c", {"v": 1})
            await store.delete("01-base/d5-c")
            with pytest.raises(ConfigConflict) as err:
                await store.put("01-base/d5-c", {"v": 2}, expected_version=v1)
            return err.value, await store._fetch("01-base/d5-c")
        finally:
            await engine.dispose()

    konflikt, gespeichert = asyncio.run(scenario())
    assert konflikt.current is None
    assert gespeichert is None


# ── Paket 4, Prüfer 2026-10-04: Versionen zählen über das Löschen hinweg ──────
#
# Eine neu angelegte Zeile begann wieder bei Version 1. Dieselbe Nummer stand
# dann für zwei verschiedene Stände: Der Konfliktschutz nahm eine Speicherung
# gegen den gelöschten Stand an (ABA), und ein Resync nach Verbindungsabriss
# verwarf die neue Zeile als „älter“ als den Cache.

def test_nach_loeschen_und_neuanlage_zaehlt_die_version_weiter(test_db) -> None:
    async def scenario():
        store, engine = _make_store(test_db)
        try:
            await store.put("01-base/d5-d", {"v": 1})
            v2 = await store.put("01-base/d5-d", {"v": 2})
            await store.delete("01-base/d5-d")
            per_upsert = await store.put("01-base/d5-d", {"v": "neu"})
            await store.delete("01-base/d5-d")
            per_anlegen = await store.put("01-base/d5-d", {"v": "neuer"}, create_only=True)
            return v2, per_upsert, per_anlegen
        finally:
            await engine.dispose()

    v2, per_upsert, per_anlegen = asyncio.run(scenario())
    assert per_upsert == v2 + 1
    assert per_anlegen == v2 + 2


def test_alte_version_nach_neuanlage_ist_ein_konflikt(test_db) -> None:
    from boerdi.services.config_conflict import ConfigConflict

    async def scenario():
        store, engine = _make_store(test_db)
        try:
            geladen = await store.put("01-base/d5-e", {"v": "alt"})  # Editor A lädt
            await store.delete("01-base/d5-e")  # B löscht …
            await store.put("01-base/d5-e", {"v": "neu"}, create_only=True)  # … und legt neu an
            with pytest.raises(ConfigConflict):
                await store.put("01-base/d5-e", {"v": "von A"}, expected_version=geladen)
            return await store._fetch("01-base/d5-e")
        finally:
            await engine.dispose()

    data, _version = asyncio.run(scenario())
    assert data == {"v": "neu"}
