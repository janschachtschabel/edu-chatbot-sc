"""Paket AS-0 (Plan 2026-11-09): ein Dokument je Ablauf (``06-ablaeufe/<id>``).

Bis AS-0 lagen alle Abläufe in einem Bereich ``06-ablaeufe/katalog``: wer einen speicherte,
speicherte alle, und Werk/eigene Fassung galten für alle zusammen. Jetzt ist ``06-ablaeufe`` ein
Ordner wie die Muster — anlegen, kopieren und löschen über die Ordner-Wege, je Ablauf eine Fassung.
Die Kennung steht im Feld ``id`` (YAML), nicht im Frontmatter; sie ist der Schlüssel.
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

_DB = "boerdi_ablauf_dokumente_test"
_AUTH = {"X-Studio-Key": "k-studio-testkey"}


@pytest.fixture()
def cfg(monkeypatch):
    """(client, seed) mit frischer Datenbank je Test."""
    from sqlalchemy.pool import NullPool

    from boerdi.db.session import make_engine

    pg_utils.create_migrated_db(_DB)
    engine = make_engine(
        Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
        poolclass=NullPool,
    )
    store = ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(_DB))
    config_loader.bind_store(store)
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    get_settings.cache_clear()
    client = TestClient(create_app())

    def seed(area: str, data: dict) -> None:
        asyncio.run(store.put(area, data, updated_by="seed"))

    yield client, seed
    config_loader.bind_store(None)
    asyncio.run(engine.dispose())
    pg_utils.drop_db(_DB)


def ablauf(kennung: str, **mehr) -> dict:
    return {"id": kennung, "titel": {"de": kennung.title()}, "aktiv": False,
            "schritte": [{"id": "hallo", "typ": "nachricht", "text": {"de": "Hallo."}},
                         {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}], **mehr}


def _anlegen(client, **body):
    return client.post("/api/config/documents", headers={**_AUTH, "Accept-Language": "de"},
                       json=body)


def _lesen(client, key: str) -> dict:
    r = client.get(f"/api/config/data/{key}", headers=_AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def _speichern(client, key: str, data: dict, version: int | None):
    return client.put(f"/api/config/data/{key}", headers=_AUTH,
                      json={"data": data, "expected_version": version,
                            **({} if version is not None else {"create": True})})


# ── anlegen ────────────────────────────────────────────────────────────────
def test_ein_neuer_ablauf_ist_ein_eigenes_dokument_und_aus(cfg) -> None:
    client, _ = cfg
    r = _anlegen(client, group="06-ablaeufe", id="themen_pruefen", label="Themen prüfen")
    assert r.status_code == 201, r.text
    assert r.json()["key"] == "06-ablaeufe/themen_pruefen"
    gelesen = _lesen(client, "06-ablaeufe/themen_pruefen")
    data = gelesen["data"]
    assert gelesen["type"] == "yaml"
    assert data["id"] == "themen_pruefen" and data["titel"] == {"de": "Themen prüfen"}
    assert data["aktiv"] is False
    assert [s["typ"] for s in data["schritte"]] == ["ende"]


@pytest.mark.parametrize("kennung", ["Themen", "themen-pruefen", "1themen", "a" * 41, "katalog"])
def test_kennungen_die_die_laufzeit_nicht_liest_werden_abgewiesen(cfg, kennung) -> None:
    client, _ = cfg
    r = _anlegen(client, group="06-ablaeufe", id=kennung, label="X")
    assert r.status_code == 400, r.text


def test_eine_vergebene_kennung_ist_ein_konflikt(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    assert _anlegen(client, group="06-ablaeufe", id="lesen", label="Lesen").status_code == 409


def test_die_kopie_bekommt_kennung_und_titel_und_startet_aus(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf(
        "lesen", aktiv=True, titel={"de": "Lesen", "en": "Read"},
        ausloeser=[{"art": "text", "wendungen": ["lies mir vor"]}]))
    r = _anlegen(client, group="06-ablaeufe", id="lesen_kopie", label="Lesen (Kopie)",
                 source="06-ablaeufe/lesen")
    assert r.status_code == 201, r.text
    kopie = _lesen(client, "06-ablaeufe/lesen_kopie")["data"]
    assert kopie["id"] == "lesen_kopie"
    # Der Name gilt für die Sprache der Anfrage; andere Sprachen bleiben.
    assert kopie["titel"] == {"de": "Lesen (Kopie)", "en": "Read"}
    # Eine Kopie wirkt erst, wenn die Redaktion sie einschaltet — sonst lösten zwei Abläufe
    # dieselbe Wendung aus.
    assert kopie["aktiv"] is False
    assert kopie["schritte"] == ablauf("lesen")["schritte"]
    assert kopie["ausloeser"] == [{"art": "text", "wendungen": ["lies mir vor"]}]


# ── speichern ──────────────────────────────────────────────────────────────
def test_die_kennung_muss_zum_schluessel_passen(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    version = _lesen(client, "06-ablaeufe/lesen")["version"]
    r = _speichern(client, "06-ablaeufe/lesen", ablauf("schreiben"), version)
    assert r.status_code == 400, r.text
    assert "06-ablaeufe/schreiben" in r.text


def test_ein_unausfuehrbarer_ablauf_wird_nicht_gespeichert(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    version = _lesen(client, "06-ablaeufe/lesen")["version"]
    kaputt = ablauf("lesen")
    kaputt["schritte"][0]["weiter"] = "gibts_nicht"
    r = _speichern(client, "06-ablaeufe/lesen", kaputt, version)
    assert r.status_code == 400, r.text
    assert "gibts_nicht" in r.text


def test_ein_ablauf_speichert_nur_sich_selbst(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    seed("06-ablaeufe/schreiben", ablauf("schreiben"))
    vorher = _lesen(client, "06-ablaeufe/schreiben")["version"]
    gelesen = _lesen(client, "06-ablaeufe/lesen")
    r = _speichern(client, "06-ablaeufe/lesen", {**gelesen["data"], "aktiv": True},
                   gelesen["version"])
    assert r.status_code == 200, r.text
    assert _lesen(client, "06-ablaeufe/lesen")["data"]["aktiv"] is True
    assert _lesen(client, "06-ablaeufe/schreiben")["version"] == vorher


# ── Schlüssel und löschen ──────────────────────────────────────────────────
@pytest.mark.parametrize("key", ["06-ablaeufe", "06-ablaeufe/a/b", "06-ablaeufe/katalog"])
def test_kein_dokument_ausserhalb_eines_blatts(cfg, key) -> None:
    client, _ = cfg
    r = _speichern(client, key, ablauf("katalog"), None)
    assert r.status_code in (400, 404), r.text


def test_ein_ablauf_laesst_sich_loeschen(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    r = client.delete("/api/config/file", headers=_AUTH, params={"path": "06-ablaeufe/lesen"})
    assert r.status_code == 200, r.text
    r = client.get("/api/config/data/06-ablaeufe/lesen", headers=_AUTH)
    assert r.json()["version"] is None


# ── Liste für die Studio-Seite „Abläufe“ ───────────────────────────────────
def test_die_liste_fasst_jeden_ablauf_zusammen(cfg) -> None:
    client, seed = cfg
    seed("06-ablaeufe/zeigen", ablauf(
        "zeigen", aktiv=True, titel={"de": "Zeigen", "en": "Show"},
        ausloeser=[{"art": "knopf"}, {"art": "text", "wendungen": ["zeig"]}],
        schritte=[{"id": "frage", "typ": "modul", "modul": "ui_entscheidung",
                   "daten": {"frage": "Was?", "optionen": [{"id": "a", "label": "A"},
                                                          {"id": "b", "label": "B"}]}},
                  {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]))
    kaputt = ablauf("lesen")
    kaputt["schritte"][0]["weiter"] = "gibts_nicht"
    seed("06-ablaeufe/lesen", kaputt)
    seed("06-ablaeufe/modellfehler", {"id": "modellfehler", "schritte": "keine Liste"})
    r = client.get("/api/config/ablaeufe", headers=_AUTH)
    assert r.status_code == 200, r.text
    liste = r.json()["ablaeufe"]
    assert [a["key"] for a in liste] == [
        "06-ablaeufe/lesen", "06-ablaeufe/modellfehler", "06-ablaeufe/zeigen"]
    zeigen = liste[2]
    assert zeigen == {"key": "06-ablaeufe/zeigen", "id": "zeigen",
                      "titel": {"de": "Zeigen", "en": "Show"}, "aktiv": True,
                      "ausloeser": ["knopf", "text"], "module": ["ui_entscheidung"],
                      "befunde": 0, "lesbar": True}
    assert liste[0]["befunde"] >= 1 and liste[0]["lesbar"] is True
    assert liste[1]["lesbar"] is False and liste[1]["befunde"] == 0


def test_die_liste_nennt_module_aus_agent_schritt_und_ausloeser(cfg) -> None:
    """Review AS-2: die Querverweise am Modul kennen auch die UI-Module, die die KI in einem
    ``agent``-Schritt zeigen darf, und die Module, auf deren Antwort ein Ablauf startet — ein
    lesendes WLO-Werkzeug daneben ist kein Modul."""
    client, seed = cfg
    seed("06-ablaeufe/ki", ablauf(
        "ki", ausloeser=[{"art": "modul", "modul": "ui_upload", "wenn_teil": "datei"}],
        schritte=[{"id": "frei", "typ": "agent",
                   "agent": {"werkzeuge": ["ui_entscheidung", "search_wlo_all"]}},
                  {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]))
    r = client.get("/api/config/ablaeufe", headers=_AUTH)
    assert r.status_code == 200, r.text
    (ki,) = [a for a in r.json()["ablaeufe"] if a["id"] == "ki"]
    assert ki["module"] == ["ui_entscheidung", "ui_upload"]


def test_die_liste_braucht_den_studio_schluessel(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/ablaeufe").status_code in (401, 403)


# ── Review AS-0 ────────────────────────────────────────────────────────────
def test_ein_feld_frontmatter_umgeht_die_kennung_nicht(cfg) -> None:
    """Befund 1: die Kennung eines Ablaufs ist sein Feld ``id`` — ein ``frontmatter`` daneben
    (das Modell lässt Zusatzfelder zu) ändert daran nichts."""
    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    version = _lesen(client, "06-ablaeufe/lesen")["version"]
    for falsch in ({**ablauf("fremd"), "frontmatter": {"id": "lesen"}},
                   {**ablauf("lesen"), "id": "", "frontmatter": None}):
        r = _speichern(client, "06-ablaeufe/lesen", falsch, version)
        assert r.status_code in (400, 422), r.text


def test_der_gestrichene_katalog_ist_nicht_mehr_adressierbar(cfg) -> None:
    """Befund 1: ``06-ablaeufe/katalog`` liegt im Ordner, ist aber gestrichen — weder lesen noch
    schreiben (eine Zeile dort ließe sich nicht mehr löschen)."""
    client, _ = cfg
    doc = {**ablauf("katalog"), "frontmatter": None}
    assert _speichern(client, "06-ablaeufe/katalog", doc, None).status_code == 404
    assert client.get("/api/config/data/06-ablaeufe/katalog", headers=_AUTH).status_code == 404
    assert client.get("/api/config/schema/06-ablaeufe/katalog", headers=_AUTH).status_code == 404


def test_eine_alte_sicherung_mit_katalog_bringt_die_ablaeufe_zurueck(cfg) -> None:
    """Befund 2: eine Sicherung von vor AS-0 trägt ``06-ablaeufe/katalog``. Sie wird beim
    Wiederherstellen in Dokumente geteilt — im Modus „exakt“ verschwinden die Abläufe nicht."""
    from boerdi.services import snapshots

    client, seed = cfg
    seed("06-ablaeufe/lesen", ablauf("lesen"))
    seed("06-ablaeufe/weg", ablauf("weg"))
    alt = ablauf("lesen")
    alt["schritte"][0]["text"] = {"de": "Aus der Sicherung."}
    blob = snapshots.build_config_zip({"06-ablaeufe/katalog": {"ablaeufe": [alt, ablauf("neu")]}})
    r = client.post("/api/config/restore", headers=_AUTH, params={"mode": "exact"},
                    files={"file": ("alt.zip", blob, "application/zip")})
    assert r.status_code == 200, r.text
    assert _lesen(client, "06-ablaeufe/lesen")["data"] == alt
    assert _lesen(client, "06-ablaeufe/neu")["data"] == ablauf("neu")
    # exakt: was die Sicherung nicht trägt, geht — wie bei jedem Bereich
    assert _lesen(client, "06-ablaeufe/weg")["version"] is None
