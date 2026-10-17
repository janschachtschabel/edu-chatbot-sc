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
    seed("01-base/notizen", {"x": 1})
    backup = client.get("/api/config/backup", headers=_AUTH)
    assert backup.status_code == 200 and backup.content[:2] == b"PK"

    # Ändern und löschen, dann aus dem ZIP zurück. Bis Review Paket 6 „löschte“
    # der Test den festen Bereich — seit S1 abgewiesen, ungeprüft: nichts fehlte.
    r = client.put("/api/config/welcome", headers=_AUTH,
                   json={"greeting": "Weg", "quick_replies": ["b"]})
    assert r.status_code == 200
    r = client.request("DELETE", "/api/config/file",
                       params={"path": "01-base/notizen.yaml"}, headers=_AUTH)
    assert r.status_code == 200
    up = client.post("/api/config/restore", headers=_AUTH,
                     files={"file": ("backup.zip", backup.content, "application/zip")})
    assert up.status_code == 200
    assert client.get("/api/config/welcome", headers=_AUTH).json()["greeting"] == "Backup"
    zurueck = client.get("/api/config/file", params={"path": "01-base/notizen.yaml"},
                         headers=_AUTH)
    assert zurueck.status_code == 200


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


def test_restore_ueberspringt_nur_ungueltige_pfade(cfg) -> None:
    # Audit 2026-09-29, A-M7: ``../…`` aus einer ZIP-Datei landet nicht mehr im
    # Bestand. Review 2026-10-03: Bereiche ohne Modell überstehen das
    # Wiederherstellen — ``01-base/rag-retrieval`` wird gelesen, ist aber nicht
    # registriert. Es gilt die Pfadregel des rohen Datei-Schreibens.
    client, _ = cfg
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("config/01-base/welcome-config.yaml", "welcome:\n  greeting: Gut\n")
        z.writestr("config/01-base/rag-retrieval.yaml", "top_k: 7\n")
        z.writestr("config/../../boese.yaml", "x: 1\n")
    up = client.post("/api/config/restore", headers=_AUTH,
                     files={"file": ("teil.zip", buf.getvalue(), "application/zip")})
    assert up.status_code == 200
    assert up.json()["areas"] == 2
    assert sorted(asyncio.run(config_loader.current_config())) == [
        "01-base/rag-retrieval", "01-base/welcome-config"]


def test_restore_weist_interne_mcp_adressen_ab_und_schreibt_nichts(cfg) -> None:
    # Review 2026-10-03: dieselbe Ausgangsprüfung wie beim Schreiben im Studio
    # (``_assert_area_document_safe``), und zwar für alles, bevor etwas
    # geschrieben wird — sonst bliebe ein halb wiederhergestellter Stand.
    client, _ = cfg
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("config/01-base/welcome-config.yaml", "welcome:\n  greeting: Gut\n")
        z.writestr("config/05-knowledge/mcp-servers.yaml",
                   "servers:\n  - id: extra\n    url: http://169.254.169.254/mcp\n")
    up = client.post("/api/config/restore", headers=_AUTH,
                     files={"file": ("teil.zip", buf.getvalue(), "application/zip")})
    assert up.status_code == 400
    assert asyncio.run(config_loader.current_config()) == {}


def test_restore_schreibt_alles_oder_nichts(cfg) -> None:
    # Paket 4, D4 (externes Audit F07): je Bereich eine eigene Transaktion —
    # scheiterte der dritte, waren die ersten beiden schon neu. Postgres weist
    # ``\u0000`` in jsonb ab, nach allen Prüfungen davor. Seit Paket 4b (A4)
    # nennt die Antwort den Bereich (400) statt als 500 zu enden.
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Vorher"}})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("config/01-base/welcome-config.yaml", "welcome:\n  greeting: Nachher\n")
        z.writestr("config/01-base/rag-retrieval.yaml", "top_k: 7\n")
        z.writestr("config/01-base/zz-kaputt.yaml", 'x: "\\0"\n')
    r = client.post("/api/config/restore", headers=_AUTH,
                    files={"file": ("teil.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 400, r.text
    assert "01-base/zz-kaputt" in r.json()["detail"]
    # Das Studio zeigt nur diesen Text: Er muss sagen, dass nichts zurückkam.
    assert "Der ganze Vorgang wurde verworfen" in r.json()["detail"]
    assert asyncio.run(config_loader.current_config()) == {
        "01-base/welcome-config": {"welcome": {"greeting": "Vorher"}}}


def test_restore_prueft_gegen_das_modell_und_schreibt_nichts(cfg) -> None:
    # Paket 4, D3 (externes Audit F07): Wiederherstellen schrieb ohne
    # ``model_validate``. Ein Bereich, den das heutige Modell abweist, lief
    # durch und schaltete danach still auf Vorgaben zurück. Jetzt: 422 mit
    # Liste über ALLE Bereiche, und nichts ist geschrieben.
    client, _ = cfg
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("config/01-base/rag-retrieval.yaml", "top_k: 7\n")  # ohne Modell
        z.writestr("config/01-base/welcome-config.yaml",
                   "welcome:\n  quick_replies: not-a-list\n")
    up = client.post("/api/config/restore", headers=_AUTH,
                     files={"file": ("teil.zip", buf.getvalue(), "application/zip")})
    assert up.status_code == 422
    fehler = up.json()["detail"]
    assert [f["area"] for f in fehler] == ["01-base/welcome-config"]
    assert fehler[0]["loc"] == ["welcome", "quick_replies"]
    assert asyncio.run(config_loader.current_config()) == {}


def test_die_sicherung_kommt_aus_der_datenbank_nicht_aus_dem_cache(cfg) -> None:
    # Paket 4, D2 (externes Audit F08): Schnappschuss, Sicherung und
    # Seed-Vergleich entstanden aus dem Prozess-Cache. Hing er einer anderen
    # Replik hinterher, sicherte das Studio einen alten Stand.
    from sqlalchemy import text

    from boerdi.services import snapshots

    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "alt"}})

    async def _andere_replik_schreibt() -> None:
        # Direkt in die Tabelle: die NOTIFY erreicht diesen Prozess hier nicht.
        async with config_loader.store_engine().begin() as conn:
            await conn.execute(text(
                "UPDATE config_areas SET data = CAST(:d AS jsonb), version = version + 1 "
                "WHERE area = '01-base/welcome-config'"),
                {"d": '{"welcome": {"greeting": "neu"}}'})
    asyncio.run(_andere_replik_schreibt())
    assert config_loader.area("01-base/welcome-config") == {"welcome": {"greeting": "alt"}}

    r = client.get("/api/config/backup", headers=_AUTH)
    assert r.status_code == 200
    assert snapshots.parse_config_zip(r.content)["01-base/welcome-config"] == {
        "welcome": {"greeting": "neu"}}


# ── Paket 7 (P5, P5-5): Wiederherstellen „ergänzend“ (Vorgabe) oder „exakt“ ──

def _vorher_schnappschuss(client, seed) -> str:
    seed("01-base/welcome-config", {"welcome": {"greeting": "Original", "quick_replies": ["a"]}})
    return client.post("/api/config/snapshots", headers=_AUTH,
                       json={"label": "vorher"}).json()["id"]


def _da(client, area: str) -> bool:
    return client.get("/api/config/file", params={"path": f"{area}.yaml"},
                      headers=_AUTH).status_code == 200


def test_ergaenzend_laesst_neu_angelegte_bereiche_stehen(cfg) -> None:
    client, seed = cfg
    snap = _vorher_schnappschuss(client, seed)
    seed("01-base/eigenbau", {"x": 1})
    r = client.post(f"/api/config/snapshots/{snap}/restore", headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["deleted"] == 0
    assert r.json()["snapshot_id"] is None          # nichts gelöscht, nichts gesichert
    assert _da(client, "01-base/eigenbau")


def test_exakt_loescht_was_seitdem_dazukam_und_sichert_vorher(cfg) -> None:
    """Ein neues Muster oder ein Eigenbau-Bereich verschwindet — mit Rückweg:
    vorher entsteht ein Schnappschuss des Stands, den das Wiederherstellen ändert."""
    client, seed = cfg
    snap = _vorher_schnappschuss(client, seed)
    seed("01-base/eigenbau", {"x": 1})
    vorher = {s["id"] for s in client.get("/api/config/snapshots", headers=_AUTH).json()}

    r = client.post(f"/api/config/snapshots/{snap}/restore", headers=_AUTH,
                    params={"mode": "exact"})
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    assert not _da(client, "01-base/eigenbau")

    sicherung = {s["id"] for s in client.get("/api/config/snapshots", headers=_AUTH).json()}
    neu = sicherung - vorher
    assert neu == {r.json()["snapshot_id"]}          # die Antwort nennt den Rückweg
    client.post(f"/api/config/snapshots/{neu.pop()}/restore", headers=_AUTH)
    assert _da(client, "01-base/eigenbau")


def test_exakt_ohne_platz_fuer_die_sicherung_wird_verweigert(cfg, monkeypatch) -> None:
    client, seed = cfg
    snap = _vorher_schnappschuss(client, seed)
    seed("01-base/eigenbau", {"x": 1})
    from boerdi.services import snapshots
    monkeypatch.setattr(snapshots, "MAX_SNAPSHOTS", 1)   # der eine ist schon da
    r = client.post(f"/api/config/snapshots/{snap}/restore", headers=_AUTH,
                    params={"mode": "exact"})
    assert r.status_code == 400
    assert _da(client, "01-base/eigenbau")                 # nichts angefasst


def test_die_sicherung_vorher_traegt_die_sprache_der_anfrage(cfg) -> None:
    """Review Paket 7, C-11: das Etikett stand auch in der englischen Liste deutsch."""
    client, seed = cfg
    snap = _vorher_schnappschuss(client, seed)
    seed("01-base/eigenbau", {"x": 1})
    r = client.post(f"/api/config/snapshots/{snap}/restore",
                    headers={**_AUTH, "Accept-Language": "en"}, params={"mode": "exact"})
    assert r.status_code == 200
    liste = client.get("/api/config/snapshots", headers=_AUTH).json()
    label = next(s["label"] for s in liste if s["id"] == r.json()["snapshot_id"])
    assert label == "before restore (exact)"


def test_auch_backup_und_werkszustand_kennen_exakt(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Backup", "quick_replies": ["a"]}})
    backup = client.get("/api/config/backup", headers=_AUTH).content
    client.post("/api/config/factory/save", headers=_AUTH)
    seed("01-base/eigenbau", {"x": 1})
    up = client.post("/api/config/restore", headers=_AUTH, params={"mode": "exact"},
                     files={"file": ("backup.zip", backup, "application/zip")})
    assert up.status_code == 200 and up.json()["deleted"] == 1
    seed("01-base/eigenbau", {"x": 2})
    fab = client.post("/api/config/factory/restore", headers=_AUTH, params={"mode": "exact"})
    assert fab.status_code == 200 and fab.json()["deleted"] == 1


def test_exakt_mit_einer_sicherung_ohne_bereiche_wird_verweigert(cfg) -> None:
    """Review Paket 7, A-4: ein Fehlgriff bei der Datei (eine ZIP ohne ``config/``)
    hätte die gesamte Konfiguration gelöscht — zurück nur über den Schnappschuss."""
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Bleibt", "quick_replies": ["a"]}})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("fotos/urlaub.txt", "x")
    up = client.post("/api/config/restore", headers=_AUTH, params={"mode": "exact"},
                     files={"file": ("falsch.zip", buf.getvalue(), "application/zip")})
    assert up.status_code == 400
    assert _da(client, "01-base/welcome-config")
    assert client.get("/api/config/snapshots", headers=_AUTH).json() == []


def test_exakt_loescht_nichts_was_die_sicherung_traegt(cfg) -> None:
    """Review Paket 7, A-4: einen Bereich, dessen Pfad die heutige Regel nicht mehr
    zulässt (ein Unterordner unter ``03-patterns/``, vor Paket 4 noch möglich),
    überspringt das Wiederherstellen — löschen darf es ihn deshalb nicht: er steht
    in der Sicherung."""
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "B", "quick_replies": ["a"]}})
    seed("03-patterns/alt/m99", {"x": 1})
    backup = client.get("/api/config/backup", headers=_AUTH).content
    up = client.post("/api/config/restore", headers=_AUTH, params={"mode": "exact"},
                     files={"file": ("backup.zip", backup, "application/zip")})
    assert up.status_code == 200
    assert up.json()["deleted"] == 0
    assert "03-patterns/alt/m99" in asyncio.run(config_loader.current_config())


# ── Paket 9 (Review Paket 7: MAJOR 5, MINOR 32) ────────────────────────────────

_WILLKOMMEN = "welcome:\n  greeting: Neu\n  quick_replies: [a]\n"


def _teil_zip(**dateien: str) -> bytes:
    """Eine Sicherung mit genau diesen Dateien (Pfad unter ``config/`` → Text)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for pfad, text in dateien.items():
            z.writestr(f"config/{pfad}", text)
    return buf.getvalue()


def _hochladen(client, blob: bytes, mode: str = "merge"):
    return client.post("/api/config/restore", headers=_AUTH, params={"mode": mode},
                       files={"file": ("teil.zip", blob, "application/zip")})


def _muster_text(kennung: str) -> str:
    """Ein gültiges Muster aus dem Auslieferungsstand mit anderer Kennung."""
    from pathlib import Path
    seed = Path(__file__).resolve().parents[1] / "seeds" / "03-patterns"
    return (seed / "m03-slot-klaerung.md").read_text(encoding="utf-8").replace(
        "id: M03", f"id: {kennung}", 1)


def test_exakt_laesst_feste_bereiche_und_sicherheitsmuster_stehen(cfg) -> None:
    """Review Paket 7 (MAJOR 5): eine Teil-Sicherung mit „Exakt“ löschte die
    Sicherheits-Konfiguration und M01 — die Moderation lief danach mit ``mode: off``.
    Gelöscht wird nur, was auch der Lösch-Endpunkt löschen ließe."""
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "B", "quick_replies": ["a"]}})
    seed("01-base/safety-config", {"crisis_pattern": "M07"})
    seed("03-patterns/m01", {"frontmatter": {"id": "M01"}, "body": "x"})
    seed("03-patterns/krise", {"frontmatter": {"id": "M07"}, "body": "x"})
    seed("03-patterns/m42", {"frontmatter": {"id": "M42"}, "body": "x"})
    seed("01-base/eigenbau", {"x": 1})
    up = _hochladen(client, _teil_zip(**{"01-base/welcome-config.yaml": _WILLKOMMEN}), "exact")
    assert up.status_code == 200
    assert up.json()["deleted"] == 2                 # M42 und der Eigenbau
    live = asyncio.run(config_loader.current_config())
    assert {"01-base/safety-config", "03-patterns/m01", "03-patterns/krise"} <= set(live)
    assert "03-patterns/m42" not in live and "01-base/eigenbau" not in live


def test_wiederherstellen_bringt_gestrichene_bereiche_nicht_zurueck(cfg) -> None:
    client, _seed = cfg
    up = _hochladen(client, _teil_zip(**{
        "01-base/welcome-config.yaml": _WILLKOMMEN,
        "05-canvas/create-triggers.yaml": "triggers: [mach]\n"}))
    assert up.status_code == 200
    assert "05-canvas/create-triggers" not in asyncio.run(config_loader.current_config())


def test_wiederherstellen_prueft_die_kennungen_und_schreibt_nichts(cfg) -> None:
    """Review Paket 7 (MINOR 32): das Wiederherstellen umging die Kennungsregeln des
    Editors — M01 ließ sich umbenennen oder ein zweites Mal anlegen."""
    client, seed = cfg
    seed("03-patterns/m01", {"frontmatter": {"id": "M01"}, "body": "x"})
    doppelt = _hochladen(client, _teil_zip(**{
        "01-base/welcome-config.yaml": _WILLKOMMEN,
        "03-patterns/zweites-m01.md": _muster_text("M01")}))
    assert doppelt.status_code == 400
    umbenannt = _hochladen(client, _teil_zip(**{"03-patterns/m01.md": _muster_text("M99")}))
    assert umbenannt.status_code == 400
    live = asyncio.run(config_loader.current_config())
    assert "03-patterns/zweites-m01" not in live and "01-base/welcome-config" not in live
    assert live["03-patterns/m01"]["frontmatter"]["id"] == "M01"


def test_unbekannte_betriebsart_wird_am_rand_abgewiesen(cfg) -> None:
    client, seed = cfg
    snap = _vorher_schnappschuss(client, seed)
    r = client.post(f"/api/config/snapshots/{snap}/restore", headers=_AUTH,
                    params={"mode": "kaputt"})
    assert r.status_code == 422


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
    assert r.json() == {"written": 1, "deleted": 0, "snapshot_id": None, "behalten": []}
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


def test_ein_ungueltiger_seed_wird_vor_schnappschuss_und_schreiben_abgewiesen(
    cfg, seed_baum
) -> None:
    """Paket 6, W2: Das Anwenden prüft wie das Wiederherstellen. Vorher schrieb es
    einen ungültigen Seed — etwa eine unbekannte Maschine, auf die ``load_engine``
    dann still mit der Muster-Maschine zurückfiel."""
    client, seed = cfg
    seed_baum("01-base/engine.yaml", "mode: kaputt\n")
    seed_baum("01-base/neu.yaml", "a: 1\n")
    seed("01-base/engine", {"mode": "agent"})
    vorher = client.get("/api/config/snapshots", headers=_AUTH).json()

    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "exact"})
    assert r.status_code == 422
    assert any(f["area"] == "01-base/engine" for f in r.json()["detail"])
    assert client.get("/api/config/snapshots", headers=_AUTH).json() == vorher
    status = client.get("/api/config/seed", headers=_AUTH).json()
    assert status["neu"] == ["01-base/neu"]          # nichts geschrieben
    assert status["abweichend"] == ["01-base/engine"]  # nichts überschrieben


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


def test_seed_anwenden_schreibt_alles_oder_nichts(cfg, seed_baum) -> None:
    # Paket 4, D4 (externes Audit F07): Das Anwenden schrieb Bereich für
    # Bereich. Scheiterte einer, war die Begrüßung schon überschrieben, und das
    # Löschen lief nie — ein Stand, den weder Seed noch Datenbank je hatten.
    # Seit Paket 4b (A4) nennt die Antwort den Bereich (400) statt 500.
    client, seed = cfg
    seed_baum("01-base/welcome-config.yaml", "welcome:\n  greeting: Seed\n")
    seed_baum("01-base/zz-kaputt.yaml", 'x: "\\0"\n')
    seed("01-base/welcome-config", {"welcome": {"greeting": "Gepflegt"}})
    seed("01-base/eigenbau", {"x": 1})

    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "exact"})
    assert r.status_code == 400, r.text
    assert "01-base/zz-kaputt" in r.json()["detail"]
    assert "Der ganze Vorgang wurde verworfen" in r.json()["detail"]
    assert asyncio.run(config_loader.current_config()) == {
        "01-base/eigenbau": {"x": 1},
        "01-base/welcome-config": {"welcome": {"greeting": "Gepflegt"}},
    }


def test_seed_endpunkte_verlangen_den_studio_schluessel(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/seed").status_code == 401
    assert client.post("/api/config/seed/apply", json={"mode": "missing"}).status_code == 401


def test_liste_unterscheidet_von_hand_und_automatisch(cfg) -> None:
    """Paket 12: selbst angelegte und automatische Schnappschüsse sind getrennt erkennbar —
    vorher nur am Namen („vor Wiederherstellen …“)."""
    from boerdi.services import snapshots

    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "A"}})
    seed("05-canvas/probe", {"x": 1})
    assert client.post("/api/config/snapshots", headers=_AUTH,
                       json={"label": "meiner"}).status_code == 200
    blob = snapshots.build_config_zip({"01-base/welcome-config": {"welcome": {"greeting": "B"}}})
    r = client.post("/api/config/restore", headers=_AUTH, params={"mode": "exact"},
                    files={"file": ("b.zip", blob, "application/zip")})
    assert r.status_code == 200, r.text
    arten = {s["label"]: s["art"] for s in client.get("/api/config/snapshots",
                                                       headers=_AUTH).json()}
    assert arten["meiner"] == "hand"
    assert set(arten.values()) == {"hand", "auto"}
