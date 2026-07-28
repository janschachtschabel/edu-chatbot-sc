"""R1c: ``generate_response`` orchestrator (services/generate.py) — port of
ALT ``llm_service.py:160-312``.

The orchestrator is a thin 5-phase wiring: ``_build_system_prompt`` (P1-P9) →
``_select_active_tools`` (P10-P11) → ``_assemble_messages`` (P12/P14) →
``_run_tool_loop`` (P15) → ``_max_iterations_fallback`` (P16). Each phase is
already pinned directly (test_response_prompt_builder / test_response_tool_
selection / test_tool_loop). So these pins cover what the orchestrator *itself*
does and nothing the phases already cover:

* the exact arg threading into every phase — including the NEU ``session``-DI
  seam (first arg into assemble + loop), ``blocked_tools=None → []``, and the
  non-obvious reorder where ``_assemble_messages`` returns
  ``(…, knowledge_prefetched, always_areas, mcp_prefetched, …)`` but the loop is
  called ``(…, knowledge_prefetched, mcp_prefetched, always_areas, …)`` — via
  argument-recording spies on the phase functions (the collaborators, not the
  unit under test);
* the single branch unique to the orchestrator: loop returns ``None`` (max
  iterations) ⇒ delegate to ``_max_iterations_fallback``;
* two integration pins that stub only the already-tested P1-P11 phases and run
  the **real** ``_assemble_messages`` + ``_run_tool_loop`` + ``_max_iterations_
  fallback`` (boundaries ``llm.chat_completion`` / ``parse_wlo_cards`` faked),
  proving the real 10-tuple contract flows through for the content and the
  LLM-error paths.

ALT's ``test_page_context_failure_degrades_gracefully`` is deliberately NOT
ported: ``generate_response`` has no page-context code (it lives inside
``_build_system_prompt``, where NEU simplify-defers P3), so it is a phase-level
concern, not an orchestrator one.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services import generate, llm, tool_loop
from boerdi.settings import get_settings

_SESSION = object()  # opaque; the orchestrator only forwards it


# ── argument-recording spy ──────────────────────────────────────────────
class _Spy:
    """Records positional call args and returns a preset value. Async so it can
    stand in for the awaited phases too (``asyncio.run`` awaits the coroutine)."""

    def __init__(self, ret):
        self.ret = ret
        self.args: tuple | None = None

    def __call__(self, *args):
        self.args = args
        return self.ret

    async def acall(self, *args):
        self.args = args
        return self.ret


def _patch_phases(monkeypatch, *, build, select, assemble, loop, fallback):
    monkeypatch.setattr(generate, "_build_system_prompt", build)
    monkeypatch.setattr(generate, "_select_active_tools", select)
    monkeypatch.setattr(generate, "_assemble_messages", assemble.acall)
    monkeypatch.setattr(generate, "_run_tool_loop", loop.acall)
    monkeypatch.setattr(generate, "_max_iterations_fallback", fallback.acall)


# ════════════════════════════════════════════════════════════════════════
# Orchestrator wiring (spied phases)
# ════════════════════════════════════════════════════════════════════════

def test_wires_phases_threads_session_and_normalizes_blocked_tools(monkeypatch):
    # Distinct sentinels so a mis-threaded arg is caught by identity.
    SYSTEM, CIM, IGM, DNT = (object() for _ in range(4))
    ACTIVE, PSD, RAFP, IQE = (object() for _ in range(4))
    MSGS, CARDS, TOOLS, OUTS = (object() for _ in range(4))
    KP, AA, MCP, TOPK, MINSC, MAXCH = (object() for _ in range(6))
    LOOP_RESULT = ("final", [], [], [])

    build = _Spy((SYSTEM, CIM, IGM, DNT))
    select = _Spy((ACTIVE, PSD, RAFP, IQE))
    assemble = _Spy((MSGS, CARDS, TOOLS, OUTS, KP, AA, MCP, TOPK, MINSC, MAXCH))
    loop = _Spy(LOOP_RESULT)
    fallback = _Spy(("unused", [], [], []))
    _patch_phases(monkeypatch, build=build, select=select, assemble=assemble,
                  loop=loop, fallback=fallback)

    CLASSIF = {"persona_id": "P-AND"}
    PATTERN = {"tools": []}
    SSTATE = {"k": "v"}
    ENV = {"e": 1}
    HIST = [{"role": "user", "content": "x"}]
    PREF_TOOL = {"pt": 1}
    PREF_EXTRAS = [{"pe": 1}]
    CANVAS = {"c": 1}
    USAGE = {"u": 1}
    TOKENCB = object()

    out = asyncio.run(generate.generate_response(
        _SESSION, "msg", HIST, CLASSIF, PATTERN, "M05", SSTATE, ENV,
        rag_context="RAG", available_rag_areas=["a"], rag_config={"r": 1},
        blocked_tools=None,  # → normalized to []
        prefetched_tool=PREF_TOOL, prefetched_extras=PREF_EXTRAS,
        canvas_state=CANVAS, usage_acc=USAGE, on_token=TOKENCB,
    ))

    # P1-P9: build gets the 8 source args (no session, no derived flags).
    assert build.args == (
        CLASSIF, PATTERN, "M05", SSTATE, ENV, "RAG", ["a"], {"r": 1})
    # P10-P11: select consumes cards_inline + degradation FROM build.
    assert select.args == (CLASSIF, PATTERN, ["a"], {"r": 1}, CIM, DNT)
    # P12/P14: assemble — session FIRST, blocked_tools normalized to [],
    # system + inline_grouping + sources_decl + rag_allowed from prior phases.
    assert assemble.args == (
        _SESSION, "msg", HIST, PATTERN, "M05", SSTATE, ["a"], {"r": 1},
        [], PREF_TOOL, PREF_EXTRAS, CANVAS, SYSTEM, IGM, PSD, RAFP)
    # P15: loop — session FIRST, active_tools + inline_qr from select, the 10
    # assemble outputs threaded with the ALT reorder (mcp_prefetched BEFORE
    # always_areas), usage_acc + on_token last.
    assert loop.args == (
        _SESSION, "msg", CLASSIF, PATTERN, "M05", SSTATE, "RAG", [],
        ACTIVE, IQE, IGM, MSGS, CARDS, TOOLS, OUTS, KP, MCP, AA,
        TOPK, MINSC, MAXCH, USAGE, TOKENCB)
    # loop returned non-None ⇒ that result is returned, fallback untouched.
    assert out is LOOP_RESULT
    assert fallback.args is None


def test_returns_fallback_when_loop_returns_none(monkeypatch):
    MSGS, CARDS, TOOLS, OUTS = (object() for _ in range(4))
    FALLBACK_RESULT = ("closing summary", [], [], [])

    build = _Spy(("sys", False, False, False))
    select = _Spy(([], None, True, False))
    assemble = _Spy((MSGS, CARDS, TOOLS, OUTS, False, [], False, 3, 0.25, 4000))
    loop = _Spy(None)  # max iterations, no final answer
    fallback = _Spy(FALLBACK_RESULT)
    _patch_phases(monkeypatch, build=build, select=select, assemble=assemble,
                  loop=loop, fallback=fallback)

    out = asyncio.run(generate.generate_response(
        _SESSION, "msg", [], {}, {"tools": []}, "M01", {}, {}))

    # Fallback gets exactly the four accumulators assemble produced.
    assert fallback.args == (MSGS, CARDS, TOOLS, OUTS)
    assert out is FALLBACK_RESULT


# ════════════════════════════════════════════════════════════════════════
# Integration: real assemble + loop + fallback (P1-P11 stubbed, boundaries faked)
# ════════════════════════════════════════════════════════════════════════

def _resp_text(text):
    msg = SimpleNamespace(role="assistant", content=text, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        usage=None, model="gpt-x")


class _SeqLLM:
    """Fake ``llm.chat_completion``: returns preset responses in order."""

    def __init__(self, responses, raises=None):
        self._responses = list(responses)
        self._raises = raises

    async def __call__(self, **kwargs):
        if self._raises is not None:
            raise self._raises
        return self._responses.pop(0)


def _integ(monkeypatch, responses, *, raises=None):
    get_settings.cache_clear()
    llm.reset()
    # Stub the already-tested P1-P11 phases; run the REAL P12-P16.
    monkeypatch.setattr(generate, "_build_system_prompt",
                        lambda *a: ("SYS", False, False, False))
    monkeypatch.setattr(generate, "_select_active_tools",
                        lambda *a: ([], None, True, False))
    monkeypatch.setattr(llm, "chat_completion", _SeqLLM(responses, raises=raises))
    monkeypatch.setattr(tool_loop, "parse_wlo_cards", lambda text: [])
    return asyncio.run(generate.generate_response(
        _SESSION, "hi", [], {}, {"tools": []}, "M01", {}, {}))


def test_integration_no_tools_returns_content(monkeypatch):
    text, cards, tools, outcomes = _integ(
        monkeypatch, [_resp_text("Hier ist deine Antwort.")])
    assert text == "Hier ist deine Antwort."
    assert cards == [] and tools == [] and outcomes == []


def test_integration_llm_error_returns_graceful_message(monkeypatch):
    # The real loop catches the upstream error and returns a user-readable
    # message instead of crashing the whole turn.
    text, cards, tools, outcomes = _integ(
        monkeypatch, [], raises=RuntimeError("upstream down"))
    assert "Fehler bei der Verarbeitung" in text
    assert isinstance(cards, list) and isinstance(tools, list)
