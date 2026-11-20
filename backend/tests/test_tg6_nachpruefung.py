"""Plan 2026-11-16, Nachprüfung TG-4–6: Knopf-Fragen ohne Freitext, das Verneinungsfenster,
mehrdeutige Grundlagen, Synonyme vor einem schreibenden Auftrag, der Wert als Stelle in der
Prüfung, „Nein danke“.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import pruefung, simulation, treiber, werkzeuge

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"


def _seed() -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(
        (_SEEDS / "themenbaum.yaml").read_text(encoding="utf-8")))


def _schritt(sid: str):
    return next(s for s in _seed().schritte if s.id == sid)


# ── MAJOR 1: Ja/Nein- und Entweder-oder-Fragen nehmen keinen Freitext ───────────────────────────

#: Wo die Antwort wirklich frei ist — nur dort Freitext.
_FREI = {"grundlage", "wofuer", "stufe", "umfang", "hinweise"}


def test_m1_freitext_nur_wo_die_antwort_frei_ist():
    ablauf = _seed()
    assert {s.id for s in ablauf.schritte if s.freitext is not None} == _FREI
    knoepfe = [s for s in ablauf.schritte if pruefung.mit_wahl(s) and s.freitext is None]
    assert {s.id for s in knoepfe} >= {"einstieg", "einstieg_mit", "ordner_weiter",
                                       "soll_ist", "ohne_daten",
                                       "ohne_entwurf", "ohne_metadaten"}
    for s in knoepfe:
        assert s.kein_treffer and s.kein_treffer.get("de") and s.kein_treffer.get("en"), s.id
        # keine Synonyme an Knopf-Fragen: ohne Freitext träfe ein Teilwort („nicht gründlich“)
        assert not any(o.synonyme for o in s.optionen or []), s.id


@pytest.mark.parametrize(("sid", "text"), [
    # U6: ``wlo_frage`` entfiel, P4 (Plan 2026-11-20) die Rückfrage vor Kestra — dieselbe Regel am
    # Ausweg ohne Angaben aus WLO
    ("ohne_metadaten", "Ja, gern"), ("ohne_metadaten", "lieber nicht"),
    ("ordner_weiter", "Passt so"), ("ordner_weiter", "ja, passt"), ("ordner_weiter", "Ja"),
    ("ordner_weiter", "Passt nicht, bitte verfeinern"),
])
def test_m1_natuerliche_saetze_treffen_keinen_knopf(sid, text):
    assert treiber.wahl_aus_text(_schritt(sid), text, "de") is None


def test_m1_das_label_trifft_weiter():
    assert treiber.wahl_aus_text(_schritt("ohne_metadaten"), "Ohne Angaben aus WLO weiter",
                                 "de") == "ohne"
    assert treiber.wahl_aus_text(_schritt("ordner_weiter"), "so lassen", "de") == "lassen"


# ── MINOR 2: die Verneinung gilt im Satzteil, davor und direkt dahinter ─────────────────────────

@pytest.mark.parametrize(("text", "erwartet"), [
    ("Lehrplan nicht, Ordner", "ordner"),
    ("Kein PDF, Ordner", "ordner"),
    ("Den Lehrplan nicht, lieber meine Ordner", "ordner"),
    ("Nicht sicher, Lehrplan", "dokument"),
    # „nicht nur“ bejaht (Feinentscheid): der Lehrplan ist gemeint, nur nicht allein
    ("nicht nur Lehrplan", "dokument"),
    ("Lehrplan, nicht Ordner", "dokument"),
    ("Ich habe keinen Lehrplan, Thema Optik", None),
])
def test_m2_verneinung_im_satzteil(text, erwartet):
    assert treiber.wahl_aus_text(_schritt("grundlage"), text, "de") == erwartet


# ── MINOR 3: mehrere Treffer sind weder Wahl noch Thema ─────────────────────────────────────────

_MEHRDEUTIG = ["Dateien aus meinem Ordner", "meine PDF-Dateien", "Ordner mit Unterlagen",
               "Dateien und Ordner (Informatik)", "nicht nur Lehrplan, auch meine Dateien"]


@pytest.mark.parametrize("text", _MEHRDEUTIG)
def test_m3_mehrdeutig_ist_keine_wahl_und_kein_freitext(text):
    ablauf, s = _seed(), _schritt("grundlage")
    assert treiber.wahl_aus_text(s, text, "de") is None
    assert treiber.mehrdeutig(s, text, "de")
    lauf = {"status": treiber.WARTET_WAHL, "schritt": "grundlage",
            "fassung": treiber.fassung(ablauf)}
    assert not treiber.wahl_gilt(ablauf, lauf, None, text)
    assert treiber.wahl_gilt(ablauf, lauf, None, "Optik (Physik)")


def test_m3_eindeutig_oder_thema_ist_nicht_mehrdeutig():
    s = _schritt("grundlage")
    for text in ("Optik (Physik)", "meine Ordner", "Lehrplan nicht, Ordner", "Meine Dateien"):
        assert not treiber.mehrdeutig(s, text, "de"), text
    # ohne ``synonyme_im_satz`` nie
    assert not treiber.mehrdeutig(_schritt("hinweise"), "Dateien und Ordner", "de")


def test_m3_die_grundlage_hat_einen_hinweis_und_die_pruefung_erlaubt_ihn():
    s = _schritt("grundlage")
    assert "Ordner" in s.kein_treffer["de"] and "folders" in s.kein_treffer["en"]
    assert not [b for b in pruefung.pruefe(_seed()) if "kein_treffer" in b]
    # ohne ``synonyme_im_satz`` bleibt Freitext + Hinweis ein Befund
    roh = _seed().model_dump(exclude_none=True)
    for x in roh["schritte"]:
        if x["id"] == "grundlage":
            x.pop("synonyme_im_satz")
    assert any("kein_treffer" in b
               for b in pruefung.pruefe(AblaufArea.model_validate(roh)))


def _fall(**roh) -> AblaufTest:
    return AblaufTest.model_validate({"name": "Probe", **roh})


def test_m3_simulation_wartet_nach_dem_hinweis():
    ablauf = _seed()
    fall = _fall(eingaben=[{"bei": "einstieg", "option": "neu"},
                           {"bei": "grundlage", "text": "Dateien aus meinem Ordner"},
                           {"bei": "grundlage", "text": "Meine Ordner"}],
                 erwartet={"weg": ["bereit", "vorhanden", "einstieg", "grundlage",
                                   "ordner_laden"], "status": "wartet_person"})
    ergebnis = asyncio.run(simulation.testen(ablauf, fall))
    assert ergebnis.ok, ergebnis.abweichungen


def test_m1_simulation_wartet_an_einer_knopf_frage():
    ablauf = _seed()
    fall = _fall(ab="ordner_weiter",
                 eingaben=[{"bei": "ordner_weiter", "text": "Passt so"},
                           {"bei": "ordner_weiter", "option": "lassen"}],
                 erwartet={"weg": ["ordner_weiter", "ende"], "status": "fertig"})
    ergebnis = asyncio.run(simulation.testen(ablauf, fall))
    assert ergebnis.ok, ergebnis.abweichungen


def test_m1_ohne_hinweis_bleibt_ein_fehlversuch_eine_abweichung():
    """Ein Schritt ohne ``kein_treffer`` nimmt den Text nicht — wie bisher eine Abweichung."""
    roh = _seed().model_dump(exclude_none=True)
    for x in roh["schritte"]:
        if x["id"] == "ordner_weiter":
            x.pop("kein_treffer")
    fall = _fall(ab="ordner_weiter", eingaben=[{"bei": "ordner_weiter", "text": "Passt so"}])
    ergebnis = asyncio.run(simulation.testen(AblaufArea.model_validate(roh), fall))
    assert not ergebnis.ok


# ── MINOR 4: Synonyme an der Zustimmung vor einem schreibenden Auftrag ──────────────────────────

def _probe(synonyme: list[str] | None) -> AblaufArea:
    ja = {"id": "ja", "label": {"de": "Ja"}, "ziel": "a"}
    if synonyme:
        ja["synonyme"] = synonyme
    return AblaufArea.model_validate({
        "id": "x", "titel": {"de": "X"}, "voraussetzungen": ["anmeldung"],
        "ausloeser": [{"art": "agent", "modus": "direkt"}],
        "schritte": [
            {"id": "q", "typ": "nachricht", "text": {"de": "Erzeugen?"},
             "optionen": [ja, {"id": "nein", "label": {"de": "Nein"}, "ziel": "weg"}]},
            {"id": "a", "typ": "auftrag", "flow": "f/x", "repo_schreibt": True, "bei_fehler": "e"},
            {"id": "e", "typ": "ende", "text": {"de": "Fertig."}},
            {"id": "weg", "typ": "ende", "text": {"de": "Ohne."}}]})


def test_m4_ein_synonym_an_der_zustimmung_ist_keine_rueckfrage():
    mit = _probe(["erzeugen"])
    # warum: ohne Freitext trifft ein Teilwort ohne Verneinung
    assert treiber.wahl_aus_text(mit.schritte[0], "Nein, nicht erzeugen", "de") == "ja"
    assert werkzeuge.ablauf_schreibt_ungefragt(mit)
    assert not werkzeuge.ablauf_schreibt_ungefragt(_probe(None))


def test_m4_pruefbefund_je_sprache():
    for lang, wort in (("de", "Synonym"), ("en", "synonym")):
        befunde = pruefung.pruefe(_probe(["erzeugen"]), lang)
        assert any(wort in b and "q" in b for b in befunde), befunde
    assert not any("ynonym" in b for b in pruefung.pruefe(_probe(None)))


# ── MINOR 5: der Wert als Stelle in der Prüfung ─────────────────────────────────────────────────

def _mit_wert(wert: str, vergleich: str = "gleich") -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "x", "titel": {"de": "X"},
        "schritte": [
            {"id": "f", "typ": "nachricht", "text": {"de": "?"}, "schreibt": "aa",
             "optionen": [{"id": "o", "label": {"de": "O"}, "ziel": "v"}]},
            {"id": "v", "typ": "verzweigung", "weiter": [
                {"wenn_wert": {"quelle": "teil.aa", "vergleich": vergleich, "wert": wert},
                 "dann": "e"},
                {"sonst": "g"}]},
            {"id": "g", "typ": "nachricht", "text": {"de": "?"}, "schreibt": "bb",
             "optionen": [{"id": "o", "label": {"de": "O"}, "ziel": "e"}]},
            {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}]})


@pytest.mark.parametrize(("wert", "vergleich", "erwartet"), [
    ("{teil.aa}", "gleich", None),
    ("{teil.aa}", "groesser", None),                  # keine Zahl nötig, die Stelle zählt
    ("{teil.fehlt.x}", "gleich", "fehlt"),           # kein Schritt schreibt den Teil
    ("{teil.bb}", "gleich", "bb"),                     # entsteht erst danach
    ("{teil.}", "gleich", "{teil.}"),                # Form ungültig
    ("{teil.aa", "gleich", "{teil.aa"),
    ("O", "gleich", None),
])
def test_m5_die_stelle_im_wert_wird_geprueft(wert, vergleich, erwartet):
    befunde = [b for b in pruefung.pruefe(_mit_wert(wert, vergleich)) if "Schritt v" in b]
    if erwartet is None:
        assert befunde == []
    else:
        assert len(befunde) == 1 and erwartet in befunde[0], befunde
    assert not any("Zahl" in b for b in befunde)


# ── NIT 8: „Nein danke“ ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("text", "erwartet"), [
    ("Nein danke", "keine"), ("nein, danke", "keine"), ("Nein, danke!", "keine"),
    ("no thanks", "keine"), ("Nein danke, aber Optik", None),
])
def test_n8_nein_danke(text, erwartet):
    assert treiber.wahl_aus_text(_schritt("hinweise"), text, "de") == erwartet
