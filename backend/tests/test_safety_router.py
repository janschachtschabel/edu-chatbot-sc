"""P7: safety router — recent safety-log rows (/logs) + aggregate stats (/stats).

Offline harness identical to ``test_rag_router_admin.py``: ``TestClient`` WITHOUT
``with`` (no lifespan → no Postgres), ``get_session`` overridden with a sentinel,
the DB query (``get_safety_logs``) faked. The query semantics live in
``services/safety_logs_query.py`` and are pinned against the real Postgres in
``test_safety_pg.py``. What is exercised HERE is the router's own logic — the
``{count, logs}`` envelope and the ``/stats`` aggregation (both ALT-verbatim from
``app/routers/safety.py``) — driven through a faked ``get_safety_logs``, the way
the rag test drives ``get_rag_area``'s grouping.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.safety as safety_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach the service


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


def _fake_logs(monkeypatch, result):
    """Fake ``get_safety_logs``, recording ``(args, kwargs)`` of each call."""
    calls: list[tuple] = []

    async def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(safety_api, "get_safety_logs", fake)
    return calls


def _row(risk_level="low", escalated=0, rate_limited=0, legal_flags=None):
    """One ALT-shaped safety-log row (all 15 keys the Studio expects)."""
    return {
        "id": 1, "session_id": "s", "ip": "", "risk_level": risk_level,
        "stages_run": [], "reasons": [], "legal_flags": legal_flags or [],
        "flagged_categories": [], "blocked_tools": [], "enforced_pattern": "",
        "escalated": escalated, "rate_limited": rate_limited, "message": "m",
        "categories_json": {}, "created_at": "2026-07-24T12:00:00+00:00",
    }


# ── GET /api/safety/logs ─────────────────────────────────────────────────
def test_logs_passes_di_session_and_default_params(client, monkeypatch):
    calls = _fake_logs(monkeypatch, [])
    r = client.get("/api/safety/logs", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"count": 0, "logs": []}
    (args, kwargs), = calls
    assert args == (_SESSION,)  # the DI session reaches the service, positionally
    assert kwargs == {"limit": 100, "risk_min": "", "session_id": ""}


def test_logs_forwards_query_params(client, monkeypatch):
    calls = _fake_logs(monkeypatch, [])
    r = client.get(
        "/api/safety/logs",
        params={"limit": 5, "risk_min": "high", "session_id": "abc"},
        headers=_AUTH,
    )
    assert r.status_code == 200
    (args, kwargs), = calls
    assert args == (_SESSION,)
    assert kwargs == {"limit": 5, "risk_min": "high", "session_id": "abc"}


def test_logs_envelope_counts_rows_and_passes_them_through(client, monkeypatch):
    rows = [_row(risk_level="high"), _row(risk_level="medium"), _row()]
    _fake_logs(monkeypatch, rows)
    body = client.get("/api/safety/logs", headers=_AUTH).json()
    assert body["count"] == 3
    assert body["logs"] == rows  # verbatim, including the categories_json key


# ── GET /api/safety/stats ────────────────────────────────────────────────
def test_stats_aggregates_risk_legal_flags_and_reads_a_wide_window(client, monkeypatch):
    calls = _fake_logs(monkeypatch, [
        _row(risk_level="high", escalated=1, legal_flags=["strafrecht", "jugendschutz"]),
        _row(risk_level="high", rate_limited=1, legal_flags=["strafrecht"]),
        _row(risk_level="medium", escalated=1),
        _row(risk_level="low"),
    ])
    r = client.get("/api/safety/stats", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "total": 4,
        "by_risk": {"low": 1, "medium": 1, "high": 2},
        "by_legal": {"strafrecht": 2, "jugendschutz": 1},
        "rate_limited": 1,
        "escalated": 2,
    }
    (args, kwargs), = calls
    assert args == (_SESSION,)
    assert kwargs == {"limit": 1000}  # ALT reads up to 1000 rows for the dashboard


def test_stats_on_empty_returns_zeroed_buckets(client, monkeypatch):
    _fake_logs(monkeypatch, [])
    assert client.get("/api/safety/stats", headers=_AUTH).json() == {
        "total": 0,
        "by_risk": {"low": 0, "medium": 0, "high": 0},
        "by_legal": {},
        "rate_limited": 0,
        "escalated": 0,
    }


# ── auth ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", ["/api/safety/logs", "/api/safety/stats"])
def test_safety_endpoints_require_studio_key(client, path):
    assert client.get(path).status_code == 401
