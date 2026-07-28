"""Tests for the proactive context-greeting node (P4-2d, R6).

Port of ALT ``test_context_greeting.py``. Two layers:

* ``maybe_context_greeting`` (the ported dispatcher): ``None`` ONLY when
  ``page_event != 'context_open'``; on ``context_open`` ALWAYS a ChatResponse —
  a greeting when every gate passes, else ``content == ""``. The two DB writes
  are patched on THIS module; ``page_context`` + ``load_context_actions`` run for
  real (unseeded config store → the ALT-identical defaults).
* ``context_greeting`` (the node adapter): sets ``ctx.early_response`` on a hit,
  leaves it None on a normal turn, and swallows dispatcher errors (a greeting bug
  must never break the turn).

NEU seam deviations over ALT: the DB writes take ``session`` first, so the fakes
and the assertion indices shift by one.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest
from boerdi.graph.nodes import context_greeting as g
from boerdi.graph.state import TurnContext
from boerdi.services import page_context

_SESSION = object()  # sentinel — the patched DB writes ignore it


def _req(session_id: str = "s1", message: str = "") -> ChatRequest:
    return ChatRequest(session_id=session_id, message=message)


def _env(page_event: str | None = "context_open", page_context: dict | None = None) -> dict:
    return {"page_event": page_event, "page_context": page_context or {}}


def _state(meta: dict, greeted: list | None = None) -> dict:
    ents: dict = {"_page_metadata": meta}
    if greeted is not None:
        ents["_greeted_pages"] = greeted
    return {"entities": ents}


def _resolved(title: str = "Optik", **extra) -> dict:
    return {"title": title, "unresolved": False, **extra}


def _collection_ctx() -> dict:
    return {"page_kind": "collection", "collection_id": "C1"}


def _patch_io(monkeypatch) -> dict:
    calls: dict = {"update": [], "save": []}

    async def fake_update(session, session_id, **kw):
        calls["update"].append((session, session_id, kw))

    async def fake_save(session, session_id, role, content, **kw):
        calls["save"].append((session, session_id, role, content, kw))

    monkeypatch.setattr(g, "update_session", fake_update)
    monkeypatch.setattr(g, "save_message", fake_save)
    return calls


# ── Dispatcher: maybe_context_greeting ──────────────────────────────────────

def test_no_page_event_returns_none(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), {"page_event": None, "page_context": _collection_ctx()},
        _state(_resolved()), ["prev"]))
    assert resp is None


def test_empty_history_returns_empty_and_persists_nothing(monkeypatch):
    calls = _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()), _state(_resolved()), []))
    assert resp is not None and resp.content == ""
    assert calls["save"] == [] and calls["update"] == []


def test_collection_greeting_full(monkeypatch):
    calls = _patch_io(monkeypatch)
    state = _state(_resolved(title="Optik"))
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()), state, ["prev"]))
    assert "Optik" in resp.content
    assert resp.debug.pattern == "CTX:collection"
    joined = "\n".join(resp.quick_replies)
    assert "__action__|Sammlung erkunden|browse_collection|" in joined
    assert "__action__|Sammlung kuratieren|curate_collection|" in joined
    assert '"collection_id": "C1"' in joined
    assert "__guide__|Inhalt melden|" in joined
    # dedup recorded + persisted exactly once each
    sig = page_context._current_context_signature(_collection_ctx())
    assert sig in state["entities"]["_greeted_pages"]
    assert len(calls["update"]) == 1
    assert len(calls["save"]) == 1 and calls["save"][0][2] == "assistant"


def test_dedup_second_call_returns_empty(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    ctx = _collection_ctx()
    r1 = asyncio.run(
        g.maybe_context_greeting(_SESSION, _req(), _env(page_context=ctx), state, ["prev"]))
    assert r1.content
    r2 = asyncio.run(
        g.maybe_context_greeting(_SESSION, _req(), _env(page_context=ctx), state, ["prev"]))
    assert r2.content == ""


def test_search_page_kind_returns_empty(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "search"}),
        _state(_resolved()), ["prev"]))
    assert resp.content == ""


def test_topic_page_kind_greets(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "topic", "collection_id": "T1"}),
        _state(_resolved(title="Klimawandel")), ["prev"]))
    assert "Klimawandel" in resp.content
    assert resp.debug.pattern == "CTX:topic"


def test_unresolved_meta_returns_empty(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()),
        _state({"title": "T", "unresolved": True}), ["prev"]))
    assert resp.content == ""


def test_content_report_pill_uses_node_id(monkeypatch):
    _patch_io(monkeypatch)
    ctx = {"page_kind": "content", "node_id": "N9"}
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=ctx), _state(_resolved(title="Material")), ["prev"]))
    joined = "\n".join(resp.quick_replies)
    assert "node=N9" in joined  # report_url {node_id} substituted


def test_melden_prefilled_and_erkunden_action_pill_parseable(monkeypatch):
    """T14-Golden: the Melden pill carries the pre-filled ID in the URL, and the
    Erkunden action pill decodes to browse_collection + valid params-JSON (the
    contract the frontend parser consumes)."""
    import json as _json
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()),
        _state(_resolved(title="Optik")), ["prev"]))

    report = next(q for q in resp.quick_replies if q.startswith("__guide__|Inhalt melden|"))
    assert "node=C1" in report and "type=quelle" in report

    erkunden = next(q for q in resp.quick_replies if q.startswith("__action__|Sammlung erkunden|"))
    _, label, action, params_json = erkunden.split("|", 3)
    assert action == "browse_collection"
    params = _json.loads(params_json)
    assert params["collection_id"] == "C1"
    assert params["title"] == "Optik"


def test_greeted_pages_fifo_cap_20(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved(), greeted=[f"sig{i}" for i in range(20)])
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()), state, ["prev"]))
    assert resp.content
    greeted = state["entities"]["_greeted_pages"]
    assert len(greeted) == 20            # capped
    assert "sig0" not in greeted         # oldest evicted
    assert page_context._current_context_signature(_collection_ctx()) in greeted


# ── Node adapter: context_greeting(ctx, session) ────────────────────────────

def _node_ctx(env: dict, session_state: dict, history: list) -> TurnContext:
    ctx = TurnContext(req=_req())
    ctx.env = env
    ctx.session_state = session_state
    ctx.history = history
    return ctx


def test_node_sets_early_response_on_greeting(monkeypatch):
    _patch_io(monkeypatch)
    ctx = _node_ctx(
        _env(page_context=_collection_ctx()), _state(_resolved(title="Optik")), ["prev"])
    out = asyncio.run(g.context_greeting(ctx, _SESSION))
    assert out.early_response is not None
    assert "Optik" in out.early_response.content
    assert out.early_response.debug.pattern == "CTX:collection"


def test_node_no_page_event_leaves_early_response_none(monkeypatch):
    _patch_io(monkeypatch)
    ctx = _node_ctx(
        {"page_event": None, "page_context": _collection_ctx()},
        _state(_resolved()), ["prev"])
    out = asyncio.run(g.context_greeting(ctx, _SESSION))
    assert out.early_response is None


def test_node_swallows_dispatcher_exception(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("greeting exploded")

    monkeypatch.setattr(g, "maybe_context_greeting", boom)
    ctx = _node_ctx(_env(page_context=_collection_ctx()), _state(_resolved()), ["prev"])
    out = asyncio.run(g.context_greeting(ctx, _SESSION))
    assert out.early_response is None  # a greeting bug must not break the turn
