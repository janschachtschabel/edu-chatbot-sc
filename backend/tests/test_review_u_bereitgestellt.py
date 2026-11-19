"""Review Paket U (19.11.) zur Antwort ``bereitgestellt`` — Dubletten (Abstimmung mit der
Oberfläche) und NIT 9 (der Satz nennt den Grund je nicht gelesener Datei).

- Inhaltsgleiche Dateien (gleicher Name, gleiche Größe, gleiche Rolle; verschiedene Ordner) lädt
  die Oberfläche einmal hoch und schickt für alle ihre ``i`` dieselbe ``upload_id``. Das nimmt der
  Server an; ``metadaten`` trägt dann je ``i`` einen Eintrag mit denselben Angaben. Sonst bleibt
  eine doppelte ``upload_id`` abgewiesen.
- Der Rahmen für die KI nennt je nicht gelesener Datei den Grund: Format, zu groß, Grenze der
  Sitzung oder Fehler — Strukturdokumente eingeschlossen.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from boerdi.services import arbeitsstand_teile as at
from boerdi.services.dokumente import metadaten_lokal as ml
from boerdi.ui_module import upload_antwort, upload_rahmen
from boerdi.ui_module import upload_bereitgestellt as bereit

_A = "11111111-1111-4111-8111-111111111111"
_B = "22222222-2222-4222-8222-222222222222"
_MIB = 1024 * 1024


def _struktur(*dateien: dict) -> dict:
    return {"name": "Unterlagen", "dateien": len(dateien), "alle_dateien": len(dateien),
            "kinder": [], "dateiliste": list(dateien)}


def _datei(i: int, name: str, groesse: int = 10, rolle: str = "inhalt") -> dict:
    return {"i": i, "name": name, "endung": name.rsplit(".", 1)[-1], "groesse": groesse,
            "rolle": rolle}


def _antwort(struktur: dict, dateien: list[dict]) -> dict:
    inhalte = sum(1 for d in struktur["dateiliste"] if d["rolle"] == "inhalt")
    strukturen = sum(1 for d in struktur["dateiliste"] if d["rolle"] == "struktur")
    return {"aktion": "bereitgestellt", "ort": "chat", "struktur": struktur,
            "zahlen": {"ordner": 1, "dateien": len(struktur["dateiliste"]), "inhalte": inhalte,
                       "ignoriert": 0, "strukturdokumente": strukturen, "bytes": 10},
            "strukturdokument": None, "warnungen": [], "dateien": dateien}


# ── Dubletten ───────────────────────────────────────────────────────────────────────────────────

def test_inhaltsgleiche_dateien_teilen_eine_upload_id():
    s = _struktur(_datei(0, "Linsen.pdf"), _datei(1, "Linsen.pdf"))
    daten = _antwort(s, [{"i": 0, "rolle": "inhalt", "upload_id": _A},
                         {"i": 1, "rolle": "inhalt", "upload_id": _A}])
    assert bereit.grund(daten, upload_antwort.dateien(s)) is None
    assert upload_antwort.grund(daten) is None


@pytest.mark.parametrize("zweite", [
    _datei(1, "Spiegel.pdf"),                       # anderer Name
    _datei(1, "Linsen.pdf", groesse=11),            # andere Größe
    _datei(1, "Linsen.pdf", rolle="struktur"),      # andere Rolle
])
def test_sonst_bleibt_eine_doppelte_upload_id_abgewiesen(zweite):
    s = _struktur(_datei(0, "Linsen.pdf"), zweite)
    daten = _antwort(s, [{"i": 0, "rolle": "inhalt", "upload_id": _A},
                         {"i": 1, "rolle": zweite["rolle"], "upload_id": _A}])
    assert bereit.grund(daten, upload_antwort.dateien(s)) == "upload_id doppelt"


def test_metadaten_tragen_je_i_dieselben_angaben():
    s = _struktur(_datei(0, "Linsen.pdf"), _datei(1, "Linsen.pdf"), _datei(2, "Folien.pptx"))
    daten = _antwort(s, [{"i": 0, "rolle": "inhalt", "upload_id": _A},
                         {"i": 1, "rolle": "inhalt", "upload_id": _A}])
    teile = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        {"modul": "ui_upload", "block_id": "b0000001", "daten": daten}))
    zeile = SimpleNamespace(id=_A, name="x", befund={"rolle": "inhalt", "angaben": {
        "titel": "Linsen im Alltag", "schlagworte": ["Optik"]}})
    neu, kurz = ml.neu_berechnet(teile["metadaten"], [zeile])
    gelesen = [e for e in neu["inhalte"] if e["lesbar"]]
    assert [(e["i"], e["titel"], e["upload_id"]) for e in gelesen] == [
        (0, "Linsen im Alltag", _A), (1, "Linsen im Alltag", _A)]
    assert kurz == "3 Inhalte, 2 gelesen"
    # und das Aufräumen setzt beide zurück
    weg = ml.ohne_uploads(neu, {_A}, teile["struktur"])
    assert not any(e["lesbar"] for e in weg["inhalte"])


# ── NIT 9: der Grund je nicht gelesener Datei ───────────────────────────────────────────────────

def _zeilen(daten: dict) -> str:
    _start, z = upload_rahmen.zeilen({"modul": "ui_upload", "daten": daten})
    return "\n".join(z)


def test_der_satz_nennt_format_groesse_und_grenze_oder_fehler(monkeypatch):
    from boerdi.domain.config_models.upload import UploadSettings

    monkeypatch.setattr(bereit, "load_upload_config", lambda: UploadSettings(max_mb=10))
    s = _struktur(_datei(0, "Linsen.pdf"), _datei(1, "Folien.pptx"),
                  _datei(2, "Riesig.pdf", groesse=11 * _MIB), _datei(3, "Weg.docx"),
                  _datei(4, "Lehrplan.pdf", rolle="struktur"))
    text = _zeilen(_antwort(s, [{"i": 0, "rolle": "inhalt", "upload_id": _A}]))
    assert "1 Inhalt (Format)" in text
    assert "1 Inhalt (zu groß)" in text
    # zweites Review, NIT 8: auch „angehalten“ (die Person hielt „Hier im Chat“ an)
    assert ("1 Inhalt und 1 Strukturdokument (nicht hochgeladen: Grenze, Fehler oder angehalten)"
            in text)
    assert "lesbar: false" in text and "Strukturdokument" in text
    assert "(Format) — von ihnen" not in text            # der alte Satz kannte nur das Format
    for name in ("Linsen", "Folien", "Riesig", "Weg", "Lehrplan"):
        assert name not in text                          # nie Namen


def test_alles_gelesen_kein_satz_auch_mit_dubletten():
    s = _struktur(_datei(0, "Linsen.pdf"), _datei(1, "Linsen.pdf"))
    text = _zeilen(_antwort(s, [{"i": 0, "rolle": "inhalt", "upload_id": _A},
                                {"i": 1, "rolle": "inhalt", "upload_id": _A}]))
    assert "Nicht gelesen" not in text and "2 Inhalte" in text


# ── MINOR 4: die Orte des Ablaufs gelten auch serverseitig ──────────────────────────────────────

def _block_daten(orte) -> dict:
    return {"zweck": "bereitstellen", "orte": orte}


def test_die_offene_frage_merkt_die_erlaubten_orte():
    from boerdi.ui_module import upload_orte  # noqa: F401 — nur die Form der Daten

    gesperrt = {"vorauswahl": "wlo", "chat": {"geht": False, "grund": "ablauf"},
                "wlo": {"geht": True}, "namen": {"geht": True}}
    assert upload_antwort.merken("b1", "ui_upload", _block_daten(gesperrt))["orte"] == [
        "wlo", "namen"]
    # andere Sperrgründe ändern sich im Lauf (Anmeldung, Sitzung) — sie binden nicht
    nur_angemeldet = {**gesperrt, "chat": {"geht": True}, "wlo": {"geht": False,
                                                                   "grund": "nur_angemeldet"}}
    assert upload_antwort.merken("b1", "ui_upload", _block_daten(nur_angemeldet))["orte"] == [
        "chat", "wlo", "namen"]
    # die Simulation trägt die Dienst-Argumente (Liste)
    assert upload_antwort.merken("b1", "ui_upload", _block_daten(["wlo"]))["orte"] == [
        "wlo", "namen"]
    assert upload_antwort.merken("b1", "ui_upload", {"zweck": "x"})["orte"] == [
        "chat", "wlo", "namen"]


def test_ein_nicht_erlaubter_ort_wird_abgewiesen():
    from boerdi.api.schemas_ui import UiAntwort
    from boerdi.ui_module.antwort import antwort_pruefen

    s = _struktur(_datei(0, "Linsen.pdf"))
    daten = _antwort(s, [{"i": 0, "rolle": "inhalt", "upload_id": _A}])
    offen = {"block_id": "b0000001", "modul": "ui_upload", "frage": "Ordner erfassen",
             "zweck": "bereitstellen", "orte": ["wlo", "namen"]}
    assert antwort_pruefen(offen, UiAntwort(block_id="b0000001", daten=daten)) is None
    assert bereit.ort_grund(daten, offen) == "Ort im Ablauf nicht erlaubt"
    namen = {k: v for k, v in daten.items() if k != "dateien"} | {"ort": "namen"}
    assert antwort_pruefen(offen, UiAntwort(block_id="b0000001", daten=namen)) is not None
    # eine offene Frage von vorher (ohne ``orte``) erlaubt alle
    alt = {k: v for k, v in offen.items() if k != "orte"}
    assert antwort_pruefen(alt, UiAntwort(block_id="b0000001", daten=daten)) is not None
