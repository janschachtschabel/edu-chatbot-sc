"""Review TW-4, Befunde 1 und 11: die echten Themenbaum-Seeds lösen richtig aus.

Alle Abläufe aus ``seeds/06-ablaeufe`` sind hier eingeschaltet, wie im Betrieb. Geprüft werden:

- **Wendungen:** Neuanlagen landen im passenden Ablauf, auch in natürlicher Satzstellung.
  „Überarbeiten“, „zusammenfassen“ und Wissensfragen starten nichts.
- **Modul-Auslöser:** Die Antwort „Themenbaum aus dem Strukturdokument“ startet den
  Dokument-Ablauf an ``gelesen``, ein bloßes „Senden“ (erfasst) startet nichts.
- **Direktstart:** Nur der Ablauf ohne Schreiben startet über die KI direkt.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser, vorschlag

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "seeds" / "06-ablaeufe"


@pytest.fixture
def alle_an(monkeypatch):
    ablaeufe = []
    for datei in sorted(SEEDS.glob("*.yaml")):
        roh = yaml.safe_load(datei.read_text(encoding="utf-8"))
        roh.pop("tests", None)
        ablaeufe.append(AblaufArea.model_validate({**roh, "aktiv": True}))
    monkeypatch.setattr(ausloeser, "katalog", lambda: ablaeufe)
    monkeypatch.setattr(ausloeser, "laden",
                        lambda k: next((a for a in ablaeufe if a.id == k), None))
    return {a.id: a for a in ablaeufe}


@pytest.mark.parametrize(("satz", "erwartet"), [
    ("Bitte einen Themenbaum aus einem Thema", "themenbaum_aus_thema"),
    ("ich will einen themenbaum zu einem thema erstellen", "themenbaum_aus_thema"),
    # Zweites Review TW, Befund 2: allgemeine Neuanlagen entscheidet die KI (sie sieht
    # ``nicht_wann``), die Quelle in der Bitte führt zum passenden Ablauf
    ("Erstelle einen Themenbaum zu Karate", None),
    ("Kannst du einen neuen Themenbaum für Physik anlegen?", None),
    ("Wie kann ich einen Themenbaum erstellen?", None),
    ("Erstelle einen Themenbaum aus diesem PDF", "themenbaum_aus_dokument"),
    ("Erstelle einen Themenbaum aus dem Bildungsplan Biologie", "themenbaum_aus_dokument"),
    ("Erstelle einen Themenbaum aus meinen Materialien", "themenbaum_aus_inhalten"),
    ("Mach mir einen Themenbaum aus meinen Unterlagen", "themenbaum_aus_inhalten"),
    ("Kannst du aus meinen Dateien einen Themenbaum erstellen?", "themenbaum_aus_inhalten"),
    ("Bitte einen Themenbaum aus meinen Inhalten", "themenbaum_aus_inhalten"),
    # Rückmeldung 11.11.: „mit“ statt „aus“
    ("Themenbaum mit Dateien erstellen", "themenbaum_aus_inhalten"),
    ("Ich möchte einen Themenbaum mit meinen Dateien bauen", "themenbaum_aus_inhalten"),
    # zusammenhängend — „Aus meinem Lehrplan bitte einen …“ trennt die Wendung, das übernimmt
    # der KI-Weg (``nicht_wann``)
    ("Aus meinem Lehrplan einen Themenbaum erstellen", "themenbaum_aus_dokument"),
    ("Mach einen Themenbaum aus dem Dokument", "themenbaum_aus_dokument"),
    # Nach-Review: „zu meinem Lehrplan“ traf auch „Ich habe schon einen Themenbaum zu meinem
    # Lehrplan, kannst du ihn prüfen?“ — das entscheidet jetzt die KI
    ("Ich habe schon einen Themenbaum zu meinem Lehrplan, kannst du ihn prüfen?", None),
    ("Themenbaum aus dem Rahmenlehrplan", "themenbaum_aus_dokument"),
    # Querschnitts-Review TW, Befund 1: Bestand, Überarbeiten und Wissen starten nichts — und
    # „einen Themenbaum zu X erstellen“ entscheidet die KI (direkt)
    ("Gibt es in WLO einen Themenbaum für Chemie?", None),
    ("Zeig mir einen Themenbaum für das Fachportal Physik", None),
    ("Hat WLO schon einen Themenbaum zu Optik?", None),
    ("ich würde gern einen themenbaum zu Karate erstellen", None),
    ("Bitte den Themenbaum überarbeiten", None),
    ("Kannst du den Themenbaum zusammenfassen?", None),
    ("Was ist ein Themenbaum für Lehrkräfte?", None),
])
def test_wendungen_der_seeds(alle_an, satz, erwartet):
    treffer = ausloeser.per_text(satz)
    assert (treffer.id if treffer else None) == erwartet


def test_der_modul_ausloeser_des_dokument_ablaufs(alle_an):
    grund = {"struktur": {"name": "RLP", "dateien": 1, "alle_dateien": 1, "kinder": []},
             "zahlen": {"ordner": 1, "inhalte": 1}}
    dokument = {"modul": "ui_upload", "block_id": "b", "daten": {
        **grund, "aktion": "dokument", "dokument": {
            "upload_id": "11111111-1111-4111-8111-111111111111", "name": "RLP.pdf",
            "format": "pdf", "ziel": "themenbaum", "befund": {}, "vorschau": []}}}
    ablauf, ab = ausloeser.per_modul(dokument)
    assert ablauf.id == "themenbaum_aus_dokument" and ablauf.schritte[ab].id == "gelesen"
    erfasst = {"modul": "ui_upload", "block_id": "b", "daten": {**grund, "aktion": "erfasst"}}
    assert ausloeser.per_modul(erfasst) is None


def test_nur_der_ablauf_ohne_schreiben_startet_direkt(alle_an):
    assert vorschlag._direkt(alle_an["themenbaum_aus_thema"])
    assert not vorschlag._direkt(alle_an["themenbaum_aus_inhalten"])
    assert not vorschlag._direkt(alle_an["themenbaum_aus_dokument"])


def test_review_qtw_2_keine_beschreibung_wird_gekuerzt(alle_an, monkeypatch):
    """Querschnitts-Review TW, Befund 2: ``wann``/``nicht_wann`` aller Seeds kommen ganz an."""
    monkeypatch.setattr(ausloeser, "erfuellt", lambda _a: True)
    for werkzeug in vorschlag.werkzeuge("de"):
        assert "…" not in werkzeug["function"]["description"], werkzeug["function"]["name"]


def test_review_qtw_5_im_muster_weg_kommen_die_module_des_schritts_dazu(alle_an):
    from boerdi.services.ablauf import ki_schritt
    from boerdi.ui_module.namen import UI_WERKZEUGE_KEY

    schritt = next(s for s in alle_an["themenbaum_aus_thema"].schritte if s.id == "entwurf")
    neu = ki_schritt.mit_schrittmodulen({UI_WERKZEUGE_KEY: ["ui_upload"], "id": "M01"}, schritt)
    assert neu[UI_WERKZEUGE_KEY] == ["ui_upload", "ui_strukturentwurf"] and neu["id"] == "M01"
    ohne = next(s for s in alle_an["themenbaum_aus_thema"].schritte if s.id == "wofuer")
    assert ki_schritt.mit_schrittmodulen({"id": "M01"}, ohne) == {"id": "M01"}
    # Zweites Review TW, Befund 3: ein fehlender Slot des Musters leerte sonst die Werkzeuge
    # (``response_prompt_builder``: degradation und missing_slots → keine Werkzeuge)
    roh = {"id": "M01", "degradation": True, "missing_slots": ["thema"]}
    neu = ki_schritt.mit_schrittmodulen(roh, schritt)
    assert not (neu.get("degradation") and neu.get("missing_slots"))
    assert neu["tools"] == [] and neu[UI_WERKZEUGE_KEY] == ["ui_strukturentwurf"]  # keine Suche
    assert roh["degradation"] is True                   # das Muster selbst bleibt unberührt


def test_review_qtw_9_der_muster_weg_laesst_den_abgelehnten_aus(alle_an, monkeypatch):
    from boerdi.services import generate

    monkeypatch.setattr(ausloeser, "erfuellt", lambda _a: True)
    state = {"entities": {}, "turn_count": 1}
    from boerdi.services.ablauf import zug_basis

    zug_basis.ausstieg_merken(state, "themenbaum_aus_thema")
    assert generate._abgelehnt(state) == "themenbaum_aus_thema"
    namen = [w["function"]["name"] for w in vorschlag.werkzeuge(
        "de", ohne=generate._abgelehnt(state))]
    assert "ablauf-themenbaum_aus_thema" not in namen and namen



def test_rueckmeldung_ohne_anmeldung_sagt_die_ki_es_statt_still(alle_an, monkeypatch):
    """Nutzer-Entscheid 11.11. „Hinweis + weiterhelfen“: passt die Wendung zu einem Ablauf mit
    fehlender Anmeldung, startet er nicht — die KI bekommt eine Zeile und sagt es in einem Satz."""
    from boerdi.services.ablauf import zug

    satz = "Themenbaum mit meinen Dateien erstellen"
    monkeypatch.setattr(ausloeser, "erfuellt", lambda _a: False)
    assert zug.text_ausloeser(satz) is None
    zeile = zug.anmelde_zeile(satz, "de")
    assert zeile and zeile.startswith("[ABLAUF OHNE ANMELDUNG") and "aus eigenen Inhalten" in zeile
    assert zug.anmelde_zeile(satz, "de", ohne="themenbaum_aus_inhalten") is None
    assert zug.anmelde_zeile("Was ist Photosynthese?", "de") is None
    monkeypatch.setattr(ausloeser, "erfuellt", lambda _a: True)
    assert zug.anmelde_zeile(satz, "de") is None          # angemeldet: der Ablauf startet selbst
