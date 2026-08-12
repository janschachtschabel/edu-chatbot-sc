"""K4 — die dünne HTTP-Schicht über ``services/usage_analytics.py``.

Vorgehen wie in ``test_quality_router.py``: TestClient OHNE ``with`` (kein
Lifespan, keine Postgres), ``get_session`` durch einen Merkstein ersetzt, der
Dienst je Test gefälscht. Die SQL- und Preis-Semantik ist in
``test_usage_analytics.py`` gegen die echte DB gepinnt; hier zählt nur, was die
Route mit Parametern, Auth und Antwort macht.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import boerdi.api.usage as usage_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()
_ANTWORT = {
    "empty": False, "calls": 1,
    "prompt_tokens": 10, "cached_tokens": 0,
    "completion_tokens": 2, "reasoning_tokens": 0,
    "currency": "EUR", "amount": "0.5", "price_unavailable": [],
    "models": [],
}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


def _fake(monkeypatch, name, result=None):
    calls: list[tuple] = []

    async def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(usage_api, name, fake)
    return calls


# ── GET /api/usage/session/{session_id} ─────────────────────────────────

def test_sitzung_reicht_di_sitzung_und_kennung_durch(client, monkeypatch) -> None:
    calls = _fake(monkeypatch, "session_usage", _ANTWORT)

    r = client.get("/api/usage/session/bb-1", headers=_AUTH)

    assert r.status_code == 200
    assert r.json() == _ANTWORT
    args, _ = calls[0]
    assert args[0] is _SESSION
    assert args[1] == "bb-1"


def test_sitzung_braucht_den_studio_schluessel(client) -> None:
    assert client.get("/api/usage/session/bb-1").status_code == 401


# ── GET /api/usage/period ───────────────────────────────────────────────

def test_zeitraum_nimmt_from_und_to_als_parameternamen(client, monkeypatch) -> None:
    """``from`` ist ein Python-Schlüsselwort; ohne Alias hieße der Parameter
    nach außen anders als im Plan vereinbart."""
    calls = _fake(monkeypatch, "period_usage", _ANTWORT)

    r = client.get("/api/usage/period", headers=_AUTH,
                   params={"from": "2026-01-01T00:00:00Z",
                           "to": "2026-02-01T00:00:00Z"})

    assert r.status_code == 200
    args, _ = calls[0]
    assert args[0] is _SESSION
    assert args[1] == datetime(2026, 1, 1, tzinfo=UTC)
    assert args[2] == datetime(2026, 2, 1, tzinfo=UTC)


def test_zeitraum_ohne_zeitzone_wird_als_utc_gelesen(client, monkeypatch) -> None:
    """``created_at`` ist ``timestamptz``. Eine zeitzonenlose Angabe würde
    sonst in der Zeitzone der DB-Sitzung ausgelegt — die Grenze verschöbe sich
    je nach Server, ohne dass es jemand merkt."""
    calls = _fake(monkeypatch, "period_usage", _ANTWORT)

    r = client.get("/api/usage/period", headers=_AUTH,
                   params={"from": "2026-01-01", "to": "2026-02-01"})

    assert r.status_code == 200
    args, _ = calls[0]
    assert args[1] == datetime(2026, 1, 1, tzinfo=UTC)
    assert args[1].tzinfo is not None


def test_zeitraum_verkehrt_herum_wird_abgewiesen(client, monkeypatch) -> None:
    """Ein leeres Ergebnis wäre die falsche Antwort: es sähe aus wie „keine
    Kosten" statt wie „so herum ergibt die Frage keinen Sinn"."""
    calls = _fake(monkeypatch, "period_usage", _ANTWORT)

    r = client.get("/api/usage/period", headers=_AUTH,
                   params={"from": "2026-02-01", "to": "2026-01-01"})

    assert r.status_code == 422
    assert calls == [], "der Dienst darf gar nicht erst gefragt werden"


def test_die_absage_spricht_die_sprache_des_studios(client, monkeypatch) -> None:
    """C1-e: Meldungen an die Redaktion gehen durch den Katalog und richten
    sich nach ``Accept-Language``."""
    _fake(monkeypatch, "period_usage", _ANTWORT)
    verkehrt = {"from": "2026-02-01", "to": "2026-01-01"}

    deutsch = client.get("/api/usage/period", headers=_AUTH, params=verkehrt)
    englisch = client.get("/api/usage/period", params=verkehrt,
                          headers={**_AUTH, "Accept-Language": "en"})

    assert "der Zeitraum ist leer" in deutsch.json()["detail"]
    assert "the period is empty" in englisch.json()["detail"]


def test_ein_uebergrosser_zeitraum_wird_abgewiesen(client, monkeypatch) -> None:
    """Ohne Deckel zieht ein vertippter Zeitraum („2000" statt „2026") die
    Gruppierung der ganzen Tabelle nach Python — je Sitzung UND Modell. Die
    Absage nennt die Grenze, sonst weiß die Redaktion nicht, was sie ändern
    soll."""
    calls = _fake(monkeypatch, "period_usage", _ANTWORT)

    r = client.get("/api/usage/period", headers=_AUTH,
                   params={"from": "2000-01-01", "to": "2026-01-01"})

    assert r.status_code == 422
    assert calls == [], "der Dienst darf gar nicht erst gefragt werden"
    assert str(usage_api.MAX_PERIOD_DAYS) in r.json()["detail"]


def test_genau_ein_jahr_ist_noch_erlaubt(client, monkeypatch) -> None:
    """Die Grenze ist einschließlich: ein volles Jahr ist die Frage, die die
    Kostenschau beantworten können muss."""
    calls = _fake(monkeypatch, "period_usage", _ANTWORT)

    r = client.get("/api/usage/period", headers=_AUTH,
                   params={"from": "2024-01-01", "to": "2024-12-31"})

    assert r.status_code == 200
    assert len(calls) == 1


def test_zeitraum_braucht_beide_grenzen(client) -> None:
    assert client.get("/api/usage/period", headers=_AUTH,
                      params={"from": "2026-01-01"}).status_code == 422


def test_zeitraum_braucht_den_studio_schluessel(client) -> None:
    r = client.get("/api/usage/period",
                   params={"from": "2026-01-01", "to": "2026-02-01"})
    assert r.status_code == 401
