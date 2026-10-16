"""Die Aufbewahrung im Studio-API (Paket 8, A): Überblick und „jetzt bereinigen“.

Ohne Datenbank: der Dienst ist die Grenze (``test_aufbewahrung.py`` prüft ihn gegen
Postgres); hier zählt die HTTP-Seite — Pfad, Antwortform, 409, Schlüssel.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.api import sessions as sessions_api
from boerdi.api.deps import get_session, get_session_factory
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_UEBERBLICK = [
    {"bereich": "safety_logs", "tage": 90, "faellig": 3, "aeltester": "2026-07-01T00:00:00+00:00"},
    {"bereich": "quality_logs", "tage": 0, "faellig": 0, "aeltester": None},
]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_session_factory] = lambda: object()
    app.state.engine = object()  # ohne Lebenszyklus — der Dienst ist ersetzt
    yield TestClient(app)
    get_settings.cache_clear()


def test_der_ueberblick_nennt_frist_und_faellige_eintraege(client, monkeypatch):
    async def _ueberblick(session):
        return _UEBERBLICK

    monkeypatch.setattr(sessions_api.aufbewahrung, "ueberblick", _ueberblick)
    r = client.get("/api/sessions/retention", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"fristen": _UEBERBLICK}


def test_jetzt_bereinigen_meldet_was_geloescht_wurde(client, monkeypatch):
    async def _lauf(engine, sitzungen):
        return {"safety_logs": 3, "quality_logs": 0}

    monkeypatch.setattr(sessions_api.aufbewahrung, "lauf", _lauf)
    r = client.post("/api/sessions/retention", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "done", "deleted": {"safety_logs": 3, "quality_logs": 0}}


def test_laeuft_die_bereinigung_schon_heisst_es_409(client, monkeypatch):
    async def _lauf(engine, sitzungen):
        return None

    monkeypatch.setattr(sessions_api.aufbewahrung, "lauf", _lauf)
    r = client.post("/api/sessions/retention", headers={**_AUTH, "Accept-Language": "en"})
    assert r.status_code == 409
    assert "already running" in r.json()["detail"]


def test_ohne_studio_schluessel_weder_ueberblick_noch_lauf(client):
    assert client.get("/api/sessions/retention").status_code == 401
    assert client.post("/api/sessions/retention").status_code == 401
