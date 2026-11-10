"""Paket A1: Ablauf-Definitionen — Modell und Prüfung beim Speichern.

Ein Ablauf (Studio-Bereich ``06-ablaeufe/<id>``) besteht aus Schritten fester Arten. Die Prüfung
weist ab, was der lokale Treiber nicht sicher ausführen kann: doppelte oder fehlende Ziele, kein
erreichbares Ende, unbekannte Module oder Werkzeuge, schreibende Werkzeuge, falsche Teilnamen.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf.pruefung import pruefe


def _ablauf(**mehr):
    roh = {
        "id": "sammlungsstruktur", "titel": {"de": "Themenbaum aus Ordnern"},
        "beschreibung": "Ordner erfassen und daraus einen Entwurf bauen.",
        "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "start", "typ": "nachricht", "text": {"de": "Los geht's."}},
            {"id": "erfassen", "typ": "modul", "modul": "ui_upload",
             "daten": {"zweck": "sammlungsstruktur"}},
            {"id": "gabel", "typ": "verzweigung",
             "weiter": [{"wenn_teil": "document", "dann": "ende"}, {"sonst": "entwurf"}]},
            {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
             "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "draft"},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}},
        ],
    }
    roh.update(mehr)
    return AblaufArea.model_validate(roh)


def test_ein_gueltiger_ablauf_hat_keine_befunde():
    assert pruefe(_ablauf()) == []


def test_unbekannte_schrittart_ist_ein_schemafehler():
    with pytest.raises(ValidationError):
        _ablauf(schritte=[{"id": "x", "typ": "zaubern"}])


@pytest.mark.parametrize(("schritte", "erwartet"), [
    ([{"id": "a", "typ": "nachricht", "text": {"de": "x"}},
      {"id": "a", "typ": "ende"}], "doppelt"),
    ([{"id": "a", "typ": "nachricht", "text": {"de": "x"}, "weiter": "fehlt"},
      {"id": "e", "typ": "ende"}], "Ziel"),
    ([{"id": "a", "typ": "nachricht", "text": {"de": "x"}}], "Ende"),
    ([{"id": "a", "typ": "modul", "modul": "ui_gibtesnicht"}, {"id": "e", "typ": "ende"}],
     "Modul"),
    ([{"id": "a", "typ": "werkzeug", "werkzeug": "wlo_create_collection"},
      {"id": "e", "typ": "ende"}], "schreibend"),
    ([{"id": "a", "typ": "werkzeug", "werkzeug": "gibt_es_nicht"}, {"id": "e", "typ": "ende"}],
     "Werkzeug"),
    ([{"id": "a", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
       "schreibt": "Böse Name"}, {"id": "e", "typ": "ende"}], "Teil"),
    ([{"id": "a", "typ": "modul", "modul": "ui_upload", "daten": {"x": {"$teil": "../x"}}},
      {"id": "e", "typ": "ende"}], "Teil"),
    ([{"id": "a", "typ": "nachricht"}, {"id": "e", "typ": "ende"}], "Text"),
    ([{"id": "a", "typ": "verzweigung", "weiter": [{"wenn_teil": "draft", "dann": "e"}]},
      {"id": "e", "typ": "ende"}], "sonst"),
])
def test_befunde(schritte, erwartet):
    befunde = pruefe(_ablauf(schritte=schritte))
    assert any(erwartet in b for b in befunde), befunde


def test_eine_schleife_ohne_wartenden_schritt_wird_abgewiesen():
    befunde = pruefe(_ablauf(schritte=[
        {"id": "a", "typ": "nachricht", "text": {"de": "x"}, "weiter": "b"},
        {"id": "b", "typ": "nachricht", "text": {"de": "y"}, "weiter": "a"},
        {"id": "e", "typ": "ende"}]))
    assert any("Schleife" in b for b in befunde)


def test_auslöser_modul_braucht_ein_modul():
    befunde = pruefe(_ablauf(ausloeser=[{"art": "modul"}]))
    assert any("Auslöser" in b for b in befunde)


def test_das_studio_weist_einen_nicht_ausfuehrbaren_ablauf_beim_speichern_ab():
    from fastapi import HTTPException

    from boerdi.api.config_guards import _assert_area_document_safe

    # seit AS-0 ein Dokument je Ablauf (``06-ablaeufe/<id>``)
    gut = _ablauf().model_dump()
    _assert_area_document_safe(f"06-ablaeufe/{gut['id']}", gut, "de")
    schlecht = _ablauf(schritte=[
        {"id": "a", "typ": "werkzeug", "werkzeug": "wlo_create_collection"},
        {"id": "e", "typ": "ende"}]).model_dump()
    with pytest.raises(HTTPException) as fehler:
        _assert_area_document_safe(f"06-ablaeufe/{schlecht['id']}", schlecht, "de")
    assert fehler.value.status_code == 400 and "schreibend" in fehler.value.detail


def test_null_oder_zu_viele_schritte():
    assert any("Schritte" in b for b in pruefe(_ablauf(schritte=[])))
    viele = [{"id": f"s{i}", "typ": "nachricht", "text": {"de": "x"}} for i in range(41)]
    assert any("Schritte" in b for b in pruefe(_ablauf(schritte=viele)))


# ── Review A1, Befund 3/8/9/12: was der Treiber anders ausführen würde, als es dasteht ──────────

_E = {"id": "e", "typ": "ende"}


@pytest.mark.parametrize(("schritte", "erwartet"), [
    # Verzweigung ohne Regeln / Regeln an einem anderen Schritt
    ([{"id": "a", "typ": "verzweigung", "weiter": "e"}, _E], "braucht Regeln"),
    ([{"id": "a", "typ": "nachricht", "text": {"de": "x"},
       "weiter": [{"wenn_teil": "draft", "dann": "e"}, {"sonst": "e"}]}, _E], "nur bei einer"),
    # Bedingung ohne dann; sonst nicht zuletzt
    ([{"id": "a", "typ": "verzweigung", "weiter": [{"wenn_teil": "draft"}, {"sonst": "e"}]}, _E],
     "Bedingung und dann"),
    ([{"id": "a", "typ": "verzweigung",
       "weiter": [{"sonst": "e"}, {"wenn_teil": "draft", "dann": "e"}]}, _E], "letzte Regel"),
    # ein Weg läuft ohne ende aus; ein Schritt ist nicht erreichbar
    ([{"id": "a", "typ": "nachricht", "text": {"de": "x"}, "weiter": "b"}, _E,
      {"id": "b", "typ": "nachricht", "text": {"de": "y"}}], "ohne Ende aus"),
    ([{"id": "a", "typ": "nachricht", "text": {"de": "x"}, "weiter": "e"},
      {"id": "b", "typ": "nachricht", "text": {"de": "y"}}, _E], "nicht erreichbar"),
    # lesende WLO-Werkzeuge bekommen keine Teile (Befund 9)
    ([{"id": "a", "typ": "werkzeug", "werkzeug": "search_wlo_all",
       "argumente": {"query": {"$teil": "document"}}}, _E], "keine Teile"),
    # feste Daten, die nicht zum Vertrag passen (Befund 4)
    ([{"id": "a", "typ": "modul", "modul": "ui_entscheidung", "daten": {"falsch": 1}}, _E],
     "passen nicht"),
])
def test_befunde_aus_dem_review(schritte, erwartet):
    befunde = pruefe(_ablauf(schritte=schritte))
    assert any(erwartet in b for b in befunde), befunde


def test_mehr_schritte_ohne_halt_als_der_treiber_je_zug_rechnet():
    from boerdi.services.ablauf.pruefung import RECHENSCHRITTE

    kette = [{"id": f"s{i}", "typ": "nachricht", "text": {"de": "x"}}
             for i in range(RECHENSCHRITTE)] + [_E]
    assert any("ohne Halt" in b for b in pruefe(_ablauf(schritte=kette)))
    assert pruefe(_ablauf(schritte=kette[1:])) == []


def test_ein_halt_teilt_die_kette():
    from boerdi.services.ablauf.pruefung import RECHENSCHRITTE

    halb = [{"id": f"s{i}", "typ": "nachricht", "text": {"de": "x"}} for i in range(15)]
    frage = {"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": {
        "frage": "Weiter?", "optionen": [{"id": "ja", "label": "Ja"},
                                         {"id": "nein", "label": "Nein"}]}}
    rest = [{"id": f"t{i}", "typ": "nachricht", "text": {"de": "x"}} for i in range(14)]
    assert len(halb) + len(rest) > RECHENSCHRITTE
    assert pruefe(_ablauf(schritte=[*halb, frage, *rest, _E])) == []


def test_unbekannte_voraussetzung_und_modus_werden_abgewiesen():
    befunde = pruefe(_ablauf(voraussetzungen=["login"], ausloeser=[{"art": "knopf",
                                                                    "modus": "direkt"}]))
    assert any("Voraussetzung 'login'" in b for b in befunde)
    # TB-E3: ``direkt`` gibt es seitdem, aber nur am Auslöser ``agent`` (Review TB-E3, Befund 8)
    assert any("nur am Auslöser agent" in b for b in befunde)
    unbekannt = pruefe(_ablauf(ausloeser=[{"art": "agent", "modus": "sofort"}]))
    assert any("Modus 'sofort'" in b for b in unbekannt)


def test_befunde_in_der_sprache_des_studios():
    befunde = pruefe(_ablauf(schritte=[{"id": "a", "typ": "nachricht"}, _E]), "en")
    assert befunde == ["Step a: text (de) missing"]
