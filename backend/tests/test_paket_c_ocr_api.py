"""Plan 2026-11-19, Paket C (C2/C3): ``POST /api/ui/dokumente`` mit Texterkennung.

Nur „Hier im Chat“: ist die Texterkennung an (Studio ``ocr``, Umgebung nicht ``off``, Anbieter
nimmt Bilder — ``ocr.aktiv``), gibt der Endpunkt ``aufbereiten`` eine Texterkennung mit (Grenze
Studio ``ocr_max_seiten``, eigene Frist). Ihr Verbrauch geht für die Sitzung in die Kostenschau —
auch, wenn das Dokument danach abgewiesen wird (bezahlt war der Aufruf)."""

from __future__ import annotations

import time

import pytest

import boerdi.api.ui_dokumente as api
from boerdi.services.dokumente import ocr, ocr_sitzung
from boerdi.services.dokumente.aufnahme import Abweisung
from boerdi.services.dokumente.ocr import OcrErgebnis
from tests import test_ui_dokumente_api as basis
from tests.test_ui_dokumente_api import _post

lage = basis.lage
client = basis.client
_umgebung = basis._umgebung


@pytest.fixture
def gebucht(monkeypatch):
    buchungen: list = []

    async def buchen(session, session_id, acc, quelle=None, **_k):
        if acc["models"]:
            buchungen.append((session_id, dict(acc["models"]), quelle))
        return len(acc["models"])

    monkeypatch.setattr(api, "record_turn_usage", buchen)
    return buchungen


@pytest.fixture
def texterkennung(monkeypatch):
    """OCR an, die Seiten liest eine Attrappe — sie bucht wie der echte Aufruf.
    ``stand["gebucht"]``: so viele OCR-Seiten hat die Sitzung schon (Review 3)."""
    ocr_sitzung.leeren()
    stand: dict = {"aufrufe": [], "gebucht": 0}

    async def seiten_lesen(rumpf, *, seiten_max, frist_ende, usage_acc, lesen=None):
        stand["aufrufe"].append({"seiten_max": seiten_max, "rest": frist_ende - time.monotonic()})
        usage_acc["models"]["gpt-6-luna"] = {"prompt": 1200, "completion": 300}
        return OcrErgebnis(markdown="# Text", seiten=1, gelesen=1, gekuerzt=False, versucht=1)

    async def seiten_gebucht(session, session_id):
        return stand["gebucht"]

    monkeypatch.setattr(api, "ocr_aktiv", lambda cfg=None: True)
    monkeypatch.setattr(ocr, "seiten_lesen", seiten_lesen)
    monkeypatch.setattr(ocr_sitzung, "seiten_gebucht", seiten_gebucht)
    return stand


def test_ohne_ocr_keine_texterkennung_und_keine_buchung(client, lage, gebucht, monkeypatch):
    monkeypatch.setattr(api, "ocr_aktiv", lambda cfg=None: False)
    assert _post(client).status_code == 200
    assert lage.ocr_lesen == [None] and gebucht == []


def test_mit_ocr_grenze_frist_und_buchung(client, lage, gebucht, texterkennung):
    lage.cfg = lage.cfg.model_copy(update={"ocr_max_seiten": 7})
    r = _post(client, name="scan.pdf")
    assert r.status_code == 200, r.text
    [aufruf] = texterkennung["aufrufe"]
    assert aufruf["seiten_max"] == 7
    assert 0 < aufruf["rest"] <= api.ocr_frist("struktur")
    # Review 3: gebucht mit der Quelle der Texterkennung — daraus zählt die Grenze der Sitzung
    assert gebucht == [(basis._SITZUNG, {"gpt-6-luna": {"prompt": 1200, "completion": 300}},
                        ocr.PHASE)]


def test_verbrauch_auch_bei_abweisung_gebucht(client, lage, gebucht, texterkennung):
    lage.ergebnis = Abweisung(400, "abgewiesen")
    r = _post(client, name="scan.pdf")
    assert (r.status_code, r.json()["detail"]) == (400, "abgewiesen")
    assert len(gebucht) == 1


def test_review_14_verbrauch_auch_bei_einer_ausnahme_nach_der_texterkennung(
        client, lage, gebucht, texterkennung, monkeypatch):
    async def bricht(rumpf, name, *, ocr_lesen=None, **_k):
        await ocr_lesen(rumpf)
        raise RuntimeError("nach der Texterkennung")

    monkeypatch.setattr(api, "aufbereiten", bricht)
    assert _post(client, name="scan.pdf").status_code == 500
    assert len(gebucht) == 1


def test_review_3_das_seitenbudget_der_sitzung_deckelt_und_endet_mit_grenze_ocr(
        client, lage, gebucht, texterkennung):
    budget = lage.cfg.lokal_max_dateien * lage.cfg.ocr_max_seiten
    texterkennung["gebucht"] = budget - 3
    assert _post(client, name="scan.pdf").status_code == 200
    assert texterkennung["aufrufe"][-1]["seiten_max"] == 3
    texterkennung["gebucht"] = budget
    r = _post(client, name="scan2.pdf", rumpf=b"%PDF anderer")
    assert (r.status_code, r.json()["detail"]) == (429, "grenze_ocr")
    assert len(texterkennung["aufrufe"]) == 1


def test_review_4_die_frist_der_texterkennung_laesst_platz_fuer_moderation_und_kurzangaben(
        client, lage, gebucht, texterkennung, monkeypatch):
    """Das Widget wartet 120 s auf die Antwort, gezählt ab dem Ende des Hochladens
    (``dokument-transport.ts``, ``ANTWORT_FRIST_MS``, zweites Review 3) — Texterkennung,
    Moderation, Kurzangaben (nur ``inhalt``) und Speichern bleiben darunter."""
    from boerdi.services.dokumente import inhalt_angaben
    from boerdi.services.safety import moderation

    puffer = 20                    # Umwandlung, Speichern, Netz (das Hochladen zählt nicht mit)
    for rolle, angaben in (("struktur", 0), ("inhalt", inhalt_angaben.FRIST_S)):
        assert api.ocr_frist(rolle) + moderation._MOD_TIMEOUT_SECONDS + angaben + puffer <= 120

    async def ermitteln(*_a, **_k):
        return None

    monkeypatch.setattr(api, "inhalt_angaben_ermitteln", ermitteln)
    assert _post(client, name="scan.pdf", rolle="inhalt").status_code == 200
    assert texterkennung["aufrufe"][-1]["rest"] <= api.ocr_frist("inhalt")
    assert api.ocr_frist("inhalt") < api.ocr_frist("struktur")
