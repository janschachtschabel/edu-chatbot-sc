"""R4f-2: POST /api/chat/stream — the SSE sibling of /api/chat.

Same turn pipeline (``build_turn_graph`` under the per-session lock), but the
response is a Server-Sent-Events stream: a ``connected`` handshake, periodic
keepalives while the turn runs, and a final ``result`` (or ``error``) frame.

Since C9 the stream also carries ``phase`` frames: the graph gets a
``TurnProgress`` bound to a queue, and this generator drains that queue while the
turn runs. The frame byte-format is contract (spec rule 6):
``event: connected\\ndata: {}\\n\\n``, ``event: phase\\ndata: <json>\\n\\n``,
``: keepalive\\n\\n``, ``event: result\\ndata: <json>\\n\\n``,
``event: error\\ndata: <json>\\n\\n``.

Endpoint wiring (content-type, connected + result in the body, error frame) is
exercised through TestClient; the keepalive / disconnect-cancel cost-control
logic is driven directly against ``_stream_turn`` with a fake request, because
TestClient reads the whole stream and never disconnects mid-turn.

``TestClient`` is used WITHOUT a ``with`` block (as in test_chat_endpoint.py):
the lifespan would need a real Postgres; ``get_session`` is overridden instead.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import boerdi.api.chat as chat_api
from boerdi.api.deps import get_session
from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.main import create_app
from boerdi.obs.progress import TurnProgress
from boerdi.settings import get_settings

_SESSION = object()  # sentinel: whatever get_session yields must reach build_turn_graph


def _ok(content="X"):
    """A normal-path graph state dict carrying a ChatResponse under ``response``."""
    return {"response": ChatResponse(session_id="bb-1", content=content)}


def _req():
    """A ChatRequest seeded exactly like the HTTP body in the TestClient tests."""
    return ChatRequest.model_validate(
        {"session_id": "bb-1", "message": "hallo", "environment": {}}
    )


class _FakeGraph:
    """Stand-in compiled graph: ``ainvoke`` returns a preset state dict or raises."""

    def __init__(self, *, result=None, exc=None):
        self._result, self._exc = result, exc

    async def ainvoke(self, state):
        if self._exc is not None:
            raise self._exc
        return self._result


class _Req:
    """Minimal Request stand-in for _stream_turn (peer_ip is patched out)."""

    def __init__(self, *, disconnected=False):
        self._disconnected = disconnected

    async def is_disconnected(self):
        return self._disconnected


async def _passthrough_pp(req, resp, *a, **k):
    return resp


async def _drain(agen):
    return [chunk async for chunk in agen]


def _patch(monkeypatch, *, result=None, exc=None):
    """Fake build_turn_graph / peer_ip / widget-postprocess on the chat module."""
    graph = _FakeGraph(result=result, exc=exc)
    builds: list[dict] = []

    def _fake_build(*, session, peer_ip="", on_token=None, progress=None):
        builds.append({
            "session": session, "peer_ip": peer_ip,
            "on_token": on_token, "progress": progress,
        })
        return graph

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    return graph, builds


def _fake_locks(monkeypatch):
    """Isolate the per-session lock and record acquire/release order."""
    events: list = []
    lock = asyncio.Lock()

    async def _acq(session_id):
        events.append(("acquire", session_id))
        return lock

    async def _rel(session_id):
        events.append(("release", session_id))

    monkeypatch.setattr(chat_api, "_get_session_lock", _acq)
    monkeypatch.setattr(chat_api, "_release_session_lock", _rel)
    return events


# ── Endpoint via TestClient ─────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")  # deterministic: no limiter interference
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    yield TestClient(app)
    get_settings.cache_clear()


def _post(client):
    body = {"session_id": "bb-1", "message": "hallo", "environment": {}}
    return client.post("/api/chat/stream", json=body)


def test_content_type_is_event_stream(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_connected_is_first_frame(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert r.text.startswith("event: connected\ndata: {}\n\n")


def test_result_frame_carries_the_response(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert "event: result\n" in r.text
    assert "HI" in r.text


def test_early_response_wins_in_stream(monkeypatch, client):
    _patch(monkeypatch, result={
        "early_response": ChatResponse(session_id="bb-1", content="EARLY"),
        "response": ChatResponse(session_id="bb-1", content="NORMAL"),
    })
    r = _post(client)
    assert "EARLY" in r.text
    assert "NORMAL" not in r.text


def test_error_frame_on_graph_exception(monkeypatch, client):
    _patch(monkeypatch, exc=RuntimeError("boom"))
    r = _post(client)
    assert r.status_code == 200  # SSE is always 200; failure is an ``error`` frame
    assert "event: error\n" in r.text
    assert "RuntimeError" in r.text
    assert "event: result" not in r.text


def test_widget_postprocess_is_applied_to_result(monkeypatch, client):
    _patch(monkeypatch, result=_ok("RAW"))

    async def _transform(req, resp, *a, **k):
        return ChatResponse(session_id=resp.session_id, content="POSTPROCESSED")

    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _transform)
    r = _post(client)
    assert "POSTPROCESSED" in r.text
    assert "RAW" not in r.text


# ── _stream_turn generator (fakes, no HTTP) ─────────────────────────────────

async def test_stream_binds_session_peer_ip_and_no_on_token(monkeypatch):
    _, builds = _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch)
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))
    assert builds[0]["session"] is _SESSION
    assert builds[0]["peer_ip"] == "7.7.7.7"
    assert builds[0]["on_token"] is None  # token streaming stays rolled back (as in ALT)
    assert frames[0] == "event: connected\ndata: {}\n\n"


async def test_session_lock_acquired_and_released(monkeypatch):
    _patch(monkeypatch, result=_ok())
    events = _fake_locks(monkeypatch)
    await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))
    assert ("acquire", "bb-1") in events
    assert ("release", "bb-1") in events


async def test_disconnect_cancels_turn_and_releases_lock(monkeypatch):
    # A hung turn + a client that has gone away must be cancelled, not run to
    # completion on full LLM/MCP cost for nobody — and the lock must be freed.
    class _HangGraph:
        def __init__(self):
            self.cancelled = False

        async def ainvoke(self, state):
            try:
                await asyncio.Event().wait()  # never completes
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    graph = _HangGraph()
    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: graph)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_SSE_KEEPALIVE_SECONDS", 0.01)
    events = _fake_locks(monkeypatch)

    frames = await _drain(chat_api._stream_turn(_req(), _Req(disconnected=True), _SESSION))

    assert frames == ["event: connected\ndata: {}\n\n"]  # no result/error frame
    assert ("release", "bb-1") in events  # finally ran during cancel cleanup
    assert graph.cancelled  # the hung turn was actually cancelled


# ── C9: phase frames ────────────────────────────────────────────────────────

def _patch_emitting(monkeypatch, steps):
    """Fake a graph that reports ``steps`` through the injected ``TurnProgress``.

    Proves the whole seam end to end: the endpoint builds a progress object, the
    graph writes into it mid-turn, and the generator turns that into SSE frames.
    """
    holder: dict = {}

    class _EmittingGraph:
        async def ainvoke(self, state):
            for step in steps:
                holder["progress"].start(step, f"L-{step}")
            return _ok("DONE")

    def _fake_build(*, session, peer_ip="", on_token=None, progress=None):
        holder["progress"] = progress
        return _EmittingGraph()

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    _fake_locks(monkeypatch)
    return holder


async def test_stream_binds_a_progress_object(monkeypatch):
    """Without a progress seam the graph has no way to report anything — pin that
    the stream always supplies one (POST /api/chat gets a sink-less default)."""
    _, builds = _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch)
    await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))
    assert isinstance(builds[0]["progress"], TurnProgress)


async def test_phase_frames_are_emitted_in_order_before_the_result(monkeypatch):
    _patch_emitting(monkeypatch, ["safety_classify", "pattern", "response"])
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))

    kinds = [f.split("\n", 1)[0] for f in frames]
    assert kinds == [
        "event: connected", "event: phase", "event: phase", "event: phase",
        "event: result",
    ]
    steps = [json.loads(f.split("data: ", 1)[1])["step"]
             for f in frames if f.startswith("event: phase")]
    assert steps == ["safety_classify", "pattern", "response"]


async def test_phase_payload_carries_the_four_contract_keys(monkeypatch):
    """``ui/stream/phase-label.ts`` reads ``data.kind`` and ``data.step``; ALT's
    listener shape (``chat.py:405``) is ``{kind, step, label, data}``."""
    _patch_emitting(monkeypatch, ["wlo_search"])
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))

    phase = next(f for f in frames if f.startswith("event: phase"))
    assert phase.endswith("\n\n")
    payload = json.loads(phase.split("data: ", 1)[1])
    assert payload == {
        "kind": "start", "step": "wlo_search", "label": "L-wlo_search", "data": {},
    }


async def test_umlauts_survive_the_phase_frame(monkeypatch):
    """The labels are German ("Lade Sitzungs-Kontext …") — no \\uXXXX escaping."""
    holder = _patch_emitting(monkeypatch, [])

    class _Umlaut:
        async def ainvoke(self, state):
            holder["progress"].record("context", "Lade Sitzungs-Kontext …")
            return _ok("DONE")

    monkeypatch.setattr(
        chat_api, "build_turn_graph",
        lambda **kw: (holder.__setitem__("progress", kw["progress"]), _Umlaut())[1],
    )
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))
    phase = next(f for f in frames if f.startswith("event: phase"))
    assert "Lade Sitzungs-Kontext …" in phase


async def test_a_flooded_queue_drops_events_but_still_finishes_the_turn(monkeypatch):
    """Cost control (ALT ``Queue(maxsize=200)``): a slow client must not let the
    queue grow without bound. Overflow drops progress — never the answer."""
    monkeypatch.setattr(chat_api, "_SSE_PROGRESS_QUEUE_MAX", 2)
    _patch_emitting(monkeypatch, [f"s{i}" for i in range(50)])
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))

    phases = [f for f in frames if f.startswith("event: phase")]
    assert 0 < len(phases) <= 2  # capped, not 50
    assert any(f.startswith("event: result\n") for f in frames)  # answer survived


async def test_progress_after_an_exception_still_yields_the_error_frame(monkeypatch):
    """A turn that reports progress and then blows up: the phases already sent
    must not swallow the ``error`` frame."""
    holder: dict = {}

    class _BoomGraph:
        async def ainvoke(self, state):
            holder["progress"].start("pattern", "Pattern selection")
            raise RuntimeError("boom")

    def _fake_build(*, session, peer_ip="", on_token=None, progress=None):
        holder["progress"] = progress
        return _BoomGraph()

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    _fake_locks(monkeypatch)

    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _SESSION))
    assert any(f.startswith("event: phase") for f in frames)
    assert any(f.startswith("event: error\n") for f in frames)


async def test_keepalive_emitted_during_slow_turn(monkeypatch):
    release = asyncio.Event()
    resp = ChatResponse(session_id="bb-1", content="DONE")

    class _GatedGraph:
        async def ainvoke(self, state):
            await release.wait()
            return {"response": resp}

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _GatedGraph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    monkeypatch.setattr(chat_api, "_SSE_KEEPALIVE_SECONDS", 0.01)
    _fake_locks(monkeypatch)

    agen = chat_api._stream_turn(_req(), _Req(disconnected=False), _SESSION)
    first = await agen.__anext__()   # connected handshake
    second = await agen.__anext__()  # turn still gated -> keepalive on timeout
    release.set()
    rest = await _drain(agen)        # turn completes -> result frame

    assert first == "event: connected\ndata: {}\n\n"
    assert second == ": keepalive\n\n"
    assert any(chunk.startswith("event: result\n") for chunk in rest)
