"""Plan 2026-11-20 (Upload-Ort und Erschließung), Paket P2: Ort, Vorauswahl, Häkchen, Wortlaut.

- **Vorauswahl (UO-5):** ``upload_orte.orte(vorzug=…)`` — ``auto`` ist die bisherige Regel (WLO,
  wenn der ganze Weg geht, sonst Chat → WLO → Namen); ``wlo``/``chat`` nehmen diesen Ort, wenn er
  geht, sonst gilt ``auto``. Im freien Chat kommt der Vorzug aus dem Studio
  (``upload-config.vorauswahl``, Vorgabe ``chat`` — auch angemeldet), aus einem Ablauf aus dem
  Schritt (``vorauswahl``, Vorgabe ``auto``). Die KI setzt ihn nie.
- **Rollen-Vorgabe:** ``rolle_vorgabe`` (``auto|gliederung|material|beides``) aus dem Schritt;
  ``einzeldatei_als_struktur: true`` (alt) heißt ``gliederung`` und schaltet nicht mehr auf
  „nur ablegen“ (kein eigener KI-Satz, kein Schlüssel in den Block-Daten).
- **Häkchen:** ``erschliessen`` aus dem Schritt steht in den Block-Daten — seit Review P2,
  Befund 1, nur, wenn der Schritt es setzt (``test_p2_review_befunde``).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.domain.config_models.upload import UploadConfigArea, UploadSettings
from boerdi.services.config_loader import upload as lader
from boerdi.ui_module import dienst, dienst_upload, katalog, rollen, upload_orte
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.namen import UPLOAD
from tests.test_paket_u4_orte import lage  # noqa: F401 — Fixture (Studio, Anmeldung, Träger)


def _daten(args: dict, *, ablauf: bool) -> dict:
    erg = asyncio.run(dienst.aufruf(katalog.katalog()[UPLOAD], {"zweck": "bereitstellen", **args},
                                    Umgebung(aus_ablauf=ablauf)))
    assert erg.block is not None, erg.text
    return erg.block.daten


def _text(args: dict, *, ablauf: bool) -> str:
    return asyncio.run(dienst.aufruf(katalog.katalog()[UPLOAD], {"zweck": "bereitstellen", **args},
                                     Umgebung(aus_ablauf=ablauf))).text


# ── Vorauswahl in ``upload_orte.orte`` ───────────────────────────────────────────────────────────

def test_auto_ist_die_bisherige_regel(lage):  # noqa: F811
    assert upload_orte.orte(vorzug="auto")["vorauswahl"] == "wlo"
    lage["flow"] = False                          # Ablage ohne Erschließung → Chat vor
    assert upload_orte.orte(vorzug="auto")["vorauswahl"] == "chat"


def test_vorzug_chat_gilt_auch_angemeldet_mit_flow(lage):  # noqa: F811
    assert upload_orte.orte(vorzug="chat")["vorauswahl"] == "chat"


def test_vorzug_wlo_gilt_auch_ohne_flow_weil_der_ort_geht(lage):  # noqa: F811
    lage["flow"] = False
    o = upload_orte.orte(vorzug="wlo")
    assert o["vorauswahl"] == "wlo" and o["wlo"]["hinweis"] == "ohne_erschliessung"


def test_geht_der_vorzug_nicht_gilt_auto(lage):  # noqa: F811
    lage["person"] = False                        # WLO gesperrt → auto: Chat
    assert upload_orte.orte(vorzug="wlo")["vorauswahl"] == "chat"
    lage["person"] = True
    lage["cfg"] = UploadSettings(dokument_im_chat=False)   # Chat aus → auto: WLO
    assert upload_orte.orte(vorzug="chat")["vorauswahl"] == "wlo"
    o = upload_orte.orte(erlaubt=["namen"], vorzug="chat")  # der Ablauf sperrt beide → Namen
    assert o["vorauswahl"] == "namen"


def test_ohne_angabe_bleibt_auto(lage):  # noqa: F811
    assert upload_orte.orte()["vorauswahl"] == "wlo"


# ── Vorauswahl über den Dienst: freier Chat aus dem Studio, Ablauf aus dem Schritt ────────────────

def test_freier_chat_waehlt_ab_werk_den_chat_auch_angemeldet(lage):  # noqa: F811
    assert UploadSettings().vorauswahl == "chat"
    assert _daten({}, ablauf=False)["orte"]["vorauswahl"] == "chat"


def test_freier_chat_folgt_dem_studio(lage, monkeypatch):  # noqa: F811
    # ``lage`` ersetzt den Lader nur in ``upload_orte`` — der Dienst liest ihn selbst
    monkeypatch.setattr(dienst_upload, "load_upload_config", lambda: lage["cfg"])
    lage["cfg"] = UploadSettings(vorauswahl="auto")
    assert _daten({}, ablauf=False)["orte"]["vorauswahl"] == "wlo"
    lage["cfg"] = UploadSettings(vorauswahl="wlo")
    assert _daten({}, ablauf=False)["orte"]["vorauswahl"] == "wlo"


def test_die_ki_setzt_die_vorauswahl_nicht(lage):  # noqa: F811
    daten = _daten({"vorauswahl": "wlo", "rolle_vorgabe": "beides", "erschliessen": False},
                   ablauf=False)
    assert daten["orte"]["vorauswahl"] == "chat"
    assert daten["rolle_vorgabe"] == "auto" and "erschliessen" not in daten


def test_ein_ablauf_ohne_angabe_nimmt_auto_nicht_das_studio(lage, monkeypatch):  # noqa: F811
    monkeypatch.setattr(dienst_upload, "load_upload_config", lambda: lage["cfg"])
    lage["cfg"] = UploadSettings(vorauswahl="chat")
    assert _daten({}, ablauf=True)["orte"]["vorauswahl"] == "wlo"
    assert _daten({"vorauswahl": "chat"}, ablauf=True)["orte"]["vorauswahl"] == "chat"
    lage["person"] = False                        # WLO gesperrt → der Vorzug fällt auf auto
    assert _daten({"vorauswahl": "wlo"}, ablauf=True)["orte"]["vorauswahl"] == "chat"


# ── Rollen-Vorgabe und der alte Schlüssel ────────────────────────────────────────────────────────

@pytest.mark.parametrize(("daten", "erwartet"), [
    ({}, "auto"),
    ({"einzeldatei_als_struktur": True}, "gliederung"),
    ({"einzeldatei_als_struktur": False}, "auto"),
    ({"rolle_vorgabe": "material"}, "material"),
    ({"rolle_vorgabe": "beides"}, "beides"),
    ({"rolle_vorgabe": "auto", "einzeldatei_als_struktur": True}, "auto"),   # ausdrücklich zählt
    ({"rolle_vorgabe": "quatsch"}, "auto"),
])
def test_rolle_vorgabe_liest_den_alten_schluessel(daten, erwartet):
    assert rollen.vorgabe(daten) == erwartet


def test_ein_ablauf_gibt_die_rollen_vorgabe_weiter(lage):  # noqa: F811
    assert _daten({"rolle_vorgabe": "material"}, ablauf=True)["rolle_vorgabe"] == "material"
    alt = _daten({"einzeldatei_als_struktur": True}, ablauf=True)
    assert alt["rolle_vorgabe"] == "gliederung"
    # der alte Schlüssel steht nicht mehr in den Block-Daten: er schaltet nichts mehr um
    assert "einzeldatei_als_struktur" not in alt


def test_der_alte_schluessel_verspricht_kein_nur_ablegen_mehr(lage, monkeypatch):  # noqa: F811
    monkeypatch.setattr(dienst_upload, "schalter", lambda: {"ablage_in_wlo": True,
                                                            "dokument_im_chat": True})
    from boerdi.services.ablauf import zug_basis

    monkeypatch.setattr(zug_basis, "wlo_erschliessen", lambda: True)
    # Review P2, Befund 1: mit Häkchen (der Schritt setzt ``erschliessen``) wie der Datei-Weg
    datei_weg = _text({"erschliessen": True}, ablauf=True)
    dokument = _text({"einzeldatei_als_struktur": True, "erschliessen": True}, ablauf=True)
    assert dokument == datei_weg
    assert "Metadaten entstehen auf diesem Weg nicht" not in dokument
    assert "Häkchen „Metadaten von WLO erzeugen lassen“" in dokument


# ── Häkchen „Metadaten von WLO erzeugen lassen“ ──────────────────────────────────────────────────

def test_erschliessen_nur_wenn_der_schritt_es_setzt(lage):  # noqa: F811
    # Review P2, Befund 1: ohne Angabe kein Häkchen (vorher: ab Werk an)
    assert "erschliessen" not in _daten({}, ablauf=True)
    assert "erschliessen" not in _daten({}, ablauf=False)
    assert _daten({"erschliessen": False}, ablauf=True)["erschliessen"] is False


# ── Studio ``01-base/upload-config.vorauswahl`` ──────────────────────────────────────────────────

def test_der_lader_gibt_die_vorauswahl_heraus(monkeypatch):
    monkeypatch.setattr(lader, "area", lambda key: {})
    assert lader.load_upload_config().vorauswahl == "chat"
    monkeypatch.setattr(lader, "area", lambda key: {"upload": {"vorauswahl": "auto"}})
    assert lader.load_upload_config().vorauswahl == "auto"


def test_das_modell_kennt_nur_drei_vorauswahlen():
    from pydantic import ValidationError

    for gut in ("auto", "wlo", "chat"):
        assert UploadConfigArea.model_validate({"upload": {"vorauswahl": gut}})
    with pytest.raises(ValidationError):
        UploadConfigArea.model_validate({"upload": {"vorauswahl": "namen"}})


def test_der_seed_nennt_die_vorauswahl_im_kopf():
    from pathlib import Path

    seed = Path(__file__).resolve().parents[1] / "seeds" / "01-base" / "upload-config.yaml"
    assert "vorauswahl: chat" in seed.read_text(encoding="utf-8")


# ── Themenbaum-Angebot nach dem Lesen: an der Rollen-Vorgabe, nicht am alten Schlüssel ──────────

def _ablauf(daten: dict) -> SimpleNamespace:
    from boerdi.ui_module.namen import STRUKTURENTWURF

    return SimpleNamespace(voraussetzungen=[], schritte=[
        SimpleNamespace(typ="modul", modul=UPLOAD, daten=daten),
        SimpleNamespace(typ="agent", agent=SimpleNamespace(werkzeuge=[STRUKTURENTWURF]))])


@pytest.mark.parametrize(("daten", "erwartet"), [
    ({"rolle_vorgabe": "gliederung"}, True),
    ({"rolle_vorgabe": "beides"}, True),
    ({"einzeldatei_als_struktur": True}, True),
    ({"rolle_vorgabe": "material"}, False),
    ({}, False),
])
def test_das_themenbaum_angebot_folgt_der_rollen_vorgabe(monkeypatch, daten, erwartet):
    from boerdi.services.ablauf import ausloeser
    from boerdi.ui_module import schalter as modul_schalter
    from boerdi.ui_module import upload_rahmen

    monkeypatch.setattr(modul_schalter, "aktiv", lambda modul: False)
    monkeypatch.setattr(ausloeser, "vorschlaege", lambda: [_ablauf(daten)])
    assert upload_rahmen._themenbaum_angeboten(dokument=True) is erwartet


# ── Review P1, MINOR 4: die Zeilen an die KI zählen ``beides`` als Material und sagen die Rolle ──

def _erfasst(*dateiliste: dict, sd: str | None = None) -> dict:
    zahlen = {"ordner": 1, "inhalte": sum(d["rolle"] == "inhalt" for d in dateiliste),
              "ignoriert": sum(d["rolle"] == "ignorieren" for d in dateiliste),
              "strukturdokumente": sum(d["rolle"] in ("struktur", "beides") for d in dateiliste)}
    daten = {"struktur": {"name": "Unterlagen", "kinder": [], "dateiliste": list(dateiliste)},
             "zahlen": zahlen, "warnungen": []}
    if sd:
        daten["strukturdokument"] = {"name": sd}
    return daten


def _d(i: int, name: str, rolle: str) -> dict:
    return {"i": i, "name": name, "endung": name.rsplit(".", 1)[-1], "groesse": 5, "rolle": rolle}


def test_beides_zaehlt_als_material_und_heisst_gliederung_auch_material():
    from boerdi.ui_module import upload_rahmen

    daten = _erfasst(_d(0, "A.pdf", "inhalt"), _d(1, "B.pdf", "beides"),
                     _d(2, "L.pdf", "struktur"), _d(3, "X.pptx", "ignorieren"), sd="B.pdf")
    _start, z = upload_rahmen._ordner_zeilen(daten)
    assert "1 Ordner, 2 Dateien als Material, 1 ignoriert." in z
    assert "Gliederung: B.pdf (auch Material), L.pdf" in z


def test_eine_gliederung_und_keine():
    from boerdi.ui_module import upload_rahmen

    _s, z = upload_rahmen._ordner_zeilen(_erfasst(_d(0, "L.pdf", "struktur"), sd="L.pdf"))
    assert "Gliederung: L.pdf" in z and "1 Ordner, 0 Dateien als Material, 0 ignoriert." in z
    _s, z = upload_rahmen._ordner_zeilen(_erfasst(_d(0, "A.pdf", "inhalt")))
    assert "Keine Datei als Gliederung markiert." in z


def test_eine_alte_antwort_ohne_dateiliste_nimmt_die_zahlen():
    from boerdi.ui_module import upload_rahmen

    daten = {"struktur": {"name": "U", "kinder": []}, "warnungen": [],
             "zahlen": {"ordner": 2, "inhalte": 7, "ignoriert": 1, "strukturdokumente": 1},
             "strukturdokument": {"name": "Lehrplan.pdf"}}
    _s, z = upload_rahmen._ordner_zeilen(daten)
    assert "2 Ordner, 7 Dateien als Material, 1 ignoriert." in z
    assert "Gliederung: Lehrplan.pdf" in z
