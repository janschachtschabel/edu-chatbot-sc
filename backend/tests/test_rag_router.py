"""P6-2a: RAG router POST /query + the request-scoped session dependency.

A router's job is HTTP translation — auth, validation, response shape. The DB
semantics live in the service layer and are pinned there (test_rag_retrieval.py
plus the pg-gated test_rag_search_pg.py), so these pins override ``get_session``
with a sentinel and fake ``query_rag``: deterministic and offline. The sentinel
doubles as the proof that the DI session is what reaches the service.

``TestClient`` is used WITHOUT a ``with`` block on purpose — the context manager
would run the lifespan, which demands a real Postgres (see test_app_lifespan.py,
where the ``session_factory`` wiring itself is pinned).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import boerdi.api.rag as rag_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach query_rag


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    yield TestClient(app)
    get_settings.cache_clear()


def _fake_query_rag(monkeypatch, results=()):
    calls: list[tuple] = []

    async def fake(session, query, area, top_k):
        calls.append((session, query, area, top_k))
        return list(results)

    monkeypatch.setattr(rag_api, "query_rag", fake)
    return calls


# ── POST /api/rag/query ──────────────────────────────────────────────────
def test_query_returns_ragresult_list_dropping_service_extras(client, monkeypatch):
    # The service dict carries `title` on top of RagResult's four fields
    # (search_rag_chunks LEFT JOINs it for get_rag_context); the response model
    # drops it, exactly as ALT's `RagResult(**r)` did.
    _fake_query_rag(monkeypatch, [
        {"chunk": "Klima ist...", "score": 0.91, "source": "k.md",
         "area": "erdkunde", "title": "Klima"},
    ])
    r = client.post("/api/rag/query", json={"query": "klima"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == [
        {"chunk": "Klima ist...", "score": 0.91, "source": "k.md", "area": "erdkunde"},
    ]


def test_query_passes_di_session_and_request_fields_to_service(client, monkeypatch):
    calls = _fake_query_rag(monkeypatch)
    r = client.post(
        "/api/rag/query",
        json={"query": "klima", "area": "erdkunde", "top_k": 5},
        headers=_AUTH,
    )
    assert r.status_code == 200
    # The session handed to the service IS the one from the dependency.
    assert calls == [(_SESSION, "klima", "erdkunde", 5)]


def test_query_defaults_area_general_and_top_k_3(client, monkeypatch):
    calls = _fake_query_rag(monkeypatch)
    client.post("/api/rag/query", json={"query": "x"}, headers=_AUTH)
    assert calls == [(_SESSION, "x", "general", 3)]  # RagQuery defaults, like ALT


def test_query_rejects_missing_query_field(client, monkeypatch):
    calls = _fake_query_rag(monkeypatch)
    r = client.post("/api/rag/query", json={"area": "erdkunde"}, headers=_AUTH)
    assert r.status_code == 422
    assert calls == []  # rejected before the service is touched


def test_query_requires_studio_key(client, monkeypatch):
    calls = _fake_query_rag(monkeypatch)
    r = client.post("/api/rag/query", json={"query": "x"})  # no X-Studio-Key
    assert r.status_code == 401
    assert calls == []


# ── get_session dependency ───────────────────────────────────────────────
def test_get_session_yields_from_app_factory_and_closes_after_request():
    closed: list[bool] = []
    session = object()

    class _FakeSessionCtx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            closed.append(True)
            return False

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=_FakeSessionCtx))
    )

    async def drive():
        agen = get_session(request)
        assert await agen.__anext__() is session
        assert closed == []  # still open while the request is being served
        with pytest.raises(StopAsyncIteration):
            await agen.__anext__()  # dependency teardown

    asyncio.run(drive())
    assert closed == [True]  # closed exactly once, after the request
