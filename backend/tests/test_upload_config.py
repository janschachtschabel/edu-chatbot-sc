"""``01-base/upload-config`` — Schalter und Grenzen des Hochladens im Studio (Paket U3-2a).

Leer gilt die Vorgabe des Codes (Dokument im Chat an, ohne Anmeldung aus, Ablage in WLO aus).
Ein Bestand am Validator vorbei (Seed-Import, alte Sicherung) bricht keine Antwort: der Lader
fällt dann ganz auf die Vorgabe zurück.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.domain.area_effects import AREA_EFFECTS
from boerdi.domain.config_models import AREA_MODELS
from boerdi.domain.config_models.upload import UploadConfigArea, UploadSettings
from boerdi.services.config_loader import upload as lader


def test_der_bereich_ist_registriert_und_wirkt_in_beiden_modi():
    assert AREA_MODELS["01-base/upload-config"] is UploadConfigArea
    assert AREA_EFFECTS["01-base/upload-config"] == {"pattern": "voll", "agent": "voll"}


def test_leer_gilt_die_vorgabe(monkeypatch):
    monkeypatch.setattr(lader, "area", lambda key: {})
    werte = lader.load_upload_config()
    assert (werte.dokument_im_chat, werte.dokument_ohne_anmeldung, werte.ablage_in_wlo) == (
        True, False, False)
    assert (werte.max_mb, werte.max_seiten, werte.aufbewahrung_h) == (10, 300, 24)


def test_studio_wert_wirkt(monkeypatch):
    monkeypatch.setattr(lader, "area", lambda key: (
        {"upload": {"dokument_ohne_anmeldung": True, "max_mb": 5}}
        if key == "01-base/upload-config" else {}))
    werte = lader.load_upload_config()
    assert werte.dokument_ohne_anmeldung is True and werte.max_mb == 5
    assert werte.max_seiten == 300


@pytest.mark.parametrize("falsch", [
    {"max_mb": 0}, {"max_mb": UploadSettings.OBERGRENZE_MB + 1},
    {"max_seiten": 1001}, {"aufbewahrung_h": 0}, {"aufbewahrung_h": 73},
])
def test_das_modell_weist_ab_was_ausserhalb_liegt(falsch):
    with pytest.raises(ValidationError):
        UploadConfigArea.model_validate({"upload": falsch})


def test_ein_kaputter_bestand_faellt_auf_die_vorgabe(monkeypatch):
    monkeypatch.setattr(lader, "area", lambda key: {"upload": {"max_mb": "viel"}})
    assert lader.load_upload_config().max_mb == 10
