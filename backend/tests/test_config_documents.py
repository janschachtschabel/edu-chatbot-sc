"""Ordner-Dokumente: anlegen, duplizieren, löschen (Paket 6, S1 — ST-3d).

Muster (``03-patterns/…``) und Personas (``04-personas/…``) sind Ordner: ein
Dokument je Eintrag. Drei Lücken schloss dieses Paket:

* **Der Schlüssel neuer Dokumente** kam aus dem Studio, die Kennung auch — und
  nichts prüfte, ob es die Kennung schon gab. Eine Persona wird zur Laufzeit
  über ``_persona_slug(id)`` gefunden; lag sie unter einem anderen Schlüssel,
  lief ihr Prompt ins Leere. Jetzt leitet der Server den Schlüssel ab.
* **Duplizieren** gab es nicht.
* **Löschen** (``DELETE /api/config/file``) nahm jeden Bereich, auch
  ``01-base/policy`` — das Studio rief es nie. Jetzt nur noch Ordner-Dokumente.
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

_DB = "boerdi_config_documents_test"
_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture()
def cfg(monkeypatch):
    """(client, seed) mit frischer Datenbank je Test — die Tests zählen Dokumente."""
    from sqlalchemy.pool import NullPool

    from boerdi.db.session import make_engine

    pg_utils.create_migrated_db(_DB)
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

    yield client, seed
    config_loader.bind_store(None)
    asyncio.run(engine.dispose())
    pg_utils.drop_db(_DB)


def _muster(kennung: str, name: str, **mehr) -> dict:
    return {"frontmatter": {"id": kennung, "label": name, **mehr}, "body": f"# {name}\n\nText."}


def _anlegen(client, **body):
    return client.post("/api/config/documents", headers=_AUTH, json=body)


def _lesen(client, key: str) -> dict:
    r = client.get(f"/api/config/data/{key}", headers=_AUTH)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ── anlegen ────────────────────────────────────────────────────────────────
def test_ein_muster_wird_unter_seiner_kennung_angelegt(cfg) -> None:
    client, _ = cfg
    r = _anlegen(client, group="03-patterns", id="M21", label="Neues Muster")
    assert r.status_code == 201, r.text
    assert r.json()["key"] == "03-patterns/m21"
    fm = _lesen(client, "03-patterns/m21")["frontmatter"]
    assert (fm["id"], fm["label"]) == ("M21", "Neues Muster")


def test_eine_persona_liegt_dort_wo_die_laufzeit_sie_sucht(cfg) -> None:
    from boerdi.services.config_loader.personas import _persona_slug

    client, _ = cfg
    r = _anlegen(client, group="04-personas", id="P-NEU", label="Neue Zielgruppe")
    assert r.status_code == 201, r.text
    assert r.json()["key"] == f"04-personas/{_persona_slug('P-NEU')}" == "04-personas/neu"


@pytest.mark.parametrize("kennung", ["", "M 21", "M21!", "-M21", "x" * 65])
def test_eine_ungueltige_kennung_wird_abgewiesen(cfg, kennung) -> None:
    client, _ = cfg
    assert _anlegen(client, group="03-patterns", id=kennung, label="X").status_code == 400


def test_die_agent_kennung_bleibt_fuer_muster_reserviert(cfg) -> None:
    client, _ = cfg
    assert _anlegen(client, group="03-patterns", id="AGENT", label="X").status_code == 400


def test_ohne_namen_und_in_fremder_gruppe_wird_abgewiesen(cfg) -> None:
    client, _ = cfg
    assert _anlegen(client, group="03-patterns", id="M21", label="  ").status_code == 400
    assert _anlegen(client, group="01-base", id="x", label="X").status_code == 400


def test_eine_vergebene_kennung_wird_abgewiesen_auch_in_anderer_schreibweise(cfg) -> None:
    client, seed = cfg
    seed("03-patterns/m05-material-suche", _muster("M05", "Suche"))
    r = _anlegen(client, group="03-patterns", id="m05", label="Noch eine Suche")
    assert r.status_code == 409
    assert "M05" in str(r.json()["detail"])


# ── duplizieren ────────────────────────────────────────────────────────────
def test_duplizieren_kopiert_den_inhalt_mit_neuer_kennung(cfg) -> None:
    client, seed = cfg
    seed("03-patterns/m05-material-suche", _muster("M05", "Suche", core_rule="Immer suchen."))
    r = _anlegen(client, group="03-patterns", id="M05-kopie", label="Suche (Kopie)",
                 source="03-patterns/m05-material-suche")
    assert r.status_code == 201, r.text
    kopie = _lesen(client, r.json()["key"])
    assert kopie["frontmatter"] == {"id": "M05-kopie", "label": "Suche (Kopie)",
                                    "core_rule": "Immer suchen."}
    assert kopie["body"] == "# Suche\n\nText."
    # Das Original bleibt, wie es war.
    assert _lesen(client, "03-patterns/m05-material-suche")["frontmatter"]["id"] == "M05"


def test_die_vorlage_muss_in_derselben_gruppe_liegen(cfg) -> None:
    client, seed = cfg
    seed("04-personas/leh", {"frontmatter": {"id": "P-LEH", "label": "Lehrkraft"}, "body": "x"})
    r = _anlegen(client, group="03-patterns", id="M30", label="X", source="04-personas/leh")
    assert r.status_code == 400
    r = _anlegen(client, group="03-patterns", id="M30", label="X", source="03-patterns/gibtsnicht")
    assert r.status_code == 400


# ── speichern über das Formular: die Kennung bleibt eindeutig ──────────────
def test_das_formular_vergibt_keine_kennung_doppelt(cfg) -> None:
    # 400, nicht 409 (Review Paket 6): auf den Speicher-Routen heißt 409 „jemand
    # hat inzwischen gespeichert“ — das Studio zeigte den Konflikt-Kasten ohne
    # Grund, und „Trotzdem speichern“ lief wieder in dieselbe Abweisung.
    client, seed = cfg
    seed("03-patterns/m05-material-suche", _muster("M05", "Suche"))
    seed("03-patterns/m06", _muster("M06", "Andere"))
    r = client.put("/api/config/data/03-patterns/m06", headers=_AUTH,
                   json={"data": _muster("M05", "Andere")})
    assert r.status_code == 400
    assert "M05" in r.json()["detail"]
    r = client.put("/api/config/file", headers=_AUTH, json={
        "path": "03-patterns/m06.md", "content": "---\nid: m05\nlabel: Andere\n---\nText\n"})
    assert r.status_code == 400
    assert "m05" in r.json()["detail"]


def test_das_formular_nimmt_keine_kennung_mit_leerzeichen(cfg) -> None:
    # Die Laufzeit nimmt das erste Wort einer Kennung: „M06 neu“ wäre „M06“.
    client, seed = cfg
    seed("03-patterns/m06", _muster("M06", "Andere"))
    r = client.put("/api/config/data/03-patterns/m06", headers=_AUTH,
                   json={"data": _muster("M06 neu", "Andere")})
    assert r.status_code == 400
    assert "M06 neu" in r.json()["detail"]


def test_eine_persona_ohne_kuerzel_wird_nicht_angelegt(cfg) -> None:
    # „P-“ ergab den Schlüssel ``04-personas/`` — geladen als Persona, aber weder
    # zu bearbeiten noch zu löschen.
    client, _ = cfg
    for kennung in ("P-", "p-"):
        assert _anlegen(client, group="04-personas", id=kennung, label="Leer").status_code == 400
    personas = client.get("/api/config/elements", headers=_AUTH).json()["personas"]
    assert personas == []


def test_eine_persona_kennung_muss_zu_ihrem_schluessel_passen(cfg) -> None:
    client, seed = cfg
    seed("04-personas/leh", {"frontmatter": {"id": "P-LEH", "label": "Lehrkraft"}, "body": "x"})
    r = client.put("/api/config/data/04-personas/leh", headers=_AUTH,
                   json={"data": {"frontmatter": {"id": "P-LEHRKRAFT", "label": "L"}, "body": "x"}})
    assert r.status_code == 400
    assert "04-personas/lehrkraft" in r.json()["detail"]


# ── löschen ─────────────────────────────────────────────────────────────────
def test_loeschen_laesst_feste_bereiche_stehen(cfg) -> None:
    client, seed = cfg
    seed("01-base/policy", {"rules": []})
    seed("01-base/tippfehler", {"x": 1})
    seed("03-patterns/m21", _muster("M21", "Weg damit"))
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": "01-base/tippfehler.yaml"})
    assert r.status_code == 200, "ein Bereich ohne Modell bleibt löschbar"
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": "01-base/policy.yaml"})
    assert r.status_code == 400
    assert client.get("/api/config/data/01-base/policy", headers=_AUTH).status_code == 200
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": "03-patterns/m21.md"})
    assert r.status_code == 200
    weg = client.get("/api/config/file", headers=_AUTH, params={"path": "03-patterns/m21.md"})
    assert weg.status_code == 404


def test_loeschen_antwortet_in_der_sprache_des_studios(cfg) -> None:
    client, _ = cfg
    r = client.delete("/api/config/file", params={"path": "03-patterns/gibtsnicht.md"},
                      headers={**_AUTH, "Accept-Language": "en"})
    assert r.status_code == 404
    assert "does not exist" in r.json()["detail"]


def test_die_sicherheits_muster_lassen_sich_nicht_loeschen(cfg) -> None:
    # Krise und Bedrohung erzwingen ein Muster (Regex-Gate fest M01/M02, die
    # Moderation `crisis_pattern`/`threat_pattern`). Ohne es fielen solche Züge
    # bis zum nächsten Start in die normale Musterwahl (Review Paket 6).
    client, seed = cfg
    seed("03-patterns/m01-krise", _muster("M01", "Krise"))
    seed("03-patterns/m02-bedrohung", _muster("M02", "Bedrohung"))
    seed("01-base/safety-config", {"crisis_pattern": "M77"})
    seed("03-patterns/m77", _muster("m77", "Eigene Krise"))
    seed("03-patterns/m21", _muster("M21", "Weg damit"))
    for pfad in ("03-patterns/m01-krise.md", "03-patterns/m02-bedrohung.md", "03-patterns/m77.md"):
        r = client.delete("/api/config/file", headers=_AUTH, params={"path": pfad})
        assert r.status_code == 400, pfad
    assert _lesen(client, "03-patterns/m77")["frontmatter"]["id"] == "m77"
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": "03-patterns/m21.md"})
    assert r.status_code == 200


def test_loeschen_mit_veraltetem_stand_wird_abgewiesen(cfg) -> None:
    # Wer aus einer veralteten Ansicht löscht, nähme die Fassung eines anderen
    # still mit (Plan S1: `expected_version` wie beim Speichern).
    client, seed = cfg
    seed("03-patterns/m21", _muster("M21", "Erst"))
    seed("03-patterns/m21", _muster("M21", "Dann"))  # jemand speichert dazwischen
    aktuell = client.get("/api/config/data/03-patterns/m21", headers=_AUTH).json()["version"]
    pfad = {"path": "03-patterns/m21.md"}
    r = client.delete("/api/config/file", headers=_AUTH,
                      params={**pfad, "expected_version": aktuell - 1})
    assert r.status_code == 409
    assert r.json()["detail"]["version"] == aktuell
    assert _lesen(client, "03-patterns/m21")["frontmatter"]["label"] == "Dann"
    r = client.delete("/api/config/file", headers=_AUTH,
                      params={**pfad, "expected_version": aktuell})
    assert r.status_code == 200
    r = client.delete("/api/config/file", headers=_AUTH,
                      params={**pfad, "expected_version": aktuell})
    assert r.status_code == 404


def test_ein_sicherheits_muster_behaelt_seine_kennung(cfg) -> None:
    # Variante zu oben: umbenannt fände das Erzwingen bei Krise kein M01 mehr,
    # und der nächste Start legte es nicht nach — der Schlüssel ist ja belegt.
    client, seed = cfg
    seed("03-patterns/m01-krise", _muster("M01", "Krise"))
    r = client.put("/api/config/data/03-patterns/m01-krise", headers=_AUTH,
                   json={"data": _muster("M01-alt", "Krise")})
    assert r.status_code == 400
    assert "M01" in r.json()["detail"]
    r = client.put("/api/config/data/03-patterns/m01-krise", headers=_AUTH,
                   json={"data": _muster("M01", "Krise, neu formuliert")})
    assert r.status_code == 200, r.text

