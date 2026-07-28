"""P2-7: snapshots / backup / factory endpoints against a fresh Compose-PG.

Create -> list -> restore -> delete; factory save/restore; live backup
download; restore upload (config areas re-applied); zip-bomb rejected at the
HTTP boundary.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.config_store import ConfigStore
from boerdi.settings import Settings, get_settings
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p2_snapshots_test"
_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture(scope="module")
def _module_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


@pytest.fixture()
def cfg(_module_db, monkeypatch):
    from sqlalchemy.pool import NullPool

    from boerdi.db.session import make_engine

    engine = make_engine(
        Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
        poolclass=NullPool,
    )
    store = ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(_DB))
    config_loader.bind_store(store)
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    client = TestClient(create_app())

    def seed(area: str, data: dict) -> None:
        asyncio.run(store.put(area, data, updated_by="seed"))

    # clean any rows a prior test left in the shared module DB
    async def _wipe():
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM config_snapshots"))
            await conn.execute(text("DELETE FROM config_areas"))
    asyncio.run(_wipe())
    store._cache.clear()

    yield client, seed
    config_loader.bind_store(None)
    asyncio.run(engine.dispose())


def test_snapshot_create_list_restore_delete(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Original", "quick_replies": ["a"]}})

    created = client.post("/api/config/snapshots", headers=_AUTH, json={"label": "before-edit"})
    assert created.status_code == 200
    snap_id = created.json()["id"]

    listing = client.get("/api/config/snapshots", headers=_AUTH).json()
    assert any(s["id"] == snap_id and s["label"] == "before-edit" for s in listing)

    # mutate config, then restore the snapshot -> original comes back
    client.put("/api/config/welcome", headers=_AUTH,
               json={"greeting": "Changed", "quick_replies": ["b"]})
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Changed"
    r = client.post(f"/api/config/snapshots/{snap_id}/restore", headers=_AUTH)
    assert r.status_code == 200
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Original"

    assert client.delete(f"/api/config/snapshots/{snap_id}", headers=_AUTH).status_code == 200
    assert client.post(f"/api/config/snapshots/{snap_id}/restore",
                       headers=_AUTH).status_code == 404


def test_snapshot_download_is_zip(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "X", "quick_replies": ["a"]}})
    snap_id = client.post("/api/config/snapshots", headers=_AUTH, json={"label": "z"}).json()["id"]
    dl = client.get(f"/api/config/snapshots/{snap_id}/download", headers=_AUTH)
    assert dl.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl.content)) as z:
        assert "config/01-base/welcome-config.yaml" in z.namelist()


def test_factory_save_and_restore(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Fabrik", "quick_replies": ["a"]}})
    assert client.post("/api/config/factory/save", headers=_AUTH).status_code == 200
    info = client.get("/api/config/factory", headers=_AUTH).json()
    assert info["exists"] is True

    client.put("/api/config/welcome", headers=_AUTH,
               json={"greeting": "Weg", "quick_replies": ["b"]})
    assert client.post("/api/config/factory/restore", headers=_AUTH).status_code == 200
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Fabrik"


def test_backup_download_and_restore_upload(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Backup", "quick_replies": ["a"]}})
    backup = client.get("/api/config/backup", headers=_AUTH)
    assert backup.status_code == 200 and backup.content[:2] == b"PK"

    # wipe + restore from the downloaded zip
    client.request("DELETE", "/api/config/file",
                   params={"path": "01-base/welcome-config.yaml"}, headers=_AUTH)
    up = client.post("/api/config/restore", headers=_AUTH,
                     files={"file": ("backup.zip", backup.content, "application/zip")})
    assert up.status_code == 200
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Backup"


def test_restore_rejects_zip_bomb(cfg, monkeypatch) -> None:
    client, _ = cfg
    from boerdi.services import snapshots
    monkeypatch.setattr(snapshots, "MAX_DECOMPRESSED_BYTES", 1024 * 1024)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("config/01-base/welcome-config.yaml", b"\0" * (5 * 1024 * 1024))
    up = client.post("/api/config/restore", headers=_AUTH,
                     files={"file": ("bomb.zip", buf.getvalue(), "application/zip")})
    assert up.status_code == 413


def test_snapshot_endpoints_require_studio_key(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/snapshots").status_code == 401
    assert client.get("/api/config/backup").status_code == 401
