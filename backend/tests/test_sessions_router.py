"""P7: sessions router — studio session-admin + the one public widget-history read.

Offline harness identical to the sibling router tests (test_rag_router_admin.py):
``TestClient`` WITHOUT ``with`` (no lifespan → no Postgres), the DI ``get_session``
overridden with a sentinel that must reach every service call, and the service
layer faked on the ``sessions`` module. The real DB semantics live in
services/db_sessions.py (pinned in test_db_sessions_pg.py) and services/
session_admin.py (pinned in the optional test_sessions_admin_pg.py).

These pins prove the HTTP layer only: ALT response shapes, the ``confirm`` purge
guard, the 503 optimize wrapper, the memory privacy gate, the public endpoint's
session-id validation + limit clamp (Audit T2), and that the DI session is passed
through to every service function.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.sessions as sessions_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach the service
_VALID = "bb-0123456789abcdef0123456789abcdef"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")  # public endpoint: no 429 interference
    get_settings.cache_clear()
    app = create_app()
    # dependency_overrides keys on the ORIGINAL dependency object; the router
    # imports it under an alias, but the underlying callable is the same.
    app.dependency_overrides[get_session] = lambda: _SESSION
    yield TestClient(app)
    get_settings.cache_clear()


def _fake(monkeypatch, name, result=None):
    """Fake a service fn on the sessions module, recording (args, kwargs)."""
    calls: list[tuple] = []

    async def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(sessions_api, name, fake)
    return calls


# ── GET / (list) ─────────────────────────────────────────────────────────
def test_list_passes_di_session_and_returns_service_list(client, monkeypatch):
    rows = [{"session_id": "bb-1", "persona_id": "", "state_id": "S1",
             "turn_count": 0, "created_at": None, "updated_at": None}]
    calls = _fake(monkeypatch, "list_sessions_admin", rows)
    r = client.get("/api/sessions/", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == rows
    assert calls == [((_SESSION,), {})]


# ── GET /db-stats ────────────────────────────────────────────────────────
def test_db_stats_returns_service_dict(client, monkeypatch):
    stats = {"size_bytes": 100, "live_tuples": 5, "dead_tuples": 2, "reclaimable_bytes": 28}
    calls = _fake(monkeypatch, "get_db_stats", stats)
    r = client.get("/api/sessions/db-stats", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == stats
    assert calls == [((_SESSION,), {})]


def test_db_stats_is_not_shadowed_by_the_session_id_route(client, monkeypatch):
    # Static /db-stats must win over the dynamic /{session_id} GET.
    _fake(monkeypatch, "get_db_stats", {"size_bytes": 1})
    got = _fake(monkeypatch, "get_or_create_session", {"session_id": "db-stats"})
    client.get("/api/sessions/db-stats", headers=_AUTH)
    assert got == []  # get_session handler never ran


# ── POST /purge ──────────────────────────────────────────────────────────
def test_purge_without_confirm_is_rejected(client, monkeypatch):
    calls = _fake(monkeypatch, "purge_all", {"messages": 0})
    r = client.post("/api/sessions/purge", headers=_AUTH)
    assert r.status_code == 400
    assert calls == []  # guard fires before any delete


def test_purge_with_confirm_forwards_flags_and_echoes_alt_shape(client, monkeypatch):
    counts = {"messages": 3, "memory": 1, "quality_logs": 2}
    calls = _fake(monkeypatch, "purge_all", counts)
    r = client.post(
        "/api/sessions/purge",
        params={"confirm": "true", "safety_logs": "true", "sessions": "false"},
        headers=_AUTH,
    )
    assert r.status_code == 200
    assert r.json() == {"status": "purged", "deleted": counts}
    (args, kwargs) = calls[0]
    assert args == (_SESSION,)
    # confirm is a router-only guard — never forwarded to the service.
    assert "confirm" not in kwargs
    assert kwargs == {"messages": True, "memory": True, "quality_logs": True,
                      "safety_logs": True, "sessions": False}


# ── POST /optimize ───────────────────────────────────────────────────────
def test_optimize_success_merges_result_into_status(client, monkeypatch):
    calls = _fake(monkeypatch, "optimize_database",
                  {"before_bytes": 10, "after_bytes": 4, "reclaimed_bytes": 6})
    r = client.post("/api/sessions/optimize", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "optimized", "before_bytes": 10,
                        "after_bytes": 4, "reclaimed_bytes": 6}
    assert calls == [((_SESSION,), {})]


def test_optimize_failure_becomes_503(client, monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(sessions_api, "optimize_database", _boom)
    r = client.post("/api/sessions/optimize", headers=_AUTH)
    assert r.status_code == 503


# ── GET /{session_id} ────────────────────────────────────────────────────
def test_get_session_returns_alt_shape_without_reparsing(client, monkeypatch):
    # NEU get_or_create_session already returns entities/signal_history parsed
    # (dict/list) — the endpoint must NOT json.loads them again (ALT deviation).
    full = {"session_id": "bb-1", "persona_id": "P-AND", "state_id": "S3",
            "entities": {"fach": "Bio"}, "signal_history": [{"s": 1}],
            "turn_count": 5, "tour_state": {}, "created_at": "x", "updated_at": "y"}
    calls = _fake(monkeypatch, "get_or_create_session", full)
    r = client.get("/api/sessions/bb-1", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"session_id": "bb-1", "persona_id": "P-AND", "state_id": "S3",
                        "entities": {"fach": "Bio"}, "signal_history": [{"s": 1}],
                        "turn_count": 5}
    assert calls == [((_SESSION, "bb-1"), {})]


# ── DELETE /{session_id} ─────────────────────────────────────────────────
def test_delete_session_reports_per_table_counts(client, monkeypatch):
    counts = {"messages": 2, "memory": 1, "quality_logs": 0, "safety_logs": 0, "sessions": 1}
    calls = _fake(monkeypatch, "db_delete_session", counts)
    r = client.delete("/api/sessions/bb-x", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "deleted", "session_id": "bb-x", "deleted": counts}
    assert calls == [((_SESSION, "bb-x"), {})]


# ── GET /{session_id}/memory ─────────────────────────────────────────────
def test_get_memory_passes_type_filter_and_returns_list(client, monkeypatch):
    mem = [{"key": "fach", "value": "Bio", "memory_type": "short"}]
    calls = _fake(monkeypatch, "get_memory", mem)
    r = client.get("/api/sessions/bb-1/memory", params={"memory_type": "short"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == mem
    assert calls == [((_SESSION, "bb-1", "short"), {})]


def test_get_memory_defaults_type_to_none(client, monkeypatch):
    calls = _fake(monkeypatch, "get_memory", [])
    client.get("/api/sessions/bb-1/memory", headers=_AUTH)
    assert calls == [((_SESSION, "bb-1", None), {})]


# ── POST /{session_id}/memory ────────────────────────────────────────────
def test_set_memory_creates_session_then_saves(client, monkeypatch):
    monkeypatch.setattr(sessions_api, "load_privacy_config", lambda: {"memory": True})
    got = _fake(monkeypatch, "get_or_create_session", {"session_id": "bb-new"})
    saved = _fake(monkeypatch, "save_memory", None)
    r = client.post("/api/sessions/bb-new/memory",
                    params={"key": "fach", "value": "Mathe"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "saved", "persisted": True,
                        "key": "fach", "memory_type": "short"}
    # N-1 (Audit): session created BEFORE the memory write (FK safety).
    assert got == [((_SESSION, "bb-new"), {})]
    assert saved == [((_SESSION, "bb-new", "fach", "Mathe", "short"), {})]


def test_set_memory_dropped_when_privacy_disables_it(client, monkeypatch):
    monkeypatch.setattr(sessions_api, "load_privacy_config", lambda: {"memory": False})
    saved = _fake(monkeypatch, "save_memory", None)
    r = client.post("/api/sessions/bb-new/memory",
                    params={"key": "fach", "value": "Mathe"}, headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is False and body["status"] == "skipped"
    assert saved == []  # nothing written


# ── DELETE /{session_id}/messages ────────────────────────────────────────
def test_delete_messages_clears_only_messages(client, monkeypatch):
    calls = _fake(monkeypatch, "delete_messages_for_session", 3)
    r = client.delete("/api/sessions/bb-x/messages", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "cleared", "session_id": "bb-x", "deleted_messages": 3}
    assert calls == [((_SESSION, "bb-x"), {})]


# ── [public] GET /{session_id}/messages ──────────────────────────────────
def test_public_messages_accepts_valid_id_and_passes_di_session(client, monkeypatch):
    calls = _fake(monkeypatch, "get_messages", [{"id": 1, "role": "user", "content": "hi"}])
    r = client.get(f"/api/sessions/{_VALID}/messages")  # NO auth header — public
    assert r.status_code == 200
    assert r.json() == [{"id": 1, "role": "user", "content": "hi"}]
    (args, _kwargs) = calls[0]
    assert args[0] is _SESSION and args[1] == _VALID


def test_public_messages_rejects_malformed_id(client, monkeypatch):
    _fake(monkeypatch, "get_messages", [])
    for bad in ["has space", "bad!bang", "a" * 200, "semi;colon"]:
        r = client.get(f"/api/sessions/{bad}/messages")
        assert r.status_code == 400, f"expected 400 for {bad!r}, got {r.status_code}"


def test_public_messages_clamps_limit(client, monkeypatch):
    calls = _fake(monkeypatch, "get_messages", [])
    client.get(f"/api/sessions/{_VALID}/messages", params={"limit": 999999})
    assert calls[-1][0][2] == 200  # upper bound
    client.get(f"/api/sessions/{_VALID}/messages", params={"limit": 0})
    assert calls[-1][0][2] == 1  # lower bound


# ── auth matrix ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/sessions/"),
        ("GET", "/api/sessions/db-stats"),
        ("POST", "/api/sessions/purge"),
        ("POST", "/api/sessions/optimize"),
        ("GET", "/api/sessions/bb-1"),
        ("DELETE", "/api/sessions/bb-1"),
        ("GET", "/api/sessions/bb-1/memory"),
        ("POST", "/api/sessions/bb-1/memory"),
        ("DELETE", "/api/sessions/bb-1/messages"),
    ],
)
def test_studio_endpoints_require_studio_key(client, method, path):
    assert client.request(method, path).status_code == 401


def test_public_messages_endpoint_needs_no_key(client, monkeypatch):
    _fake(monkeypatch, "get_messages", [])
    # No X-Studio-Key header, yet reachable — the widget restores history openly.
    assert client.get(f"/api/sessions/{_VALID}/messages").status_code == 200


def test_public_messages_returns_200_under_active_rate_limit(monkeypatch):
    # Regression: the endpoint returns list[dict] (not a Response). slowapi
    # (headers_enabled=True) injects X-RateLimit-* via the endpoint's
    # `response: Response` param; without it the SUCCESS path 500s once the limiter
    # is active (V7 default ON). The `client` fixture sets RATE_LIMIT_CHAT=off,
    # which masks this — here the limiter is ON.
    monkeypatch.setenv("RATE_LIMIT_CHAT", "100/minute")
    get_settings.cache_clear()

    async def _fake_messages(*args, **kwargs):
        return []

    monkeypatch.setattr(sessions_api, "get_messages", _fake_messages)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    limited = TestClient(app, raise_server_exceptions=False)
    r = limited.get(f"/api/sessions/{_VALID}/messages")
    assert r.status_code == 200
    assert r.json() == []
    assert "x-ratelimit-limit" in {k.lower() for k in r.headers}
    get_settings.cache_clear()
