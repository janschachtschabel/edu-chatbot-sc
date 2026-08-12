"""P7: quality analytics router (studio) — the thin HTTP layer.

Offline strategy mirrors ``test_rag_router_admin.py``: TestClient WITHOUT ``with``
(no lifespan → no Postgres), ``get_session`` overridden with a sentinel, the
analytics service faked per-test. The DB/jsonb semantics live in
``services/quality_analytics.py`` and are pinned there (pg-gated
``test_quality_pg.py``).

The two mutating service fns collide by name with the endpoint functions
(``delete_quality_log`` / ``clear_quality_logs``), so the router imports them
under ``*_svc`` aliases — that is what the fakes patch here.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.quality as quality_api
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


def _fake(monkeypatch, name, result=None):
    """Patch one analytics fn on the router module, recording (args, kwargs)."""
    calls: list[tuple] = []

    async def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(quality_api, name, fake)
    return calls


# ── GET /api/quality/logs ────────────────────────────────────────────────
def test_logs_wraps_rows_with_count_and_passes_filters(client, monkeypatch):
    calls = _fake(monkeypatch, "get_quality_logs", [{"id": 2}, {"id": 1}])
    r = client.get(
        "/api/quality/logs",
        params={"limit": 5, "session_id": "s", "pattern_id": "M04",
                "intent_id": "I01", "scope": "eval"},
        headers=_AUTH,
    )
    assert r.status_code == 200
    assert r.json() == {"count": 2, "logs": [{"id": 2}, {"id": 1}]}
    args, kwargs = calls[0]
    assert args[0] is _SESSION  # DI session reaches the service first
    assert kwargs == {"limit": 5, "session_id": "s", "pattern_id": "M04",
                      "intent_id": "I01", "scope": "eval"}


def test_logs_defaults_match_alt(client, monkeypatch):
    calls = _fake(monkeypatch, "get_quality_logs", [])
    r = client.get("/api/quality/logs", headers=_AUTH)
    assert r.json() == {"count": 0, "logs": []}
    _, kwargs = calls[0]
    assert kwargs == {"limit": 100, "session_id": "", "pattern_id": "",
                      "intent_id": "", "scope": "all"}


def test_logs_limit_bounds_are_enforced(client, monkeypatch):
    _fake(monkeypatch, "get_quality_logs", [])
    assert client.get("/api/quality/logs", params={"limit": 0},
                      headers=_AUTH).status_code == 422
    assert client.get("/api/quality/logs", params={"limit": 501},
                      headers=_AUTH).status_code == 422


# ── DELETE /api/quality/logs/{log_id} ────────────────────────────────────
def test_delete_returns_status_and_id(client, monkeypatch):
    calls = _fake(monkeypatch, "delete_quality_log_svc", 1)
    r = client.delete("/api/quality/logs/42", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "deleted", "id": 42}
    assert calls[0][0] == (_SESSION, 42)  # session + log_id, positional


def test_delete_missing_row_is_404(client, monkeypatch):
    _fake(monkeypatch, "delete_quality_log_svc", 0)
    r = client.delete("/api/quality/logs/999", headers=_AUTH)
    assert r.status_code == 404
    # C1-e3: zweisprachig, ohne Header deutsch (siehe test_i18n_messages).
    assert r.json()["detail"] == "Log nicht gefunden."


def test_delete_missing_row_message_follows_accept_language(client, monkeypatch):
    _fake(monkeypatch, "delete_quality_log_svc", 0)
    r = client.delete("/api/quality/logs/999",
                      headers={**_AUTH, "Accept-Language": "en"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Log not found."


# ── POST /api/quality/logs/clear ─────────────────────────────────────────
def test_clear_with_filter_echoes_filter_and_deleted(client, monkeypatch):
    calls = _fake(monkeypatch, "clear_quality_logs_svc", 3)
    r = client.post("/api/quality/logs/clear", params={"session_id": "s"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "status": "cleared", "deleted": 3,
        "filter": {"session_id": "s", "pattern_id": "", "intent_id": "", "scope": "all"},
    }
    args, kwargs = calls[0]
    assert args[0] is _SESSION
    assert kwargs == {"session_id": "s", "pattern_id": "", "intent_id": "", "scope": "all"}


def test_clear_without_filter_or_confirm_is_400_and_skips_service(client, monkeypatch):
    calls = _fake(monkeypatch, "clear_quality_logs_svc", 99)
    r = client.post("/api/quality/logs/clear", headers=_AUTH)
    assert r.status_code == 400
    assert calls == []  # guard trips before the service is ever called


def test_clear_confirm_true_bypasses_guard(client, monkeypatch):
    calls = _fake(monkeypatch, "clear_quality_logs_svc", 7)
    r = client.post("/api/quality/logs/clear", params={"confirm": "true"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["deleted"] == 7
    assert len(calls) == 1


def test_clear_scope_not_all_bypasses_guard(client, monkeypatch):
    calls = _fake(monkeypatch, "clear_quality_logs_svc", 4)
    r = client.post("/api/quality/logs/clear", params={"scope": "eval"}, headers=_AUTH)
    assert r.status_code == 200
    _, kwargs = calls[0]
    assert kwargs == {"session_id": "", "pattern_id": "", "intent_id": "", "scope": "eval"}


# ── GET analytics passthrough (dict returned verbatim) ───────────────────
@pytest.mark.parametrize(
    ("path", "svc_name", "params", "expected_kwargs"),
    [
        ("/api/quality/stats", "get_quality_stats",
         {"scope": "eval"}, {"scope": "eval"}),
        ("/api/quality/matrix", "get_routing_matrix",
         {"scope": "production", "min_count": 3}, {"scope": "production", "min_count": 3}),
        ("/api/quality/state-transitions", "get_state_transitions",
         {"scope": "eval", "days": 7, "min_count": 2},
         {"scope": "eval", "days": 7, "min_count": 2}),
        ("/api/quality/tight-races", "get_tight_races_breakdown",
         {"scope": "all", "threshold": 0.05, "limit": 10},
         {"scope": "all", "threshold": 0.05, "limit": 10}),
        ("/api/quality/degradations", "get_degradation_breakdown",
         {"scope": "eval", "limit": 5}, {"scope": "eval", "limit": 5}),
        ("/api/quality/empty-entities", "get_empty_entities_breakdown",
         {"scope": "eval", "limit": 5}, {"scope": "eval", "limit": 5}),
        ("/api/quality/low-confidence", "get_low_confidence_turns",
         {"scope": "eval", "max_confidence": 0.4, "limit": 5},
         {"scope": "eval", "max_confidence": 0.4, "limit": 5}),
    ],
)
def test_analytics_get_passthrough(client, monkeypatch, path, svc_name, params, expected_kwargs):
    sentinel = {"ok": True, "svc": svc_name}
    calls = _fake(monkeypatch, svc_name, sentinel)
    r = client.get(path, params=params, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == sentinel  # service dict returned verbatim
    args, kwargs = calls[0]
    assert args[0] is _SESSION
    assert kwargs == expected_kwargs


@pytest.mark.parametrize(
    ("path", "svc_name", "expected_kwargs"),
    [
        ("/api/quality/stats", "get_quality_stats", {"scope": "all"}),
        ("/api/quality/matrix", "get_routing_matrix", {"scope": "all", "min_count": 1}),
        ("/api/quality/state-transitions", "get_state_transitions",
         {"scope": "all", "days": 30, "min_count": 1}),
        ("/api/quality/tight-races", "get_tight_races_breakdown",
         {"scope": "all", "threshold": 0.02, "limit": 50}),
        ("/api/quality/degradations", "get_degradation_breakdown",
         {"scope": "all", "limit": 50}),
        ("/api/quality/empty-entities", "get_empty_entities_breakdown",
         {"scope": "all", "limit": 50}),
        ("/api/quality/low-confidence", "get_low_confidence_turns",
         {"scope": "all", "max_confidence": 0.6, "limit": 30}),
    ],
)
def test_analytics_get_defaults_match_alt(client, monkeypatch, path, svc_name, expected_kwargs):
    calls = _fake(monkeypatch, svc_name, {})
    r = client.get(path, headers=_AUTH)
    assert r.status_code == 200
    _, kwargs = calls[0]
    assert kwargs == expected_kwargs


def test_state_transitions_days_bounds_enforced(client, monkeypatch):
    _fake(monkeypatch, "get_state_transitions", {})
    assert client.get("/api/quality/state-transitions", params={"days": 0},
                      headers=_AUTH).status_code == 422
    assert client.get("/api/quality/state-transitions", params={"days": 366},
                      headers=_AUTH).status_code == 422


# ── auth (router-level StudioKey security) ───────────────────────────────
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/quality/logs"),
        ("DELETE", "/api/quality/logs/1"),
        ("POST", "/api/quality/logs/clear"),
        ("GET", "/api/quality/stats"),
        ("GET", "/api/quality/matrix"),
        ("GET", "/api/quality/state-transitions"),
        ("GET", "/api/quality/tight-races"),
        ("GET", "/api/quality/degradations"),
        ("GET", "/api/quality/empty-entities"),
        ("GET", "/api/quality/low-confidence"),
    ],
)
def test_quality_endpoints_require_studio_key(client, method, path):
    assert client.request(method, path).status_code == 401
