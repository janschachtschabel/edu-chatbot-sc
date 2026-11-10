"""Paket AS-0: die Laufzeit liest jeden Ablauf aus seinem Dokument (``06-ablaeufe/<id>``).

- Gelesen werden alle Dokumente unter ``06-ablaeufe/``, in fester Reihenfolge (nach Schlüssel) —
  „der erste passende gewinnt“ bei Wendungen bleibt so stabil.
- Ein kaputtes Dokument wird übersprungen, die anderen gelten.
- Die **Fassung** eines Laufs (Prüfsumme der Schritte) ist für denselben Ablauf vor und nach der
  Umstellung gleich: ein vor AS-0 begonnener Lauf läuft weiter.
- Zwei aktive Abläufe mit derselben Wendung: „Prüfen“ warnt.
"""

from __future__ import annotations

import pathlib

import yaml

from boerdi.domain.config_models import AREA_MODELS, GESTRICHENE_BEREICHE, model_for
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser, pruefung
from boerdi.services.ablauf.treiber import fassung

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"


def _ablauf(kennung: str, **mehr) -> dict:
    return {"id": kennung, "titel": {"de": kennung}, "aktiv": True,
            "ausloeser": [{"art": "knopf"}],
            "schritte": [{"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}], **mehr}


def _dokumente(monkeypatch, dokumente: dict[str, object]) -> None:
    monkeypatch.setattr(ausloeser, "cached_keys", lambda prefix="": sorted(
        k for k in dokumente if k.startswith(prefix)))
    monkeypatch.setattr(ausloeser, "area", lambda key: dokumente.get(key) or {})


def test_der_ordner_hat_ein_modell_und_der_alte_katalog_ist_gestrichen():
    assert model_for("06-ablaeufe/lesen") is AblaufArea
    assert "06-ablaeufe/katalog" not in AREA_MODELS
    assert "06-ablaeufe/katalog" in GESTRICHENE_BEREICHE


def test_alle_dokumente_gelten_in_fester_reihenfolge(monkeypatch):
    _dokumente(monkeypatch, {
        "06-ablaeufe/zeta": _ablauf("zeta"),
        "06-ablaeufe/alpha": _ablauf("alpha"),
        "01-base/policy": {"rules": []},
    })
    assert [a.id for a in ausloeser.katalog()] == ["alpha", "zeta"]
    assert ausloeser.laden("zeta").id == "zeta"


def test_ein_kaputtes_dokument_wird_uebersprungen(monkeypatch):
    _dokumente(monkeypatch, {
        "06-ablaeufe/alpha": _ablauf("alpha"),
        "06-ablaeufe/kaputt": {"id": "kaputt", "schritte": "kein Liste"},
        "06-ablaeufe/leer": None,
    })
    assert [a.id for a in ausloeser.katalog()] == ["alpha"]


def test_die_fassung_eines_laufs_bleibt_beim_umzug_gleich():
    """Der Seed vor AS-0 (Katalog mit Liste) und danach (ein Dokument je Ablauf) beschreiben
    denselben Ablauf — die Fassung, an der ein wartender Lauf hängt, ist dieselbe."""
    dokument = yaml.safe_load((_SEEDS / "sammlungsstruktur.yaml").read_text(encoding="utf-8"))
    vorher = yaml.safe_load(_KATALOG_VOR_AS0)["ablaeufe"][0]
    assert fassung(AblaufArea.model_validate(dokument)) == fassung(
        AblaufArea.model_validate(vorher))
    assert not (_SEEDS / "katalog.yaml").exists()


def test_pruefen_warnt_bei_derselben_wendung_in_zwei_aktiven_ablaeufen(monkeypatch):
    text = [{"art": "text", "wendungen": ["Themenbaum bauen"]}]
    _dokumente(monkeypatch, {
        "06-ablaeufe/alpha": _ablauf("alpha", ausloeser=text),
        "06-ablaeufe/beta": _ablauf("beta", ausloeser=text),
        "06-ablaeufe/gamma": _ablauf("gamma", aktiv=False, ausloeser=text),
    })
    neu = AblaufArea.model_validate(_ablauf("delta", ausloeser=[
        {"art": "text", "wendungen": ["themenbaum  BAUEN", "etwas anderes"]}]))
    warnungen = pruefung.wendungs_warnungen(neu, ausloeser.katalog(), "de")
    assert len(warnungen) == 1
    assert "themenbaum bauen" in warnungen[0] and "alpha" in warnungen[0] and "beta" in warnungen[0]
    # sich selbst zählt ein Ablauf nicht, ein inaktiver nicht
    [eigene] = pruefung.wendungs_warnungen(ausloeser.laden("alpha"), ausloeser.katalog(), "de")
    assert "beta" in eigene and "alpha" not in eigene
    assert pruefung.wendungs_warnungen(neu.model_copy(update={"aktiv": False}),
                                       ausloeser.katalog(), "de") == []


def test_pruefen_warnt_auch_bei_ineinander_enthaltenen_wendungen(monkeypatch):
    """Review AS-0, Befund 5: ``per_text`` sucht Teilzeichenketten — „themenbaum“ startet auch bei
    „themenbaum aus meinem ordner“; die Warnung kennt dieselbe Regel."""
    _dokumente(monkeypatch, {"06-ablaeufe/alpha": _ablauf("alpha", ausloeser=[
        {"art": "text", "wendungen": ["Themenbaum"]}])})
    lang = AblaufArea.model_validate(_ablauf("beta", ausloeser=[
        {"art": "text", "wendungen": ["themenbaum aus meinem ordner", "ganz anders"]}]))
    [warnung] = pruefung.wendungs_warnungen(lang, ausloeser.katalog(), "de")
    assert "themenbaum aus meinem ordner" in warnung and "alpha" in warnung


#: Der Seed ``06-ablaeufe/katalog.yaml`` vor AS-0 (Stand main 2ea4839), nur der Ablauf.
_KATALOG_VOR_AS0 = """
ablaeufe:
  - id: sammlungsstruktur
    titel: {de: Themenbaum aus Ordnern, en: Topic tree from folders}
    beschreibung: Die Person erfasst einen Ordner; daraus entsteht ein bearbeitbarer
      Themenbaum-Entwurf.
    wann: [Die Person will aus eigenen Ordnern eine Sammlungsstruktur bauen]
    aktiv: false
    ausloeser:
      - {art: knopf}
      - {art: agent}
      - {art: text, wendungen: [themenbaum aus meinem ordner, themenbaum aus meinen ordnern]}
    schritte:
      - id: erfassen
        typ: modul
        modul: ui_upload
        text: {de: "Wähle den Ordner mit deinen Unterlagen.",
               en: "Choose the folder with your materials."}
        daten: {zweck: sammlungsstruktur}
      - id: entwurf
        typ: werkzeug
        werkzeug: strukturentwurf_aus_ordnern
        argumente: {struktur: {$teil: structure}}
        schreibt: draft
        bei_fehler: ohne_ordner
      - id: bearbeiten
        typ: modul
        modul: ui_strukturentwurf
        text: {de: "So sieht deine Ordnerstruktur als Themenbaum aus. Du kannst ihn hier
                    bearbeiten.",
               en: "This is your folder structure as a topic tree. You can edit it here."}
        daten: {$teil: draft}
      - id: ende
        typ: ende
        text: {de: "Dein Entwurf ist gespeichert.", en: "Your draft is saved."}
      - id: ohne_ordner
        typ: ende
        text: {de: "Ohne Unterordner gibt es noch keinen Themenbaum.",
               en: "Without subfolders there is no topic tree yet."}
"""


def test_testfaelle_nehmen_den_ablauf_nicht_aus_der_laufzeit(monkeypatch):
    """Querschnitts-Review AS-0…AS-2, Befund 4: die Laufzeit liest ``tests`` nie — ein Testteil,
    der nicht (mehr) zum Modell passt, lässt den Ablauf trotzdem laufen."""
    from boerdi.services.ablauf import ausloeser

    roh = _ablauf("mit_tests")
    roh["tests"] = "kein Testfall"
    monkeypatch.setattr(ausloeser, "cached_keys", lambda praefix: ["06-ablaeufe/mit_tests"])
    monkeypatch.setattr(ausloeser, "area", lambda key: roh)
    assert [a.id for a in ausloeser.katalog()] == ["mit_tests"]
