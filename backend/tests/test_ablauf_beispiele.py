"""Paket AS-8c (Plan 2026-11-09 D7): die Beispiel-Abläufe aus ``seeds/06-ablaeufe`` — das Handbuch
``docs/ablaeufe.md`` verweist auf sie. Jedes Beispiel besteht „Prüfen“, ist aus, bis die Redaktion
es einschaltet, und seine eigenen Testfälle laufen grün."""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import simulation
from boerdi.services.ablauf.pruefung import pruefe

_ORDNER = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"
_BEISPIELE = sorted(_ORDNER.glob("*.yaml"))


def test_die_beispiele_des_handbuchs_liegen_als_seeds_vor():
    namen = {p.stem for p in _BEISPIELE}
    assert {"themenbaum", "sammlung_pruefen", "fuehrung"} <= namen


def test_g1_die_abgeloesten_themenbaum_ablaeufe_sind_nicht_mehr_im_werk():
    """Plan 2026-11-20, G1: „Themenbaum erstellen“ deckt alle Grundlagen ab — die vier alten
    Einzel-Abläufe sind aus den Werks-Seeds entfernt."""
    alt = {"themenbaum_aus_thema", "themenbaum_aus_dokument", "themenbaum_aus_inhalten",
           "sammlungsstruktur"}
    assert not alt & {p.stem for p in _BEISPIELE}


# Plan 2026-11-16, TG-6 (G-E2): „Themenbaum erstellen“ ist ab Werk an (mit dem WLO-Weg,
# Rückmeldung 16.11.)
_AN = {"themenbaum"}


@pytest.mark.parametrize("datei", _BEISPIELE, ids=lambda p: p.stem)
def test_jedes_beispiel_besteht_pruefung_und_eigene_tests(datei):
    ablauf = AblaufArea.model_validate(yaml.safe_load(datei.read_text(encoding="utf-8")))
    assert ablauf.id == datei.stem
    # Nutzer-Entscheid 11.11.: Themenbaum-Abläufe sind im Werkszustand an, alle anderen aus, bis
    # die Redaktion sie einschaltet — seit TG-6 nur noch „Themenbaum erstellen“ (sein Auftrag hat
    # einen Ersatzweg, ein nicht freigeschalteter Flow sperrt den Werksabgleich also nicht)
    assert ablauf.aktiv is (ablauf.id in _AN)
    assert pruefe(ablauf) == []
    ergebnisse = asyncio.run(simulation.alle(ablauf))
    assert all(e.ok for e in ergebnisse), [(e.name, e.abweichungen) for e in ergebnisse]


def test_sammlung_pruefen_ruft_im_ki_schritt_nur_suche_und_abgleich():
    ablauf = AblaufArea.model_validate(yaml.safe_load(
        (_ORDNER / "sammlung_pruefen.yaml").read_text(encoding="utf-8")))
    [ki] = [s for s in ablauf.schritte if s.typ == "agent"]
    # Querschnitts-Review AS-8, Befund 2: einen Namen kann die KI nur mit der Suche auflösen
    assert ki.agent is not None
    assert ki.agent.werkzeuge == ["search_wlo_all", "ui_strukturabgleich"]
    # schreibt nichts in WLO: weder Freigabe- noch Auftragsschritte
    assert not any(s.typ == "auftrag" or s.freigabe for s in ablauf.schritte)


def test_querschnitt_as8_1_ein_ausfall_der_zaehlung_fuehrt_zu_ohne_zahlen():
    """Der Dienst liefert bei einem Ausfall ``gezaehlt: 0`` statt nichts — das Beispiel prüft den
    Wert, und ein eigener Testfall stellt genau das nach."""
    ablauf = AblaufArea.model_validate(yaml.safe_load(
        (_ORDNER / "sammlung_pruefen.yaml").read_text(encoding="utf-8")))
    [fall] = [t for t in ablauf.tests if t.name == "Zählung ohne Ergebnis"]
    assert fall.werkzeuge["luecken"]["gezaehlt"] == 0
    assert fall.erwartet.weg[-1] == "ohne_zahlen"
