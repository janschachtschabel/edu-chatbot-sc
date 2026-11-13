"""Paket AS-1 (Plan 2026-11-09 §5c): Testfälle eines Ablaufs, mit dem echten Treiber simuliert.

Ein Testfall nennt die Teile vor dem Start, die Ergebnisse der Werkzeuge je Schritt und die
Eingaben an jedem wartenden Schritt (Antwort eines Moduls, Auftrag fertig/gescheitert, Freigabe
ja/nein, Teile der KI). Erwartet werden Weg, Status, Ende und Teile. Die Simulation ruft weder LLM
noch MCP, startet keinen Auftrag und legt nichts vor — sie kostet nichts und ist wiederholbar.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.main import create_app
from boerdi.services.ablauf import simulation, werkzeuge
from boerdi.settings import get_settings

_FRAGE = {"frage": "Was soll passieren?", "optionen": [
    {"id": "zaehlen", "label": "Zählen"}, {"id": "anlegen", "label": "Anlegen"}]}


def _ablauf(**mehr) -> AblaufArea:
    roh = {
        "id": "pruefen", "titel": {"de": "Prüfen"}, "voraussetzungen": ["anmeldung"],
        "schritte": [
            {"id": "start", "typ": "nachricht", "text": {"de": "Los."}},
            {"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE},
            {"id": "wohin", "typ": "verzweigung", "weiter": [
                {"wenn_gewaehlt": "zaehlen", "dann": "zaehlen"},
                {"wenn_gewaehlt": "anlegen", "dann": "anlegen"},
                {"sonst": "ende"}]},
            {"id": "zaehlen", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
             "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "zahlen",
             "bei_fehler": "ohne_zahlen", "weiter": "volltext"},
            {"id": "volltext", "typ": "auftrag", "flow": "wlo/volltext", "schreibt": "texte",
             "argumente": {"node_ids": ["n-1"]}, "bei_fehler": "ohne_zahlen", "weiter": "ende"},
            {"id": "anlegen", "typ": "werkzeug", "werkzeug": "wlo_create_collection",
             "argumente": {"name": "Optik"}, "schreibt": "sammlung",
             "freigabe": {"de": "Soll ich die Sammlung anlegen?"}, "weiter": "nachdenken"},
            {"id": "nachdenken", "typ": "agent", "text": {"de": "Wir besprechen das."},
             "agent": {"werkzeuge": ["search_wlo_all"], "ausgabe": "notiz", "zuege": 3},
             "weiter": "ende"},
            {"id": "ohne_zahlen", "typ": "ende", "text": {"de": "Ohne Zahlen."}},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}},
        ], **mehr}
    return AblaufArea.model_validate(roh)


def _test(**roh) -> AblaufTest:
    return AblaufTest.model_validate({"name": "t", **roh})


def _lauf(test: AblaufTest, ablauf: AblaufArea | None = None):
    return asyncio.run(simulation.testen(ablauf or _ablauf(), test, "de"))


@pytest.fixture(autouse=True)
def _keine_echten_aufrufe(monkeypatch):
    """Ein echter Dienst, MCP-Aufruf oder Auftrag ließe den Test scheitern. Der Flow der Beispiele
    ist freigeschaltet — „Tests ausführen“ prüft den Ablauf vorher wie beim Speichern."""
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/jobs/flows/{flow}")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    async def verboten(*_a, **_k):
        raise AssertionError("echter Aufruf in der Simulation")

    monkeypatch.setattr(werkzeuge, "DIENSTE", {k: verboten for k in werkzeuge.DIENSTE})
    from boerdi.services.auftraege import client as auftraege
    from boerdi.services.mcp import client
    from boerdi.ui_module import aufruf
    monkeypatch.setattr(client, "call_mcp_tool_antwort", verboten)
    # Review AS-1 (NIT): auch Modul-Dienste und Aufträge
    monkeypatch.setattr(aufruf, "asynchron", verboten)
    monkeypatch.setattr(auftraege, "starten", verboten)


# ── Wege ───────────────────────────────────────────────────────────────────
def test_zaehlen_mit_werkzeug_und_auftrag_bis_zum_ende():
    test = _test(
        teile={"draft": {"titel": "Optik", "knoten": []}},
        werkzeuge={"zaehlen": {"punkte": [{"id": "a", "treffer": 3}]}},
        eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["zaehlen"]}},
                  {"bei": "volltext", "ergebnis": {"outputs": {"n": 1}}}],
        erwartet={"weg": ["start", "frage", "wohin", "zaehlen", "volltext", "ende"],
                  "status": "fertig", "ende": "ende", "teile": ["zahlen", "texte"]})
    e = _lauf(test)
    assert e.ok, e.abweichungen
    assert e.weg == ["start", "frage", "wohin", "zaehlen", "volltext", "ende"]


def test_ein_werkzeug_ohne_ergebnis_geht_zu_bei_fehler():
    test = _test(teile={"draft": {"knoten": []}}, werkzeuge={"zaehlen": None},
                 eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["zaehlen"]}}],
                 erwartet={"ende": "ohne_zahlen", "status": "fertig"})
    assert _lauf(test).ok


def test_ein_gescheiterter_auftrag_geht_zu_bei_fehler():
    test = _test(teile={"draft": {"knoten": []}}, werkzeuge={"zaehlen": {"n": 1}},
                 eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["zaehlen"]}},
                           {"bei": "volltext", "fehler": True}],
                 erwartet={"ende": "ohne_zahlen"})
    assert _lauf(test).ok


def test_freigabe_ja_und_die_ki_hinterlaesst_ihren_teil():
    test = _test(eingaben=[
        {"bei": "frage", "antwort": {"gewaehlt": ["anlegen"]}},
        {"bei": "anlegen", "freigabe": "ja", "ergebnis": {"nodeId": "c-1"}},
        {"bei": "nachdenken", "teile": {"notiz": "passt"}}],
        erwartet={"weg": ["start", "frage", "wohin", "anlegen", "nachdenken", "ende"],
                  "status": "fertig", "teile": ["sammlung", "notiz"]})
    e = _lauf(test)
    assert e.ok, e.abweichungen


def test_freigabe_nein_laesst_den_lauf_warten():
    test = _test(eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["anlegen"]}},
                           {"bei": "anlegen", "freigabe": "nein"}],
                 erwartet={"status": "wartet_freigabe", "ende": "anlegen"})
    assert _lauf(test).ok


def test_ohne_eingabe_bleibt_der_lauf_am_wartenden_schritt():
    e = _lauf(_test(erwartet={"status": "wartet_person", "ende": "frage"}))
    assert e.ok and e.weg == ["start", "frage"]


# ── Abweichungen ───────────────────────────────────────────────────────────
def test_abweichungen_werden_genannt():
    test = _test(eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["gibtsnicht"]}},
                           {"bei": "volltext", "ergebnis": {}}],
                 erwartet={"weg": ["start", "frage", "zaehlen"], "status": "fehler",
                           "ende": "zaehlen", "teile": ["zahlen"]})
    e = _lauf(test)
    # Querschnitts-Review AS-0…AS-2, Befund 3: „gibtsnicht“ bot die Frage nicht an — der Betrieb
    # verwürfe die Antwort, der Lauf bleibt an der Frage stehen
    assert not e.ok and e.status == "wartet_person" and e.ende == "frage"
    text = " | ".join(e.abweichungen)
    for teil in ("passt nicht zur Frage", "Weg", "Status", "Ende", "zahlen", "volltext"):
        assert teil in text, (teil, text)


def test_eine_eingabe_fuer_einen_anderen_schritt_haelt_an():
    e = _lauf(_test(eingaben=[{"bei": "volltext", "ergebnis": {}}]))
    assert not e.ok and e.status == "wartet_person"
    assert any("frage" in a and "volltext" in a for a in e.abweichungen)


def test_ohne_erwartung_zaehlt_nur_dass_nichts_abweicht():
    assert _lauf(_test()).ok


# ── Grenzen und Modell ─────────────────────────────────────────────────────
def test_tests_haengen_am_ablauf_und_aendern_seine_fassung_nicht():
    from boerdi.services.ablauf.treiber import fassung

    ohne = _ablauf()
    mit = _ablauf(tests=[{"name": "a", "erwartet": {}}])
    assert fassung(ohne) == fassung(mit) and mit.tests[0].name == "a"


@pytest.mark.parametrize("roh", [
    {"name": ""}, {"name": "x" * 81},
    {"name": "a", "eingaben": [{"bei": "frage"}] * 31},
    {"name": "a", "eingaben": [{"bei": "frage", "freigabe": "vielleicht"}]},
])
def test_ein_testfall_ist_gedeckelt(roh):
    with pytest.raises(ValueError):
        AblaufTest.model_validate(roh)


def test_alle_testfaelle_eines_ablaufs():
    ablauf = _ablauf(tests=[
        {"name": "wartet", "erwartet": {"status": "wartet_person"}},
        {"name": "falsch", "erwartet": {"status": "fertig"}}])
    ergebnisse = asyncio.run(simulation.alle(ablauf, "de"))
    assert [(e.name, e.ok) for e in ergebnisse] == [("wartet", True), ("falsch", False)]


# ── Endpunkt ───────────────────────────────────────────────────────────────
@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-as1")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    yield TestClient(create_app(), raise_server_exceptions=False)
    get_settings.cache_clear()


def test_der_endpunkt_fuehrt_die_testfaelle_aus(studio):
    roh = _ablauf(tests=[{"name": "wartet", "erwartet": {"status": "wartet_person",
                                                          "weg": ["start", "frage"]}}]
                  ).model_dump(mode="json", exclude_none=True)
    assert studio.post("/api/config/ablauf-testen", json=roh).status_code == 401
    r = studio.post("/api/config/ablauf-testen", json=roh,
                    headers={"X-Studio-Key": "k-studio-as1"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ergebnisse": [{"name": "wartet", "ok": True, "status": "wartet_person",
                                        "weg": ["start", "frage"], "ende": "frage",
                                        "abweichungen": [], "texte": ["Los."]}]}


# ── Review AS-1 ────────────────────────────────────────────────────────────
def _klein(*schritte, **mehr) -> AblaufArea:
    return AblaufArea.model_validate({"id": "klein", "titel": {"de": "K"}, "schritte": [
        *schritte, {"id": "gut", "typ": "ende"}, {"id": "kaputt", "typ": "ende"}], **mehr})


def test_ein_modul_mit_falschen_daten_geht_zu_bei_fehler_wie_im_betrieb():
    """Befund 1: der Platzhalter galt für jedes Modul — im Betrieb geht ein Modul, dessen Daten
    nicht zum Vertrag passen, zu ``bei_fehler``."""
    ablauf = _klein({"id": "frage", "typ": "modul", "modul": "ui_entscheidung",
                     "daten": {"$teil": "dd"}, "bei_fehler": "kaputt", "weiter": "gut"})
    e = _lauf(_test(teile={"dd": {"falsch": True}}, erwartet={"ende": "kaputt"}), ablauf)
    assert e.ok, e.abweichungen


def test_ein_lesendes_werkzeug_liefert_text_wie_im_betrieb():
    """Befund 2: im Betrieb liefert ein lesendes MCP-Werkzeug Text — ein ``pfad`` darin findet
    nichts."""
    ablauf = _klein(
        {"id": "suchen", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "Optik"}, "schreibt": "treffer"},
        {"id": "zeigen", "typ": "modul", "modul": "ui_entscheidung",
         "daten": {"$teil": "treffer", "pfad": "frage"}, "bei_fehler": "kaputt", "weiter": "gut"})
    test = _test(werkzeuge={"suchen": {"frage": {"frage": "x", "optionen": []}}},
                 erwartet={"ende": "kaputt"})
    e = _lauf(test, ablauf)
    assert e.ok, e.abweichungen


def test_nach_nein_geht_ein_ja_wie_nach_vorschau_erneut():
    """Befund 3: im Betrieb wartet der Lauf nach einem Nein — „Vorschau erneut“, dann ja."""
    test = _test(eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["anlegen"]}},
                           {"bei": "anlegen", "freigabe": "nein"},
                           {"bei": "anlegen", "freigabe": "ja", "ergebnis": {"nodeId": "c"}}],
                 erwartet={"status": "wartet_ki", "ende": "nachdenken"})
    e = _lauf(test)
    assert e.ok, e.abweichungen


@pytest.mark.parametrize(("eingaben", "schritt"), [
    ([{"bei": "frage"}], "frage"),                                     # Modul ohne Antwort
    ([{"bei": "frage", "antwort": {"gewaehlt": ["zaehlen"]}},
      {"bei": "volltext"}], "volltext"),                               # Auftrag ohne Ausgang
    ([{"bei": "frage", "antwort": {"gewaehlt": ["anlegen"]}},
      {"bei": "anlegen", "ergebnis": {}}], "anlegen"),                 # Freigabe ohne ja/nein
])
def test_eine_eingabe_die_nicht_zum_wartepunkt_passt_wird_gemeldet(eingaben, schritt):
    """Befund 4: still ein „nein“ oder ein leerer Erfolg — jetzt eine Abweichung."""
    e = _lauf(_test(teile={"draft": {}}, werkzeuge={"zaehlen": {"n": 1}}, eingaben=eingaben))
    assert not e.ok
    assert any("passt nicht" in a and schritt in a for a in e.abweichungen), e.abweichungen


def test_ein_unausfuehrbarer_ablauf_wird_nicht_als_bestanden_gemeldet(studio):
    """Befund 5: ``schritte: []`` warf 500; ein Ablauf mit Befunden der Prüfung „bestand“."""
    roh = {"id": "leer", "titel": {"de": "L"}, "schritte": [],
           "tests": [{"name": "a", "erwartet": {}}]}
    r = studio.post("/api/config/ablauf-testen", json=roh,
                    headers={"X-Studio-Key": "k-studio-as1"})
    assert r.status_code == 200, r.text
    [e] = r.json()["ergebnisse"]
    assert e["ok"] is False and e["abweichungen"]


def test_ohne_anmeldung_startet_ein_ablauf_mit_voraussetzung_nicht():
    """Befund 6: ``angemeldet: false`` — die Voraussetzung ``anmeldung`` fehlt."""
    e = _lauf(_test(angemeldet=False, erwartet={"status": "nicht_gestartet"}))
    assert e.ok and e.weg == []


def test_ohne_anmeldung_geht_ein_auftrag_zu_bei_fehler():
    ablauf = _klein({"id": "holen", "typ": "auftrag", "flow": "wlo/volltext",
                     "bei_fehler": "kaputt", "weiter": "gut"})
    assert _lauf(_test(angemeldet=False, erwartet={"ende": "kaputt"}), ablauf).ok


def test_ein_testfall_kann_nach_einem_modul_beginnen_wie_ein_modul_ausloeser():
    """Befund 6: ``ab`` und ``gewaehlt`` — wie ein Modul-Auslöser nach dem beantworteten Modul."""
    e = _lauf(_test(ab="wohin", gewaehlt=["anlegen"], erwartet={
        "weg": ["wohin", "anlegen"], "status": "wartet_freigabe"}))
    assert e.ok, e.abweichungen


def test_status_steht_in_worten_in_der_abweichung():
    e = _lauf(_test(erwartet={"status": "fertig"}))
    assert any("wartet auf die Person" in a for a in e.abweichungen), e.abweichungen


def test_ablauf_testen_hat_eine_eigene_rumpfgrenze():
    from boerdi.api.body_limit import body_limit_for

    assert body_limit_for("/api/config/ablauf-testen") == 2 * 1024 * 1024


# ── Querschnitts-Review AS-0…AS-2 ──────────────────────────────────────────
def _zwei_werkzeuge() -> AblaufArea:
    return _klein(
        {"id": "eins", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "a"}, "schreibt": "erste_treffer", "bei_fehler": "kaputt",
         "weiter": "zwei"},
        {"id": "zwei", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "b"}, "schreibt": "zweite_treffer", "weiter": "gut"})


def test_die_frist_greift_mitten_im_testfall(monkeypatch):
    """Befund 1: die Kette gibt die Schleife nie frei — die Frist prüft jeder Schritt selbst."""
    import time

    async def langsam(self, schritt, name, args):
        time.sleep(0.2)                      # rechnet, ohne die Schleife freizugeben
        return "x"

    monkeypatch.setattr(simulation._Stand, "ersatz", langsam)
    monkeypatch.setattr(simulation, "BUDGET_S", 0.05)
    ablauf = _zwei_werkzeuge().model_copy(update={"tests": [_test(name="a"), _test(name="b")]})
    ergebnisse = asyncio.run(simulation.alle(ablauf, "de"))
    assert [e.ok for e in ergebnisse] == [False, False]
    assert all("Zeitbudget" in e.abweichungen[0] for e in ergebnisse)


def test_ein_kreisender_lauf_endet_am_deckel(monkeypatch):
    monkeypatch.setattr(simulation, "MAX_SCHRITTE", 1)
    ablauf = _zwei_werkzeuge().model_copy(update={"tests": [_test()]})
    (e,) = asyncio.run(simulation.alle(ablauf, "de"))
    assert not e.ok and "Mehr als 1 Schritte" in e.abweichungen[0]


def test_der_endpunkt_rechnet_in_einem_eigenen_thread():
    import threading

    gesehen: list[str] = []

    async def alle(ablauf, lang):
        gesehen.append(threading.current_thread().name)
        return []

    haupt = threading.current_thread().name
    alt = simulation.alle
    simulation.alle = alle
    try:
        assert asyncio.run(simulation.im_thread(_ablauf(), "de")) == []
    finally:
        simulation.alle = alt
    assert gesehen and gesehen[0] != haupt


def test_eine_antwort_die_der_betrieb_verwuerfe_ist_eine_abweichung():
    """Befund 3: ``wenn_gewaehlt: neu``, die Möglichkeit heißt aber anders — im Betrieb ist „neu“
    nie wählbar. Die Simulation prüft die Antwort wie der Betrieb gegen die Frage."""
    test = _test(eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["neu"]}}])
    e = _lauf(test)
    assert not e.ok
    assert any("passt nicht zur Frage" in a for a in e.abweichungen)
    # eine angebotene Möglichkeit geht durch
    gut = _lauf(_test(eingaben=[{"bei": "frage", "antwort": {"gewaehlt": ["zaehlen"]}}],
                      werkzeuge={"zaehlen": {"n": 1}}))
    assert "zaehlen" in gut.weg


def test_review_r2_7_dokument_lesen_wie_im_betrieb(monkeypatch):
    """Review R2, Befund 7: die Voraussetzung ``dokument_lesen`` gilt im Testfall wie live
    (``ausloeser.fehlt`` mit ``angemeldet`` des Testfalls statt der echten Anmeldung)."""
    from boerdi.domain.config_models.upload import UploadSettings
    from boerdi.services.ablauf import ausloeser

    ablauf = _ablauf(voraussetzungen=["dokument_lesen"])
    monkeypatch.setattr(ausloeser, "load_upload_config",
                        lambda: UploadSettings(dokument_ohne_anmeldung=False))
    nicht = _lauf(_test(angemeldet=False, erwartet={"status": "nicht_gestartet"}), ablauf)
    assert nicht.ok and nicht.weg == []
    assert _lauf(_test(angemeldet=True), ablauf).weg
