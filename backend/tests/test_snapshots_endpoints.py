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


# ── S3: Auslieferungsstand aus dem Bild (docs/plans/2026-08-17-…) ──────────
# Der Seed-Baum wird je Test frisch gebaut: ein echter Baum im Repo hätte 35
# Bereiche und machte die Zählungen unlesbar. Geprüft wird die Mechanik, nicht
# der Inhalt des ausgelieferten Standes.

@pytest.fixture()
def seed_baum(tmp_path, monkeypatch):
    """Ein winziger Seed-Baum + ``CONFIG_SEED_DIR`` darauf."""
    (tmp_path / "01-base").mkdir()

    def schreibe(rel: str, text: str) -> None:
        (tmp_path / rel).write_text(text, encoding="utf-8")

    monkeypatch.setenv("CONFIG_SEED_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield schreibe
    get_settings.cache_clear()


def test_seed_status_zaehlt_gegen_den_gelebten_stand(cfg, seed_baum) -> None:
    client, seed = cfg
    seed_baum("01-base/engine.yaml", "mode: pattern\n")          # gleich
    seed_baum("01-base/welcome-config.yaml", "welcome:\n  greeting: Seed\n")  # abweichend
    seed_baum("01-base/neu.yaml", "a: 1\n")                       # nur im Seed
    seed("01-base/engine", {"mode": "pattern"})
    seed("01-base/welcome-config", {"welcome": {"greeting": "Gepflegt"}})
    seed("01-base/eigenbau", {"x": 1})                            # nur in der DB

    r = client.get("/api/config/seed", headers=_AUTH)
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is True and d["area_count"] == 3
    assert d["neu"] == ["01-base/neu"]
    assert d["gleich"] == ["01-base/engine"]
    assert d["abweichend"] == ["01-base/welcome-config"]
    assert d["nur_in_db"] == ["01-base/eigenbau"]


def test_seed_status_ohne_baum_ist_nicht_verfuegbar(cfg, monkeypatch) -> None:
    """Fremd gebautes Bild / falsche Variable: kein 500, sondern eine Aussage."""
    client, _ = cfg
    monkeypatch.setenv("CONFIG_SEED_DIR", "gibt-es-nicht-42")
    get_settings.cache_clear()
    d = client.get("/api/config/seed", headers=_AUTH).json()
    assert d["available"] is False and d["area_count"] == 0
    get_settings.cache_clear()


def test_missing_zieht_nur_fehlende_nach(cfg, seed_baum) -> None:
    client, seed = cfg
    seed_baum("01-base/welcome-config.yaml", "welcome:\n  greeting: Seed\n")
    seed_baum("01-base/neu.yaml", "a: 1\n")
    seed("01-base/welcome-config", {"welcome": {"greeting": "Gepflegt"}})

    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "missing"})
    assert r.status_code == 200
    assert r.json() == {"written": 1, "deleted": 0, "snapshot_id": None}
    # die gepflegte Begrüßung hat den Lauf überlebt — das ist der ganze Zweck
    # des harmlosen Knopfes
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Gepflegt"


def test_exact_ueberschreibt_loescht_und_sichert_vorher(cfg, seed_baum) -> None:
    client, seed = cfg
    seed_baum("01-base/welcome-config.yaml",
              "welcome:\n  greeting: Seed\n  quick_replies: [a]\n")
    seed("01-base/welcome-config", {"welcome": {"greeting": "Gepflegt", "quick_replies": ["b"]}})
    seed("01-base/eigenbau", {"x": 1})

    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "exact"})
    assert r.status_code == 200
    d = r.json()
    assert d["written"] == 1 and d["deleted"] == 1
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Seed"

    # Der Rückweg ist das Kernversprechen des scharfen Knopfes: der Schnappschuss
    # muss existieren UND den Zustand VOR dem Lauf tragen.
    assert d["snapshot_id"] is not None
    assert any(s["id"] == d["snapshot_id"] for s in
               client.get("/api/config/snapshots", headers=_AUTH).json())
    client.post(f"/api/config/snapshots/{d['snapshot_id']}/restore", headers=_AUTH)
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Gepflegt"


def test_exact_ohne_platz_fuer_den_schnappschuss_wird_verweigert(
    cfg, seed_baum, monkeypatch
) -> None:
    """Ohne Rückweg kein verlustbehafteter Lauf — lieber 400 als eine Löschung,
    die niemand rückgängig machen kann."""
    client, seed = cfg
    seed_baum("01-base/neu.yaml", "a: 1\n")
    seed("01-base/eigenbau", {"x": 1})
    from boerdi.services import snapshots
    monkeypatch.setattr(snapshots, "MAX_SNAPSHOTS", 0)

    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "exact"})
    assert r.status_code == 400
    # nichts angefasst
    assert client.get("/api/config/seed", headers=_AUTH).json()["nur_in_db"] == \
        ["01-base/eigenbau"]


def test_apply_ohne_baum_ist_404(cfg, monkeypatch) -> None:
    """Der Status-Code allein beweist hier nichts: eine unbekannte Route
    antwortet ebenfalls mit 404. Geprüft wird deshalb die Begründung."""
    client, _ = cfg
    monkeypatch.setenv("CONFIG_SEED_DIR", "gibt-es-nicht-42")
    get_settings.cache_clear()
    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "missing"})
    assert r.status_code == 404
    assert "CONFIG_SEED_DIR" in r.json()["detail"]
    get_settings.cache_clear()


def test_unbekannter_modus_wird_am_rand_abgewiesen(cfg, seed_baum) -> None:
    """Der Literal-Typ hält den Tippfehler auf, bevor er die Datenbank sieht."""
    client, _ = cfg
    seed_baum("01-base/neu.yaml", "a: 1\n")
    assert client.post("/api/config/seed/apply", headers=_AUTH,
                       json={"mode": "alles"}).status_code == 422


def test_seed_endpunkte_verlangen_den_studio_schluessel(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/seed").status_code == 401
    assert client.post("/api/config/seed/apply", json={"mode": "missing"}).status_code == 401
