"""Die alten Sammelrouten prüfen Kennungen wie das Studio (Befundliste §1.4, Paket 11).

``PUT /api/config/patterns`` und ``PUT /api/config/personas`` sind ALT-treu portiert und wurden vom
Studio nicht mehr benutzt. Sie ließen zu, was die übrigen Schreibwege seit Paket 6/9 abweisen
(``api/config_kennungen.kennungs_einwand``): Kennungen, die sich nur in Groß/Klein unterscheiden —
auch neben einem Sicherheitsmuster —, und eine Persona „P-“, die den Schlüssel ``04-personas/``
schrieb. Geschrieben wird nur, wenn ALLE Einträge die Prüfung bestehen.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k-studio-testkey"}
_M01 = {"frontmatter": {"id": "M01", "label": "Krise"}, "body": "x"}
_LEH = {"frontmatter": {"id": "P-LEH", "label": "Lehrkraft"}, "body": "x"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    get_settings.cache_clear()
    return TestClient(create_app())  # ohne Kontextmanager: keine Lebensdauer, keine DB


@pytest.fixture()
def geschrieben(monkeypatch) -> list[str]:
    aufrufe: list[str] = []

    async def _area(key, data, updated_by="studio", **_bedingung):
        aufrufe.append(key)
        return 1

    async def _bestand():
        return {"03-patterns/m01-krisen-empathie": _M01, "04-personas/leh": _LEH}

    async def _lesen(_key):
        return None

    monkeypatch.setattr(config_loader, "write_area", _area)
    monkeypatch.setattr(config_loader, "current_config", _bestand)
    monkeypatch.setattr(config_loader, "read_area", _lesen)
    return aufrufe


def test_kennungen_nur_in_gross_klein_verschieden_werden_abgewiesen(client, geschrieben):
    r = client.put("/api/config/patterns", headers=_AUTH, json={
        "patterns": [{"id": "M77", "label": "A"}, {"id": "m77", "label": "B"}]})
    assert r.status_code == 400
    assert geschrieben == []


def test_ein_zweites_m01_in_anderer_schreibweise_wird_abgewiesen(client, geschrieben):
    r = client.put("/api/config/patterns", headers=_AUTH, json={
        "patterns": [{"id": "m01", "label": "Doppelt"}]})
    assert r.status_code == 400
    assert geschrieben == []


def test_persona_ohne_kennungsrest_wird_abgewiesen(client, geschrieben):
    """„P-“ ergab den Schlüssel ``04-personas/`` — ein Dokument ohne Namen."""
    r = client.put("/api/config/personas", headers=_AUTH, json={
        "personas": [{"id": "P-", "label": "Leer"}]})
    assert r.status_code == 400
    assert geschrieben == []


def test_gewoehnliche_eintraege_werden_weiter_gespeichert(client, geschrieben):
    r = client.put("/api/config/patterns", headers=_AUTH, json={
        "patterns": [{"id": "M01", "label": "Krise neu"}, {"id": "M78", "label": "Neu"}]})
    assert r.status_code == 200, r.text
    assert "03-patterns/m01-krisen-empathie" in geschrieben
    r = client.put("/api/config/personas", headers=_AUTH, json={
        "personas": [{"id": "P-LEH", "label": "Lehrkraft"}]})
    assert r.status_code == 200, r.text
    assert "04-personas/leh" in geschrieben
