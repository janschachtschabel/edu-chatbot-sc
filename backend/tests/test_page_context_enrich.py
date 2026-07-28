"""Tests for the page-context enrichment node (P4-2 / R6).

The node injects the page-context IDs the widget supplies into
``session_state['entities']`` and best-effort resolves the host page's metadata via
MCP (populating the ``_page_metadata`` cache that ``context_greeting`` and — later —
``respond``'s prompt read). It runs AFTER the tour early-exit (so tour ticks skip the
MCP latency; ALT ``chat_turn_setup:90`` returns before the resolve at :92) and never
short-circuits. ``resolve_page_context`` is patched on THIS module; the injection
runs for real.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.graph.nodes import page_context_enrich as m
from boerdi.graph.state import TurnContext


def _ctx(page_context: dict | None = None) -> TurnContext:
    ctx = TurnContext(req=ChatRequest(session_id="s1", message="hi"))
    ctx.env = Environment(page_context=page_context or {}).model_dump()
    ctx.session_state = {"entities": {}}
    return ctx


def _patch_resolve(monkeypatch) -> list:
    calls: list = []

    async def fake_resolve(page_context, session_state, **kw):
        calls.append((page_context, session_state))
        return None

    monkeypatch.setattr(m, "resolve_page_context", fake_resolve)
    return calls


def test_injects_present_page_context_ids_into_entities(monkeypatch):
    _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1", "collection_id": "C1", "subject_slug": "mathe"})
    out = asyncio.run(m.page_context_enrich(ctx))
    ents = out.session_state["entities"]
    assert ents["node_id"] == "N1"
    assert ents["collection_id"] == "C1"
    assert ents["subject_slug"] == "mathe"


def test_skips_absent_and_falsy_keys(monkeypatch):
    _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1", "collection_id": ""})
    out = asyncio.run(m.page_context_enrich(ctx))
    # empty collection_id skipped; absent keys skipped
    assert out.session_state["entities"] == {"node_id": "N1"}


def test_calls_resolve_with_page_ctx_and_session_state(monkeypatch):
    calls = _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1"})
    asyncio.run(m.page_context_enrich(ctx))
    assert len(calls) == 1
    page_ctx, session_state = calls[0]
    assert page_ctx == {"node_id": "N1"}
    assert session_state is ctx.session_state  # resolve caches on the live session_state


def test_resolve_failure_is_swallowed_and_ids_still_injected(monkeypatch):
    async def boom(page_context, session_state, **kw):
        raise RuntimeError("mcp down")

    monkeypatch.setattr(m, "resolve_page_context", boom)
    ctx = _ctx({"node_id": "N1"})
    out = asyncio.run(m.page_context_enrich(ctx))  # must not raise
    assert out.session_state["entities"]["node_id"] == "N1"


def test_never_sets_early_response(monkeypatch):
    _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.early_response is None
