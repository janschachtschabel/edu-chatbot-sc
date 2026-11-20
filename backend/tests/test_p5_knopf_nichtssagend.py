"""Plan 2026-11-20, P5 (UO-8): die Prüfung meldet nichtssagende Beschriftungen an Knöpfen, die zu
einem Schritt führen, der ins Repositorium schreibt.

Ein Knopf vor einem schreibenden Schritt (Auftrag mit ``repo_schreibt``, schreibendes
WLO-Werkzeug) sagt, was geschieht — „OK“, „Weiter“, „Ja“ oder „Los“ sagen es nicht. Geprüft wird
jede Sprache der Beschriftung, ohne Satzzeichen, Leerzeichen und Groß/Klein; dazu die Text-Chips
(``text_antworten``) an derselben Frage, weil sie neben den schreibenden Knöpfen stehen.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.services.ablauf import pruefung
from boerdi.services.ablauf.pruefung_texte import _T as TEXTE

_HIER = pathlib.Path(__file__).parent
_SEEDS = sorted((_HIER.parent / "seeds" / "06-ablaeufe").glob("*.yaml"))
_BEISPIELE = sorted((_HIER / "ablauf_beispiele").glob("*.yaml"))
_KEIN_TREFFER = {"de": "Bitte wähle einen der Knöpfe.", "en": "Please choose one of the buttons."}


def _ziel(art: str) -> dict:
    if art == "auftrag":
        return {"id": "schreiben", "typ": "auftrag", "flow": METADATEN_FLOW, "repo_schreibt": True,
                "argumente": {"node_ids": ["n-1"]}, "schreibt": "lauf", "bei_fehler": "ohne",
                "weiter": "fertig", "text": {"de": "Ich lasse die Metadaten erzeugen."}}
    if art == "werkzeug":
        return {"id": "schreiben", "typ": "werkzeug", "werkzeug": "wlo_create_collection",
                "argumente": {"title": "Physik"}, "freigabe": {"de": "Soll ich das anlegen?"},
                "bei_fehler": "ohne", "weiter": "fertig"}
    # liest nur — kein Repositorium
    return {"id": "schreiben", "typ": "nachricht", "text": {"de": "Hier sind die Angaben."},
            "weiter": "fertig"}


def _ablauf(label: dict[str, str], *, ziel: str = "auftrag",
            text_antworten: list[dict] | None = None) -> AblaufArea:
    frage: dict = {"id": "frage", "typ": "nachricht", "text": {"de": "Wie weiter?"},
                   "optionen": [{"id": "knopf", "label": label, "ziel": "schreiben"},
                                {"id": "anders", "label": {"de": "Ohne Metadaten weiter",
                                                           "en": "Continue without metadata"},
                                 "ziel": "ohne"}],
                   "kein_treffer": _KEIN_TREFFER}
    if text_antworten is not None:
        frage["text_antworten"] = text_antworten
    return AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": False,
        "ausloeser": [{"art": "knopf"}], "voraussetzungen": ["anmeldung"],
        "schritte": [frage, _ziel(ziel),
                     {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
                     {"id": "ohne", "typ": "ende", "text": {"de": "Ohne."}}]})


def _nichtssagend(ablauf: AblaufArea, lang: str = "de") -> list[tuple[int | None, str]]:
    """Die Befunde ``knopf_nichtssagend`` — erkannt an allen festen Stücken der Vorlage."""
    stuecke = [x for x in re.split(r"\{[^}]+\}", TEXTE["knopf_nichtssagend"][lang]) if x]
    return [(i, t) for i, t in pruefung.pruefe_gegliedert(ablauf, lang)
            if all(x in t for x in stuecke)]


@pytest.mark.parametrize("label", [
    {"de": "OK"}, {"de": "O.K."}, {"de": "Okay"}, {"de": " Weiter "}, {"de": "Ja!"},
    {"de": "Nein"}, {"de": "Los."}, {"de": "Start"}, {"de": "Go"}, {"de": "Fortfahren"},
    {"de": "Metadaten erzeugen", "en": "Yes"}, {"de": "Metadaten erzeugen", "en": "Next"},
    {"de": "Metadaten erzeugen", "en": "Continue…"}, {"de": "Metadaten erzeugen", "en": "no"},
])
def test_nichtssagender_knopf_vor_einem_auftrag_wird_gemeldet(label):
    befunde = _nichtssagend(_ablauf(label))
    assert len(befunde) == 1
    i, text = befunde[0]
    assert i == 0                                     # am Schritt mit dem Knopf
    assert "frage" in text and "knopf" in text and "schreiben" in text


def test_auch_vor_einem_schreibenden_werkzeug():
    assert len(_nichtssagend(_ablauf({"de": "Ja"}, ziel="werkzeug"))) == 1


@pytest.mark.parametrize("label", [
    {"de": "Ja, Metadaten erzeugen", "en": "Yes, create metadata"},
    {"de": "In WLO ablegen und erschließen", "en": "Store and index in WLO"},
    {"de": "Jahr", "en": "Gopher"},
])
def test_eine_beschriftung_die_sagt_was_geschieht_ist_gut(label):
    assert _nichtssagend(_ablauf(label)) == []


def test_vor_einem_lesenden_schritt_ist_ja_erlaubt():
    assert _nichtssagend(_ablauf({"de": "Ja"}, ziel="nachricht")) == []


def test_ein_text_chip_der_keine_option_trifft_schreibt_nie():
    """Review P5/P6, NIT 6: ein Text-Chip zählt wie getippter Text — trifft er keine Option, führt
    er zum Hinweis ``kein_treffer``, nie zum schreibenden Schritt („Nein“/„No“ erst recht nicht)."""
    chips = [{"label": {"de": "OK", "en": "OK"}}, {"label": {"de": "Nein", "en": "No"}},
             {"label": {"de": "Bin mir nicht sicher"}}]
    assert _nichtssagend(_ablauf({"de": "Metadaten erzeugen"}, text_antworten=chips)) == []


def test_ein_text_chip_der_die_schreibende_option_trifft_wird_gemeldet():
    """Trifft ein nichtssagender Chip über ein Synonym die schreibende Option, wählt er sie."""
    ablauf = _ablauf({"de": "Sammlung anlegen"}, ziel="werkzeug",
                     text_antworten=[{"label": {"de": "Okay"}}])
    ablauf.schritte[0].optionen[0].synonyme = ["okay"]
    befunde = _nichtssagend(ablauf)
    assert len(befunde) == 1 and "Okay" in befunde[0][1] and "text_antworten" in befunde[0][1]


def test_text_chips_vor_lesenden_schritten_bleiben_frei():
    chips = [{"label": {"de": "OK"}}]
    assert _nichtssagend(_ablauf({"de": "Weiter lesen"}, ziel="nachricht",
                                 text_antworten=chips)) == []


def test_der_befund_folgt_der_sprache_des_studios():
    de = _nichtssagend(_ablauf({"de": "OK"}), "de")
    en = _nichtssagend(_ablauf({"de": "OK"}), "en")
    assert len(de) == len(en) == 1 and de[0][1] != en[0][1]
    assert set(TEXTE["knopf_nichtssagend"]) == {"de", "en"}


@pytest.mark.parametrize("pfad", [*_SEEDS, *_BEISPIELE], ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_werkseeds_und_beispiele_haben_keine_nichtssagenden_knoepfe(pfad):
    ablauf = AblaufArea.model_validate(yaml.safe_load(pfad.read_text(encoding="utf-8")))
    assert _nichtssagend(ablauf) == []


# ── Review P5/P6, MINOR 4: Knöpfe, die über Verzweigungen zum schreibenden Schritt führen ──────

def _ueber(weiche: list[dict], label: dict[str, str] | None = None) -> AblaufArea:
    """Der Knopf führt zur ersten Verzweigung in ``weiche``; ``schreiben`` schreibt ins Repo."""
    frage = {"id": "frage", "typ": "nachricht", "text": {"de": "Wie weiter?"},
             "optionen": [{"id": "knopf", "label": label or {"de": "OK"}, "ziel": weiche[0]["id"]},
                          {"id": "anders", "label": {"de": "Ohne Metadaten weiter"},
                           "ziel": "ohne"}],
             "kein_treffer": _KEIN_TREFFER}
    return AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": False,
        "ausloeser": [{"art": "knopf"}], "voraussetzungen": ["anmeldung"],
        "schritte": [frage, *weiche, _ziel("auftrag"),
                     {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
                     {"id": "ohne", "typ": "ende", "text": {"de": "Ohne."}}]})


def _weiche(sid: str, dann: str, sonst: str) -> dict:
    return {"id": sid, "typ": "verzweigung", "weiter": [
        {"wenn_wert": {"quelle": "teil.start.x", "vergleich": "vorhanden"}, "dann": dann},
        {"sonst": sonst}]}


def test_ein_knopf_vor_einer_verzweigung_zum_schreibenden_schritt_wird_gemeldet():
    befunde = _nichtssagend(_ueber([_weiche("weg", "schreiben", "ohne")]))
    assert len(befunde) == 1
    assert befunde[0][0] == 0 and "knopf" in befunde[0][1] and "schreiben" in befunde[0][1]


def test_auch_ueber_mehrere_verzweigungen_und_den_sonst_zweig():
    weiche = [_weiche("weg1", "ohne", "weg2"), _weiche("weg2", "ohne", "schreiben")]
    assert len(_nichtssagend(_ueber(weiche))) == 1


def test_ein_kreis_aus_verzweigungen_ohne_schreibenden_schritt_bleibt_frei():
    weiche = [_weiche("weg1", "weg2", "ohne"), _weiche("weg2", "weg1", "ohne")]
    assert _nichtssagend(_ueber(weiche)) == []


def test_eine_nachricht_dazwischen_wird_durchlaufen():
    """Zweites Review P4–P6, NIT 3: eine Nachricht ohne Wahl wartet nicht — „OK“ → Hinweis →
    schreibender Schritt schreibt ohne weitere Frage; der Knopf wird gemeldet."""
    zwischen = {"id": "erklaerung", "typ": "nachricht", "text": {"de": "Gleich geht es los."},
                "weiter": "schreiben"}
    befunde = _nichtssagend(_ueber([_weiche("weg", "erklaerung", "ohne"), zwischen]))
    assert len(befunde) == 1 and befunde[0][0] == 0 and "schreiben" in befunde[0][1]


def test_eine_nachricht_direkt_nach_dem_knopf_wird_durchlaufen():
    zwischen = {"id": "erklaerung", "typ": "nachricht", "text": {"de": "Gleich geht es los."},
                "weiter": "schreiben"}
    assert len(_nichtssagend(_ueber([zwischen]))) == 1


def test_eine_frage_dazwischen_unterbricht_die_kette():
    """Ein Schritt, der auf die Person wartet (hier eine weitere Frage), sagt selbst, was folgt —
    gemeldet wird dann nur ihr eigener Knopf, wenn er nichtssagend ist (hier nicht)."""
    zwischen = {"id": "nochmal", "typ": "nachricht", "text": {"de": "Wirklich?"},
                "optionen": [{"id": "gut", "label": {"de": "Metadaten erzeugen"},
                              "ziel": "schreiben"}],
                "kein_treffer": _KEIN_TREFFER}
    assert _nichtssagend(_ueber([_weiche("weg", "nochmal", "ohne"), zwischen])) == []


def test_eine_gute_beschriftung_vor_der_verzweigung_ist_frei():
    weiche = [_weiche("weg", "schreiben", "ohne")]
    assert _nichtssagend(_ueber(weiche, {"de": "In WLO ablegen und erschließen"})) == []
