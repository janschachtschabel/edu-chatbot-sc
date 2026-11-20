"""Plan 2026-11-16, TG-2, zweites Review: was im Vorgang **nutzbar** bereitliegt (Dienst
``bereitgestellt``), Schnellantworten, die Teile verwerfen (``verwirft``), und die Leiste der
beiden Abläufe, die Bereitgestelltes übernehmen.

- ``bereitgestellt`` meldet ein Dokument nur als lesbar, wenn es das lesbare Dokument der Sitzung
  ist, und Ordner mit der Zahl ihrer Unterordner (MINOR 4/5).
- ``verwirft`` entfernt Teile, bevor der Ablauf weitergeht — sonst nähme „Andere wählen“ still
  das abgelehnte Dokument (MAJOR 1).
- Die Leiste springt nicht: Die Prüfung steht vor dem Einstieg, es gibt keinen Zwischenschritt
  „übernehmen“ mehr (MINOR 6).
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.i18n import bot_text
from boerdi.services.ablauf import simulation, treiber, typen, werkzeuge
from boerdi.services.ablauf.pruefung import pruefe
from tests.leiste_halte import leiste, ohne_sprung

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"
_DOK = {"ref": "dokument:11111111-1111-4111-8111-111111111111", "name": "Rahmenlehrplan.pdf",
        "format": "pdf", "befund": {}}
_ORDNER = {"struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 4, "kinder": [
    {"name": "Optik", "dateien": 2, "alle_dateien": 2, "kinder": []},
    {"name": "Mechanik", "dateien": 2, "alle_dateien": 2, "kinder": []}]},
    "zahlen": {"ordner": 3, "inhalte": 4}}


def _seed(name: str) -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(
        (_SEEDS / f"{name}.yaml").read_text(encoding="utf-8")))


def _bereit(teile: dict, dokument_id=None, sprache="de"):
    async def lader(name):
        return teile.get(name)

    async def kennung():
        return dokument_id

    kontext = werkzeuge.DienstKontext(teile=lader, sprache=sprache,
                                      dokument_id=None if dokument_id is False else kennung)
    return asyncio.run(werkzeuge.DIENSTE["bereitgestellt"]({}, kontext))


# ── Dienst ``bereitgestellt`` (MINOR 4/5) ────────────────────────────────────────────────────────

#: Durchtest Paket K (19.11.): ``bereit`` sagt, warum es „gründlich“ nicht gibt — ohne Angabe, ob
#: eine Anmeldung hülfe (drittes Review), „gerade nicht verfügbar“.
_OHNE_GRUENDLICH = bot_text("de", "action.ablauf.gruendlichNichtDa")


def test_ohne_teile_liegt_nichts_bereit():
    # TG-3a: dazu die Zahl der Dateien mit Namen (Teil ``struktur``); TG-3e: Strukturdokumente;
    # TG-6: was ein Ablauf übernehmen kann (``art``, ``name``) und ob die Ablage angeboten ist
    assert _bereit({}) == {"dokument": None, "ordner": None, "dateien": 0, "inhaltsdateien": 0,
                           "strukturdokumente": [], "lesbare_strukturdokumente": 0,
                           "art": None, "name": None, "wlo_ablage": False,
                           "wlo_erschliessen": False, "ohne_gruendlich": _OHNE_GRUENDLICH}


def test_ein_dokument_ist_nur_lesbar_wenn_es_das_der_sitzung_ist():
    lesbar = _bereit({"document": _DOK}, dokument_id="11111111-1111-4111-8111-111111111111")
    assert lesbar["dokument"] == {"name": "Rahmenlehrplan.pdf", "lesbar": True}
    fremd = _bereit({"document": _DOK}, dokument_id="22222222-2222-4222-8222-222222222222")
    assert fremd["dokument"] == {"name": "Rahmenlehrplan.pdf", "lesbar": False}
    assert _bereit({"document": _DOK}, dokument_id=None)["dokument"]["lesbar"] is False
    # ohne Prüfmöglichkeit (Simulation) gilt das Dokument im Vorgang als lesbar
    assert _bereit({"document": _DOK}, dokument_id=False)["dokument"]["lesbar"] is True


def test_ordner_mit_der_zahl_ihrer_unterordner():
    assert _bereit({"structure": _ORDNER})["ordner"] == {"name": "Physik", "unterordner": 2}
    flach = {"struktur": {"name": "", "dateien": 3, "alle_dateien": 3, "kinder": []}}
    assert _bereit({"structure": flach})["ordner"] == {"name": "Auswahl", "unterordner": 0}
    assert _bereit({"structure": flach}, sprache="en")["ordner"]["name"] == "selection"


def test_ein_kaputter_teil_liegt_nicht_bereit():
    assert _bereit({"document": "kaputt", "structure": {"struktur": "x"},
                    "struktur": {"struktur": "x"}, "strukturdokument": "x"}) == {
        "dokument": None, "ordner": None, "dateien": 0, "inhaltsdateien": 0,
        "strukturdokumente": [], "lesbare_strukturdokumente": 0, "art": None, "name": None,
        "wlo_ablage": False, "wlo_erschliessen": False, "ohne_gruendlich": _OHNE_GRUENDLICH}


def test_bereitgestellt_ist_ein_bekannter_reiner_dienst_mit_eigenem_typ():
    assert werkzeuge.bekannt("bereitgestellt") and "bereitgestellt" in werkzeuge.REINE_DIENSTE
    assert typen.dienst_typ("bereitgestellt") == "wlo.bereit@1"



def test_die_kurzbeschreibung_nennt_was_bereitliegt():
    """Die Zeile unter „Gesammelte Daten“ (Leiste) — nicht der Typname des Werts."""
    kurz = werkzeuge.ZUSAMMENFASSUNG["bereitgestellt"]
    assert kurz({"dokument": {"name": "Lehrplan.pdf", "lesbar": True},
                 "ordner": {"name": "Physik", "unterordner": 2}}) == (
        "Dokument „Lehrplan.pdf“, Ordner „Physik“")
    assert kurz({"dokument": {"name": "Alt.pdf", "lesbar": False}, "ordner": None}) == "—"
    assert kurz({"dokument": None, "ordner": None}) == "—"

# ── ``verwirft`` an einer Schnellantwort (MAJOR 1) ───────────────────────────────────────────────

def _mit_verwirft(verwirft) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "frage", "typ": "nachricht", "text": {"de": "Welches?"}, "optionen": [
                {"id": "neu", "label": {"de": "Neu"}, "ziel": "pruefen",
                 **({"verwirft": verwirft} if verwirft is not None else {})},
                {"id": "alt", "label": {"de": "Alt"}, "ziel": "pruefen"}]},
            {"id": "pruefen", "typ": "verzweigung", "weiter": [
                {"wenn_teil": "document", "dann": "mit"}, {"sonst": "ohne"}]},
            {"id": "mit", "typ": "ende", "text": {"de": "mit"}},
            {"id": "ohne", "typ": "ende", "text": {"de": "ohne"}}]})


def test_verwirft_ist_ohne_angabe_nicht_gesetzt_und_aendert_die_fassung_nicht():
    ohne, leer = _mit_verwirft(None), _mit_verwirft([])
    assert ohne.schritte[0].optionen[0].verwirft is None
    assert leer.schritte[0].optionen[0].verwirft is None
    assert treiber.fassung(ohne) == treiber.fassung(leer)


def _wahl(ablauf: AblaufArea, option: str) -> AblaufTest:
    return AblaufTest.model_validate({
        "name": "t", "teile": {"document": _DOK}, "eingaben": [{"bei": "frage", "option": option}]})


def test_die_wahl_verwirft_den_teil_bevor_es_weitergeht():
    ablauf = _mit_verwirft(["document"])
    neu = asyncio.run(simulation.testen(ablauf, _wahl(ablauf, "neu")))
    assert neu.weg == ["frage", "pruefen", "ohne"]
    alt = asyncio.run(simulation.testen(ablauf, _wahl(ablauf, "alt")))
    assert alt.weg == ["frage", "pruefen", "mit"]


def test_der_treiber_meldet_die_verworfenen_teile():
    ablauf = _mit_verwirft(["document"])

    async def lader(name):
        return _DOK if name == "document" else None

    lauf = {"ablauf": "probe", "fassung": treiber.fassung(ablauf), "schritt": "frage",
            "status": treiber.WARTET_WAHL}
    aus = asyncio.run(treiber.weiter_wahl(ablauf, lauf, "neu", None, treiber.Umgebung(teile=lader)))
    # Review TG-3a–c, R3-5: mit dem Alias-Partner
    assert aus is not None and aus.verworfen == ["document", "strukturdokument"]
    assert aus.lauf["schritt"] == "ohne"


@pytest.mark.parametrize(("verwirft", "befund"), [
    (["document"], False),
    (["gibt_es_nicht"], True),
    # Nachprüfung TG-2, 5: ``ablage`` verweist auf Knoten im Repositorium — nie verwerfen
    (["ablage"], True),
])
def test_die_pruefung_kennt_nur_teile_die_der_ablauf_kennt(verwirft, befund):
    ablauf = _mit_verwirft(verwirft)
    roh = ablauf.model_dump(mode="json", exclude_none=True)
    # ein Upload-Schritt schreibt ``document`` (sonst wäre schon das ein Befund)
    roh["schritte"].insert(1, {"id": "laden", "typ": "modul", "modul": "ui_upload",
                               "text": {"de": "Wähle."}, "daten": {"zweck": "bereitstellen"}})
    roh["schritte"][0]["optionen"][0]["ziel"] = "laden"
    befunde = pruefe(AblaufArea.model_validate(roh))
    assert any("verwirft" in b or "verwerfen" in b for b in befunde) is befund, befunde


def test_nachpruefung_5_repositorium_teile_sind_nicht_verwerfbar():
    from boerdi.services.ablauf import pruefung_texte

    assert "ablage" in typen.NICHT_VERWERFBAR
    assert set(pruefung_texte._T["verwirft_repo"]) == {"de", "en"}
    befunde = pruefe(_mit_verwirft(["ablage"]))
    assert any("Repositori" in b and "ablage" in b for b in befunde), befunde
    assert any("repository" in b for b in pruefe(_mit_verwirft(["ablage"]), lang="en"))


# ── Seeds: Prüfung, Platzhalter, Leiste (MINOR 6) ────────────────────────────────────────────────
# Plan 2026-11-20, G1: „aus einem Dokument“ und „aus Ordnern“ sind nicht mehr im Werk — dieselben
# Regeln am generischen Seed, der ihre Wege (Dokument, Ordner, Dateien) und Einstiege übernimmt.

@pytest.mark.parametrize("name", ["themenbaum"])
def test_die_seeds_pruefen_zuerst_was_bereitliegt(name):
    ablauf = _seed(name)
    assert pruefe(ablauf) == []          # auch der Platzhalter {teil.bereit.…} ist zulässig
    assert [s.id for s in ablauf.schritte[:2]] == ["bereit", "vorhanden"]
    assert ablauf.schritte[0].werkzeug == "bereitgestellt"
    assert "uebernehmen" not in {s.id for s in ablauf.schritte}


# Plan 2026-11-16, Review TG-4–6, Befund 10: die Leiste zählt die Halte des Laufs — Werkzeuge wie
# ``bereitgestellt`` und Verzweigungen zählen nicht, der Einstieg ist Schritt 1.

@pytest.mark.parametrize(("name", "fall"), [
    ("themenbaum", "Thema getippt bis zum Entwurf"),
    ("themenbaum", "Ordner, anonym, so lassen"),
])
def test_ohne_daten_zaehlt_die_leiste_ohne_sprung(monkeypatch, name, fall):
    halte = leiste(monkeypatch, _seed(name), fall)
    ohne_sprung(halte)                                                   # 1, 2, 3, … ohne Lücke
    assert halte[0][0] == "einstieg"


@pytest.mark.parametrize(("name", "fall"), [
    ("themenbaum", "Dokument schon gelesen, verwenden"),
    ("themenbaum", "Dateien schon erfasst, verwenden, anonym"),
])
def test_mit_daten_steht_der_einstieg_an_derselben_stelle(monkeypatch, name, fall):
    halte = leiste(monkeypatch, _seed(name), fall)
    ohne_sprung(halte)
    assert halte[0][:2] == ("einstieg_mit", 1)                           # wie ``einstieg``
