"""Paket U1-d1 (d1-1, d1-2): das Modul ``ui_entscheidung`` und die Modul-Werkzeuge allgemein.

Das Manifest ist die eine Quelle (Frontend-Ordner → ``manifeste.json``): Der Katalog prüft es samt
Beispielen, die Werkzeugbeschreibung für die KI entsteht daraus, und ein Werkzeugaufruf wird gegen
``eingabe`` geprüft, bevor ein Block entsteht. Ein Fehler geht als Werkzeug-Ergebnis an die KI
zurück, damit sie den Aufruf berichtigen kann.
"""

from __future__ import annotations

import pytest

from boerdi.ui_module import katalog
from boerdi.ui_module.werkzeuge import (
    ist_modul_werkzeug,
    modul_aufruf_annehmen,
    modul_werkzeuge,
    werkzeug_aus_manifest,
)

ENTSCHEIDUNG = "ui_entscheidung"


def _args(**mehr) -> dict:
    args = {
        "frage": "Für welche Klassenstufe?",
        "optionen": [{"id": "unter", "label": "Klasse 5–6"},
                     {"id": "mittel", "label": "Klasse 7–8", "hinweis": "mit Vorwissen"}],
    }
    args.update(mehr)
    return args


# ── d1-1 Manifest ──────────────────────────────────────────────────────────


def test_die_entscheidung_steht_im_katalog_als_abfragendes_agent_modul():
    m = katalog.katalog()[ENTSCHEIDUNG]
    assert (m["art"], m["agent"], m["faehigkeiten"]) == ("abfragen", True, ["antworten"])
    assert m["textfassung"] == {"vorlage": "nummerierte_liste", "feld": "optionen"}


def test_die_eingabe_deckelt_frage_optionen_und_kennungen():
    m = katalog.katalog()[ENTSCHEIDUNG]
    props = m["eingabe"]["properties"]
    assert props["frage"]["maxLength"] == 300
    assert (props["optionen"]["minItems"], props["optionen"]["maxItems"]) == (2, 8)
    assert props["optionen"]["items"]["properties"]["id"]["pattern"] == "^[a-z0-9_-]{1,40}$"
    assert set(props) == {"frage", "optionen", "mehrfach", "freitext"}
    assert m["antwort"]["properties"]["freitext"]["maxLength"] == 1000


def test_jedes_beispiel_hat_eine_passende_antwort():
    # Die Prüfung selbst macht der Katalog beim Laden; hier: es gibt welche, und sie wählen
    # nur Kennungen, die das Beispiel anbietet.
    for beispiel in katalog.katalog()[ENTSCHEIDUNG]["beispiele"]:
        ids = {o["id"] for o in beispiel["daten"]["optionen"]}
        assert set(beispiel["antwort"]["gewaehlt"]) <= ids, beispiel["titel"]


@pytest.mark.parametrize("daten", [
    _args(optionen=[{"id": "a", "label": "Nur eine"}]),
    _args(optionen=[{"id": f"o{i}", "label": f"O{i}"} for i in range(9)]),
    _args(optionen=[{"id": "Groß", "label": "A"}, {"id": "b", "label": "B"}]),
    _args(frage="x" * 301),
])
def test_falsche_daten_verletzen_die_eingabe(daten):
    assert katalog.daten_fehler(katalog.katalog()[ENTSCHEIDUNG], daten)


# ── d1-2 Modul-Werkzeuge allgemein ─────────────────────────────────────────


def test_werkzeuge_gibt_es_nur_fuer_agent_module_ohne_eigenen_weg():
    namen = [w["function"]["name"] for w in modul_werkzeuge(katalog.katalog(), fuer="agent")]
    # Inhaltsrahmen hat seinen eigenen Weg (Dokument-Werkzeug), Linkbox und Trefferliste
    # entstehen ohne Aufruf aus der Antwort. Ohne verfügbare MCP-Werkzeuge fehlt der Themenbaum
    # (Datenquelle); Strukturentwurf (U2) und Upload (U3-1) haben einen Dienst und brauchen keines.
    assert namen == [ENTSCHEIDUNG, "ui_strukturentwurf", "ui_upload"]
    assert ist_modul_werkzeug(ENTSCHEIDUNG)
    for name in ("ui_inhaltsrahmen", "ui_linkbox", "ui_trefferliste", "search_wlo_content"):
        assert not ist_modul_werkzeug(name)


def test_werkzeuge_gibt_es_nur_fuer_gemeldete_module():
    """Review U1-d1, Befund 8: nur, was das Widget zeigen kann (``Environment.ui_module``)."""
    assert modul_werkzeuge([], fuer="agent") == []
    assert modul_werkzeuge(["ui_linkbox", "ui_trefferliste"], fuer="agent") == []
    namen = [w["function"]["name"] for w in modul_werkzeuge([ENTSCHEIDUNG], fuer="agent")]
    assert namen == [ENTSCHEIDUNG]


def test_das_werkzeug_ist_das_manifest():
    [werkzeug] = modul_werkzeuge([ENTSCHEIDUNG], fuer="agent")
    assert werkzeug == werkzeug_aus_manifest(katalog.katalog()[ENTSCHEIDUNG])
    assert werkzeug["function"]["parameters"]["required"] == ["frage", "optionen"]


def test_ein_gueltiger_aufruf_ergibt_einen_offenen_block_mit_textfassung():
    block, fehler = modul_aufruf_annehmen(ENTSCHEIDUNG, _args())
    assert fehler is None and block is not None
    assert (block.modul, block.art, block.status, block.version) == (
        ENTSCHEIDUNG, "abfragen", "offen", katalog.katalog()[ENTSCHEIDUNG]["version"])
    assert block.daten == _args()
    # Textfassung (ältere Widgets): die Frage, darunter die nummerierten Möglichkeiten.
    assert block.text == ("Für welche Klassenstufe?\n\n1. Klasse 5–6\n"
                          "2. Klasse 7–8 — mit Vorwissen")


def test_zwei_aufrufe_ergeben_verschiedene_kennungen():
    a, _ = modul_aufruf_annehmen(ENTSCHEIDUNG, _args())
    b, _ = modul_aufruf_annehmen(ENTSCHEIDUNG, _args())
    assert a is not None and b is not None and a.block_id != b.block_id


def test_falsche_argumente_gehen_mit_pfad_an_die_ki():
    block, fehler = modul_aufruf_annehmen(ENTSCHEIDUNG, _args(optionen=[{"id": "a", "label": "A"}]))
    assert block is None
    assert fehler is not None and "optionen" in fehler and ENTSCHEIDUNG in fehler


def test_doppelte_kennungen_der_optionen_werden_abgewiesen():
    block, fehler = modul_aufruf_annehmen(ENTSCHEIDUNG, _args(
        optionen=[{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]))
    assert block is None
    assert fehler is not None and "optionen" in fehler and "„a“" in fehler


def test_ein_unbekanntes_modul_ist_kein_block():
    block, fehler = modul_aufruf_annehmen("ui_gibtsnicht", {})
    assert block is None and fehler
