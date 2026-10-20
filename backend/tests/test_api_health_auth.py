"""Paket 17 (D2): ``/api/health`` nennt Anbieter, Modelle, Repositorium und Reranker —
Betriebsdetails, die nach dem Leitfaden „Übergabe an Team 6“ nicht öffentlich sein sollen.
Das Studio liest sie über seinen Proxy (der den Studio-Schlüssel einsetzt); ``/health`` (nur
``{"status":"ok"}``) bleibt offen."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.settings import get_settings

_SCHLUESSEL = "studio-schluessel-fuer-den-test-0123456789"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", _SCHLUESSEL)
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_api_health_ohne_studio_schluessel_abgewiesen(client) -> None:
    assert client.get("/api/health").status_code == 401


def test_api_health_mit_studio_schluessel(client) -> None:
    r = client.get("/api/health", headers={"X-Studio-Key": _SCHLUESSEL})
    assert r.status_code == 200
    assert "provider" in r.json()


def test_liveness_bleibt_offen(client) -> None:
    assert client.get("/health").status_code == 200


def test_die_wurzel_fuehrt_nicht_mehr_auf_die_betriebsdaten(client) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] != "/api/health"
