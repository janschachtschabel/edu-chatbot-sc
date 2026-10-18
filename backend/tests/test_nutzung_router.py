"""Paket 16, D3 — die dünne HTTP-Schicht über ``services/nutzung.py``.

Wie ``test_usage_router.py``: TestClient ohne Lifespan, ``get_session`` als Merkstein, der Dienst
gefälscht. Die SQL steht in ``test_nutzung.py`` gegen die echte Datenbank.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import boerdi.api.nutzung as nutzung_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()
_URL = "/api/nutzung/ueberblick"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


@pytest.fixture()
def dienst(monkeypatch):
    aufrufe: list[tuple] = []

    async def fake(*args, **kwargs):
        aufrufe.append((args, kwargs))
        return {"zuege": 3}

    monkeypatch.setattr(nutzung_api, "ueberblick", fake)
    monkeypatch.setattr(nutzung_api, "qualitaetsprotokoll_an", lambda: False)
    return aufrufe


def test_reicht_zeitraum_herkunft_und_maschine_durch_und_sagt_ob_protokolliert_wird(
        client, dienst):
    r = client.get(_URL, params={"from": "2026-03-01T00:00:00", "to": "2026-03-31T00:00:00",
                                 "scope": "production", "engine": "agent"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"zuege": 3, "protokoll_an": False}
    args, kwargs = dienst[0]
    assert args[0] is _SESSION
    assert args[1] == datetime(2026, 3, 1, tzinfo=UTC)          # zonenlos = UTC
    assert kwargs == {"scope": "production", "engine": "agent"}


def test_vertauschter_oder_zu_langer_zeitraum_ist_ein_eingabefehler(client, dienst):
    assert client.get(_URL, params={"from": "2026-03-31", "to": "2026-03-01"},
                      headers=_AUTH).status_code == 422
    assert client.get(_URL, params={"from": "2024-01-01", "to": "2026-03-01"},
                      headers=_AUTH).status_code == 422
    assert client.get(_URL, params={"from": "2026-03-01", "to": "2026-03-02", "engine": "x"},
                      headers=_AUTH).status_code == 422
    assert dienst == []


def test_braucht_den_studio_schluessel(client, dienst):
    assert client.get(_URL, params={"from": "2026-03-01", "to": "2026-03-02"}).status_code == 401
