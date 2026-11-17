"""Plan 2026-11-16, zweites Review TG-4–6: Freitext vor Synonymen, die Gesamtzahl der Leiste, eine
echte Rückfrage, Wortformen der Grundlage, Stufe und Thema, Direktstart, „Nochmal“ und die Ablage
der jetzigen Auswahl.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import simulation, treiber, vergleich, vorschlag, werkzeuge
from boerdi.services.ablauf import vorbelegung as vb
from tests.leiste_halte import leiste

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"


def _seed(name: str = "themenbaum") -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(
        (_SEEDS / f"{name}.yaml").read_text(encoding="utf-8")))


def _schritt(sid: str):
    return next(s for s in _seed().schritte if s.id == sid)


# ── A: an Fragen mit Freitext schlägt ein Satz nicht über ein Synonym die freie Antwort ─────────

@pytest.mark.parametrize(("sid", "text", "erwartet"), [
    ("hinweise", "Keine Atomphysik", None),
    ("hinweise", "Nichts zur Quantenmechanik", None),
    ("hinweise", "Nein, aber bitte Lernfeld 3 ausführlich", None),
    ("hinweise", "nein", "keine"),
    ("hinweise", "Nein.", "keine"),
    ("ordner_weiter", "Passt nicht, bitte verfeinern", None),
    # Nachprüfung TG-4–6, MAJOR 1: Knopf-Fragen ohne Synonyme — nur das Label trifft
    ("ordner_weiter", "passt", None),
    ("ordner_weiter", "So lassen", "lassen"),
    ("wlo_frage", "nicht gründlich, schnell", None),
    ("wlo_frage", "schnell", None),
])
def test_a_nur_der_ganze_text_trifft_ein_synonym(sid, text, erwartet):
    assert treiber.wahl_aus_text(_schritt(sid), text, "de") == erwartet


def test_a_nur_die_grundlage_ordnet_saetze_zu():
    """Das Merkmal ``synonyme_im_satz`` trägt nur die Grundlage; es ändert keine Fassung."""
    ablauf = _seed()
    assert [s.id for s in ablauf.schritte if s.synonyme_im_satz] == ["grundlage"]
    ohne = AblaufArea.model_validate({**ablauf.model_dump(exclude_none=True), "schritte": [
        {**s.model_dump(exclude_none=True), "synonyme_im_satz": False}
        for s in ablauf.schritte]})
    roh = ablauf.model_dump(exclude_none=True)
    for s in roh["schritte"]:
        s.pop("synonyme_im_satz", None)
    assert treiber.fassung(ohne) == treiber.fassung(AblaufArea.model_validate(roh))


# ── D: Wortformen der Grundlage, Verneinung, mehrere Treffer ────────────────────────────────────

@pytest.mark.parametrize(("text", "erwartet"), [
    ("meine Dokumente", "dokument"), ("Lehrpläne", "dokument"), ("die Curricula", "dokument"),
    ("Curriculum Biologie", "dokument"), ("zwei PDFs", "dokument"),
    ("des Kerncurriculums", "dokument"), ("des Bildungsplans", "dokument"),
    ("Materialien", "dateien"), ("meine Unterlagen", "dateien"), ("my documents", "dateien"),
    ("my files", "dateien"), ("my folders", "ordner"),
    # Fehltreffer aus dem Review
    ("Dateien und Ordner (Informatik)", None),
    ("Ich habe keinen Lehrplan, Thema Optik", None),
    ("ohne Ordner, nur Thema Optik", None),
])
def test_d_grundlage_wortformen_und_fehltreffer(text, erwartet):
    assert treiber.wahl_aus_text(_schritt("grundlage"), text, "de") == erwartet


def test_d_andere_grundlage_auch_ohne_entwurf():
    andere = next(o for o in _schritt("ohne_entwurf").optionen if o.id == "andere")
    assert andere.ziel == "grundlage" and "grundlage" in andere.verwirft


# ── B: die Gesamtzahl der Leiste ────────────────────────────────────────────────────────────────

def _hauptweg(ablauf: AblaufArea, name: str, halte) -> bool:
    """Ein Testfall auf dem regulären Weg: kein Schritt zweimal, kein Fehlerweg (``ohne_…``,
    ``bei_fehler``-Ziele), keine wiederholte Frage. Nachprüfung TG-4–6, MINOR 6: der erste Halt
    zählt nicht als Fehlerweg — ``einstieg`` ist zugleich der Ersatzweg von ``bereit`` und der
    reguläre Anfang von „Themenbaum erstellen“."""
    fehler = {s.bei_fehler for s in ablauf.schritte if s.bei_fehler}
    ids = [s for s, _n, _m in halte]
    return (len(ids) == len(set(ids))
            and not any(i.startswith("ohne") or (n > 0 and i in fehler)
                        for n, i in enumerate(ids))
            and [n for _s, n, _m in halte] == list(range(1, len(halte) + 1)))


@pytest.mark.parametrize("name", ["themenbaum", "themenbaum_aus_dokument", "fuehrung"])
def test_b_m_steigt_nie_und_n_bleibt_unter_m(monkeypatch, name):
    ablauf = _seed(name)
    geprueft: list[str] = []
    for t in ablauf.tests:
        halte = leiste(monkeypatch, ablauf, t.name)
        if not halte or not _hauptweg(ablauf, t.name, halte):
            continue
        geprueft.append(t.name)
        ms = [m for _s, _n, m in halte]
        assert all(a >= b for a, b in zip(ms, ms[1:], strict=False)), (t.name, halte)
        assert all(n < m for _s, n, m in halte[:-1]), (t.name, halte)
        assert halte[-1][1] <= halte[-1][2]
    assert len(geprueft) >= 2
    if name == "themenbaum":
        # MINOR 6: der Hauptweg ab ``einstieg`` ist dabei
        assert {"Thema getippt bis zum Entwurf", "Dokument neu lesen lassen"} <= set(geprueft)


def test_b_an_einem_fehlerschritt_zaehlt_der_weg_nach_nochmal_mit(monkeypatch):
    """„Damit komme ich nicht weiter“ ist nicht das Ende: m zählt die Halte nach „Nochmal“."""
    halte = leiste(monkeypatch, _seed(), "Dokument nicht gelesen, nochmal")
    [(_s, n, m)] = [h for h in halte if h[0] == "ohne_daten"]
    assert m > n


# ── C: „Nein“ muss wirklich wegführen ───────────────────────────────────────────────────────────

def _zwei_fragen(b_ziel: str) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "x", "titel": {"de": "X"}, "voraussetzungen": ["anmeldung"],
        "ausloeser": [{"art": "agent", "modus": "direkt"}],
        "schritte": [
            {"id": "q1", "typ": "nachricht", "text": {"de": "Erzeugen?"},
             "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "a"},
                          {"id": "nein", "label": {"de": "Nein"}, "ziel": "q2"}]},
            {"id": "q2", "typ": "nachricht", "text": {"de": "Sicher?"},
             "optionen": [{"id": "doch", "label": {"de": "Doch"}, "ziel": "a"},
                          {"id": "b", "label": {"de": "Zurück"}, "ziel": b_ziel}]},
            {"id": "a", "typ": "auftrag", "flow": "f/x", "repo_schreibt": True, "bei_fehler": "e"},
            {"id": "e", "typ": "ende", "text": {"de": "Fertig."}},
            {"id": "weg", "typ": "ende", "text": {"de": "Ohne."}}]})


def test_c_ein_nein_im_kreis_ist_keine_wahl():
    assert werkzeuge.ablauf_schreibt_ungefragt(_zwei_fragen("q1"))
    assert not werkzeuge.ablauf_schreibt_ungefragt(_zwei_fragen("weg"))


# ── E: Stufe nur als bekanntes Label, getippte Grundlage ist das Thema ──────────────────────────

def _belegt(antworten: dict, ablauf=None) -> dict:
    schritt = next(s for s in _seed().schritte if s.id == "entwurf_thema")

    async def teile(name):
        return antworten.get(name)

    return asyncio.run(vb.vorbelegung(schritt, teile, antworten, "de", ablauf=ablauf))


def test_e_eine_getippte_stufe_wird_eine_hinweiszeile():
    belegt = _belegt({"stufe": "Klasse 7 Gymnasium"})
    assert "bildungsstufe" not in belegt
    assert belegt["hinweise"] == "Für wen/Stufe: Klasse 7 Gymnasium"
    assert _belegt({"stufe": "Grundschule"})["bildungsstufe"] == "Primarstufe"
    assert _belegt({"stufe": "Für alle"}) == {}


def test_e_eine_getippte_grundlage_wird_das_thema():
    ablauf = _seed()
    assert _belegt({"grundlage": "Optik (Physik)"}, ablauf)["thema"] == "Optik (Physik)"
    assert "thema" not in _belegt({"grundlage": "Meine Ordner"}, ablauf)
    assert "thema" not in _belegt({"grundlage": "Optik"})            # ohne Ablauf unbekannt


def test_e_keine_toten_zuordnungen():
    assert "publikum" not in {n for n, _v in vb.ZEILEN}
    geschrieben = {s.schreibt for s in _seed().schritte if s.schreibt}
    geschrieben |= {s.freitext.schreibt for s in _seed().schritte if s.freitext}
    assert {n for n, _v in vb.ZEILEN} | {"umfang", "stufe", vb.GRUNDLAGE} <= geschrieben


# ── I: Platz für die Hinweise der KI ────────────────────────────────────────────────────────────

def test_i_die_hinweise_der_ki_behalten_ihren_platz():
    eigene = {"hinweise": "Hinweise der Person: " + "x" * 590}
    von_ki = "Schwerpunkt Wetter und Wasserkreislauf " * 3
    neu = vb.vorbelegt({"thema": "W", "hinweise": von_ki}, eigene)
    assert len(neu["hinweise"]) <= vb.HINWEISE_ZEICHEN
    assert neu["hinweise"].endswith(von_ki.strip()[:100][-20:]) or von_ki.strip()[:100] in neu[
        "hinweise"]
    assert neu["hinweise"].split("\n")[-1].startswith("Schwerpunkt Wetter")
    assert len(neu["hinweise"].split("\n")[-1]) >= min(len(von_ki.strip()), 150)


# ── F: der Direktstart schließt nichts ohne Klick ──────────────────────────────────────────────

def test_f_direktstart_wird_zum_knopf_wenn_der_start_den_vorgang_schloesse(monkeypatch):
    from boerdi.services.ablauf import ausloeser

    ablauf = _seed()
    monkeypatch.setattr(ausloeser, "vorschlaege", lambda: [ablauf])
    eintrag = [{"ablauf": "themenbaum"}]
    assert vorschlag.direkt_knopf(eintrag, "de", {"teile": {"draft": {}}})
    assert vorschlag.direkt_knopf(eintrag, "de", {"teile": {"ablage": {}}}) is None
    assert vorschlag.direkt_knopf(eintrag, "de",
                                  {"teile": {}, "lauf": {"status": "wartet_wahl"}}) is None
    assert vorschlag.direkt_knopf(eintrag, "de", None)                # ohne Verweis wie bisher


# ── G und H: „Nochmal“ nach bereitgestellten Ordnern, Ablage der jetzigen Auswahl ────────────────

def _fall(**roh) -> AblaufTest:
    return AblaufTest.model_validate({"name": "Probe", **roh})


def test_g_nochmal_ohne_bereitgestellte_ordner_fuehrt_zum_upload():
    ablauf = _seed()
    fall = _fall(ab="daten", teile={"bereit": {"art": "ordner"}},
                 erwartet={"weg": ["daten", "ordner_laden"], "status": "wartet_person"})
    ergebnis = asyncio.run(simulation.testen(ablauf, fall))
    assert ergebnis.ok, ergebnis.abweichungen


_FLACH = {"aktion": "erfasst",
          "struktur": {"name": "U", "dateien": 1, "alle_dateien": 1, "kinder": [],
                       "dateiliste": [{"i": 0, "name": "a.pdf", "endung": "pdf", "groesse": 1,
                                       "rolle": "inhalt"}]},
          "zahlen": {"ordner": 1, "dateien": 1, "inhalte": 1, "ignoriert": 0,
                     "strukturdokumente": 0, "bytes": 1},
          "strukturdokument": None, "warnungen": []}


@pytest.mark.parametrize(("block_id", "weiter"), [
    ("simulationuiupload", "metadaten_frage"),       # dasselbe Feld: die Ablage gehört dazu
    ("einfrueheresfeld01", "dateien_weg"),           # eine frühere Auswahl: nicht zu den Metadaten
])
def test_h_nur_die_ablage_der_jetzigen_auswahl(block_id, weiter):
    ablauf = _seed()
    fall = _fall(ab="ordner_laden", angemeldet=False,
                 teile={"ablage": {"format": "wlo.ablage@1", "block_id": block_id,
                                   "inhalte": []}},
                 eingaben=[{"bei": "ordner_laden", "antwort": _FLACH}])
    ergebnis = asyncio.run(simulation.testen(ablauf, fall))
    assert ergebnis.weg[:3] == ["ordner_laden", "ordner_geladen", weiter], ergebnis.weg


def test_h_ein_wert_kann_eine_andere_stelle_sein():
    teile = {"ablage": {"block_id": "b1"}, "struktur": {"block_id": "b1"}, "x": {"block_id": "b2"}}

    async def lader(name):
        return teile.get(name)

    def greift(soll):
        return asyncio.run(vergleich.greift("teil.ablage.block_id", "gleich", soll, lader))

    assert greift("{teil.struktur.block_id}") and not greift("{teil.x.block_id}")
    assert not greift("{teil.fehlt.block_id}") and greift("b1")
    assert vergleich.wert_quelle("{teil.struktur.block_id}") == ("struktur", "block_id")
