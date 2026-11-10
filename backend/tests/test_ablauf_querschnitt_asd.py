"""Querschnitts-Review AS-D (Plan 2026-11-09 §5e): was zwischen Auswahl, Typen, Sicht und Diensten
liegt.

- Befund 1: die Simulation rechnet reine Dienste selbst (ohne Netz) — ein Testfall überschreibt;
  so bildet sie die Kette Entwurf → Baum → Anlegen → Kennungen ab.
- Befund 2: Pfad oder Auswahl in einem Text-Teil, eine Auswahl an einem Objekt-Argument eines
  Dienstes — Befunde; eine Auswahl auf eine Liste, die der Typ nicht trägt — Warnung.
- Befund 3: das Ergebnis einer Freigabe geht in der Simulation wie im Betrieb in den Lauf (ohne
  Schlüssel; alle Einträge gescheitert → ``bei_fehler``).
- Befund 4: eine Auswahl an einem Argument, das einen einzelnen Wert nimmt — Befund.
- Befund 5: die Typen der Module und der Ablage stimmen mit ``typen`` überein.
- Befund 6: ein zu tiefer Verweis schaltet die Vertragsprüfung der Moduldaten nicht ab.
"""

from __future__ import annotations

import asyncio

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services import arbeitsstand_teile
from boerdi.services.ablage import vorgang_teil
from boerdi.services.ablauf import freigabe_ergebnis, simulation, typen, werkzeuge
from boerdi.services.ablauf.pruefung import pruefe, warnungen

_ID = "{:08x}-0000-4000-8000-000000000000"
_ENTWURF = {"titel": "Physik", "quelle": "ki", "knoten": [
    {"id": "mech", "titel": "Mechanik", "kinder": [{"id": "kin", "titel": "Kinematik"}]},
    {"id": "opt", "titel": "Optik"}]}


def _ablauf(*schritte, tests=()):
    return AblaufArea.model_validate({
        "id": "kette", "titel": {"de": "Kette"}, "voraussetzungen": ["anmeldung"],
        "schritte": [*schritte, {"id": "fehler", "typ": "ende"}, {"id": "e", "typ": "ende"}],
        "tests": list(tests)})


_BAUM = {"id": "baum", "typ": "werkzeug", "werkzeug": "baum_aus_entwurf",
         "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "baum", "bei_fehler": "fehler"}
_ANLEGEN = {"id": "anlegen", "typ": "werkzeug", "werkzeug": "wlo_create_collection_tree",
            "argumente": {"parentCollectionId": _ID.format(5), "tree": {"$teil": "baum"}},
            "freigabe": {"de": "Anlegen?"}, "schreibt": "angelegt", "bei_fehler": "fehler"}
_VERBINDEN = {"id": "verbinden", "typ": "werkzeug", "werkzeug": "struktur_mit_nodeids",
              "argumente": {"entwurf": {"$teil": "draft"}, "angelegt": {"$teil": "angelegt"}},
              "schreibt": "draft_mit_ids", "bei_fehler": "fehler", "weiter": "e"}


def _testen(ablauf, test):
    return asyncio.run(simulation.testen(ablauf, AblaufTest.model_validate(test)))


# ── Befund 1 ────────────────────────────────────────────────────────────────

def test_reine_dienste_sind_die_ohne_mcp():
    assert werkzeuge.REINE_DIENSTE == frozenset(werkzeuge.DIENSTE) - set(werkzeuge.DIENST_MCP)
    assert {"baum_aus_entwurf", "struktur_mit_nodeids"} <= werkzeuge.REINE_DIENSTE
    assert "abdeckung_zaehlen" not in werkzeuge.REINE_DIENSTE


def test_die_simulation_rechnet_die_kette_selbst():
    ablauf = _ablauf(_BAUM, _ANLEGEN, _VERBINDEN)
    angelegt = {"complete": True, "nodes": [
        {"path": "Mechanik", "nodeId": _ID.format(1), "status": "created"},
        {"path": "Mechanik/Kinematik", "nodeId": _ID.format(2), "status": "created"},
        {"path": "Optik", "nodeId": _ID.format(3), "status": "created"}]}
    ergebnis = _testen(ablauf, {
        "name": "kette", "teile": {"draft": _ENTWURF},
        "eingaben": [{"bei": "anlegen", "freigabe": "ja", "ergebnis": angelegt}],
        "erwartet": {"weg": ["baum", "anlegen", "verbinden", "e"], "status": "fertig",
                     "teile": ["draft_mit_ids"]}})
    assert ergebnis.ok, ergebnis.abweichungen
    # die Vorschau zeigt, was eingesetzt wurde (Befund 4b): der Baum aus dem Entwurf
    assert any("Mechanik" in t and "Kinematik" in t for t in ergebnis.texte), ergebnis.texte


def test_ein_ergebnis_eines_anderen_baums_geht_zu_bei_fehler():
    ablauf = _ablauf(_BAUM, _ANLEGEN, _VERBINDEN)
    anderer = {"nodes": [{"path": "Chemie", "nodeId": _ID.format(1), "status": "created"}]}
    ergebnis = _testen(ablauf, {
        "name": "fremd", "teile": {"draft": _ENTWURF},
        "eingaben": [{"bei": "anlegen", "freigabe": "ja", "ergebnis": anderer}],
        "erwartet": {"weg": ["baum", "anlegen", "verbinden", "fehler"], "status": "fertig"}})
    assert ergebnis.ok, ergebnis.abweichungen


def test_ein_eintrag_im_testfall_ueberschreibt_den_dienst():
    ablauf = _ablauf({**_BAUM, "weiter": "e"})
    ergebnis = _testen(ablauf, {
        "name": "null", "teile": {"draft": _ENTWURF}, "werkzeuge": {"baum": None},
        "erwartet": {"weg": ["baum", "fehler"], "status": "fertig"}})
    assert ergebnis.ok, ergebnis.abweichungen


# ── Befund 3 ────────────────────────────────────────────────────────────────

def test_alle_gescheitert_geht_in_der_simulation_zu_bei_fehler():
    ablauf = _ablauf(_BAUM, _ANLEGEN, _VERBINDEN)
    gescheitert = {"complete": True, "nodes": [
        {"path": "Mechanik", "status": "failed", "code": "x"},
        {"path": "Optik", "status": "failed", "code": "x"}]}
    ergebnis = _testen(ablauf, {
        "name": "gescheitert", "teile": {"draft": _ENTWURF},
        "eingaben": [{"bei": "anlegen", "freigabe": "ja", "ergebnis": gescheitert}],
        "erwartet": {"weg": ["baum", "anlegen", "fehler"], "status": "fertig"}})
    assert ergebnis.ok, ergebnis.abweichungen


def test_das_ergebnis_einer_freigabe_ohne_schluessel():
    roh = {"nodes": [{"path": "A", "status": "created", "nodeId": _ID.format(1)}],
           "confirm": {"token": "geheim"}, "confirmToken": "geheim"}
    sauber = freigabe_ergebnis.fuer_lauf(roh)
    assert "confirm" not in sauber and "confirmToken" not in sauber
    assert freigabe_ergebnis.fuer_lauf({"items": [{"status": "failed"}]}) is None
    assert freigabe_ergebnis.fuer_lauf({"items": [{"status": "failed"}, {"status": "ok"}]})


# ── Befund 2 ────────────────────────────────────────────────────────────────

_SUCHE = {"id": "suche", "typ": "werkzeug", "werkzeug": "search_wlo_all",
          "argumente": {"query": "Optik"}, "schreibt": "treffer", "bei_fehler": "fehler"}


def _modul_mit(daten):
    return {"id": "zeigen", "typ": "modul", "modul": "ui_strukturentwurf", "daten": daten,
            "bei_fehler": "fehler"}


def test_pfad_oder_auswahl_in_einem_text_teil_ist_ein_befund():
    fuer_auswahl = _ablauf(_SUCHE, {**_ANLEGEN, "argumente": {
        "parentCollectionId": _ID.format(5),
        "tree": {"$teil": "treffer", "liste": "knoten", "feld": "titel"}}})
    assert any("treffer" in b and "Text" in b for b in pruefe(fuer_auswahl))
    fuer_pfad = _ablauf(_SUCHE, {**_ANLEGEN, "argumente": {
        "parentCollectionId": _ID.format(5), "tree": {"$teil": "treffer", "pfad": "knoten"}}})
    assert any("treffer" in b and "Text" in b for b in pruefe(fuer_pfad))
    # der ganze Text-Teil ist kein solcher Befund
    ganz = _ablauf(_SUCHE, {**_ANLEGEN, "argumente": {
        "parentCollectionId": _ID.format(5), "tree": {"$teil": "treffer"}}})
    assert not any("treffer" in b and "Text" in b for b in pruefe(ganz))


def test_auswahl_an_einem_objekt_argument_eines_dienstes_ist_ein_befund():
    auswahl = _ablauf({**_BAUM, "argumente": {
        "entwurf": {"$teil": "draft", "liste": "knoten", "feld": "titel"}}})
    assert any("entwurf" in b and "Auswahl" in b for b in pruefe(auswahl))
    # ``angelegt`` nimmt auch die Liste ``nodes``
    liste = _ablauf({**_VERBINDEN, "argumente": {
        "entwurf": {"$teil": "draft"},
        "angelegt": {"$teil": "angelegt", "liste": "nodes", "wo": {"status": "created"}}}})
    assert not any("angelegt" in b and "Auswahl" in b for b in pruefe(liste))


def test_auswahl_auf_eine_liste_die_der_typ_nicht_traegt_ist_eine_warnung():
    verbinden = {**_VERBINDEN, "weiter": None}
    falsch = _ablauf(_BAUM, _ANLEGEN, verbinden, {
        "id": "a", "typ": "auftrag", "flow": "wlo/volltext", "schreibt": "texte",
        "argumente": {"ids": {"$teil": "angelegt", "liste": "knoten", "feld": "nodeId"}},
        "bei_fehler": "fehler"})
    w = warnungen(falsch)
    assert any("angelegt" in x and "knoten" in x and "nodes" in x for x in w), w
    richtig = _ablauf(_BAUM, _ANLEGEN, verbinden, {
        "id": "a", "typ": "auftrag", "flow": "wlo/volltext", "schreibt": "texte",
        "argumente": {"ids": {"$teil": "angelegt", "liste": "nodes", "feld": "nodeId"}},
        "bei_fehler": "fehler"})
    assert not any("knoten" in x or "nodes" in x for x in warnungen(richtig))


# ── Befund 4 ────────────────────────────────────────────────────────────────

def test_auswahl_an_einem_einzelnen_wert_ist_ein_befund():
    ablauf = _ablauf({**_ANLEGEN, "argumente": {
        "parentCollectionId": {"$teil": "draft", "liste": "knoten", "feld": "wlo_id"},
        "tree": {"$teil": "baum"}}}, _BAUM)
    assert any("parentCollectionId" in b and "einzelnen" in b for b in pruefe(ablauf))


# ── Befund 5 ────────────────────────────────────────────────────────────────

def test_die_typen_der_module_stimmen_mit_typen_ueberein():
    upload = arbeitsstand_teile._teile({"modul": "ui_upload", "daten": {
        "struktur": {"name": "x"}, "zahlen": {}, "aktion": "dokument",
        "dokument": {"name": "a", "befund": {}}}})
    entwurf = arbeitsstand_teile._teile({"modul": "ui_strukturentwurf", "daten": _ENTWURF})
    for name, typ, _w, _z in upload + entwurf:
        assert typen.MODUL_TEILE[name] == typ, name
    assert {n for n, *_ in upload + entwurf} == {"structure", "document", "draft"}
    assert vorgang_teil.TEIL in typen.MODUL_TEILE
    assert typen.MODUL_TEILE[vorgang_teil.TEIL] == vorgang_teil.TYP == typen.ABLAGE


# ── Befund 6 ────────────────────────────────────────────────────────────────

def test_ein_zu_tiefer_verweis_schaltet_die_vertragspruefung_nicht_ab():
    tief = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"$teil": "draft"}}}}}}}}
    befunde = pruefe(_ablauf(_modul_mit({"falsch": 1, **tief})))
    assert any("zu tief" in b or "tiefer" in b for b in befunde), befunde
    assert any("ui_strukturentwurf" in b for b in befunde), befunde
