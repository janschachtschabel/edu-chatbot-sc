"""Plan 2026-11-16, TG-6 (G-E2, G-E6, G-E7, G-E9, G-E10): der Ablauf „Themenbaum erstellen“.

- **Ein Ablauf** für alle Grundlagen (Thema, Dokument, Ordner, Dateien) löst die vier alten ab; sie
  bleiben als Werksfassung, ab Werk aus. Ab Werk an, ohne Voraussetzung (anonym startbar).
- **Bereitgestelltes zuerst:** ``bereitgestellt`` meldet ``art``/``name``/``wlo_ablage``.
- **„Gründlich über WLO“** fragt der Ablauf nur, wenn das Upload-Feld die Ablage anbietet
  (Systemfelder des Upload-Dienstes); sonst schnell aus den Dateinamen (``inhalte_aus_dateien``).
- **Kein stummes Ende** (``stumme_enden``): eine Prüfung über alle Seeds.
- **Direktstart** trotz Auftrag, weil vor ihm direkt die Rückfrage steht; der frische Vorgang
  (N14) bleibt.
- Die Leiste springt nicht.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser, fortschritt, simulation, vorschlag, werkzeuge
from boerdi.services.ablauf.pruefung import (
    MAX_OPTIONEN,
    MAX_SCHRITTE,
    pruefe,
    warnungen,
    wendungs_warnungen,
)
from boerdi.services.ablauf.stumme_enden import stumme_enden
from tests.leiste_halte import leiste, ohne_sprung

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"
_ALT = ("themenbaum_aus_thema", "themenbaum_aus_dokument", "themenbaum_aus_inhalten",
        "sammlungsstruktur")


def _seed(name: str) -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(
        (_SEEDS / f"{name}.yaml").read_text(encoding="utf-8")))


def _alle() -> list[AblaufArea]:
    return [_seed(p.stem) for p in sorted(_SEEDS.glob("*.yaml"))]


# ── Der Seed ─────────────────────────────────────────────────────────────────────────────────────

def test_der_seed_besteht_pruefung_hinweise_und_alle_selbsttests():
    ablauf = _seed("themenbaum")
    assert ablauf.aktiv is True and ablauf.voraussetzungen == []
    assert len(ablauf.schritte) <= MAX_SCHRITTE
    assert all(len(s.optionen or []) <= MAX_OPTIONEN for s in ablauf.schritte)
    assert pruefe(ablauf) == [] and warnungen(ablauf) == []
    ergebnisse = asyncio.run(simulation.alle(ablauf))
    assert all(e.ok for e in ergebnisse), [(e.name, e.abweichungen) for e in ergebnisse]


def test_jeder_zweig_hat_einen_selbsttest():
    """Thema, Dokument (neu, schon da, mehrere), Ordner mit und ohne Unterordner, Dateien schnell
    und gründlich (Kestra attrappiert), Ausstieg, Fehler."""
    ablauf = _seed("themenbaum")
    besucht = {s for t in ablauf.tests for e in t.eingaben for s in [e.bei]}
    besucht |= {s for t in ablauf.tests for s in t.erwartet.weg or []}
    for schritt in ("entwurf_thema", "entwurf_dokument", "aus_ordnern", "ordner_pruefen",
                    "aus_dateien", "entwurf_inhalte", "metadaten", "lesen", "einstieg_mit",
                    "frei", "ohne_daten", "ohne_entwurf", "ohne_metadaten", "dokument_gelesen",
                    "ordner_geladen", "dateien_geladen", "wlo_frage", "nach_lesen",
                    "ordner_weiter", "entwurf_ordner", "schnell"):
        assert schritt in besucht, schritt
    namen = {t.name for t in ablauf.tests}
    assert {"Mehrere Dokumente", "Dateien gründlich über WLO mit Kestra",
            "Ordner ohne Unterordner wird der Weg Dateien", "Ohne Führung"} <= namen


def test_die_ki_schritte_belegen_den_auftrag_vor_und_tragen_die_regeln():
    ablauf = _seed("themenbaum")
    ki = [s for s in ablauf.schritte if s.typ == "agent"]
    assert {s.id for s in ki} == {"entwurf_thema", "entwurf_dokument", "entwurf_inhalte",
                                  "entwurf_ordner"}
    for s in ki:
        assert s.agent.vorbelegen is True and s.agent.ausgabe == "draft"
        de = s.agent.vorgaben["de"]
        # Wissenssammlung: Breite, keine Einzelkinder, keine Facetten als Knoten
        assert "5 bis 15" in de and "3 bis 20" in de and "nur einem Unterpunkt" in de
        assert "Format" in de and "Stufe" in de
    assert "Herkunft" in ki[2].agent.vorgaben["de"]                 # Ordner sind Herkunft
    assert "Herkunft" in ki[3].agent.vorgaben["de"]
    # Review TG-4–6, NIT 17: auch aus Inhalten der Zweck „Überblick für eine Webseite“
    assert "Überblick für eine Webseite" in ki[2].agent.vorgaben["de"]
    # MINOR 11: die englischen Vorgaben nennen die deutschen Werte der Antworten mit
    assert all("Unterricht planen" in s.agent.vorgaben["en"] for s in ki)
    # MAJOR 4: auf dem Ordner-Weg verfeinert die KI den geprüften Entwurf
    assert "vorlage: true" in ki[3].agent.hinweis["de"]
    pruefen = next(s for s in ablauf.schritte if s.id == "ordner_pruefen")
    assert "Ausgangspunkt" in pruefen.text["de"]                     # G-E10


def test_die_leitfragen_nehmen_getippten_text():
    """Nachprüfung TG-4–6, MAJOR 1: nur Fragen mit freier Antwort; Entweder-oder-Fragen
    (``soll_ist``, ``ordner_weiter``, ``wlo_frage``) zeigen ohne Treffer ``kein_treffer``."""
    ablauf = _seed("themenbaum")
    for sid in ("grundlage", "wofuer", "stufe", "umfang", "hinweise"):
        s = next(x for x in ablauf.schritte if x.id == sid)
        assert s.freitext is not None, sid
    for sid in ("soll_ist", "ordner_weiter", "wlo_frage"):
        s = next(x for x in ablauf.schritte if x.id == sid)
        assert s.freitext is None and s.kein_treffer, sid


def test_die_alten_vier_sind_aus_und_abgeloest():
    for name in _ALT:
        text = (_SEEDS / f"{name}.yaml").read_text(encoding="utf-8")
        assert "abgelöst durch themenbaum" in text.casefold()
        ablauf = _seed(name)
        assert ablauf.aktiv is False
        assert pruefe(ablauf) == []


def test_die_wendungen_der_alten_sind_uebernommen_und_kollidieren_nicht():
    neu = _seed("themenbaum")
    eigene = {w for a in neu.ausloeser if a.art == "text" for w in a.wendungen}
    for name in _ALT:
        alt = {w for a in _seed(name).ausloeser if a.art == "text" for w in a.wendungen}
        assert alt <= eigene, name
    # wie im Betrieb: die Seeds mit ihrem eigenen ``aktiv``
    assert wendungs_warnungen(neu, _alle()) == []


# ── Kein stummes Ende ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", [p.stem for p in sorted(_SEEDS.glob("*.yaml"))])
def test_kein_seed_endet_stumm(name):
    assert stumme_enden(_seed(name)) == []


def _mini(schritte: list[dict]) -> AblaufArea:
    return AblaufArea.model_validate({"id": "x", "titel": {"de": "X"}, "schritte": schritte})


_ENDE = {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}
_DIENST = {"id": "w", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
           "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "draft"}


def test_ein_ende_nach_einem_fehler_ist_stumm():
    ablauf = _mini([{**_DIENST, "bei_fehler": "aus"}, _ENDE,
                    {"id": "aus", "typ": "ende", "text": {"de": "Ohne Unterordner nichts."}}])
    assert stumme_enden(ablauf) == ["ende", "aus"]   # in der Reihenfolge der Schritte
    assert any("Schritt aus" in w for w in warnungen(ablauf))


def test_ergebnis_wahl_und_ausstieg_sind_nicht_stumm():
    ablauf = _mini([
        {"id": "frage", "typ": "nachricht", "text": {"de": "Weiter?"},
         "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "ki"},
                      {"id": "nein", "label": {"de": "Nein"}, "ziel": "beendet"}]},
        {"id": "ki", "typ": "agent", "agent": {"werkzeuge": ["ui_strukturentwurf"],
                                               "ausgabe": "draft"}, "bei_fehler": "frei"},
        _ENDE,
        {"id": "beendet", "typ": "ende", "text": {"de": "Gut."}},
        {"id": "frei", "typ": "ende", "ausstieg": True, "text": {"de": "Frei."}}])
    assert stumme_enden(ablauf) == []


def test_eine_wahl_vor_dem_upload_zaehlt_danach_nicht_mehr():
    """Das Upload-Feld stellt nur bereit: danach ist ein Ende ohne Ergebnis wieder stumm."""
    ablauf = _mini([
        {"id": "frage", "typ": "nachricht", "text": {"de": "Los?"},
         "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "laden"}]},
        {"id": "laden", "typ": "modul", "modul": "ui_upload", "daten": {"zweck": "bereitstellen"}},
        {"id": "pruefen", "typ": "verzweigung",
         "weiter": [{"wenn_teil": "document", "dann": "ende"}, {"sonst": "leer"}]},
        _ENDE, {"id": "leer", "typ": "ende", "text": {"de": "Nichts gelesen."}}])
    assert stumme_enden(ablauf) == ["ende", "leer"]


# ── Bereitgestelltes: art, name, wlo_ablage ──────────────────────────────────────────────────────

def _bereit(teile: dict, *, wlo: bool | None = None, sprache: str = "de") -> dict:
    async def lader(name):
        return teile.get(name)

    kontext = werkzeuge.DienstKontext(teile=lader, sprache=sprache,
                                      wlo_ablage=None if wlo is None else (lambda: wlo))
    return asyncio.run(werkzeuge.DIENSTE["bereitgestellt"]({}, kontext))


_ORDNER = {"struktur": {"name": "Physik", "kinder": [{"name": "Optik"}, {"name": "Mechanik"}]}}
_FLACH = {"struktur": {"name": "Unterlagen", "kinder": [], "dateiliste": [
    {"i": 0, "name": "a.pdf", "rolle": "inhalt"}, {"i": 1, "name": "b.pdf", "rolle": "inhalt"}]}}


def test_art_und_name_in_der_reihenfolge_dokument_ordner_dateien():
    leer = _bereit({})
    assert leer["art"] is None and leer["name"] is None and leer["wlo_ablage"] is False
    dok = {"ref": "dokument:11111111-1111-4111-8111-111111111111", "name": "Lehrplan.pdf"}
    alles = _bereit({"document": dok, "structure": _ORDNER, "struktur": _FLACH})
    assert alles["art"] == "dokument" and alles["name"] == "das Dokument „Lehrplan.pdf“"
    assert _bereit({"structure": _ORDNER})["name"] == "die Ordner „Physik“"
    flach = _bereit({"structure": {"struktur": {"name": "Unterlagen", "kinder": []}},
                     "struktur": _FLACH}, sprache="en")
    assert flach["art"] == "dateien" and flach["name"] == "2 files from “Unterlagen”"


def test_wlo_ablage_folgt_den_systemfeldern_des_upload_dienstes(monkeypatch):
    assert _bereit({}, wlo=True)["wlo_ablage"] is True
    assert _bereit({}, wlo=False)["wlo_ablage"] is False
    from boerdi.services.ablauf import zug_basis
    from boerdi.ui_module import dienst_upload

    monkeypatch.setattr(dienst_upload, "schalter", lambda: {"ablage_in_wlo": True})
    assert zug_basis._wlo_ablage() is True
    monkeypatch.setattr(dienst_upload, "schalter", lambda: {"ablage_nach_anmeldung": True})
    assert zug_basis._wlo_ablage() is False


def test_ohne_anmeldung_fragt_der_ablauf_nicht_nach_dem_gruendlichen_weg():
    """Simulation: die Ablage gilt wie Aufträge nur angemeldet (``angemeldet`` des Testfalls)."""
    ablauf = _seed("themenbaum")
    [fall] = [t for t in ablauf.tests if t.name == "Dateien anonym aus den Namen"]
    assert fall.angemeldet is False
    ergebnis = asyncio.run(simulation.testen(ablauf, fall))
    assert ergebnis.ok and "wlo_frage" not in ergebnis.weg and "schnell" in ergebnis.weg


# ── Direktstart, frischer Vorgang, Anmeldung ─────────────────────────────────────────────────────

def test_direktstart_trotz_auftrag_mit_rueckfrage_davor():
    ablauf = _seed("themenbaum")
    assert werkzeuge.ablauf_schreibt_selbst(ablauf)            # N14: frischer Vorgang bleibt
    assert not werkzeuge.ablauf_schreibt_ungefragt(ablauf)
    assert vorschlag._direkt(ablauf)
    assert not any("modus direkt" in b for b in pruefe(ablauf))


def test_ein_auftrag_ohne_rueckfrage_bleibt_ein_vorschlag():
    ablauf = AblaufArea.model_validate({
        "id": "x", "titel": {"de": "X"}, "voraussetzungen": ["anmeldung"],
        "ausloeser": [{"art": "agent", "modus": "direkt"}],
        "schritte": [{"id": "a", "typ": "auftrag", "flow": "f/x", "bei_fehler": "ende"},
                     _ENDE]})
    assert werkzeuge.ablauf_schreibt_ungefragt(ablauf) and not vorschlag._direkt(ablauf)
    assert any("modus direkt" in b for b in pruefe(ablauf))


def test_ohne_anmeldung_genuegt_ein_ersatzweg_am_auftrag():
    def _ablauf(bei_fehler: str | None) -> AblaufArea:
        schritt = {"id": "a", "typ": "auftrag", "flow": "f/x"}
        if bei_fehler:
            schritt["bei_fehler"] = bei_fehler
        return AblaufArea.model_validate({"id": "x", "titel": {"de": "X"},
                                          "schritte": [schritt, _ENDE]})

    assert any("Voraussetzung Anmeldung" in b for b in pruefe(_ablauf(None)))
    assert not any("Voraussetzung Anmeldung" in b for b in pruefe(_ablauf("ende")))


# ── Die Leiste springt nicht (Review TG-4–6, Befund 10) ──────────────────────────────────────────

#: Die Hauptwege — ohne Rückweg („Nochmal“) und ohne Start mitten im Ablauf (``ab``).
_HAUPTWEGE = ["Thema getippt bis zum Entwurf", "Lerninhalte sind ein Thema",
              "Dokument neu lesen lassen", "Mehrere Dokumente",
              "Dokument schon gelesen, verwenden",
              "Dokument da, anderes wählen, Dateien angemeldet",
              "Ordner, anonym, so lassen", "Ordner mit Angaben verfeinern",
              "Ordner nach WLO übertragen und erschließen",
              "Ordner ohne Unterordner wird der Weg Dateien", "Dateien anonym aus den Namen",
              "Dateien schon erfasst, verwenden, anonym", "Ohne Führung"]


@pytest.mark.parametrize("fall", _HAUPTWEGE)
def test_die_leiste_steigt_je_halt_um_eins(monkeypatch, fall):
    halte = leiste(monkeypatch, _seed("themenbaum"), fall)
    ohne_sprung(halte)
    assert halte[0][0] in ("einstieg", "einstieg_mit")     # kein Werkzeug davor zählt


def test_auf_einem_rueckweg_zaehlt_die_leiste_weiter(monkeypatch):
    """Ein „Nochmal“ ist ein weiterer Halt — n steigt, es springt nicht zurück."""
    ohne_sprung(leiste(monkeypatch, _seed("themenbaum"), "Nichts Brauchbares hochgeladen, nochmal"))


def test_der_lauf_traegt_seine_halte():
    """Ein neuer Lauf beginnt mit 0 Halten; ein Lauf ohne ``halte`` (vor dieser Fassung) bekommt
    keine — für ihn bleibt die Rechnung über den längsten Weg."""
    from boerdi.services.ablauf import treiber

    ablauf = _seed("themenbaum")

    async def nichts(_name):
        return None

    umgebung = treiber.Umgebung(teile=nichts)
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    assert lauf["schritt"] == "einstieg" and lauf["halte"] == 1
    alt = {k: v for k, v in lauf.items() if k != "halte"}
    weiter = asyncio.run(treiber.weiter_wahl(ablauf, alt, "neu", None, umgebung))
    assert "halte" not in weiter.lauf
    assert fortschritt.position(ablauf, "grundlage") is not None   # Rückfall: längster Weg


# ── Netze aus TW-6 und TG-2 finden den neuen Ablauf ──────────────────────────────────────────────

def test_ein_entwurf_ohne_grundlage_wird_auf_themenbaum_umgelenkt(monkeypatch):
    neu = _seed("themenbaum")
    monkeypatch.setattr(ausloeser, "vorschlaege", lambda: [neu])
    hinweis = vorschlag.umlenkung("ui_strukturentwurf", {"thema": "Karate"},
                                  ["ui_strukturentwurf", "ablauf-themenbaum"], {"entities": {}})
    assert hinweis and "ablauf-themenbaum" in hinweis


def test_ein_ablauf_ohne_upload_geht_beim_entwurf_vor(monkeypatch):
    """Wie vor TG-6: ist „aus einem Thema“ an, lenkt ``ui_strukturentwurf`` nur dorthin."""
    neu, thema = _seed("themenbaum"), _seed("themenbaum_aus_thema")
    monkeypatch.setattr(ausloeser, "vorschlaege", lambda: [neu, thema])
    hinweis = vorschlag.umlenkung(
        "ui_strukturentwurf", {"thema": "Karate"},
        ["ui_strukturentwurf", "ablauf-themenbaum", "ablauf-themenbaum_aus_thema"],
        {"entities": {}})
    assert "ablauf-themenbaum_aus_thema" in hinweis and "ablauf-themenbaum (" not in hinweis


def test_nach_dem_lesen_nennt_der_rahmen_den_themenbaum(monkeypatch):
    from boerdi.ui_module import schalter as modul_schalter
    from boerdi.ui_module import upload_antwort

    monkeypatch.setattr(modul_schalter, "aktiv", lambda modul: False)
    monkeypatch.setattr(ausloeser, "vorschlaege", lambda: [_seed("themenbaum")])
    assert upload_antwort._themenbaum_angeboten(dokument=True)
    assert upload_antwort._themenbaum_angeboten(dokument=False)
