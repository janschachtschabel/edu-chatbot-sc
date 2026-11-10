"""Paket AS-3a (Plan 2026-11-09 §5d, D2): Schnellantworten mit Ziel und Freitext.

Ein ``nachricht``- oder ``modul``-Schritt kann ``optionen`` tragen (Chips mit Label und Ziel) und
``freitext`` (getippter Text wird ein Teil, dann geht es zum Ziel). Mit beiden wartet der
Schritt (``wartet_wahl``); die Wahl verzweigt direkt, ohne eigenen ``verzweigung``-Schritt. Neue
Felder haben die Vorgabe ``None`` — die Fassung eines Ablaufs ohne sie bleibt gleich.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import simulation, treiber
from boerdi.services.ablauf.pruefung import nachfolger, pruefe

_FRAGE = {"id": "frage", "typ": "nachricht", "text": {"de": "Wie weiter?", "en": "How?"},
          "optionen": [{"id": "neu", "label": {"de": "Neu anlegen", "en": "Create"}, "ziel": "neu"},
                       {"id": "alt", "label": {"de": "Bestehende"}, "ziel": "alt"}],
          "freitext": {"ziel": "notiz", "schreibt": "wunsch"}}


def _ablauf(frage=None, **mehr) -> AblaufArea:
    return AblaufArea.model_validate({"id": "wahl", "titel": {"de": "Wahl"}, "schritte": [
        frage or _FRAGE,
        {"id": "neu", "typ": "ende", "text": {"de": "Neu."}},
        {"id": "alt", "typ": "ende", "text": {"de": "Alt."}},
        {"id": "notiz", "typ": "ende", "text": {"de": "Notiert."}},
    ], **mehr})


def _umgebung(teile=None):
    teile = dict(teile or {})

    async def lader(name):
        return teile.get(name)

    return treiber.Umgebung(teile=lader)


# ── Modell und Prüfung ─────────────────────────────────────────────────────

def test_ein_schritt_mit_optionen_und_freitext_ist_gueltig():
    assert pruefe(_ablauf()) == []
    assert nachfolger(_ablauf(), 0) == ["neu", "alt", "notiz"]


def test_ohne_die_neuen_felder_bleibt_die_fassung_gleich():
    """Vorgabe ``None``: ein Ablauf ohne Optionen hat dieselbe Fassung wie vor AS-3a."""
    roh = {"id": "a", "titel": {"de": "A"}, "schritte": [
        {"id": "x", "typ": "nachricht", "text": {"de": "x"}}, {"id": "e", "typ": "ende"}]}
    ablauf = AblaufArea.model_validate(roh)
    dump = ablauf.schritte[0].model_dump(mode="json", exclude_none=True)
    assert "optionen" not in dump and "freitext" not in dump
    # das Studio speichert eine leere Liste — sie zählt wie nicht gesetzt
    leer = AblaufArea.model_validate({**roh, "schritte": [
        {**roh["schritte"][0], "optionen": []}, roh["schritte"][1]]})
    assert treiber.fassung(leer) == treiber.fassung(ablauf)


@pytest.mark.parametrize(("aenderung", "erwartet"), [
    ({"optionen": [{"id": "a", "label": {"de": "A"}, "ziel": "gibtsnicht"}]}, "gibtsnicht"),
    ({"optionen": [{"id": "a", "label": {"de": "A"}, "ziel": "neu"},
                   {"id": "a", "label": {"de": "B"}, "ziel": "alt"}]}, "doppelt"),
    ({"optionen": [{"id": "a", "label": {"en": "A"}, "ziel": "neu"}]}, "Beschriftung"),
    ({"optionen": [{"id": f"o{i}", "label": {"de": "x"}, "ziel": "neu"} for i in range(9)]},
     "höchstens 8"),
    ({"freitext": {"ziel": "neu", "schreibt": "Böse"}}, "Teil"),
    ({"weiter": "neu"}, "weiter"),
])
def test_befunde_an_den_schnellantworten(aenderung, erwartet):
    befunde = pruefe(_ablauf({**_FRAGE, **aenderung}))
    assert any(erwartet in b for b in befunde), befunde


def test_ein_abfragendes_modul_traegt_keine_schnellantworten():
    frage = {"id": "frage", "typ": "modul", "modul": "ui_entscheidung",
             "daten": {"frage": "?", "optionen": [{"id": "a", "label": "A"}]},
             "optionen": [{"id": "x", "label": {"de": "X"}, "ziel": "neu"}]}
    assert any("abfragend" in b for b in pruefe(_ablauf(frage)))


def test_schnellantworten_gibt_es_nur_an_nachricht_und_modul():
    frage = {"id": "frage", "typ": "werkzeug", "werkzeug": "search_wlo_all",
             "argumente": {"query": "x"},
             "optionen": [{"id": "x", "label": {"de": "X"}, "ziel": "neu"}]}
    assert any("nur an nachricht und modul" in b for b in pruefe(_ablauf(frage)))


def test_ein_wartender_wahl_schritt_haelt_eine_schleife_an():
    frage = {**_FRAGE, "optionen": [{"id": "nochmal", "label": {"de": "Nochmal"}, "ziel": "frage"},
                                    {"id": "fertig", "label": {"de": "Fertig"}, "ziel": "neu"}],
             "freitext": None}
    schritte = _ablauf(frage)
    assert not any("Schleife" in b for b in pruefe(schritte))


# ── Treiber ────────────────────────────────────────────────────────────────

def test_der_treiber_haelt_und_bietet_die_wahl_an():
    aus = asyncio.run(treiber.starten(_ablauf(), _umgebung()))
    assert aus.texte == ["Wie weiter?"]
    assert aus.lauf["status"] == treiber.WARTET_WAHL and aus.lauf["schritt"] == "frage"
    assert aus.wahl == {"schritt": "frage", "freitext": True,
                        "optionen": [("neu", "Neu anlegen"), ("alt", "Bestehende")]}
    en = asyncio.run(treiber.starten(_ablauf(), treiber.Umgebung(teile=_umgebung().teile,
                                                                 sprache="en")))
    # ohne englisches Label gilt das deutsche
    assert en.wahl["optionen"] == [("neu", "Create"), ("alt", "Bestehende")]


def test_eine_wahl_verzweigt_direkt():
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_wahl(_ablauf(), dict(lauf), "alt", None, _umgebung()))
    assert aus.texte == ["Alt."] and aus.lauf["status"] == "fertig"
    assert aus.lauf["gewaehlt"] == ["alt"]


def test_freitext_wird_ein_teil_und_geht_zum_ziel():
    frage = {**_FRAGE, "freitext": {"ziel": "notiz", "schreibt": "wunsch"}}
    ablauf = AblaufArea.model_validate({"id": "wahl", "titel": {"de": "W"}, "schritte": [
        frage, {"id": "neu", "typ": "ende"}, {"id": "alt", "typ": "ende"},
        {"id": "notiz", "typ": "modul", "modul": "ui_entscheidung",
         "daten": {"frage": {"$teil": "wunsch"}, "optionen": [{"id": "ok", "label": "OK"},
                                                              {"id": "nein", "label": "Nein"}]}},
        {"id": "e", "typ": "ende"}]})
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), None, "  Physik, Klasse 7 ",
                                          _umgebung()))
    assert [t[:3] for t in aus.neue_teile] == [("wunsch", "text", "Physik, Klasse 7")]
    # der Teil gilt schon im selben Zug: das Modul danach liest ihn
    assert aus.bloecke and aus.bloecke[0].daten["frage"] == "Physik, Klasse 7"


@pytest.mark.parametrize(("wahl", "text"), [("gibtsnicht", None), (None, None), (None, "   ")])
def test_was_der_schritt_nicht_anbietet_setzt_nicht_fort(wahl, text):
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    assert asyncio.run(treiber.weiter_wahl(_ablauf(), dict(lauf), wahl, text, _umgebung())) is None


def test_ohne_freitext_setzt_getippter_text_nicht_fort():
    ablauf = _ablauf({**_FRAGE, "freitext": None})
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    assert asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), None, "x", _umgebung())) is None


def test_eine_alte_fassung_setzt_nicht_fort():
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    anders = _ablauf({**_FRAGE, "text": {"de": "Anders?"}})
    assert asyncio.run(treiber.weiter_wahl(anders, dict(lauf), "neu", None, _umgebung())) is None


def test_ein_anzeigendes_modul_mit_schnellantworten():
    frage = {"id": "frage", "typ": "modul", "modul": "ui_linkbox",
             "daten": {"links": [{"url": "https://example.org", "titel": "E"}]},
             "optionen": [{"id": "ok", "label": {"de": "Gelesen"}, "ziel": "neu"}],
             "bei_fehler": "alt"}
    ablauf = _ablauf(frage)
    aus = asyncio.run(treiber.starten(ablauf, _umgebung()))
    assert aus.lauf["status"] == treiber.WARTET_WAHL
    assert [b.modul for b in aus.bloecke] == ["ui_linkbox"]


def test_freitext_vergisst_eine_fruehere_wahl():
    """Review AS-3a, Befund 6: eine Verzweigung nach dem Freitext sieht keine alte Wahl."""
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    lauf["gewaehlt"] = ["alt"]
    aus = asyncio.run(treiber.weiter_wahl(_ablauf(), dict(lauf), None, "Optik", _umgebung()))
    assert aus.lauf["gewaehlt"] == []
    # die Kennzeile des Teils trägt nicht den Inhalt, aber seinen Namen (Browser-Abnahme AS-U,
    # L-1: „Text“ allein sagte der Person in „Gesammelte Daten“ nichts)
    assert aus.neue_teile[0][3] == "Text: wunsch"
    assert "Optik" not in aus.neue_teile[0][3]


def test_ein_label_nur_aus_leerraum_gilt_nicht():
    frage = {**_FRAGE, "optionen": [{"id": "neu", "label": {"de": "Neu", "en": "  "},
                                     "ziel": "neu"}]}
    aus = asyncio.run(treiber.starten(_ablauf(frage), treiber.Umgebung(
        teile=_umgebung().teile, sprache="en")))
    assert aus.wahl["optionen"] == [("neu", "Neu")]


# ── Simulation ─────────────────────────────────────────────────────────────

def _test(**roh) -> AblaufTest:
    return AblaufTest.model_validate({"name": "t", **roh})


def test_die_simulation_waehlt_und_tippt():
    gewaehlt = asyncio.run(simulation.testen(_ablauf(), _test(
        eingaben=[{"bei": "frage", "option": "neu"}],
        erwartet={"ende": "neu", "status": "fertig"})))
    assert gewaehlt.ok, gewaehlt.abweichungen
    getippt = asyncio.run(simulation.testen(_ablauf(), _test(
        eingaben=[{"bei": "frage", "text": "Optik"}], erwartet={"ende": "notiz",
                                                               "teile": ["wunsch"]})))
    assert getippt.ok, getippt.abweichungen


def test_eine_wahl_die_der_schritt_nicht_anbietet_ist_eine_abweichung():
    e = asyncio.run(simulation.testen(_ablauf(), _test(eingaben=[{"bei": "frage", "option": "x"}])))
    assert not e.ok and any("bietet" in a for a in e.abweichungen), e.abweichungen


def test_ohne_eingabe_wartet_der_testfall_auf_die_wahl():
    e = asyncio.run(simulation.testen(_ablauf(), _test(erwartet={"status": "wartet_wahl"})))
    assert e.ok, e.abweichungen


# ── Querschnitts-Review AS-3 ───────────────────────────────────────────────

def test_die_simulation_erkennt_ein_getipptes_label_wie_der_betrieb():
    """Befund 2: „bestehende“ ist die Wahl „alt“ — auch an einem Schritt mit Freitext."""
    e = asyncio.run(simulation.testen(_ablauf(), _test(
        eingaben=[{"bei": "frage", "text": " Bestehende "}], erwartet={"ende": "alt"})))
    assert e.ok, e.abweichungen
    ohne = _ablauf({**_FRAGE, "freitext": None})
    e = asyncio.run(simulation.testen(ohne, _test(
        eingaben=[{"bei": "frage", "text": "neu anlegen"}], erwartet={"ende": "neu"})))
    assert e.ok, e.abweichungen


def test_eine_wahl_leert_einen_frueheren_freitext():
    """Befund 3: nach „Passt so“ gilt der Text aus dem vorigen Durchgang nicht mehr."""
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_wahl(_ablauf(), dict(lauf), "alt", None,
                                          _umgebung({"wunsch": "alter Text"})))
    assert ("wunsch", "text", "", "—") in aus.neue_teile
    # ohne früheren Freitext entsteht kein leerer Teil
    aus = asyncio.run(treiber.weiter_wahl(_ablauf(), dict(lauf), "alt", None, _umgebung()))
    assert aus.neue_teile == []


def test_gleiche_labels_sind_ein_befund():
    """Befund 7: getippter Text träfe sonst immer die erste."""
    frage = {**_FRAGE, "optionen": [{"id": "a", "label": {"de": "Ja"}, "ziel": "neu"},
                                    {"id": "b", "label": {"de": " ja "}, "ziel": "alt"}]}
    assert any("gleich beschriftet" in b for b in pruefe(_ablauf(frage)))
