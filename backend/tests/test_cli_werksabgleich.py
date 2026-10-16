"""``import-config --werksabgleich`` (Paket 12, W4) gegen eine echte Wegwerf-Datenbank.

Der Abgleich ersetzt ``--only-missing`` im ``migrate``-Dienst: er legt Fehlendes an wie bisher,
hebt aber auch unberührte Bereiche auf eine neue Werksfassung — Angepasstes und im Studio
Gelöschtes bleibt, wie es ist.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_cli_werk_test"
_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


@pytest.fixture
def db(monkeypatch):
    from boerdi.settings import get_settings

    pg_utils.create_migrated_db(_DB)
    monkeypatch.setenv("DATABASE_URL", pg_utils.sqlalchemy_url(_DB))
    get_settings.cache_clear()
    yield _DB
    get_settings.cache_clear()
    pg_utils.drop_db(_DB)


def _mit_store(szenario):
    from boerdi.db.notify import asyncpg_dsn
    from boerdi.db.session import make_engine
    from boerdi.services.config_store import ConfigStore
    from boerdi.settings import get_settings

    async def lauf():
        settings = get_settings()
        engine = make_engine(settings)
        try:
            store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))
            return await szenario(store)
        finally:
            await engine.dispose()

    return asyncio.run(lauf())


def _cli(*args: str) -> int:
    from boerdi.cli import main

    return main(["import-config", *args])


def _baum(wurzel: Path, gruss: str, geraet: int) -> Path:
    base = wurzel / "01-base"
    base.mkdir(parents=True, exist_ok=True)
    (base / "welcome-config.yaml").write_text(f"greeting: {gruss}\n", encoding="utf-8")
    (base / "device-config.yaml").write_text(f"mobile_breakpoint: {geraet}\n", encoding="utf-8")
    (base / "extra.yaml").write_text("x: 1\n", encoding="utf-8")
    return wurzel


def test_echter_seed_ist_nach_import_und_abgleich_ganz_werk(db):
    """Prüfsumme und jsonb-Rundreise passen für JEDEN ausgelieferten Bereich zusammen."""
    from boerdi.services import seed_sync, werkfassung

    assert _cli("--from", str(_SEEDS)) == 0
    assert _cli("--from", str(_SEEDS), "--werksabgleich") == 0

    async def lesen(store):
        return await store.fassungen()

    zeilen = _mit_store(lesen)
    seed = asyncio.run(seed_sync.seed_lesen(_SEEDS))
    assert len(zeilen) == len(seed)
    nicht_werk = [z["area"] for z in zeilen
                  if werkfassung.status(data=z["data"], werk_hash=z["werk_hash"],
                                        werk=seed[z["area"]], entfernt=False) != werkfassung.WERK
                  or z["werk_hash"] != werkfassung.pruefsumme(seed[z["area"]])]
    assert nicht_werk == []


def test_neue_werksfassung_hebt_unberuehrtes_an_und_laesst_eigenes(db, tmp_path):
    v1 = _baum(tmp_path / "v1", "alt", 640)
    v2 = _baum(tmp_path / "v2", "neu", 700)
    assert _cli("--from", str(v1), "--werksabgleich") == 0

    async def anpassen(store):
        await store.put("01-base/device-config", {"mobile_breakpoint": 500}, updated_by="studio")
        await store.delete("01-base/extra")

    _mit_store(anpassen)
    assert _cli("--from", str(v2), "--werksabgleich") == 0

    async def lesen(store):
        return {z["area"]: z["data"] for z in await store.fassungen()}

    stand = _mit_store(lesen)
    assert stand["01-base/welcome-config"] == {"greeting": "neu"}      # unberührt → angehoben
    assert stand["01-base/device-config"] == {"mobile_breakpoint": 500}  # eigen → bleibt
    assert "01-base/extra" not in stand                                 # gelöscht → bleibt weg


def test_einfacher_import_gilt_nur_aus_dem_seed_als_werk(db, tmp_path):
    """Review #3: ein Import aus einem anderen Baum (Server-Umzug, ALT) ist nicht die
    Werksfassung — sonst überschriebe der nächste Start ihn als „unberührt“. Aus dem
    Seed-Ordner merkt er die Basis."""
    fremd = _baum(tmp_path / "fremd", "fremd", 111)
    assert _cli("--from", str(fremd)) == 0
    assert _cli("--from", str(_SEEDS)) == 0

    async def lesen(store):
        return {z["area"]: z for z in await store.fassungen()}

    zeilen = _mit_store(lesen)
    assert zeilen["01-base/extra"]["updated_by"] == "import-cli"
    assert zeilen["01-base/extra"]["werk_hash"] is None
    assert zeilen["01-base/welcome-config"]["werk_hash"] is not None
