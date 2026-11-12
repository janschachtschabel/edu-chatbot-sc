"""Paket K2c-1 (Plan 2026-11-08): was das Studio für einen bequemen Ablauf-Editor braucht.

- **Felder je Schritttyp:** ``x-nur-bei`` an den Feldern von ``Schritt`` sagt, bei welchem ``typ``
  ein Feld gilt — das Studio blendet die anderen aus (K2c-2). Nur eine Auszeichnung im Schema: sie
  ändert weder gespeicherte Daten noch die Fassung eines Ablaufs (wartende Läufe brächen sonst ab).
- **Flow-Auswahl:** ``Schritt.flow`` zeigt den Katalog ``ablauf_flows`` — die Freischaltliste
  ``B_API_JOBS_FLOWS`` (ohne Abruf bei der b-api: der Katalog-Endpunkt ruft keinen Fremddienst).
- **„Prüfen“ ohne Speichern:** ``POST /api/config/ablauf-pruefen`` — die Befunde von
  ``pruefung.pruefe`` je Schritt, nur mit Studio-Schlüssel, schreibt nichts.
"""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.main import create_app
from boerdi.services.ablauf import pruefung, treiber
from boerdi.settings import get_settings
from tests.test_ablauf_auftrag import _SCHRITTE, _roh

_AUTH = {"X-Studio-Key": "k-studio-k2c1"}

#: Felder je Schritttyp — aus ``treiber`` und ``pruefung`` gelesen (Plan, Zuschnitt K2c).
ERWARTET = {
    "text": {"nachricht", "modul", "agent", "auftrag", "seite", "ende"},  # AS-7a: seite
    "modul": {"modul"},
    "daten": {"modul"},
    "werkzeug": {"werkzeug"},
    "flow": {"auftrag"},
    "argumente": {"werkzeug", "auftrag"},
    "warten": {"auftrag"},
    "dateien_holen": {"auftrag"},  # K2d-2
    "schreibt": {"werkzeug", "auftrag", "nachricht"},   # TB-T1: Label der Wahl
    "freigabe": {"werkzeug"},  # Paket S
    "weiter": {"nachricht", "modul", "werkzeug", "verzweigung", "agent", "auftrag", "seite"},
    "bei_fehler": {"modul", "werkzeug", "agent", "auftrag"},
    "agent": {"agent"},
    # AS-7a (Plan 2026-11-09 §5m): Führungen
    "url": {"seite"},
    "label": {"seite"},
    "ankunft": {"seite"},
}


def _props() -> dict:
    return Schritt.model_json_schema()["properties"]


def test_jedes_schrittfeld_sagt_bei_welchem_typ_es_gilt():
    props = _props()
    typen = set(props["typ"]["x-choices"])
    for feld, erwartet in ERWARTET.items():
        marke = props[feld].get("x-nur-bei")
        assert marke == {"feld": "typ", "werte": sorted(erwartet)}, feld
        assert set(marke["werte"]) <= typen, feld
    assert "x-nur-bei" not in props["id"] and "x-nur-bei" not in props["typ"]


def test_die_auszeichnung_aendert_weder_daten_noch_fassung():
    roh = _roh()
    ablauf = AblaufArea.model_validate(copy.deepcopy(roh))
    for s_roh, s in zip(roh["schritte"], ablauf.schritte, strict=True):
        assert s.model_dump(mode="json", exclude_none=True) == {
            k: v for k, v in s_roh.items() if v is not None}
    # Review K2c-1, Befund 1: die Fassung, die main (vor K2c-1) für dieselben Daten rechnet — ändert
    # eine Auszeichnung je das Dump, bräche jeder wartende Lauf ab.
    assert treiber.fassung(ablauf) == "5d2ade455776"


def test_der_flow_zeigt_die_freischaltliste(monkeypatch):
    from boerdi.api import config_choices

    assert _props()["flow"]["anyOf"][0].get("x-catalog") == "ablauf_flows"
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext, edusharing.support/test-mit-jan")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/flows/{flow}/jobs")
    get_settings.cache_clear()
    try:
        werte = [e["value"] for e in config_choices._SOURCES["ablauf_flows"]()]
    finally:
        get_settings.cache_clear()
    assert werte == ["edusharing.support/test-mit-jan", "wlo/volltext"]


# ── „Prüfen“ ohne Speichern ─────────────────────────────────────────────────────────────────

@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-k2c1")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/flows/{flow}/jobs")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    yield TestClient(create_app(), raise_server_exceptions=False)
    get_settings.cache_clear()


def test_pruefen_braucht_den_studio_schluessel(studio):
    assert studio.post("/api/config/ablauf-pruefen", json=_roh()).status_code == 401


def test_ein_stimmiger_ablauf_hat_keine_befunde(studio):
    r = studio.post("/api/config/ablauf-pruefen", json=_roh(), headers=_AUTH)
    assert r.status_code == 200, r.text
    # AS-Db: ``document`` kommt aus dem Gespräch (``ui_upload``) — ein Hinweis, kein Befund
    assert r.json()["befunde"] == []
    assert [w for w in r.json()["warnungen"] if "document" in w and "Gespräch" in w]


def test_befunde_stehen_am_schritt(studio):
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[1] = {**schritte[1], "warten": "gesperrt"}       # nur an Auftragsschritten
    schritte[0] = {**schritte[0], "weiter": "gibt_es_nicht"}
    r = studio.post("/api/config/ablauf-pruefen", json=_roh(schritte=schritte), headers=_AUTH)
    assert r.status_code == 200, r.text
    befunde = r.json()["befunde"]
    assert {b["schritt"] for b in befunde} == {schritte[0]["id"], schritte[1]["id"]}
    assert {b["nr"] for b in befunde} == {0, 1}
    assert all(isinstance(b["text"], str) and b["text"] for b in befunde)


def test_befunde_des_ganzen_ablaufs_haben_keinen_schritt(studio):
    schritte = [s for s in copy.deepcopy(_SCHRITTE) if s["typ"] != "ende"]
    r = studio.post("/api/config/ablauf-pruefen", json=_roh(schritte=schritte), headers=_AUTH)
    assert r.status_code == 200, r.text
    assert any(b["schritt"] is None for b in r.json()["befunde"])


def test_englisch_auf_wunsch(studio):
    schritte = [s for s in copy.deepcopy(_SCHRITTE) if s["typ"] != "ende"]
    de = studio.post("/api/config/ablauf-pruefen", json=_roh(schritte=schritte), headers=_AUTH)
    en = studio.post("/api/config/ablauf-pruefen", json=_roh(schritte=schritte),
                     headers={**_AUTH, "Accept-Language": "en"})
    assert de.json() != en.json()


def test_ein_kaputter_ablauf_ist_ein_422(studio):
    r = studio.post("/api/config/ablauf-pruefen", json={"id": "Kein Name"}, headers=_AUTH)
    assert r.status_code == 422


def test_gegliedert_und_flach_sagen_dasselbe():
    """``pruefe`` (Speichern, Wächter) bleibt die flache Liste derselben Befunde, gleiche Folge."""
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[1] = {**schritte[1], "warten": "gesperrt"}
    ablauf = AblaufArea.model_validate(_roh(schritte=schritte))
    assert [t for _s, t in pruefung.pruefe_gegliedert(ablauf)] == pruefung.pruefe(ablauf)


def test_der_flow_katalog_ist_leer_ohne_eingerichtete_auftraege(monkeypatch):
    """Review K2c-1, Befund 3: ohne eingerichtete Aufträge keine Vorschläge (sonst meldete „Prüfen“
    danach „nicht freigeschaltet“). Seit Paket KF (K-E3) hat ein leerer Start-Pfad eine Vorgabe —
    aus sind Aufträge ohne freigegebenen Flow oder mit unsicherem Pfad."""
    from boerdi.api import config_choices

    monkeypatch.delenv("B_API_JOBS_FLOWS", raising=False)
    monkeypatch.setenv("B_API_JOBS_START_PATH", "")
    get_settings.cache_clear()
    try:
        assert config_choices._SOURCES["ablauf_flows"]() == []
        monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
        monkeypatch.setenv("B_API_JOBS_START_PATH", "//boese.example/{flow}")
        get_settings.cache_clear()
        assert config_choices._SOURCES["ablauf_flows"]() == []
        monkeypatch.setenv("B_API_JOBS_START_PATH", "")          # Vorgabe greift
        get_settings.cache_clear()
        assert [e["value"] for e in config_choices._SOURCES["ablauf_flows"]()] == ["wlo/volltext"]
    finally:
        get_settings.cache_clear()


def test_doppelte_kennungen_tragen_ihren_index(studio):
    schritte = copy.deepcopy(_SCHRITTE)
    schritte.append({**schritte[0], "weiter": "nirgends"})   # zweites „lesen“, Ziel unbekannt
    r = studio.post("/api/config/ablauf-pruefen", json=_roh(schritte=schritte), headers=_AUTH)
    am_schritt = [b for b in r.json()["befunde"] if b["schritt"] == "lesen"]
    assert am_schritt and {b["nr"] for b in am_schritt} == {len(schritte) - 1}


#: Review K2c-1, Befund 2: was ``pruefe`` auf main (vor K2c-1) für diese Abläufe meldete — wörtlich,
#: in dieser Reihenfolge. Gerechnet mit dem Stand von main, nicht mit dem neuen Code.
_GOLD = {
    "A/de": [
        "Schritt-IDs doppelt: fertig",
        "Schritt lesen: Flow 'wlo/volltext' ist nicht freigegeben "
        "(Abläufe → Kestra-Flows freigeben)",
        "Schritt lesen: Ziel 'nirgends' gibt es nicht",
        "Aufträge brauchen die Voraussetzung Anmeldung"
    ],
    "A/en": [
        "Duplicate step ids: fertig",
        "Step lesen: flow 'wlo/volltext' is not enabled (Workflows → Enable Kestra flows)",
        "Step lesen: target 'nirgends' does not exist",
        "Jobs need the requirement sign-in"
    ],
    "B/de": [
        "Schritt insel: Text (de) fehlt",
        "Kein Schritt ende — der Lauf hätte kein Ende",
        "Schritt insel: nicht erreichbar",
        "Schritt mitte: der Lauf liefe ohne Ende aus (letzter Schritt ohne weiter)"
    ],
    "B/en": [
        "Step insel: text (de) missing",
        "No end step — the run would never end",
        "Step insel: unreachable",
        "Step mitte: the run would stop without an end step (last step, no next)"
    ]
}


def _gold_faelle() -> dict:
    a = copy.deepcopy(_SCHRITTE)
    a[0] = {**a[0], "weiter": "nirgends"}
    a.append({"id": "fertig", "typ": "ende", "text": {"de": "Nochmal."}})
    b = [{"id": "start", "typ": "nachricht", "text": {"de": "Hallo"}, "weiter": "mitte"},
         {"id": "insel", "typ": "nachricht"},
         {"id": "mitte", "typ": "nachricht", "text": {"de": "Und?"}}]
    return {"A": _roh(schritte=a, voraussetzungen=[]), "B": _roh(schritte=b)}


@pytest.mark.parametrize("schluessel", sorted(_GOLD))
def test_pruefe_meldet_wie_vor_k2c1(schluessel):
    fall, lang = schluessel.split("/")
    ablauf = AblaufArea.model_validate(_gold_faelle()[fall])
    assert pruefung.pruefe(ablauf, lang) == _GOLD[schluessel]
    assert [t for _i, t in pruefung.pruefe_gegliedert(ablauf, lang)] == _GOLD[schluessel]


def test_tief_geschachtelte_daten_brechen_die_pruefung_nicht():
    """Review K2c-1, Befund 8 (älter): sonst ``RecursionError`` → 500."""
    wert: dict = {"$teil": "ganz_unten"}
    for _ in range(5000):
        wert = {"x": wert}
    assert pruefung._alle_verweis_namen(wert) == []
    assert pruefung._alle_verweis_namen({"a": {"$teil": "oben"}}) == ["oben"]

