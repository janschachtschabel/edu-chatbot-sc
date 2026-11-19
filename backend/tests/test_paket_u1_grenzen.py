"""Paket U1 (Plan 2026-11-17): Grenzen „hier im Chat“ im Studio — ``lokal_max_dateien`` und
``lokal_max_mb_gesamt``; die Ablage der Sitzungsdokumente richtet sich danach."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.upload import UploadConfigArea, UploadSettings
from boerdi.services.config_loader import upload as lader


def test_vorgaben_der_neuen_grenzen(monkeypatch):
    monkeypatch.setattr(lader, "area", lambda key: {})
    werte = lader.load_upload_config()
    assert (werte.lokal_max_dateien, werte.lokal_max_mb_gesamt) == (10, 50)


def test_studio_werte_der_grenzen_wirken(monkeypatch):
    monkeypatch.setattr(lader, "area", lambda key: {
        "upload": {"lokal_max_dateien": 3, "lokal_max_mb_gesamt": 7}})
    werte = lader.load_upload_config()
    assert (werte.lokal_max_dateien, werte.lokal_max_mb_gesamt) == (3, 7)


@pytest.mark.parametrize("falsch", [
    {"lokal_max_dateien": 0}, {"lokal_max_dateien": 31},
    {"lokal_max_mb_gesamt": 0}, {"lokal_max_mb_gesamt": 201},
])
def test_grenzen_ausserhalb_werden_abgewiesen(falsch):
    with pytest.raises(ValidationError):
        UploadConfigArea.model_validate({"upload": falsch})


def test_die_ablage_liest_die_grenze_aus_dem_studio(monkeypatch):
    from boerdi.services.dokumente import ablage

    monkeypatch.setattr(lader, "area", lambda key: {"upload": {"lokal_max_dateien": 4}})
    assert ablage.max_je_sitzung() == 4
    monkeypatch.setattr(lader, "area", lambda key: {})
    assert ablage.max_je_sitzung() == UploadSettings().lokal_max_dateien == 10


def test_die_gesamtgroesse_in_bytes(monkeypatch):
    from boerdi.services.dokumente import ablage

    monkeypatch.setattr(lader, "area", lambda key: {"upload": {"lokal_max_mb_gesamt": 2}})
    assert ablage.max_bytes_je_sitzung() == 2 * 1024 * 1024
