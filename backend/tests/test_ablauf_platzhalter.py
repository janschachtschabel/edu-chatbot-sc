"""Paket AS-3b (Plan 2026-11-09 §5d, D3): Platzhalter in den Texten eines Ablaufs.

``{teil.<name>}`` und ``{teil.<name>.<pfad>}`` in ``text`` und ``freigabe`` werden beim Ausgeben
aus den Teilen des Laufs gefüllt — als Text, gekürzt, ohne Markdown-Wirkung; ein fehlender Wert
wird „—“.
``{start.<feld>}`` liest seit AS-4a die Startdaten (``test_ablauf_startdaten``).
Die Prüfung meldet kaputte Platzhalter, unbekannte Teile
und Platzhalter in Beschriftungen von Schnellantworten (dort wirken sie nicht).
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import platzhalter, treiber
from boerdi.services.ablauf.pruefung import pruefe


def _teile(werte):
    async def lader(name):
        return werte.get(name)

    return lader


def _einsetzen(text, werte):
    return asyncio.run(platzhalter.einsetzen(text, _teile(werte)))


def test_werte_werden_eingesetzt_auch_mit_pfad():
    werte = {"sammlung": {"titel": "Optik", "zahlen": {"inhalte": 12}}, "wunsch": "Klasse 7"}
    assert _einsetzen("Für {teil.sammlung.titel} ({teil.sammlung.zahlen.inhalte}): {teil.wunsch}",
                      werte) == "Für Optik (12): Klasse 7"


def test_ein_fehlender_wert_wird_ein_strich():
    assert _einsetzen("A {teil.gibtsnicht} B {teil.wunsch.x}", {"wunsch": "x"}) == "A — B —"


def test_werte_haben_keine_markdown_wirkung_und_sind_gekuerzt():
    text = _einsetzen("{teil.boese}", {"boese": "[klick](https://x.y) **fett**\n# Titel"})
    assert "[" not in text.replace("\\[", "") and "\n" not in text
    assert text.startswith("\\[klick\\]")
    lang = _einsetzen("{teil.lang}", {"lang": "x" * 500})
    assert len(lang) == platzhalter.MAX_ZEICHEN and lang.endswith("…")


def test_ein_objekt_mit_titel_zeigt_den_titel_sonst_kompaktes_json():
    assert _einsetzen("{teil.sa}", {"sa": {"titel": "Optik", "x": 1}}) == "Optik"
    assert _einsetzen("{teil.nn}", {"nn": [1, 2]}) == "\\[1\\,2\\]"


def test_text_ohne_platzhalter_und_fremde_klammern_bleiben():
    assert _einsetzen("{nicht} {teil} {start.x}", {}) == "{nicht} {teil} {start.x}"


# ── Prüfung ────────────────────────────────────────────────────────────────

def _ablauf(*schritte) -> AblaufArea:
    return AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        *schritte, {"id": "ende", "typ": "ende", "text": {"de": "Fertig {teil.zahl}."}}]})


_ZAHL = {"id": "zaehlen", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "x"}, "schreibt": "zahl", "weiter": "ende"}


def test_bekannte_platzhalter_sind_gueltig():
    assert pruefe(_ablauf(_ZAHL)) == []


@pytest.mark.parametrize(("text", "erwartet"), [
    ("{teil.gibtsnicht}", "gibtsnicht"),
    ("{teil.Böse}", "Platzhalter"),
    ("{teil.zahl..x}", "Platzhalter"),
    ("{start.sammlung}", "start"),
])
def test_befunde_an_platzhaltern(text, erwartet):
    schritt = {"id": "a", "typ": "nachricht", "text": {"de": "x", "en": text}, "weiter": "zaehlen"}
    befunde = pruefe(_ablauf(schritt, _ZAHL))
    assert any(erwartet in b for b in befunde), befunde


def test_teile_aus_modul_antworten_und_freitext_sind_bekannt():
    frage = {"id": "frage", "typ": "nachricht", "text": {"de": "Wunsch?"},
             "freitext": {"ziel": "zeigen", "schreibt": "wunsch"}}
    zeigen = {"id": "zeigen", "typ": "nachricht",
              "text": {"de": "Du willst {teil.wunsch}, Baum {teil.structure.zahlen.ordner}."},
              "weiter": "ende"}
    upload = {"id": "upload", "typ": "modul", "modul": "ui_upload", "daten": {},
              "weiter": "frage", "bei_fehler": "ende"}
    befunde = pruefe(AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        upload, frage, zeigen, {"id": "ende", "typ": "ende"}]}))
    assert not any("Platzhalter" in b or "Teil" in b for b in befunde), befunde


def test_in_beschriftungen_wirken_platzhalter_nicht():
    frage = {"id": "frage", "typ": "nachricht", "text": {"de": "?"},
             "optionen": [{"id": "a", "label": {"de": "Für {teil.zahl}"}, "ziel": "ende"}]}
    assert any("Beschriftung" in b for b in pruefe(_ablauf(_ZAHL | {"weiter": "frage"}, frage)))


# ── Treiber ────────────────────────────────────────────────────────────────

def test_der_treiber_setzt_ein_auch_teile_aus_demselben_zug():
    ablauf = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        {"id": "a", "typ": "nachricht", "text": {"de": "Hallo {teil.name}!"}},
        {"id": "ende", "typ": "ende", "text": {"de": "Tschüss {teil.name}."}}]})
    aus = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=_teile({"name": "Kim"}))))
    assert aus.texte == ["Hallo Kim!", "Tschüss Kim."]



# ── Review AS-3b ───────────────────────────────────────────────────────────

def test_nackte_adressen_und_icons_werden_keine_links():
    """Befund 1: GFM machte aus einer nackten Adresse einen Link — jedes Satzzeichen ist escapt."""
    text = _einsetzen("{teil.boese}", {"boese": "https://phish.example/login www.x.de a@b.de"})
    assert "https://" not in text and "www.x" not in text and "a@b" not in text
    assert text.startswith("https\\:\\/\\/")
    assert "@@" not in _einsetzen("{teil.ic}", {"ic": "@@ICON:book@@"})
    # ``$`` bleibt (stripLatex)
    assert _einsetzen("{teil.preis}", {"preis": "5 $"}) == "5 $"


def test_steuer_und_bidi_zeichen_fallen_weg():
    text = _einsetzen("{teil.boese}", {"boese": "a\u202eb\u200bc\x00d"})
    assert text == "abcd"


def test_ein_punkt_ohne_pfad_ist_keine_gueltige_form():
    """Befund 7: ``{teil.x.}`` setzte sonst den ganzen Teil ein."""
    assert _einsetzen("{teil.zahl.}", {"zahl": {"a": 1}}) == "{teil.zahl.}"
    schritt = {"id": "a", "typ": "nachricht", "text": {"de": "{teil.zahl.}"}, "weiter": "ende"}
    assert any("Platzhalter" in b for b in pruefe(_ablauf(_ZAHL | {"weiter": "a"}, schritt)))


@pytest.mark.parametrize("text", ["{Teil.zahl}", "{teil.zahl wert}", "{ teil.zahl}"])
def test_fast_richtige_platzhalter_sind_ein_befund(text):
    """Befund 8: was wie ein Platzhalter aussieht, aber nie eingesetzt wird."""
    schritt = {"id": "a", "typ": "nachricht", "text": {"de": text}, "weiter": "ende"}
    befunde = pruefe(_ablauf(_ZAHL | {"weiter": "a"}, schritt))
    assert any("gültige Form" in b for b in befunde), befunde


def test_ein_teil_der_erst_spaeter_entsteht_ist_ein_befund():
    """Befund 3: „den kein Schritt davor schreibt“ — sonst stünde „—“ oder ein alter Wert da."""
    vorher = {"id": "a", "typ": "nachricht", "text": {"de": "Es sind {teil.zahl}."},
              "weiter": "zaehlen"}
    befunde = pruefe(_ablauf(vorher, _ZAHL))
    assert any("erst nach diesem Schritt" in b for b in befunde), befunde


def test_ui_module_eines_ki_schritts_schreiben_ihre_teile():
    """Befund 2: ``ui_upload`` in ``agent.werkzeuge`` schreibt ``structure``."""
    ki = {"id": "ki", "typ": "agent", "agent": {"werkzeuge": ["ui_upload"]}, "weiter": "zeigen"}
    zeigen = {"id": "zeigen", "typ": "nachricht",
              "text": {"de": "{teil.structure.zahlen.ordner} Ordner"}, "weiter": "ende"}
    befunde = pruefe(_ablauf(ki, zeigen))
    assert not any("structure" in b for b in befunde), befunde


def test_ein_verdecktes_schreibt_an_einer_nachricht_fuellt_nichts():
    """Befund 9: ``schreibt`` zählt nur an Werkzeug und Auftrag."""
    verdeckt = {"id": "a", "typ": "nachricht", "text": {"de": "x"}, "schreibt": "geist",
                "weiter": "b"}
    zeigen = {"id": "b", "typ": "nachricht", "text": {"de": "{teil.geist}"}, "weiter": "ende"}
    assert any("geist" in b for b in pruefe(_ablauf(verdeckt, zeigen)))


def test_teile_aus_dem_werkzeug_desselben_zugs():
    """Befund 6: ein Werkzeug-Ergebnis im selben ``_rechne``."""
    ablauf = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        {"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all", "argumente": {"query": "q"},
         "schreibt": "treffer"},
        {"id": "ende", "typ": "ende", "text": {"de": "Gefunden: {teil.treffer}"}}]})

    async def mcp(_name, _args):
        return "drei Treffer"

    aus = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=_teile({}), mcp=mcp)))
    assert aus.texte == ["Gefunden: drei Treffer"]


def test_freitext_im_folgenden_text():
    ablauf = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        {"id": "f", "typ": "nachricht", "text": {"de": "Wunsch?"},
         "freitext": {"ziel": "ende", "schreibt": "wunsch"}},
        {"id": "ende", "typ": "ende", "text": {"de": "Notiert: {teil.wunsch}"}}]})
    lauf = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=_teile({})))).lauf
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), None, "Optik",
                                          treiber.Umgebung(teile=_teile({}))))
    assert aus.texte == ["Notiert: Optik"]


def test_freigabe_satz_und_auftragstext_werden_eingesetzt():
    freigabe = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"},
                                          "voraussetzungen": ["anmeldung"], "schritte": [
        {"id": "anlegen", "typ": "werkzeug", "werkzeug": "wlo_create_collection",
         "argumente": {"name": "x"}, "freigabe": {"de": "Sammlung für {teil.wunsch} anlegen?"}},
        {"id": "ende", "typ": "ende"}]})

    async def vorlegen(name, args):
        return treiber.Vorlage("Vorschau", "schluessel")

    aus = asyncio.run(treiber.starten(freigabe, treiber.Umgebung(
        teile=_teile({"wunsch": "Optik"}), vorlegen=vorlegen)))
    assert aus.texte == ["Sammlung für Optik anlegen?"]

    auftrag = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"},
                                         "voraussetzungen": ["anmeldung"], "schritte": [
        {"id": "lesen", "typ": "auftrag", "flow": "wlo/volltext", "argumente": {"x": 1},
         "text": {"de": "Ich lese {teil.wunsch}."}, "schreibt": "texte"},
        {"id": "ende", "typ": "ende"}]})

    async def starten(_flow, _args):
        return "job-1"

    aus = asyncio.run(treiber.starten(auftrag, treiber.Umgebung(
        teile=_teile({"wunsch": "Optik"}), auftrag_starten=starten)))
    assert aus.texte == ["Ich lese Optik."]
    assert all("Optik" in (b.daten.get("text") or "Optik") for b in aus.bloecke)


def test_die_simulation_gibt_die_texte_zurueck():
    """Befund 4: ein Testfall sieht den eingesetzten Text."""
    from boerdi.services.ablauf import simulation

    ablauf = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        {"id": "f", "typ": "nachricht", "text": {"de": "Wunsch?"},
         "freitext": {"ziel": "ende", "schreibt": "wunsch"}},
        {"id": "ende", "typ": "ende", "text": {"de": "Notiert: {teil.wunsch}"}}]})
    test = simulation.AblaufTest.model_validate({
        "name": "t", "eingaben": [{"bei": "f", "text": "Optik"}]})
    e = asyncio.run(simulation.testen(ablauf, test))
    assert e.texte == ["Wunsch?", "Notiert: Optik"]
