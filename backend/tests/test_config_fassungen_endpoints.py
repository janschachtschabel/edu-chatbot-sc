"""Paket 12, W5: Werk und eigene Fassung im Studio — Liste, Umschalten, Vergleich, Abgleich.

Gegen eine frische Compose-Postgres und einen kleinen Seed-Baum (``CONFIG_SEED_DIR``).
"""

from __future__ import annotations

import asyncio

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

_DB = "boerdi_w5_fassungen_test"
_AUTH = {"X-Studio-Key": "k"}
_GRUSS = "01-base/welcome-config"
_MUSTER = "03-patterns/m77-probe"


@pytest.fixture(scope="module")
def _module_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


@pytest.fixture()
def studio(_module_db, monkeypatch, tmp_path):
    from sqlalchemy import text
    from sqlalchemy.pool import NullPool

    from boerdi.db.session import make_engine

    (tmp_path / "01-base").mkdir()
    (tmp_path / "01-base" / "welcome-config.yaml").write_text(
        "welcome:\n  greeting: aus dem Werk\n", encoding="utf-8")
    (tmp_path / "03-patterns").mkdir()
    (tmp_path / "03-patterns" / "m77-probe.md").write_text(
        "---\nid: M77\nlabel: Probe\n---\nWerkstext\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_SEED_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()

    engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
                         poolclass=NullPool)
    store = ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(_DB))

    async def leeren():
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM config_areas"))
            await conn.execute(text("DELETE FROM config_werk_entfernt"))

    asyncio.run(leeren())
    config_loader.bind_store(store)
    yield TestClient(create_app()), store
    config_loader.bind_store(None)
    asyncio.run(engine.dispose())


def _liste(client) -> dict[str, dict]:
    r = client.get("/api/config/fassungen", headers=_AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["available"] is True
    return {b["area"]: b for b in r.json()["bereiche"]}


def _umschalten(client, area, ziel, version=None):
    return client.post("/api/config/fassungen/umschalten", headers=_AUTH,
                       json={"area": area, "ziel": ziel, "expected_version": version})


def test_abgleich_legt_an_und_alles_ist_werk(studio):
    client, _ = studio
    vorher = _liste(client)
    assert vorher[_GRUSS]["status"] == "werk-fehlt"
    r = client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    assert r.status_code == 200 and r.json()["neu"] == 2
    assert {b["status"] for b in _liste(client).values()} == {"werk"}


def test_angepasst_auf_werk_und_zurueck_ohne_verlust(studio):
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    asyncio.run(store.put(_GRUSS, {"welcome": {"greeting": "eigener Gruß"}}, updated_by="studio"))
    eintrag = _liste(client)[_GRUSS]
    assert eintrag["status"] == "eigen"

    r = _umschalten(client, _GRUSS, "werk", eintrag["version"])
    assert r.status_code == 200, r.text
    eintrag = _liste(client)[_GRUSS]
    assert eintrag["status"] == "werk" and eintrag["hat_eigene_fassung"] is True
    assert config_loader.area(_GRUSS)["welcome"]["greeting"] == "aus dem Werk"

    r = _umschalten(client, _GRUSS, "eigen", eintrag["version"])
    assert r.status_code == 200, r.text
    eintrag = _liste(client)[_GRUSS]
    assert eintrag["status"] == "eigen" and eintrag["hat_eigene_fassung"] is False
    assert config_loader.area(_GRUSS)["welcome"]["greeting"] == "eigener Gruß"


def test_veraltete_version_ist_ein_konflikt(studio):
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    version = _liste(client)[_GRUSS]["version"]
    asyncio.run(store.put(_GRUSS, {"welcome": {"greeting": "zwischendurch"}}, updated_by="studio"))
    assert _umschalten(client, _GRUSS, "werk", version).status_code == 409


def test_vergleich_zeigt_die_unterschiede_als_zeilen(studio):
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    asyncio.run(store.put(_MUSTER, {"frontmatter": {"id": "M77", "label": "Probe"},
                                    "body": "Eigener Text\n"}, updated_by="studio"))
    r = client.get("/api/config/fassungen/vergleich", params={"area": _MUSTER}, headers=_AUTH)
    assert r.status_code == 200, r.text
    zeilen = r.json()["zeilen"]
    assert "-Werkstext" in zeilen and "+Eigener Text" in zeilen
    # Paket 16, C6: dieselben Unterschiede je Feld — für die Tabelle in der Sicherung.
    felder = {f["pfad"]: f for f in r.json()["felder"]}
    assert felder["body"]["eigen"] == '"Eigener Text\\n"'
    assert r.json()["felder_gesamt"] == len(r.json()["felder"])


def test_geloeschter_werksbereich_bleibt_weg_und_laesst_sich_wiederherstellen(studio):
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    asyncio.run(store.delete(_MUSTER))
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    assert _liste(client)[_MUSTER]["status"] == "werk-entfernt"
    assert _umschalten(client, _MUSTER, "werk").status_code == 200
    assert _liste(client)[_MUSTER]["status"] == "werk"


def test_ohne_eigene_fassung_oder_werk_gibt_es_nichts_umzuschalten(studio):
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    version = _liste(client)[_GRUSS]["version"]
    assert _umschalten(client, _GRUSS, "eigen", version).status_code == 400
    asyncio.run(store.put("01-base/nur-hier", {"x": 1}, updated_by="studio"))
    assert _liste(client)["01-base/nur-hier"]["status"] == "nur-eigen"
    assert _umschalten(client, "01-base/nur-hier", "werk", 1).status_code == 404


def test_ohne_seed_ist_die_ansicht_nicht_verfuegbar(studio, monkeypatch, tmp_path):
    client, _ = studio
    monkeypatch.setenv("CONFIG_SEED_DIR", str(tmp_path / "gibt-es-nicht"))
    get_settings.cache_clear()
    r = client.get("/api/config/fassungen", headers=_AUTH)
    assert r.status_code == 200 and r.json() == {"available": False, "bereiche": []}


def test_nur_mit_studio_schluessel(studio):
    client, _ = studio
    assert client.get("/api/config/fassungen").status_code in (401, 403)


def test_vergleich_zeigt_keine_scheinunterschiede_aus_der_schluesselfolge(studio, tmp_path):
    """Browser-Abnahme 2026-10-16: jsonb ordnet Schlüssel selbst (Länge, dann Bytes); die
    Werksfassung behält die Folge der Datei. Ohne gleiche Ordnung zeigte der Vergleich eines
    unveränderten Bereichs ganze Blöcke als verschoben."""
    client, _ = studio
    seed = tmp_path / "03-patterns" / "m77-probe.md"
    seed.write_text("---\nlabel: Probe\nid: M77\npriority: 5\n---\nWerkstext\n", encoding="utf-8")
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    r = client.get("/api/config/fassungen/vergleich", params={"area": _MUSTER}, headers=_AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["zeilen"] == []


def test_nach_dem_umschalten_weiter_bearbeitet_geht_nichts_verloren(studio):
    """Review #1: Werk wählen, weiter bearbeiten, zurück — beide eigenen Fassungen bleiben."""
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    asyncio.run(store.put(_GRUSS, {"welcome": {"greeting": "C"}}, updated_by="studio"))
    assert _umschalten(client, _GRUSS, "werk", _liste(client)[_GRUSS]["version"]).status_code == 200
    asyncio.run(store.put(_GRUSS, {"welcome": {"greeting": "W-strich"}}, updated_by="studio"))

    # Auf Werk ginge jetzt eine Fassung verloren → abgewiesen, nichts geändert.
    eintrag = _liste(client)[_GRUSS]
    r = _umschalten(client, _GRUSS, "werk", eintrag["version"])
    assert r.status_code == 400
    assert config_loader.area(_GRUSS)["welcome"]["greeting"] == "W-strich"

    # Auf eigen tauscht: C wird gelebt, W′ liegt still.
    assert _umschalten(client, _GRUSS, "eigen", eintrag["version"]).status_code == 200
    fassung = asyncio.run(store.fassung(_GRUSS))
    assert fassung["data"]["welcome"]["greeting"] == "C"
    assert fassung["eigene_fassung"]["welcome"]["greeting"] == "W-strich"


def test_werksabgleich_ueberspringt_eine_vergebene_kennung(studio):
    """Review #6: das Studio hat M77 unter anderem Schlüssel — der Abgleich legt kein zweites an."""
    client, store = studio
    asyncio.run(store.put("03-patterns/m77-eigenes", {
        "frontmatter": {"id": "M77", "label": "Eigenes"}, "body": "x"}, updated_by="studio"))
    r = client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    assert r.status_code == 200 and r.json()["konflikt"] == 1
    assert _liste(client)[_MUSTER]["status"] == "werk-fehlt"


def _auf_werk_mit_eigener(client, store):
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    asyncio.run(store.put(_MUSTER, {"frontmatter": {"id": "M77", "label": "Probe"},
                                    "body": "Eigener Text\n"}, updated_by="studio"))
    version = _liste(client)[_MUSTER]["version"]
    assert _umschalten(client, _MUSTER, "werk", version).status_code == 200


def test_studio_loeschen_verweigert_bei_stillgelegter_fassung(studio):
    """Review 2 #1."""
    client, store = studio
    _auf_werk_mit_eigener(client, store)
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": f"{_MUSTER}.md"})
    assert r.status_code == 400
    assert "eigene Fassung" in r.json()["detail"] or "own version" in r.json()["detail"]
    assert asyncio.run(store.fassung(_MUSTER)) is not None


def test_vor_0011_angepasster_werksbereich_bleibt_nach_dem_loeschen_weg(studio):
    """Review 2 #2: ohne Basis (Bestand) — das Studio-Löschen weiß aus dem Seed, dass es ein
    Werksbereich ist; der nächste Abgleich legt ihn nicht wieder an."""
    client, store = studio
    asyncio.run(store.put(_MUSTER, {"frontmatter": {"id": "M77", "label": "Alt"}, "body": "a"},
                          updated_by="studio"))
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": f"{_MUSTER}.md"})
    assert r.status_code == 200, r.text
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    assert _liste(client)[_MUSTER]["status"] == "werk-entfernt"


def test_exaktes_wiederherstellen_behaelt_bereiche_mit_stillgelegter_fassung(studio):
    from boerdi.services import snapshots

    client, store = studio
    _auf_werk_mit_eigener(client, store)
    blob = snapshots.build_config_zip({_GRUSS: {"welcome": {"greeting": "aus der Sicherung"}}})
    r = client.post("/api/config/restore", headers=_AUTH, params={"mode": "exact"},
                    files={"file": ("b.zip", blob, "application/zip")})
    assert r.status_code == 200, r.text
    assert r.json()["behalten"] == [_MUSTER]
    assert asyncio.run(store.fassung(_MUSTER))["eigene_fassung"] is not None


def test_fehlende_nachziehen_holt_geloeschte_werksbereiche_nicht_zurueck(studio):
    """Review 2 #7: „Fehlende nachziehen“ legte im Studio Gelöschtes wieder an."""
    client, store = studio
    client.post("/api/config/fassungen/werksabgleich", headers=_AUTH)
    assert client.delete("/api/config/file", headers=_AUTH,
                         params={"path": f"{_MUSTER}.md"}).status_code == 200
    r = client.post("/api/config/seed/apply", headers=_AUTH, json={"mode": "missing"})
    assert r.status_code == 200, r.text
    assert _liste(client)[_MUSTER]["status"] == "werk-entfernt"


def test_als_geprueft_markieren_nimmt_den_bereich_aus_neue_werksfassung(studio):
    client, store = studio
    asyncio.run(store.put(_GRUSS, {"welcome": {"greeting": "Bestand"}}, updated_by="studio"))
    eintrag = _liste(client)[_GRUSS]
    assert eintrag["status"] == "eigen-neues-werk"
    assert _umschalten(client, _GRUSS, "geprueft", eintrag["version"]).status_code == 200
    assert _liste(client)[_GRUSS]["status"] == "eigen"
    assert config_loader.area(_GRUSS)["welcome"]["greeting"] == "Bestand"


def test_vergleich_zeigt_auch_die_stillgelegte_fassung(studio):
    """Review 2 #10: vor „Eigene Fassung verwenden“ lässt sich die stillgelegte ansehen."""
    client, store = studio
    _auf_werk_mit_eigener(client, store)
    r = client.get("/api/config/fassungen/vergleich", params={"area": _MUSTER}, headers=_AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["zeilen"] == []                       # gelebt == Werk
    assert "+Eigener Text" in r.json()["zeilen_eigene"]   # stillgelegt gegen Werk
    assert r.json()["felder"] == []
    assert [f["pfad"] for f in r.json()["felder_eigene"]] == ["body"]
