"""Paket U4 (Plan 2026-11-17, E13): „Wo verarbeiten?“ — welche Orte das Upload-Feld anbietet, was
vorgewählt ist und warum ein Ort gesperrt ist (Codes, keine Sätze); Grenzen; Einschränkung durch
einen Ablauf (``orte``). Dazu der Vertrag der neuen Antwort ``aktion: bereitgestellt``."""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.upload import UploadSettings
from boerdi.ui_module import dienst, katalog, upload_orte
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.namen import UPLOAD


@pytest.fixture
def lage(monkeypatch):
    """Studio, Anmeldung, Stapel-Ablage des MCP und Flow-Träger — je Test einstellbar."""
    werte = {"cfg": UploadSettings(), "person": True, "ablage": True, "flow": True, "ocr": False,
             "flow_grund": "dienst_nicht_erreichbar"}
    # Paket C: die Texterkennung prüfen ihre eigenen Tests (``test_paket_c_ocr_orte``)
    monkeypatch.setattr(upload_orte, "_texterkennung", lambda cfg: werte["ocr"])
    monkeypatch.setattr(upload_orte, "load_upload_config", lambda: werte["cfg"])
    monkeypatch.setattr(upload_orte, "has_personal_auth", lambda: werte["person"])
    monkeypatch.setattr(upload_orte, "_ablage_da", lambda: werte["ablage"])
    monkeypatch.setattr(upload_orte, "_flow_da", lambda: werte["flow"])
    # Review P2, Befund 3: der Grund ohne Flow (eigener Test in ``test_p2_review_befunde``)
    monkeypatch.setattr(upload_orte, "_ohne_flow_grund", lambda: werte["flow_grund"])
    # Durchtest U8: ob die Anmeldung hilft, prüft ein eigener Weg (ohne Starter dieses Zuges)
    monkeypatch.setattr(upload_orte, "_flow_nach_anmeldung", lambda: werte["flow"])
    return werte


def test_angemeldet_mit_flow_traeger_ist_wlo_vorgewaehlt(lage):
    o = upload_orte.orte()
    assert o["vorauswahl"] == "wlo"
    assert o["wlo"] == {"geht": True}
    assert o["chat"] == {"geht": True, "ueber_grenze": "ueber_grenze"}
    assert o["namen"] == {"geht": True}


def test_angemeldet_ohne_flow_traeger_wlo_nur_ablage_mit_hinweis_chat_vorgewaehlt(lage):
    lage["flow"] = False
    o = upload_orte.orte()
    assert o["wlo"] == {"geht": True, "hinweis": "ohne_erschliessung",
                        "grund_erschliessung": "dienst_nicht_erreichbar"}
    assert o["vorauswahl"] == "chat"


def test_ohne_anmeldung_chat_bis_zur_grenze_wlo_gesperrt(lage):
    lage["person"] = False
    o = upload_orte.orte()
    assert o["vorauswahl"] == "chat"
    assert o["wlo"] == {"geht": False, "grund": "nur_angemeldet"}
    # über der Grenze nur Namen — mit dem Hinweis, dass die Anmeldung hilft
    assert o["chat"] == {"geht": True, "ueber_grenze": "ueber_grenze_anmelden"}


def test_ohne_anmeldung_und_ohne_ablage_hilft_die_anmeldung_nicht(lage):
    lage["person"], lage["ablage"] = False, False
    o = upload_orte.orte()
    assert o["wlo"] == {"geht": False, "grund": "aus"}
    assert o["chat"]["ueber_grenze"] == "ueber_grenze"


def test_studio_aus_sperrt_die_orte_mit_code(lage):
    lage["cfg"] = UploadSettings(dokument_im_chat=False, ablage_in_wlo=False)
    o = upload_orte.orte()
    assert o["chat"] == {"geht": False, "grund": "aus"}
    assert o["wlo"] == {"geht": False, "grund": "aus"}
    assert o["vorauswahl"] == "namen"


def test_chat_ohne_anmeldung_abgeschaltet(lage):
    lage["person"] = False
    lage["cfg"] = UploadSettings(dokument_ohne_anmeldung=False)
    o = upload_orte.orte()
    assert o["chat"] == {"geht": False, "grund": "nur_angemeldet"}
    assert o["vorauswahl"] == "namen"


def test_ein_ablauf_schraenkt_die_orte_ein(lage):
    o = upload_orte.orte(erlaubt=["chat", "namen"])
    assert o["wlo"] == {"geht": False, "grund": "ablauf"}
    assert o["vorauswahl"] == "chat"
    o = upload_orte.orte(erlaubt=["namen"])
    assert o["chat"]["geht"] is False and o["chat"]["grund"] == "ablauf"
    assert o["vorauswahl"] == "namen"


def test_namen_gehen_immer_auch_wenn_der_ablauf_sie_nicht_nennt(lage):
    """„Nur Namen senden“ ist der Datenschutz-Ausweg (E7) — nie gesperrt."""
    o = upload_orte.orte(erlaubt=["wlo"])
    assert o["namen"] == {"geht": True}
    assert o["vorauswahl"] == "wlo"


def _manifest() -> dict:
    return katalog.katalog()[UPLOAD]


def test_der_dienst_liefert_orte_und_grenzen(lage):
    erg = asyncio.run(dienst.aufruf(_manifest(), {"zweck": "bereitstellen"}, Umgebung()))
    d = erg.block.daten
    # Plan 2026-11-20, P2 (UO-5): im freien Chat wählt das Studio vor — ab Werk ``chat``, auch
    # angemeldet mit Flow (vorher ``wlo``; die Regel ``auto`` prüft ``test_p2_ort_vorauswahl``)
    assert d["orte"]["vorauswahl"] == "chat"
    assert d["grenzen"]["lokal_max_dateien"] == 10 and d["grenzen"]["lokal_max_mb_gesamt"] == 50
    assert d["grenzen"]["lokal_max_mb_datei"] == 10
    # Teil b: die Frist „Hier im Chat“ für die Erklärzeile (Studio ``aufbewahrung_h``)
    assert d["grenzen"]["lokal_aufbewahrung_h"] == 24


def test_orte_vom_ablauf_wirken_nur_aus_dem_ablauf(lage):
    args = {"zweck": "bereitstellen", "orte": ["namen"]}
    frei = asyncio.run(dienst.aufruf(_manifest(), args, Umgebung()))
    # P2: frei gilt die Vorauswahl des Studios (``chat``) — die Einschränkung wirkt nicht
    assert frei.block.daten["orte"]["vorauswahl"] == "chat"
    assert frei.block.daten["orte"]["wlo"] == {"geht": True}
    ablauf = asyncio.run(dienst.aufruf(_manifest(), args, Umgebung(aus_ablauf=True)))
    assert ablauf.block.daten["orte"]["vorauswahl"] == "namen"


# ── Vertrag der Antwort ────────────────────────────────────────────────────────────────────────

def _struktur() -> dict:
    return {"name": "Unterlagen", "dateien": 3, "alle_dateien": 3, "kinder": [], "dateiliste": [
        {"i": 0, "name": "Linsen.pdf", "endung": "pdf", "groesse": 10, "rolle": "inhalt"},
        {"i": 1, "name": "Folien.pptx", "endung": "pptx", "groesse": 10, "rolle": "inhalt"},
        {"i": 2, "name": "Lehrplan.pdf", "endung": "pdf", "groesse": 10, "rolle": "struktur"}]}


def bereitgestellt(ort: str, **mehr) -> dict:
    daten = {"aktion": "bereitgestellt", "ort": ort, "struktur": _struktur(),
             "zahlen": {"ordner": 1, "dateien": 3, "inhalte": 2, "ignoriert": 0,
                        "strukturdokumente": 1, "bytes": 30},
             "strukturdokument": {"name": "Lehrplan.pdf", "groesse": 10, "endung": "pdf"},
             "warnungen": []}
    daten.update(mehr)
    return daten


_A = "11111111-1111-4111-8111-111111111111"
_B = "22222222-2222-4222-8222-222222222222"
CHAT_DATEIEN = [{"i": 0, "rolle": "inhalt", "upload_id": _A},
                {"i": 2, "rolle": "struktur", "upload_id": _B}]
ABLAGE = {"layout": "flach", "gesamt": 3, "abgelegt": 3, "unklar": 0, "fehler": 0,
          "abgebrochen": 0, "ordner_verweigert": False, "vorgang_abgelegt": True}


@pytest.mark.parametrize("daten", [
    bereitgestellt("chat", dateien=CHAT_DATEIEN),
    bereitgestellt("wlo", dateien=[{"i": 0, "rolle": "inhalt"}, {"i": 1, "rolle": "inhalt"},
                                   {"i": 2, "rolle": "struktur"}], ablage=ABLAGE),
    bereitgestellt("namen"),
])
def test_das_schema_nimmt_jeden_ort(daten):
    assert katalog.antwort_fehler(_manifest(), daten) == []


@pytest.mark.parametrize("daten", [
    bereitgestellt("hier"),                                             # unbekannter Ort
    bereitgestellt("chat", dateien=[{"i": 0, "rolle": "inhalt", "upload_id": "x"}]),
])
def test_das_schema_weist_ab(daten):
    assert katalog.antwort_fehler(_manifest(), daten) != []


@pytest.mark.parametrize(("daten", "grund"), [
    ({**bereitgestellt("namen"), "aktion": "erfasst"}, "Ort nur mit aktion bereitgestellt"),
    ({k: v for k, v in bereitgestellt("namen").items() if k != "ort"},
     "bereitgestellt braucht einen Ort"),
    (bereitgestellt("chat"), "Dateien nur mit Ort chat oder wlo"),
    (bereitgestellt("namen", dateien=CHAT_DATEIEN), "Dateien nur mit Ort chat oder wlo"),
    (bereitgestellt("wlo", dateien=[{"i": 0, "rolle": "inhalt"}]), "Ablage nur mit Ort wlo"),
    (bereitgestellt("chat", dateien=CHAT_DATEIEN, ablage=ABLAGE), "Ablage nur mit Ort wlo"),
    (bereitgestellt("wlo", dateien=[{"i": 0, "rolle": "inhalt", "upload_id": _A}], ablage=ABLAGE),
     "upload_id nur mit Ort chat"),
    (bereitgestellt("chat", dateien=[{"i": 9, "rolle": "inhalt", "upload_id": _A}]),
     "Datei nicht in der Auswahl"),
    (bereitgestellt("chat", dateien=[{"i": 0, "rolle": "struktur", "upload_id": _A}]),
     "Rolle passt nicht zur Auswahl"),
    (bereitgestellt("chat", dateien=[{"i": 0, "rolle": "inhalt", "upload_id": _A},
                                     {"i": 0, "rolle": "inhalt", "upload_id": _B}]),
     "Datei doppelt"),
    (bereitgestellt("chat", dateien=[{"i": 0, "rolle": "inhalt", "upload_id": _A},
                                     {"i": 2, "rolle": "struktur", "upload_id": _A}]),
     "upload_id doppelt"),
])
def test_grund_ueber_das_schema_hinaus(daten, grund):
    from boerdi.ui_module import upload_antwort

    assert katalog.antwort_fehler(_manifest(), daten) == []
    assert upload_antwort.grund(daten) == grund


def test_gueltige_bereitstellung_hat_keinen_grund():
    from boerdi.ui_module import upload_antwort

    assert upload_antwort.grund(bereitgestellt("chat", dateien=CHAT_DATEIEN)) is None
    assert upload_antwort.grund(bereitgestellt("namen")) is None
