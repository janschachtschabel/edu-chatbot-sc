"""Migration 0021 (Paket AS-0): der Ablauf-Katalog wird ein Dokument je Ablauf.

``06-ablaeufe/katalog`` (eine Liste) → ``06-ablaeufe/<id>`` je Eintrag, mit derselben Fassungsart:
- **unberührt** (der Inhalt gleicht der gemerkten Werksfassung): jeder Ablauf merkt sich seine
  eigene Prüfsumme als Basis — der Werksabgleich hebt ihn wie gewohnt an;
- **angepasst**: ohne Basis — er gilt als eigen und wird nie überschrieben;
- eine **stillgelegte eigene Fassung** wird je Kennung mit aufgeteilt;
- ein im Studio **gelöschter** Katalog: je Werks-Ablauf ein Löschvermerk.
Vorhandene Dokumente bleiben unberührt. Der Rückweg setzt den Katalog wieder zusammen.
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from boerdi.services.werkfassung import pruefsumme
from tests import pg_utils

_DB = "boerdi_as0_ablauf_dokumente_test"
_DSN = pg_utils.asyncpg_dsn(_DB)

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]


def _alembic() -> Config:
    cfg = Config(str(pg_utils.BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(pg_utils.BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_utils.sqlalchemy_url(_DB))
    return cfg


def _ablauf(kennung: str, text: str = "Fertig.") -> dict:
    return {"id": kennung, "titel": {"de": kennung}, "aktiv": False,
            "schritte": [{"id": "ende", "typ": "ende", "text": {"de": text}}]}


def _sql(*befehle: tuple[str, tuple]) -> list[list[asyncpg.Record]]:
    async def lauf():
        conn = await asyncpg.connect(_DSN)
        try:
            return [await conn.fetch(sql, *werte) for sql, werte in befehle]
        finally:
            await conn.close()
    return asyncio.run(lauf())


def _zeilen() -> dict[str, dict]:
    [rows] = _sql(("SELECT area, data, werk_hash, eigene_fassung, updated_by FROM config_areas "
                   "WHERE area LIKE '06-ablaeufe/%'", ()))
    return {r["area"]: {"data": json.loads(r["data"]), "werk_hash": r["werk_hash"],
                        "eigene": json.loads(r["eigene_fassung"]) if r["eigene_fassung"] else None,
                        "updated_by": r["updated_by"]} for r in rows}


def _katalog(data: dict, *, werk_hash: str | None, eigene: dict | None = None) -> None:
    _sql(("INSERT INTO config_areas (area, data, version, updated_by, werk_hash, eigene_fassung) "
          "VALUES ('06-ablaeufe/katalog', $1::jsonb, 3, 'studio-form', $2, $3::jsonb)",
          (json.dumps(data), werk_hash, json.dumps(eigene) if eigene else None)))


@pytest.fixture()
def db():
    pg_utils.create_migrated_db(_DB, "0020")
    yield
    pg_utils.drop_db(_DB)


def test_ein_unberuehrter_katalog_wird_werks_dokumente(db):
    katalog = {"ablaeufe": [_ablauf("lesen"), _ablauf("schreiben")]}
    _katalog(katalog, werk_hash=pruefsumme(katalog))
    pg_utils.upgrade_db(_DB, "head")
    z = _zeilen()
    assert set(z) == {"06-ablaeufe/lesen", "06-ablaeufe/schreiben"}
    assert z["06-ablaeufe/lesen"]["data"] == _ablauf("lesen")
    assert z["06-ablaeufe/lesen"]["werk_hash"] == pruefsumme(_ablauf("lesen"))


def test_ein_angepasster_katalog_bleibt_eigen_samt_stillgelegter_fassung(db):
    katalog = {"ablaeufe": [_ablauf("lesen", "Angepasst."), _ablauf("eigener")]}
    still = {"ablaeufe": [_ablauf("lesen", "Alt."), _ablauf("weg")]}
    _katalog(katalog, werk_hash="0" * 64, eigene=still)
    pg_utils.upgrade_db(_DB, "head")
    z = _zeilen()
    assert set(z) == {"06-ablaeufe/lesen", "06-ablaeufe/eigener"}
    assert all(zeile["werk_hash"] is None for zeile in z.values())
    assert z["06-ablaeufe/lesen"]["eigene"] == _ablauf("lesen", "Alt.")
    assert z["06-ablaeufe/eigener"]["eigene"] is None


def test_vorhandene_dokumente_bleiben_und_kaputte_eintraege_fallen_nicht_ins_gewicht(db):
    _sql(("INSERT INTO config_areas (area, data, version, updated_by) VALUES "
          "('06-ablaeufe/lesen', $1::jsonb, 1, 'studio-form')",
          (json.dumps(_ablauf("lesen", "Da.")),)))
    _katalog({"ablaeufe": [_ablauf("lesen"), {"id": "../boese"}, "kein objekt", _ablauf("neu")]},
             werk_hash=None)
    pg_utils.upgrade_db(_DB, "head")
    z = _zeilen()
    assert set(z) == {"06-ablaeufe/lesen", "06-ablaeufe/neu"}
    assert z["06-ablaeufe/lesen"]["data"] == _ablauf("lesen", "Da.")


def test_ein_geloeschter_katalog_bleibt_geloescht(db):
    _sql(("INSERT INTO config_werk_entfernt (area) VALUES ('06-ablaeufe/katalog')", ()))
    pg_utils.upgrade_db(_DB, "head")
    [rows] = _sql(("SELECT area FROM config_werk_entfernt", ()))
    assert {r["area"] for r in rows} == {"06-ablaeufe/sammlungsstruktur"}


def test_rueckweg_setzt_den_katalog_wieder_zusammen(db):
    katalog = {"ablaeufe": [_ablauf("lesen"), _ablauf("schreiben")]}
    _katalog(katalog, werk_hash=pruefsumme(katalog))
    pg_utils.upgrade_db(_DB, "head")
    command.downgrade(_alembic(), "0020")
    z = _zeilen()
    assert set(z) == {"06-ablaeufe/katalog"}
    assert z["06-ablaeufe/katalog"]["data"] == katalog
    # wieder hoch: dasselbe Ergebnis wie beim ersten Mal
    pg_utils.upgrade_db(_DB, "head")
    assert set(_zeilen()) == {"06-ablaeufe/lesen", "06-ablaeufe/schreiben"}


def test_ein_entfernter_werks_ablauf_bleibt_entfernt(db):
    """Review AS-0, Befund 3: fehlt ``sammlungsstruktur`` im Katalog, hatte die Redaktion ihn
    entfernt — der Werksabgleich darf ihn nicht wieder anlegen."""
    _katalog({"ablaeufe": [_ablauf("eigener")]}, werk_hash=None)
    pg_utils.upgrade_db(_DB, "head")
    [rows] = _sql(("SELECT area FROM config_werk_entfernt", ()))
    assert {r["area"] for r in rows} == {"06-ablaeufe/sammlungsstruktur"}


def test_ein_aus_dem_werk_importierter_katalog_bleibt_anhebbar(db):
    """Review AS-0, Befund 4: ohne Basis, aber vom Werk geschrieben (``updated_by: import``) galt
    der Katalog als „werk-veraltet“ — die Abläufe behalten das."""
    katalog = {"ablaeufe": [_ablauf("sammlungsstruktur")]}
    _sql(("INSERT INTO config_areas (area, data, version, updated_by) "
          "VALUES ('06-ablaeufe/katalog', $1::jsonb, 1, 'import')", (json.dumps(katalog),)))
    pg_utils.upgrade_db(_DB, "head")
    z = _zeilen()
    assert z["06-ablaeufe/sammlungsstruktur"]["updated_by"] == "import"
    assert z["06-ablaeufe/sammlungsstruktur"]["werk_hash"] is None
