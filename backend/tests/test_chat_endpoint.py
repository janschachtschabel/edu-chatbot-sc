"""R4f-1: POST /api/chat — the non-streaming endpoint = first-e2e-turn wiring.

The router's job is HTTP translation + turn-orchestration glue: build the
per-request turn graph, run it under the per-session lock, extract
``early_response or response`` from the state dict, apply the widget-modes
postprocess, and convert any unhandled graph error into a graceful chat bubble
(never HTTP 500). The graph and its nodes have their own suites, so these pins
fake ``build_turn_graph`` and patch the collaborators on the chat module —
deterministic and offline. The sentinel session doubles as proof that the DI
session reaches the graph builder.

``TestClient`` is used WITHOUT a ``with`` block on purpose (as in
test_rag_router.py): the context manager would run the lifespan, which needs a
real Postgres. ``get_session`` is overridden, so it is never called.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import boerdi.api.chat as chat_api
from boerdi.api.deps import get_session
from boerdi.api.schemas import ChatResponse
from boerdi.main import create_app
from boerdi.settings import get_settings

_SESSION = object()  # sentinel: whatever get_session yields must reach build_turn_graph


def _ok(content="X"):
    """A normal-path graph result dict carrying a ChatResponse under ``response``."""
    return {"response": ChatResponse(session_id="bb-1", content=content)}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")  # deterministic: no limiter interference
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    yield TestClient(app)
    get_settings.cache_clear()


class _FakeGraph:
    """Stand-in compiled graph: ``ainvoke`` returns a preset state dict or raises."""

    def __init__(self, *, result=None, exc=None):
        self._result, self._exc = result, exc
        self.invoked_with = None

    async def ainvoke(self, state):
        self.invoked_with = state
        if self._exc is not None:
            raise self._exc
        return self._result


def _patch(monkeypatch, *, result=None, exc=None):
    graph = _FakeGraph(result=result, exc=exc)
    builds: list[dict] = []

    def _fake_build(*, session, peer_ip="", on_token=None):
        builds.append({"session": session, "peer_ip": peer_ip, "on_token": on_token})
        return graph

    async def _fake_pp(req, resp, *a, **k):
        return resp

    saves: list[dict] = []

    async def _fake_save(session, session_id, role, content, **k):
        saves.append({"session": session, "session_id": session_id,
                      "role": role, "content": content, "debug": k.get("debug")})

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _fake_pp)
    monkeypatch.setattr(chat_api, "save_message", _fake_save)
    return graph, builds, saves


def _post(client, **over):
    body = {"session_id": "bb-1", "message": "hallo", "environment": {}}
    body.update(over)
    return client.post("/api/chat", json=body)


# ── Response extraction ─────────────────────────────────────────────────────

def test_returns_response_from_graph(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert r.status_code == 200
    assert r.json()["content"] == "HI"


def test_early_response_takes_precedence_over_response(monkeypatch, client):
    _patch(monkeypatch, result={
        "early_response": ChatResponse(session_id="bb-1", content="EARLY"),
        "response": ChatResponse(session_id="bb-1", content="NORMAL"),
    })
    assert _post(client).json()["content"] == "EARLY"


# ── Seam binding ────────────────────────────────────────────────────────────

def test_passes_di_session_peer_ip_and_no_on_token(monkeypatch, client):
    _, builds, _ = _patch(monkeypatch, result=_ok())
    _post(client)
    assert builds[0]["session"] is _SESSION
    assert builds[0]["peer_ip"] == "7.7.7.7"
    assert builds[0]["on_token"] is None  # non-streaming path


def test_chat_returns_200_under_active_rate_limit(monkeypatch):
    # Regression: /api/chat returns a ChatResponse (a Pydantic model, NOT a
    # Response). slowapi (headers_enabled=True) injects X-RateLimit-* via the
    # endpoint's `response: Response` param; without it the SUCCESS path 500s the
    # moment the limiter is active (V7 default ON). The `client` fixture sets
    # RATE_LIMIT_CHAT=off, which masks this — here the limiter is ON.
    monkeypatch.setenv("RATE_LIMIT_CHAT", "100/minute")
    get_settings.cache_clear()
    _patch(monkeypatch, result=_ok("HI"))
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    limited = TestClient(app, raise_server_exceptions=False)
    r = limited.post("/api/chat", json={"session_id": "bb-1", "message": "hallo"})
    assert r.status_code == 200
    assert r.json()["content"] == "HI"
    assert "x-ratelimit-limit" in {k.lower() for k in r.headers}
    get_settings.cache_clear()


def test_turncontext_seeded_from_request(monkeypatch, client):
    graph, _, _ = _patch(monkeypatch, result=_ok())
    _post(client, message="frage?")
    assert graph.invoked_with.req.message == "frage?"
    assert graph.invoked_with.req.session_id == "bb-1"


def test_widget_postprocess_output_is_returned(monkeypatch, client):
    _patch(monkeypatch, result=_ok("RAW"))

    async def _transform(req, resp, *a, **k):
        return ChatResponse(session_id=resp.session_id, content="POSTPROCESSED")

    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _transform)
    assert _post(client).json()["content"] == "POSTPROCESSED"


# ── Error bubble (never HTTP 500) ───────────────────────────────────────────

def test_graph_exception_becomes_graceful_bubble(monkeypatch, client):
    _, _, saves = _patch(monkeypatch, exc=RuntimeError("boom"))
    r = _post(client)
    assert r.status_code == 200  # NOT 500
    body = r.json()
    assert "schiefgelaufen" in body["content"]
    assert "RuntimeError" in body["content"]
    assert body["quick_replies"] == ["Nochmal versuchen"]
    assert body["debug"]["pattern"] == "ERROR: unhandled_chat_exception"
    assert saves and saves[0]["role"] == "assistant"
    assert "unhandled error: RuntimeError" in saves[0]["content"]


def test_error_persist_failure_never_masks_bubble(monkeypatch, client):
    _patch(monkeypatch, exc=RuntimeError("boom"))

    async def _boom_save(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(chat_api, "save_message", _boom_save)
    r = _post(client)  # DB write failing must NOT turn the bubble into a 500
    assert r.status_code == 200
    assert "schiefgelaufen" in r.json()["content"]


# ── Per-session lock ────────────────────────────────────────────────────────

def test_session_lock_acquired_and_released(monkeypatch, client):
    _patch(monkeypatch, result=_ok())
    events: list = []
    lock = asyncio.Lock()

    async def _acq(session_id):
        events.append(("acquire", session_id))
        return lock

    async def _rel(session_id):
        events.append(("release", session_id))

    monkeypatch.setattr(chat_api, "_get_session_lock", _acq)
    monkeypatch.setattr(chat_api, "_release_session_lock", _rel)
    _post(client)
    assert ("acquire", "bb-1") in events
    assert ("release", "bb-1") in events
