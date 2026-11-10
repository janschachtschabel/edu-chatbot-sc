"""Paket AS-3c (Plan 2026-11-09 §5d, D4): die Bedingung ``wenn_wert`` einer Verzweigung.

Eine Regel vergleicht eine Stelle eines Teils (``quelle``: ``teil.<name>[.<pfad>]``) mit einem Wert:
``gleich``, ``enthaelt``, ``vorhanden``, ``leer``, ``groesser``, ``kleiner``. Zahlen vergleicht sie
nur, wenn beide Seiten Zahlen sind — sonst greift die Regel nicht. ``enthaelt`` gilt für Text (Teil
des Texts) und Listen (ein Element). Groß- und Kleinschreibung zählt nicht.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import simulation, treiber
from boerdi.services.ablauf.pruefung import pruefe

#: Die Fassung des Ablaufs aus ``test_ohne_wenn_wert_aendert_sich_die_fassung_nicht`` — vor AS-3c
#: gemessen; bleibt sie gleich, behalten bestehende Abläufe ihre Fassung.
FASSUNG_OHNE_WENN_WERT = "f71787e5f7b2"


def _ablauf(wenn_wert, schreibt="zahlen") -> AblaufArea:
    return AblaufArea.model_validate({"id": "w", "titel": {"de": "W"}, "schritte": [
        {"id": "holen", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "x"}, "schreibt": schreibt, "bei_fehler": "nein"},
        {"id": "wohin", "typ": "verzweigung", "weiter": [
            {"wenn_wert": wenn_wert, "dann": "ja"}, {"sonst": "nein"}]},
        {"id": "ja", "typ": "ende", "text": {"de": "Ja."}},
        {"id": "nein", "typ": "ende", "text": {"de": "Nein."}}]})


def _ende(wenn_wert, wert) -> str:
    ablauf = _ablauf(wenn_wert)

    async def teile(name):
        return wert if name == "zahlen" else None

    async def mcp(_name, _args):
        return wert

    aus = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=teile, mcp=mcp)))
    return aus.lauf["schritt"]


_GR = {"quelle": "teil.zahlen.inhalte", "vergleich": "groesser", "wert": "10"}
_KL = {"quelle": "teil.zahlen.inhalte", "vergleich": "kleiner", "wert": "10"}


@pytest.mark.parametrize(("bedingung", "wert", "ziel"), [
    (_GR, {"inhalte": 12}, "ja"),
    (_GR, {"inhalte": 3}, "nein"),
    (_KL, {"inhalte": "3"}, "ja"),
    (_GR, {"inhalte": "viel"}, "nein"),
    ({"quelle": "teil.zahlen.titel", "vergleich": "gleich", "wert": "optik"}, {"titel": "Optik"},
     "ja"),
    ({"quelle": "teil.zahlen.inhalte", "vergleich": "gleich", "wert": "12"}, {"inhalte": 12.0},
     "ja"),
    ({"quelle": "teil.zahlen.titel", "vergleich": "enthaelt", "wert": "tik"}, {"titel": "Optik"},
     "ja"),
    ({"quelle": "teil.zahlen.faecher", "vergleich": "enthaelt", "wert": "physik"},
     {"faecher": ["Mathe", "Physik"]}, "ja"),
    ({"quelle": "teil.zahlen.faecher", "vergleich": "enthaelt", "wert": "phy"},
     {"faecher": ["Mathe", "Physik"]}, "nein"),
    ({"quelle": "teil.zahlen.titel", "vergleich": "vorhanden"}, {"titel": "x"}, "ja"),
    ({"quelle": "teil.zahlen.titel", "vergleich": "vorhanden"}, {"titel": ""}, "nein"),
    ({"quelle": "teil.zahlen.titel", "vergleich": "leer"}, {"titel": []}, "ja"),
    ({"quelle": "teil.zahlen.gibtsnicht", "vergleich": "leer"}, {"titel": "x"}, "ja"),
    ({"quelle": "teil.zahlen", "vergleich": "vorhanden"}, {"x": 1}, "ja"),
    ({"quelle": "teil.zahlen.ok", "vergleich": "gleich", "wert": "ja"}, {"ok": True}, "ja"),
    # Review AS-3c, Befund 7
    ({"quelle": "teil.zahlen.ok", "vergleich": "gleich", "wert": "true"}, {"ok": True}, "ja"),
    ({"quelle": "teil.zahlen.x", "vergleich": "gleich", "wert": "1,5"}, {"x": 1.5}, "ja"),
    ({"quelle": "teil.zahlen", "vergleich": "enthaelt", "wert": "titel"}, {"titel": "x"}, "ja"),
    ({"quelle": "teil.zahlen.fehlt", "vergleich": "gleich", "wert": "x"}, {"titel": "x"}, "nein"),
    # Befund 2: zwei Texte bleiben Texte, große Zahlen exakt
    ({"quelle": "teil.zahlen.plz", "vergleich": "gleich", "wert": "1067"}, {"plz": "01067"},
     "nein"),
    ({"quelle": "teil.zahlen.n", "vergleich": "gleich", "wert": "12345678901234568"},
     {"n": 12345678901234567}, "nein"),
    ({"quelle": "teil.zahlen.n", "vergleich": "groesser", "wert": "10"}, {"n": 10 ** 400}, "ja"),
    # Befund 1: nan/inf sind keine Zahlen
    ({"quelle": "teil.zahlen.x", "vergleich": "groesser", "wert": "10"}, {"x": "inf"}, "nein"),
    ({"quelle": "teil.zahlen.x", "vergleich": "gleich", "wert": "nan"}, {"x": "NaN"}, "ja"),
    # Befund 9: Listen-Elemente wie gleich
    ({"quelle": "teil.zahlen.l", "vergleich": "enthaelt", "wert": "1.0"}, {"l": [1, 2]}, "ja"),
])
def test_die_regel_vergleicht(bedingung, wert, ziel):
    assert _ende(bedingung, wert) == ziel


def test_eine_gueltige_regel_hat_keine_befunde():
    assert pruefe(_ablauf({"quelle": "teil.zahlen.inhalte", "vergleich": "groesser",
                           "wert": "10"})) == []


@pytest.mark.parametrize(("bedingung", "erwartet"), [
    ({"quelle": "zahlen.inhalte", "vergleich": "gleich", "wert": "1"}, "Quelle"),
    ({"quelle": "teil.Böse", "vergleich": "gleich", "wert": "1"}, "Quelle"),
    ({"quelle": "teil.gibtsnicht", "vergleich": "vorhanden"}, "gibtsnicht"),
    ({"quelle": "teil.zahlen", "vergleich": "gleich"}, "Wert"),
    ({"quelle": "teil.zahlen", "vergleich": "groesser", "wert": "viel"}, "Zahl"),
    ({"quelle": "teil.zahlen", "vergleich": "leer", "wert": "x"}, "ohne Wert"),
    ({"quelle": "teil.zahlen", "vergleich": "groesser", "wert": "nan"}, "Zahl"),
    ({"quelle": "teil.zahlen", "vergleich": "kleiner", "wert": "1e3"}, "Zahl"),
])
def test_befunde_an_wenn_wert(bedingung, erwartet):
    befunde = pruefe(_ablauf(bedingung))
    assert any(erwartet in b for b in befunde), befunde


def test_ein_teil_der_erst_nach_der_verzweigung_entsteht_ist_ein_befund():
    ablauf = AblaufArea.model_validate({"id": "w", "titel": {"de": "W"}, "schritte": [
        {"id": "wohin", "typ": "verzweigung", "weiter": [
            {"wenn_wert": {"quelle": "teil.spaeter", "vergleich": "vorhanden"}, "dann": "holen"},
            {"sonst": "holen"}]},
        {"id": "holen", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "x"}, "schreibt": "spaeter"},
        {"id": "e", "typ": "ende"}]})
    assert any("erst nach diesem Schritt" in b for b in pruefe(ablauf))


def test_ein_unbekannter_vergleich_ist_ein_modellfehler():
    with pytest.raises(ValueError):
        _ablauf({"quelle": "teil.zahlen", "vergleich": "ungefaehr", "wert": "1"})


def test_eine_regel_mit_zwei_bedingungen_ist_ein_befund():
    ablauf = AblaufArea.model_validate({"id": "w", "titel": {"de": "W"}, "schritte": [
        {"id": "wohin", "typ": "verzweigung", "weiter": [
            {"wenn_wert": {"quelle": "teil.zahlen", "vergleich": "vorhanden"},
             "wenn_teil": "zahlen", "dann": "e"}, {"sonst": "e"}]},
        {"id": "e", "typ": "ende"}]})
    assert pruefe(ablauf)


def test_ohne_wenn_wert_aendert_sich_die_fassung_nicht():
    """Vorgabe ``None``: eine Regel ohne ``wenn_wert`` trägt das Feld nicht im Dump der Fassung."""
    ablauf = AblaufArea.model_validate({"id": "a", "titel": {"de": "A"}, "schritte": [
        {"id": "v", "typ": "verzweigung", "weiter": [{"wenn_teil": "x", "dann": "e"},
                                                     {"sonst": "e"}]},
        {"id": "e", "typ": "ende"}]})
    assert "wenn_wert" not in str(ablauf.schritte[0].model_dump(mode="json", exclude_none=True))
    # fester Wert: ändert sich die Fassung bestehender Abläufe, bräche jeder wartende Lauf ab
    assert treiber.fassung(ablauf) == FASSUNG_OHNE_WENN_WERT


def test_die_simulation_verzweigt_ueber_die_ergebnisse_des_testfalls():
    """Ein lesendes MCP-Werkzeug liefert Text (wie im Betrieb) — ``enthaelt`` greift darin, ein
    Pfad in den Text nicht."""
    ablauf = _ablauf({"quelle": "teil.zahlen", "vergleich": "enthaelt", "wert": "optik"})
    test = simulation.AblaufTest.model_validate({
        "name": "t", "werkzeuge": {"holen": {"titel": "Optik"}}, "erwartet": {"ende": "ja"}})
    e = asyncio.run(simulation.testen(ablauf, test))
    assert e.ok, e.abweichungen
