"""P7: loadtest router (studio, gated by ``allow_loadtest``; runs persisted in
``loadtest_runs`` — improvement V9).

Offline strategy as in ``test_rag_router_admin.py``: TestClient WITHOUT ``with``
(no lifespan → no Postgres), ``get_session`` overridden with a sentinel, the
service layer faked. The run **executor is never invoked for real** — the
background runner fires the live /api/chat pipeline (LLM+MCP), so both it and the
fire-and-forget spawn are replaced with recorders. The DB semantics live in
``services/loadtest.py`` and are pinned there (``test_loadtest_pg.py``).

The gate helper is ported from ALT ``test_loadtest_gate.py`` (env → 403), adapted
to the settings-based ``allow_loadtest`` flag.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import boerdi.api.loadtest as loadtest_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach the service


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Isolate the lru_cached settings around every test (gate toggles env)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


def _afake(monkeypatch, name, result=None):
    """Replace an async service coroutine referenced on the router module."""
    calls: list[tuple] = []

    async def fake(*args, **kwargs):
        calls.append(args)
        return result

    monkeypatch.setattr(loadtest_api, name, fake)
    return calls


def _capture_runner(monkeypatch):
    """Neutralise the runner + fire-and-forget spawn so no real load fires."""
    exec_calls: list[tuple] = []
    spawned: list = []

    def fake_exec(*args, **kwargs):
        exec_calls.append(args)
        return "coro-sentinel"

    def fake_spawn(coro):
        spawned.append(coro)

    monkeypatch.setattr(loadtest_api, "execute_load_test", fake_exec)
    monkeypatch.setattr(loadtest_api, "_spawn_background", fake_spawn)
    return exec_calls, spawned


# ── GET /api/loadtest/mix-options ─────────────────────────────────────────
def test_mix_options_lists_every_category_with_label_and_prompt(client):
    r = client.get("/api/loadtest/mix-options", headers=_AUTH)
    assert r.status_code == 200
    opts = r.json()["options"]
    assert {o["key"] for o in opts} == {"wissen", "suche", "orientierung", "lernpfad"}
    assert all(o["label"] and o["prompt"] for o in opts)


# ── gate helper (ported from ALT test_loadtest_gate.py) ───────────────────
def test_gate_helper_allows_by_default(monkeypatch):
    monkeypatch.delenv("BOERDI_ALLOW_LOADTEST", raising=False)
    get_settings.cache_clear()
    assert loadtest_api._ensure_loadtest_allowed("de") is None


def test_gate_helper_allows_explicit_true(monkeypatch):
    monkeypatch.setenv("BOERDI_ALLOW_LOADTEST", "true")
    get_settings.cache_clear()
    assert loadtest_api._ensure_loadtest_allowed("de") is None


# ALT accepted whitespace-padded values (" Off ") via its own ``.strip().lower()``;
# NEU reads the ported ``allow_loadtest`` bool setting, and pydantic's bool parser
# only strips ``str``-typed fields — a padded bool env value raises at settings
# build time. Realistic operator values (no surrounding spaces) all work here.
@pytest.mark.parametrize("val", ["false", "0", "no", "off", "FALSE"])
def test_gate_helper_raises_403_when_disabled(monkeypatch, val):
    monkeypatch.setenv("BOERDI_ALLOW_LOADTEST", val)
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        loadtest_api._ensure_loadtest_allowed("de")
    assert exc.value.status_code == 403


def test_post_run_refused_403_when_gate_disabled(client, monkeypatch):
    monkeypatch.setenv("BOERDI_ALLOW_LOADTEST", "false")
    get_settings.cache_clear()
    r = client.post("/api/loadtest/runs", json={}, headers=_AUTH)
    assert r.status_code == 403


def test_gate_meldet_in_der_sprache_der_anfrage(client, monkeypatch):
    """C1-e2: derselbe 403 spricht die Sprache, die die Anfrage mitbringt.

    Der Weg lohnt einen echten Endpunkt-Test statt nur des Katalog-Wächters:
    zwischen `Accept-Language` und dem Satz liegen die Abhängigkeit in
    `deps.py`, die Signatur des Handlers und die Weitergabe an den Helfer —
    drei Stellen, an denen ein Katalog-Eintrag stumm bleiben könnte.
    """
    monkeypatch.setenv("BOERDI_ALLOW_LOADTEST", "false")
    get_settings.cache_clear()

    ohne = client.post("/api/loadtest/runs", json={}, headers=_AUTH)
    assert "deaktiviert" in ohne.json()["detail"]

    englisch = client.post(
        "/api/loadtest/runs",
        json={},
        headers={**_AUTH, "Accept-Language": "en-GB,en;q=0.9,de;q=0.8"},
    )
    assert englisch.status_code == 403
    assert "is disabled on this instance" in englisch.json()["detail"]

    # Eine Sprache, die es nicht gibt, fällt auf Deutsch zurück statt auf leer.
    fremd = client.post(
        "/api/loadtest/runs", json={}, headers={**_AUTH, "Accept-Language": "fr-FR"}
    )
    assert "deaktiviert" in fremd.json()["detail"]


# ── POST /api/loadtest/runs ───────────────────────────────────────────────
def test_start_run_persists_running_row_and_spawns_runner(client, monkeypatch):
    running = _afake(monkeypatch, "any_run_running", None)
    created = _afake(monkeypatch, "create_run", None)
    exec_calls, spawned = _capture_runner(monkeypatch)

    r = client.post(
        "/api/loadtest/runs",
        json={
            "stages": [1, 2, 4],
            "requests_per_stage": 6,
            "mix": {"wissen": 1, "suche": 1, "orientierung": 1},
            "p95_threshold_s": 20.0,
        },
        headers=_AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    norm = {
        "stages": [1, 2, 4],
        "requests_per_stage": 6,
        "mix": {"wissen": 1, "suche": 1, "orientierung": 1},
        "p95_threshold_s": 20.0,
        "total_requests": 18,
    }
    assert body["status"] == "running"
    assert body["id"].startswith("lt-")
    assert body["profile"] == norm
    # running-check first, then the row is persisted with the DI session + norm
    assert running == [(_SESSION,)]
    assert created[0][0] is _SESSION
    assert created[0][1] == body["id"]
    assert created[0][2] == norm
    # runner handed the app + run_id + norm, then dispatched exactly once
    assert exec_calls[0][1] == body["id"] and exec_calls[0][2] == norm
    assert len(spawned) == 1


def test_start_run_409_when_a_run_is_already_running(client, monkeypatch):
    _afake(monkeypatch, "any_run_running", "lt-busy")
    created = _afake(monkeypatch, "create_run", None)
    exec_calls, spawned = _capture_runner(monkeypatch)

    r = client.post("/api/loadtest/runs", json={}, headers=_AUTH)
    assert r.status_code == 409
    assert "lt-busy" in r.json()["detail"]
    assert created == []  # nothing persisted, nothing spawned
    assert exec_calls == [] and spawned == []


def test_start_run_400_when_profile_exceeds_total_cap(client, monkeypatch):
    _afake(monkeypatch, "any_run_running", None)
    created = _afake(monkeypatch, "create_run", None)
    _capture_runner(monkeypatch)

    # 6 stages * 60 requests = 360 > MAX_TOTAL_REQUESTS (200)
    r = client.post(
        "/api/loadtest/runs",
        json={"stages": [1, 2, 3, 4, 5, 6], "requests_per_stage": 60, "mix": {"wissen": 1}},
        headers=_AUTH,
    )
    assert r.status_code == 400
    assert created == []


def test_start_run_400_on_unknown_mix_category(client, monkeypatch):
    _afake(monkeypatch, "any_run_running", None)
    _afake(monkeypatch, "create_run", None)
    _capture_runner(monkeypatch)

    r = client.post(
        "/api/loadtest/runs",
        json={"stages": [1], "requests_per_stage": 1, "mix": {"quatsch": 1}},
        headers=_AUTH,
    )
    assert r.status_code == 400
    assert "quatsch" in r.json()["detail"]


# ── GET /api/loadtest/runs ────────────────────────────────────────────────
def test_list_runs_passes_di_session_and_wraps_service_list(client, monkeypatch):
    row = {"id": "lt-1", "status": "completed", "created_at": "2026-07-24T00:00:00+00:00",
           "finished_at": None, "profile": {}, "summary": None, "error": None}
    calls = _afake(monkeypatch, "list_runs", [row])
    r = client.get("/api/loadtest/runs", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"runs": [row]}
    assert calls == [(_SESSION,)]


# ── GET /api/loadtest/runs/{run_id} ───────────────────────────────────────
def test_get_run_returns_the_full_service_dict(client, monkeypatch):
    full = {"id": "lt-9", "status": "running", "created_at": "2026-07-24T00:00:00+00:00",
            "finished_at": None, "profile": {"stages": [1]}, "stages": [],
            "resource_samples": [], "summary": None, "error": None}
    calls = _afake(monkeypatch, "load_run", full)
    r = client.get("/api/loadtest/runs/lt-9", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == full
    assert calls == [(_SESSION, "lt-9")]


def test_get_run_404_when_missing(client, monkeypatch):
    _afake(monkeypatch, "load_run", None)
    r = client.get("/api/loadtest/runs/nope", headers=_AUTH)
    assert r.status_code == 404


# ── DELETE /api/loadtest/runs/{run_id} ────────────────────────────────────
def test_delete_run_removes_a_finished_run(client, monkeypatch):
    _afake(monkeypatch, "load_run", {"id": "lt-2", "status": "completed"})
    deleted = _afake(monkeypatch, "delete_run", True)
    r = client.delete("/api/loadtest/runs/lt-2", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"deleted": "lt-2"}
    assert deleted == [(_SESSION, "lt-2")]


def test_delete_run_409_refuses_a_running_run(client, monkeypatch):
    _afake(monkeypatch, "load_run", {"id": "lt-3", "status": "running"})
    deleted = _afake(monkeypatch, "delete_run", True)
    r = client.delete("/api/loadtest/runs/lt-3", headers=_AUTH)
    assert r.status_code == 409
    assert deleted == []  # never asked to delete a live run


def test_delete_run_404_when_nothing_deleted(client, monkeypatch):
    _afake(monkeypatch, "load_run", None)
    _afake(monkeypatch, "delete_run", False)
    r = client.delete("/api/loadtest/runs/ghost", headers=_AUTH)
    assert r.status_code == 404


# ── auth ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/loadtest/mix-options"),
        ("GET", "/api/loadtest/runs"),
        ("POST", "/api/loadtest/runs"),
        ("GET", "/api/loadtest/runs/lt-1"),
        ("DELETE", "/api/loadtest/runs/lt-1"),
    ],
)
def test_endpoints_require_studio_key(client, method, path):
    assert client.request(method, path).status_code == 401
