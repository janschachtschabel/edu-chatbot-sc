"""P5-3 tool-loop: ``_max_iterations_fallback`` (P16), ``_assemble_messages``
(P12/P14) and ``_run_tool_loop`` (P15) — ports of ALT llm_tool_loop.py:199-236,
239-563 and 565-1158.

ALT drove all three only indirectly via ``generate_response``; these pins
exercise them directly. Boundaries faked: ``llm._acompletion`` (transport,
mirroring test_llm_curation) for the fallback; ``llm.chat_completion`` /
``tool_loop._stream_completion`` for the loop's LLM rounds; the lazy
rag/parser/outcome/config seams are patched at their source modules
(``rag.retrieval``, ``mcp.parsers``, ``outcome_service``, ``config_loader``)
and the module-level ``parse_wlo_cards`` binding on ``tool_loop`` itself —
matching where ALT declares each patch point.
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

from boerdi.services import llm, tool_loop
from boerdi.settings import get_settings


def _content_resp(text):
    return SimpleNamespace(
        model="gpt-5.6-luna",
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=50, completion_tokens=20,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
    )


class _Capture:
    def __init__(self, text=None, raises=None):
        self.text, self.raises = text, raises
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return _content_resp(self.text)


def _run(monkeypatch, cap, *, messages=None, all_cards=None,
         tools_called=None, outcomes=None):
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    return asyncio.run(tool_loop._max_iterations_fallback(
        [] if messages is None else messages,
        [] if all_cards is None else all_cards,
        [] if tools_called is None else tools_called,
        [] if outcomes is None else outcomes,
    ))


def test_fallback_summarizes_when_cards_present(monkeypatch):
    cap = _Capture(text="Kurz zusammengefasst.")
    cards = [{"node_id": "a"}, {"node_id": "b"}]
    tools = ["search_wlo_content"]
    outs = ["o1"]
    base = [{"role": "user", "content": "finde X"}]
    text, out_cards, out_tools, out_outs = _run(
        monkeypatch, cap, messages=base,
        all_cards=cards, tools_called=tools, outcomes=outs)
    assert text == "Kurz zusammengefasst."
    # cards / tools / outcomes pass straight through, same objects
    assert out_cards is cards and out_tools is tools and out_outs is outs
    # ALT appends exactly ONE closing "summarize now, no more tools" user turn
    sent = cap.calls[0]["messages"]
    assert sent[:-1] == base
    assert sent[-1]["role"] == "user"
    assert "ohne weitere Tool-Aufrufe" in sent[-1]["content"]


def test_fallback_strips_reasoning_markers(monkeypatch):
    cap = _Capture(text="<think>Plan</think>Fertige Antwort")
    text, *_ = _run(monkeypatch, cap, all_cards=[{"node_id": "a"}])
    assert text == "Fertige Antwort"


def test_fallback_empty_summary_falls_through_to_card_count(monkeypatch):
    cap = _Capture(text="   ")  # whitespace → empty after strip → generic line
    cards = [{"node_id": "a"}, {"node_id": "b"}, {"node_id": "c"}]
    text, *_ = _run(monkeypatch, cap, all_cards=cards)
    assert text == (
        "Ich habe 3 passende Materialien für dich gefunden — "
        "schau sie dir gerne an:"
    )


def test_fallback_summary_exception_falls_through_to_card_count(monkeypatch, caplog):
    cap = _Capture(raises=RuntimeError("boom"))
    with caplog.at_level(logging.WARNING):
        text, *_ = _run(monkeypatch, cap, all_cards=[{"node_id": "a"}])
    assert text == (
        "Ich habe 1 passende Materialien für dich gefunden — "
        "schau sie dir gerne an:"
    )
    assert "Fallback summary failed" in caplog.text


def test_fallback_no_cards_returns_no_answer_and_skips_llm(monkeypatch):
    cap = _Capture(text="unused")
    text, out_cards, out_tools, out_outs = _run(monkeypatch, cap, all_cards=[])
    assert text == "Ich konnte leider keine Antwort generieren."
    assert cap.calls == []  # no cards → no LLM round-trip


# ---------------------------------------------------------------------------
# _assemble_messages (P12/P14): system + canvas context + history[-10:],
# RAG always-prefetch as simulated tool call, MCP prefetch injection
# primary/extras, node_id dedupe, UI-box status message, tools_called/
# outcomes seeding, retrieval-settings passthrough.
# ---------------------------------------------------------------------------

_SESSION = object()  # opaque; only forwarded to the (faked) get_rag_context


class _RagCtx:
    """Fake for rag.retrieval.get_rag_context capturing the call."""

    def __init__(self, text="", sources=None):
        self.text, self.sources = text, list(sources or [])
        self.calls: list[dict] = []

    async def __call__(self, session, query, areas=None, top_k=3,
                       min_score=0.25, max_chars_per_area=0, out_sources=None):
        self.calls.append({
            "session": session, "query": query, "areas": areas, "top_k": top_k,
            "min_score": min_score, "max_chars_per_area": max_chars_per_area,
        })
        if out_sources is not None:
            out_sources.extend(self.sources)
        return self.text


def _run_assemble(monkeypatch, *, rag_ctx=None, settings=None,
                  parse_cards=None, parse_topic=None, **kw):
    from boerdi.services.mcp import parsers
    from boerdi.services.rag import retrieval

    monkeypatch.setattr(
        retrieval, "get_retrieval_settings",
        lambda: settings
        or {"top_k": 7, "min_score": 0.4, "max_chars_per_area": 5000})
    monkeypatch.setattr(retrieval, "get_rag_context", rag_ctx or _RagCtx())
    if parse_cards is not None:
        monkeypatch.setattr(tool_loop, "parse_wlo_cards", parse_cards)
    if parse_topic is not None:
        monkeypatch.setattr(parsers, "parse_wlo_topic_page_cards", parse_topic)

    args = dict(
        session=_SESSION,
        message="finde material",
        history=[],
        pattern_output={},
        pattern_label="M06",
        session_state={},
        available_rag_areas=None,
        rag_config=None,
        blocked_tools=[],
        prefetched_tool=None,
        prefetched_extras=None,
        canvas_state=None,
        system="SYS",
        _inline_grouping_mode=False,
        _pattern_sources_decl=None,
        _rag_allowed_for_pattern=True,
    )
    args.update(kw)
    return asyncio.run(tool_loop._assemble_messages(**args))


def test_assemble_minimal_stack_and_settings_passthrough(monkeypatch):
    (messages, all_cards, tools_called, outcomes, knowledge_prefetched,
     always_areas, mcp_prefetched, top_k, min_score, max_chars) = \
        _run_assemble(monkeypatch, history=[{"role": "user", "content": "hi"}])
    assert messages == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hi"},
        {"role": "user", "content": "finde material"},
    ]
    assert all_cards == [] and tools_called == [] and outcomes == []
    assert knowledge_prefetched is False and mcp_prefetched is False
    assert always_areas == []
    # retrieval settings are read once and passed through for the tool loop
    assert (top_k, min_score, max_chars) == (7, 0.4, 5000)


def test_assemble_trims_history_to_last_10(monkeypatch):
    history = [{"role": "user", "content": f"m{i}"} for i in range(12)]
    messages = _run_assemble(monkeypatch, history=history)[0]
    # system + 10 history + current user message
    assert len(messages) == 12
    assert messages[1]["content"] == "m2" and messages[10]["content"] == "m11"


def test_assemble_canvas_context_injected_for_material(monkeypatch):
    md = "x" * 5000
    canvas = {"mode": "material", "title": "Bruchrechnung",
              "material_type": "Arbeitsblatt", "markdown": md}
    messages = _run_assemble(monkeypatch, canvas_state=canvas)[0]
    ctx = messages[1]
    assert ctx["role"] == "system"
    assert "Canvas-Modus: material" in ctx["content"]
    assert "Titel: Bruchrechnung" in ctx["content"]
    assert "Material-Typ: Arbeitsblatt" in ctx["content"]
    # markdown capped at 4000 chars
    assert "x" * 4000 in ctx["content"] and "x" * 4001 not in ctx["content"]


def test_assemble_canvas_cards_mode_shows_count_not_markdown(monkeypatch):
    canvas = {"mode": "cards", "cards_count": 6, "markdown": "SOLLNICHTREIN"}
    messages = _run_assemble(monkeypatch, canvas_state=canvas)[0]
    ctx = messages[1]["content"]
    assert "Angezeigte Kacheln: 6" in ctx
    assert "SOLLNICHTREIN" not in ctx


def test_assemble_canvas_skipped_when_empty(monkeypatch):
    for canvas in (None, {}, {"mode": "empty", "markdown": "x"}):
        messages = _run_assemble(monkeypatch, canvas_state=canvas)[0]
        assert messages == [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "finde material"},
        ]


def test_assemble_rag_always_prefetch_injects_simulated_tool_call(monkeypatch):
    rag = _RagCtx(text="WISSEN-KONTEXT")
    state: dict = {}
    (messages, _cards, tools_called, _outs, knowledge_prefetched,
     always_areas, _mcp, *_rest) = _run_assemble(
        monkeypatch, rag_ctx=rag, session_state=state,
        available_rag_areas=["hilfe", "extra"],
        rag_config={"hilfe": {"mode": "always"}, "extra": {"mode": "on_demand"}})
    assert knowledge_prefetched is True and always_areas == ["hilfe"]
    # settings flow into the retrieval call, session is forwarded as-is
    assert rag.calls == [{
        "session": _SESSION, "query": "finde material", "areas": ["hilfe"],
        "top_k": 7, "min_score": 0.4, "max_chars_per_area": 5000,
    }]
    # stack: system, user, simulated assistant tool call, tool result — and
    # NO second plain user message afterwards
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    tc = messages[2]["tool_calls"][0]
    assert tc["id"] == "prefetch_knowledge"
    assert tc["function"]["name"] == "query_knowledge"
    assert json.loads(tc["function"]["arguments"]) == {
        "area": "hilfe", "query": "finde material"}
    assert messages[3]["tool_call_id"] == "prefetch_knowledge"
    assert messages[3]["content"] == (
        "[Bereits durchsuchte Bereiche: hilfe]\n\nWISSEN-KONTEXT")
    assert tools_called == ["query_knowledge (prefetch)"]
    assert state["_rag_areas_used"] == ["hilfe"]


def test_assemble_rag_gate_closed_skips_prefetch(monkeypatch):
    rag = _RagCtx(text="WISSEN")
    (messages, _cards, tools_called, _outs, knowledge_prefetched,
     always_areas, *_rest) = _run_assemble(
        monkeypatch, rag_ctx=rag,
        available_rag_areas=["hilfe"], rag_config={"hilfe": {"mode": "always"}},
        _rag_allowed_for_pattern=False)
    assert rag.calls == []  # gate closed → no retrieval round-trip
    assert knowledge_prefetched is False and always_areas == []
    assert tools_called == []
    assert messages[-1] == {"role": "user", "content": "finde material"}


def test_assemble_rag_empty_context_falls_back_to_plain_user(monkeypatch):
    rag = _RagCtx(text="")
    state: dict = {}
    (messages, _cards, tools_called, _outs, knowledge_prefetched,
     always_areas, *_rest) = _run_assemble(
        monkeypatch, rag_ctx=rag, session_state=state,
        available_rag_areas=["hilfe"], rag_config={"hilfe": {"mode": "always"}})
    # empty context → no injection, but always_areas were still computed
    assert knowledge_prefetched is False and always_areas == ["hilfe"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert tools_called == [] and "_rag_areas_used" not in state


def test_assemble_rag_out_sources_deduped_into_session_state(monkeypatch):
    rag = _RagCtx(text="WISSEN", sources=["s1.md", "s2.md"])
    state = {"_rag_top_sources": ["s1.md"]}
    _run_assemble(
        monkeypatch, rag_ctx=rag, session_state=state,
        available_rag_areas=["hilfe"], rag_config={"hilfe": {"mode": "always"}})
    assert state["_rag_top_sources"] == ["s1.md", "s2.md"]


def test_assemble_mcp_prefetch_primary_injected(monkeypatch):
    from boerdi.api.schemas import ToolOutcome
    cards = [{"node_id": "n1", "title": "T1"}]
    (messages, all_cards, tools_called, outcomes, _kp, _aa,
     mcp_prefetched, *_rest) = _run_assemble(
        monkeypatch, parse_cards=lambda txt: list(cards),
        prefetched_tool={"name": "search_wlo_content",
                         "arguments": {"searchQuery": "bruch"},
                         "result_text": "RAW-MCP"})
    assert mcp_prefetched is True and all_cards == cards
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    tc = messages[2]["tool_calls"][0]
    assert tc["id"] == "prefetch_mcp"
    assert tc["function"]["name"] == "search_wlo_content"
    assert json.loads(tc["function"]["arguments"]) == {"searchQuery": "bruch"}
    # not in inline mode → redaction passes the raw text through (capped)
    assert messages[3] == {"role": "tool", "tool_call_id": "prefetch_mcp",
                           "content": "RAW-MCP"}
    assert tools_called == ["search_wlo_content (prefetch)"]
    assert outcomes == [ToolOutcome(tool="search_wlo_content",
                                    status="success", item_count=1)]


def test_assemble_mcp_prefetch_blocked_tool_skipped(monkeypatch):
    (messages, all_cards, tools_called, outcomes, _kp, _aa,
     mcp_prefetched, *_rest) = _run_assemble(
        monkeypatch, parse_cards=lambda txt: [{"node_id": "n1"}],
        blocked_tools=["search_wlo_content"],
        prefetched_tool={"name": "search_wlo_content", "arguments": {},
                         "result_text": "RAW"})
    assert mcp_prefetched is False and all_cards == []
    assert [m["role"] for m in messages] == ["system", "user"]
    assert tools_called == [] and outcomes == []


def test_assemble_mcp_prefetch_topic_pages_uses_topic_parser(monkeypatch):
    topic_calls: list[str] = []

    def fake_topic(txt):
        topic_calls.append(txt)
        return [{"node_id": "tp1", "topic_pages": [{"u": 1}]}]

    def fail_cards(txt):  # normal parser must NOT run for topic pages
        raise AssertionError("parse_wlo_cards called for search_wlo_topic_pages")

    all_cards = _run_assemble(
        monkeypatch, parse_cards=fail_cards, parse_topic=fake_topic,
        prefetched_tool={"name": "search_wlo_topic_pages", "arguments": {},
                         "result_text": "TP-RAW"})[1]
    assert topic_calls == ["TP-RAW"]
    assert all_cards == [{"node_id": "tp1", "topic_pages": [{"u": 1}]}]


def test_assemble_mcp_prefetch_collections_get_node_type_default(monkeypatch):
    all_cards = _run_assemble(
        monkeypatch,
        parse_cards=lambda txt: [{"node_id": "c1"},
                                 {"node_id": "c2", "node_type": "portal"}],
        prefetched_tool={"name": "search_wlo_collections", "arguments": {},
                         "result_text": "RAW"})[1]
    assert all_cards[0]["node_type"] == "collection"  # defaulted
    assert all_cards[1]["node_type"] == "portal"      # existing value kept


def test_assemble_parse_error_still_injects_with_empty_outcome(monkeypatch):
    def boom(txt):
        raise ValueError("kaputt")

    (messages, all_cards, _tools, outcomes, _kp, _aa,
     mcp_prefetched, *_rest) = _run_assemble(
        monkeypatch, parse_cards=boom,
        prefetched_tool={"name": "search_wlo_content", "arguments": {},
                         "result_text": "RAW"})
    # parsing failed, but the simulated tool call is still injected
    assert mcp_prefetched is True and all_cards == []
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    assert outcomes[0].status == "empty" and outcomes[0].item_count == 0


def test_assemble_extras_injected_with_unique_ids_and_dedupe(monkeypatch):
    from boerdi.api.schemas import ToolOutcome
    primary = [{"node_id": "n1", "title": "T1"}]
    extra_cards = [{"node_id": "n1", "topic_pages": [{"u": 1}],
                    "topic_page_url": "https://tp"},
                   {"node_id": "n2"}]
    (messages, all_cards, tools_called, outcomes, _kp, _aa,
     _mcp, *_rest) = _run_assemble(
        monkeypatch,
        parse_cards=lambda txt: list(primary) if txt == "RAW" else list(extra_cards),
        prefetched_tool={"name": "search_wlo_content", "arguments": {},
                         "result_text": "RAW"},
        prefetched_extras=[
            {"name": "blockiert", "arguments": {}, "result_text": "X"},
            {"name": "search_wlo_content", "arguments": {"q": "e"},
             "result_text": "EXTRA-RAW"},
        ],
        blocked_tools=["blockiert"])
    # dedupe by node_id: n1 kept once, topic_pages/topic_page_url backfilled
    assert [c["node_id"] for c in all_cards] == ["n1", "n2"]
    assert all_cards[0]["topic_pages"] == [{"u": 1}]
    assert all_cards[0]["topic_page_url"] == "https://tp"
    # the blocked extra is skipped but keeps its enumerate slot → id _1
    extra_tc = messages[4]["tool_calls"][0]
    assert extra_tc["id"] == "prefetch_extra_1"
    assert messages[5]["tool_call_id"] == "prefetch_extra_1"
    # ALT wart kept: the seeding loop at the end runs over ALL extras with no
    # skip conditions — blocked/empty ones are still counted as called
    assert tools_called == ["search_wlo_content (prefetch)",
                            "blockiert (prefetch-extra)",
                            "search_wlo_content (prefetch-extra)"]
    assert outcomes[1] == ToolOutcome(tool="blockiert",
                                      status="success", item_count=0)
    assert outcomes[2] == ToolOutcome(tool="search_wlo_content",
                                      status="success", item_count=0)


def test_assemble_extra_without_name_or_text_skipped(monkeypatch):
    (messages, all_cards, tools_called, outcomes, *_rest) = _run_assemble(
        monkeypatch, parse_cards=lambda txt: [{"node_id": "x"}],
        prefetched_extras=[{"name": "", "result_text": "X"},
                           {"name": "tool_a", "result_text": ""}])
    # nothing injected into the stack, no cards parsed …
    assert [m["role"] for m in messages] == ["system", "user"]
    assert all_cards == []
    # … but the ALT seeding loop still records every extra ("" → "?")
    assert tools_called == ["? (prefetch-extra)", "tool_a (prefetch-extra)"]
    assert [o.tool for o in outcomes] == ["?", "tool_a"]


def test_assemble_ui_box_footer_only_in_inline_mode(monkeypatch):
    prefetched = {"name": "search_wlo_collections", "arguments": {},
                  "result_text": "RAW"}
    coll = [{"node_id": "c1", "node_type": "collection"}]
    # inline mode on → real _ui_box_state_footer appends a status system msg
    messages = _run_assemble(
        monkeypatch, parse_cards=lambda txt: list(coll),
        prefetched_tool=dict(prefetched), _inline_grouping_mode=True)[0]
    assert messages[-1]["role"] == "system"
    assert messages[-1]["content"].startswith(
        "Status der UI-Boxen aus den Prefetch-Tool-Calls:")
    assert "1 Sammlung(en) sichtbar" in messages[-1]["content"]
    # inline mode off → footer is empty → no status message
    messages = _run_assemble(
        monkeypatch, parse_cards=lambda txt: list(coll),
        prefetched_tool=dict(prefetched), _inline_grouping_mode=False)[0]
    assert messages[-1]["role"] == "tool"


# ════════════════════════════════════════════════════════════════════════
# _run_tool_loop (P15) — ALT llm_tool_loop.py:565-1158
# ════════════════════════════════════════════════════════════════════════

_ACTIVE = [{"type": "function", "function": {"name": "search_wlo_content"}}]


def _resp_text(text, usage=None):
    msg = SimpleNamespace(role="assistant", content=text, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        usage=usage, model="gpt-x")


def _resp_tools(calls, usage=None):
    tcs = [SimpleNamespace(id=i, type="function",
                           function=SimpleNamespace(name=n, arguments=a))
           for i, n, a in calls]
    msg = SimpleNamespace(role="assistant", content=None, tool_calls=tcs)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=usage, model="gpt-x")


class _SeqLLM:
    """Fake ``llm.chat_completion``: returns the preset responses in order."""

    def __init__(self, responses, raises=None):
        self.calls: list[dict] = []
        self._responses = list(responses)
        self._raises = raises

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._responses.pop(0)


class _OutcomeFake:
    """Fake ``outcome_service.call_with_outcome`` capturing (name, args)."""

    def __init__(self, result_map=None):
        self.calls: list[tuple[str, dict]] = []
        self._map = result_map or {}

    async def __call__(self, tool_name, tool_args):
        from boerdi.api.schemas import ToolOutcome
        self.calls.append((tool_name, dict(tool_args)))
        text = self._map.get(tool_name, f"result:{tool_name}")
        return text, ToolOutcome(tool=tool_name, status="success", item_count=1)


def _run_loop(monkeypatch, responses, *, raises=None, outcome=None,
              parse_cards=None, **kw):
    from boerdi.services import card_collect, outcome_service

    fake = _SeqLLM(responses, raises=raises)
    monkeypatch.setattr(llm, "chat_completion", fake)
    monkeypatch.setattr(outcome_service, "call_with_outcome",
                        outcome if outcome is not None else _OutcomeFake())
    # A4c-2a: Die Karten-Ernte des Tool-Loops wohnt in ``services/card_collect``
    # (zweiter Aufrufer: die Agent-Schleife). Nur der ORT hat sich geändert —
    # ``_run_assemble`` patcht weiter an ``tool_loop``, denn die Prefetch-Karten
    # in ``_assemble_messages`` sind dort geblieben.
    monkeypatch.setattr(card_collect, "parse_wlo_cards",
                        parse_cards if parse_cards is not None else (lambda text: []))
    state = dict(
        message="hallo",
        classification={},
        pattern_output={},
        pattern_label="X",
        session_state={},
        rag_context="",
        blocked_tools=[],
        active_tools=[],
        _inline_qr_enabled=False,
        _inline_grouping_mode=False,
        messages=[{"role": "system", "content": "sys"}],
        all_cards=[],
        tools_called=[],
        outcomes=[],
        knowledge_prefetched=False,
        mcp_prefetched=False,
        always_areas=[],
        _RAG_TOP_K=3,
        _RAG_MIN_SCORE=0.25,
        _RAG_MAX_CHARS_PER_AREA=4000,
        usage_acc=None,
        on_token=None,
    )
    state.update(kw)
    result = asyncio.run(tool_loop._run_tool_loop(_SESSION, **state))
    return fake, result, state


def test_loop_final_text_returned_and_stripped(monkeypatch):
    _fake, result, st = _run_loop(
        monkeypatch, [_resp_text("<think>geheim</think>Antwort")])
    text, cards, tools, outs = result
    assert text == "Antwort"  # strip_reasoning_markers on the content path
    # the loop returns the SAME in-place-continued objects
    assert cards is st["all_cards"] and tools is st["tools_called"]
    assert outs is st["outcomes"]


def test_loop_first_iteration_forces_tool_choice_required(monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", '{"query": "mathe"}')]),
        _resp_text("fertig"),
    ], active_tools=_ACTIVE)
    assert fake.calls[0]["tool_choice"] == "required"   # nothing prefetched yet
    assert fake.calls[0]["tools"] == _ACTIVE
    assert fake.calls[0]["temperature"] == 0.4
    assert fake.calls[0]["messages"] is st["messages"]  # loop feeds the live list
    assert fake.calls[1]["tool_choice"] is None         # only the FIRST round forces
    assert result[0] == "fertig"
    assert st["tools_called"] == ["search_wlo_content"]
    # assistant tool-call round is re-serialized as a plain dict
    asst = [m for m in st["messages"] if m.get("role") == "assistant"][0]
    assert asst["tool_calls"] == [{
        "id": "tc1", "type": "function",
        "function": {"name": "search_wlo_content",
                     "arguments": '{"query": "mathe"}'}}]


def test_loop_no_force_when_context_already_available(monkeypatch):
    fake, _r, _st = _run_loop(monkeypatch, [_resp_text("ok")],
                              active_tools=_ACTIVE, knowledge_prefetched=True)
    assert fake.calls[0]["tool_choice"] is None
    fake, _r, _st = _run_loop(
        monkeypatch, [_resp_text("ok")], active_tools=_ACTIVE,
        session_state={"entities": {"_last_contents": [{"id": 1}]}})
    assert fake.calls[0]["tool_choice"] is None


def test_loop_force_tool_use_overrides_prefetch_suffix(monkeypatch):
    # "query_knowledge (prefetch)" is NOT a real MCP call — force still fires.
    fake, _r, _st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", "{}")]),
        _resp_text("ok"),
    ], active_tools=_ACTIVE, knowledge_prefetched=True,
        pattern_output={"force_tool_use": True},
        tools_called=["query_knowledge (prefetch)"])
    assert fake.calls[0]["tool_choice"] == "required"


def test_loop_verbosity_mapping_and_rag_bump(monkeypatch):
    fake, _r, _st = _run_loop(monkeypatch, [_resp_text("a")],
                              pattern_output={"length": "lang"})
    assert fake.calls[0]["verbosity"] == "high"
    fake, _r, _st = _run_loop(monkeypatch, [_resp_text("a")],
                              pattern_output={"length": "kurz"},
                              knowledge_prefetched=True)
    assert fake.calls[0]["verbosity"] == "medium"       # low bumped one notch
    fake, _r, _st = _run_loop(monkeypatch, [_resp_text("a")],
                              rag_context="x" * 501)
    assert fake.calls[0]["verbosity"] == "high"         # mittel bumped via rag_context


def test_loop_api_error_returns_error_tuple(monkeypatch):
    _fake, result, st = _run_loop(monkeypatch, [], raises=RuntimeError("boom"))
    text, cards, _tools, outs = result
    assert text == "Fehler bei der Verarbeitung: boom"
    assert cards is st["all_cards"] and outs is st["outcomes"]


def test_loop_usage_phase_labels_per_iteration(monkeypatch):
    from boerdi.obs import usage as usage_mod
    acc = usage_mod.new_accumulator()
    u = SimpleNamespace(prompt_tokens=10, completion_tokens=5,
                        prompt_tokens_details=None)
    _fake, _r, _st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", "{}")], usage=u),
        _resp_text("fertig", usage=u),
    ], active_tools=_ACTIVE, usage_acc=acc)
    assert acc["per_phase"]["tool_loop"]["calls"] == 1   # tool round
    assert acc["per_phase"]["response"]["calls"] == 1    # final round
    assert acc["calls"] == 2


def test_loop_streaming_branch_uses_stream_completion(monkeypatch):
    seen: dict = {}

    async def fake_stream(on_token, **kwargs):
        seen["on_token"] = on_token
        seen["kwargs"] = kwargs
        return _resp_text("gestreamt")

    monkeypatch.setattr(tool_loop, "_stream_completion", fake_stream)

    def tok(_s):
        return None

    fake, result, _st = _run_loop(monkeypatch, [], on_token=tok)
    assert result[0] == "gestreamt"
    assert seen["on_token"] is tok
    assert seen["kwargs"]["temperature"] == 0.4  # same kwargs set as non-streaming
    assert fake.calls == []                      # chat_completion NOT used


def test_loop_malformed_tool_args_reported_and_loop_continues(monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", "{kein json")]),
        _resp_text("fertig"),
    ], active_tools=_ACTIVE)
    assert result[0] == "fertig"
    assert st["tools_called"] == []  # malformed call is not counted (B8)
    tool_msgs = [m for m in st["messages"] if m.get("role") == "tool"]
    assert tool_msgs[0]["tool_call_id"] == "tc1"
    assert tool_msgs[0]["content"] == (
        "Fehler: Die Tool-Argumente waren kein gültiges JSON. Bitte denselben "
        "Aufruf mit korrektem JSON wiederholen.")
    assert len(fake.calls) == 2


def test_loop_select_top_cards_sanitizes_stashes_and_acks(monkeypatch):
    from boerdi.services import config_loader as cfg

    monkeypatch.setattr(cfg, "load_display_rules_config", lambda: {
        "prompt_anzeige_konsistenz": {"enabled": True, "exclude_patterns": []}})
    args = json.dumps({"card_ids": ["a", "a", "", 5, "b", "c", "d", "e", "f"],
                       "reasoning": " weil passend "})
    _fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "select_top_cards", args)]),
        _resp_text("fertig"),
    ], _inline_qr_enabled=True)
    assert result[0] == "fertig"
    # sanitize: strings only, deduped, max 5
    assert st["session_state"]["_selected_card_ids"] == ["a", "b", "c", "d", "e"]
    assert st["session_state"]["_selected_card_reasoning"] == "weil passend"
    assert st["tools_called"] == ["select_top_cards"]
    ack = [m for m in st["messages"] if m.get("role") == "tool"][0]["content"]
    assert ack.startswith(
        "OK — Auswahl gespeichert (5 IDs). "
        "Rufe jetzt respond_to_user mit der Prosa-Antwort auf.")
    # Welle-E consistency tail from display-rules config
    assert "WICHTIG: Im nächsten ``respond_to_user``-Aufruf" in ack
    assert "genau diese 5 ausgewählten IDs" in ack


def test_loop_select_top_cards_ack_variant_and_pattern_exclude(monkeypatch):
    from boerdi.services import config_loader as cfg

    monkeypatch.setattr(cfg, "load_display_rules_config", lambda: {
        "prompt_anzeige_konsistenz": {"enabled": True,
                                      "exclude_patterns": ["PAT-9"]}})
    args = json.dumps({"card_ids": ["a"]})
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "select_top_cards", args)]),
        _resp_text("fertig"),
    ], pattern_output={"id": "PAT-9"})
    ack = [m for m in st["messages"] if m.get("role") == "tool"][0]["content"]
    # no inline-QR hint (flag off) and no consistency tail (pattern excluded)
    assert ack == "OK — Auswahl gespeichert (1 IDs)."


def test_loop_respond_to_user_inline_final(monkeypatch):
    args = json.dumps({
        "text": "Antwort hier\n**Mehr Mathe**",
        "quick_replies": ["Mehr Mathe", "Zeig Videos", "", 3, "a", "b"],
    })
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "respond_to_user", args),
                     ("tc2", "search_wlo_content", "{}")]),
    ], _inline_qr_enabled=True)
    text, _cards, tools, _outs = result
    assert text == "Antwort hier"  # trailing QR option line stripped
    assert st["session_state"]["_inline_quick_replies"] == [
        "Mehr Mathe", "Zeig Videos", "a", "b"]  # strings only, max 4
    assert len(fake.calls) == 1    # inline final ends the loop
    assert tools == ["respond_to_user"]  # tc2 after the break is NOT processed
    tool_msgs = [m for m in st["messages"] if m.get("role") == "tool"]
    # Anchored on tc1's id rather than on "the last tool message": since F-5 the
    # skipped sibling tc2 also gets an (honest, different) answer, and this pin
    # is about respond_to_user's own acknowledgement.
    assert [m for m in tool_msgs if m["tool_call_id"] == "tc1"][0]["content"] == "OK"


def test_loop_respond_to_user_beantwortet_uebersprungene_geschwister(monkeypatch):
    """Audit F-5: Der ``break`` nach ``respond_to_user`` ließ jeden Tool-Call
    derselben parallelen Runde ohne ``role=tool``-Antwort zurück. Verworfen wird
    die Kette nur im Normalfall — der Reflection-Retry schickt genau sie erneut
    los, und OpenAI weist eine Kette mit unbeantwortetem ``tool_call`` zurück.
    Der Zug degradierte dann zu einer Fehlermeldung, obwohl die Antwort des
    Modells bereits vorlag."""
    args = json.dumps({"text": "Antwort hier"})
    _fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "respond_to_user", args),
                     ("tc2", "search_wlo_content", "{}"),
                     ("tc3", "search_wlo_collections", "{}")]),
    ], _inline_qr_enabled=True)

    assert result[2] == ["respond_to_user"]  # tc2/tc3 laufen weiterhin NICHT

    gefordert = {tc["id"] for m in st["messages"]
                 if isinstance(m, dict) and m.get("role") == "assistant"
                 for tc in (m.get("tool_calls") or [])}
    beantwortet = {m["tool_call_id"] for m in st["messages"]
                   if isinstance(m, dict) and m.get("role") == "tool"}
    assert gefordert == {"tc1", "tc2", "tc3"}
    assert gefordert <= beantwortet, "jeder tool_call braucht eine role=tool-Antwort"

    # Und die Quittung sagt die Wahrheit: „OK" würde dem Modell im
    # Reflection-Durchgang vorspiegeln, die Suche sei gelaufen.
    uebersprungen = [m for m in st["messages"]
                     if isinstance(m, dict) and m.get("tool_call_id") == "tc2"][0]
    assert "respond_to_user" in uebersprungen["content"]
    assert uebersprungen["content"] != "OK"


def test_loop_query_knowledge_rag_dispatch_with_session(monkeypatch):
    from boerdi.services.rag import retrieval

    rag = _RagCtx("Wissen: Suche nutzt Filter.", sources=["s1.md", "s2.md"])
    monkeypatch.setattr(retrieval, "get_rag_context", rag)
    args = json.dumps({"area": "hilfe", "query": "wie suche ich"})
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "query_knowledge", args)]),
        _resp_text("fertig"),
    ], session_state={"_rag_top_sources": ["s1.md"]})
    assert rag.calls == [{
        "session": _SESSION, "query": "wie suche ich", "areas": ["hilfe"],
        "top_k": 3, "min_score": 0.25, "max_chars_per_area": 4000,
    }]
    assert st["session_state"]["_rag_areas_used"] == ["hilfe"]
    assert st["session_state"]["_rag_top_sources"] == ["s1.md", "s2.md"]  # deduped
    msg = [m for m in st["messages"] if m.get("role") == "tool"][0]
    assert msg["content"] == "Wissen: Suche nutzt Filter."
    assert st["tools_called"] == ["query_knowledge"]


def test_loop_query_knowledge_prefetch_guard_and_empty_result(monkeypatch):
    from boerdi.services.rag import retrieval

    rag = _RagCtx("")
    monkeypatch.setattr(retrieval, "get_rag_context", rag)
    # (a) area already prefetched + same query → short hint, NO rag call
    args = json.dumps({"area": "hilfe", "query": "hallo"})
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "query_knowledge", args)]),
        _resp_text("fertig"),
    ], knowledge_prefetched=True, always_areas=["hilfe"])
    assert rag.calls == []
    msg = [m for m in st["messages"] if m.get("role") == "tool"][0]
    assert msg["content"] == (
        "Bereich 'hilfe' wurde bereits vorab durchsucht. Die Ergebnisse "
        "findest du in der vorherigen query_knowledge-Antwort.")
    # (b) empty rag result → placeholder text
    args = json.dumps({"area": "anders", "query": "neu"})
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "query_knowledge", args)]),
        _resp_text("fertig"),
    ])
    msg = [m for m in st["messages"] if m.get("role") == "tool"][0]
    assert msg["content"] == (
        "Keine relevanten Informationen im Bereich 'anders' gefunden.")


def test_loop_blocked_tool_refused(monkeypatch):
    from boerdi.api.schemas import ToolOutcome

    out = _OutcomeFake()
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", "{}")]),
        _resp_text("fertig"),
    ], outcome=out, blocked_tools=["search_wlo_content"])
    assert out.calls == []  # never dispatched
    assert st["outcomes"] == [ToolOutcome(
        tool="search_wlo_content", status="error",
        error="blocked by safety layer")]
    msg = [m for m in st["messages"] if m.get("role") == "tool"][0]
    assert msg["content"] == "Tool wurde aus Sicherheitsgruenden blockiert."


def test_loop_max_results_clamped_to_five(monkeypatch):
    out = _OutcomeFake()
    _fake, _r, _st = _run_loop(monkeypatch, [
        _resp_tools([
            ("tc1", "get_collection_contents", json.dumps({"maxItems": 9})),
            ("tc2", "search_wlo_content", json.dumps({"maxResults": 3})),
        ]),
        _resp_text("fertig"),
    ], outcome=out)
    args1 = out.calls[0][1]
    assert args1["maxResults"] == 5 and "maxItems" not in args1  # legacy key migrated + clamped
    assert out.calls[1][1]["maxResults"] == 3  # explicit lower value kept


def test_loop_entity_filters_injected(monkeypatch):
    out = _OutcomeFake()
    _fake, _r, _st = _run_loop(monkeypatch, [
        _resp_tools([
            ("tc1", "search_wlo_content", json.dumps({
                "query": "brüche", "resourceType": "Arbeitsblatt",
                "educationalLevel": "Primarstufe"})),
            ("tc2", "search_wlo_collections", json.dumps({"query": "brüche"})),
        ]),
        _resp_text("fertig"),
    ], outcome=out, classification={"entities": {
        "medientyp": "Video", "fach": "Mathematik", "stufe": "Sekundarstufe I"}})
    args1 = out.calls[0][1]
    assert args1["learningResourceType"] == "Arbeitsblatt"  # legacy key wins over entity
    assert "resourceType" not in args1
    assert args1["educationalContext"] == "Primarstufe"
    assert args1["discipline"] == "Mathematik"              # injected from entities
    args2 = out.calls[1][1]
    assert args2["discipline"] == "Mathematik"
    assert args2["educationalContext"] == "Sekundarstufe I"
    assert "learningResourceType" not in args2              # collections: no LRT filter


def test_loop_card_yielding_gate_and_collection_marking(monkeypatch):
    out = _OutcomeFake({"search_wlo_collections": "colls",
                        "lookup_wlo_vocabulary": "## Vokabular"})
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_collections", "{}"),
                     ("tc2", "lookup_wlo_vocabulary", "{}")]),
        _resp_text("fertig"),
    ], outcome=out, parse_cards=lambda text: [{"node_id": "n1", "title": "T"}])
    # collections yield cards, marked node_type=collection
    assert st["all_cards"] == [
        {"node_id": "n1", "title": "T", "node_type": "collection"}]
    # vocabulary tool yields NO cards (CARD_YIELDING_TOOLS gate), but the raw
    # text goes back to the LLM (non-inline mode: no redaction, empty footer)
    tool_msgs = [m for m in st["messages"] if m.get("role") == "tool"]
    assert tool_msgs[0]["content"] == "colls"
    assert tool_msgs[1]["content"] == "## Vokabular"
    assert [o.tool for o in st["outcomes"]] == [
        "search_wlo_collections", "lookup_wlo_vocabulary"]


def test_loop_card_dedupe_backfills_topic_pages(monkeypatch):
    existing = {"node_id": "n1", "title": "Alt"}
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", "{}")]),
        _resp_text("fertig"),
    ], parse_cards=lambda text: [
        {"node_id": "n1", "topic_pages": [{"variant_id": "v1"}],
         "topic_page_url": "https://t"},
        {"node_id": "n2"},
    ], all_cards=[existing])
    assert st["all_cards"][0] is existing                     # not duplicated
    assert existing["topic_pages"] == [{"variant_id": "v1"}]  # backfilled
    assert existing["topic_page_url"] == "https://t"
    assert st["all_cards"][1] == {"node_id": "n2"}


def test_loop_topic_pages_parser_merge_and_promote(monkeypatch):
    from boerdi.services.mcp import parsers

    existing = {"node_id": "n1", "node_type": "content",
                "topic_pages": [{"variant_id": "v1"}]}

    def fail_parse(text):
        raise AssertionError("standard parser must not run for topic_pages")

    monkeypatch.setattr(parsers, "parse_wlo_topic_page_cards", lambda text: [
        {"node_id": "n1",
         "topic_pages": [{"variant_id": "v1"}, {"variant_id": "v2"}]}])
    _fake, _r, st = _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_topic_pages", "{}")]),
        _resp_text("fertig"),
    ], parse_cards=fail_parse, all_cards=[existing])
    assert existing["node_type"] == "collection"  # promoted for isTopicPage()
    assert [v["variant_id"] for v in existing["topic_pages"]] == ["v1", "v2"]
    assert len(st["all_cards"]) == 1              # merged, not appended


def test_loop_reflection_retries_once_when_required_tool_missing(monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _resp_text("erster"), _resp_text("zweiter"),
    ], pattern_output={"force_tool_use": True, "tools": ["search_wlo_content"]})
    assert result[0] == "zweiter"     # first final was rejected + retried
    assert len(fake.calls) == 2       # reflection runs exactly once
    corr = [m for m in st["messages"] if m.get("role") == "user"][-1]["content"]
    assert corr.startswith(
        "⚠ KORREKTUR: Du hast PAT-X gewählt, aber KEINEN der verlangten "
        "Tools genutzt: search_wlo_content.")
    assert "mindestens EINEN" in corr


def test_loop_reflection_satisfied_by_prefetch_bare_name(monkeypatch):
    # ALT wart kept: actual_bare strips the " (prefetch)" suffix, so a prefetch
    # alone satisfies the reflection gate — no retry fires.
    fake, result, _st = _run_loop(
        monkeypatch, [_resp_text("direkt")],
        pattern_output={"force_tool_use": True, "tools": ["search_wlo_content"]},
        tools_called=["search_wlo_content (prefetch)"], knowledge_prefetched=True)
    assert result[0] == "direkt"
    assert len(fake.calls) == 1


def test_loop_reflection_requires_all_lists_missing(monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _resp_text("erster"), _resp_text("zweiter"),
    ], pattern_output={
        "force_tool_use": True, "requires_all_tools": True,
        "tools": ["search_wlo_content", "search_wlo_collections"]},
        tools_called=["search_wlo_content"])
    assert result[0] == "zweiter"
    assert len(fake.calls) == 2
    corr = [m for m in st["messages"] if m.get("role") == "user"][-1]["content"]
    assert ("verlangt ALLE diese Tools nacheinander: "
            "search_wlo_content, search_wlo_collections") in corr
    assert "die fehlenden Tools (search_wlo_collections)" in corr


def test_loop_exhausted_returns_none_for_p16_fallback(monkeypatch):
    bad = _resp_tools([("tc1", "search_wlo_content", "{nope")])
    fake, result, _st = _run_loop(monkeypatch, [bad] * 5, active_tools=_ACTIVE)
    assert result is None          # continuation marker → caller runs P16
    assert len(fake.calls) == 5    # max_iterations


# ── W9b: welche Werkzeuge Karten liefern ────────────────────────────────
def test_card_yielding_tools_is_module_level_and_covers_the_combo_search():
    """``search_wlo_all`` fehlte in der Karten-Weiche.

    Live gemessen 2026-08-01: das Werkzeug liefert 13 Treffer in drei Töpfen
    (``content``/``collections``/``topicPages``), aber sein Envelope hat kein
    Top-Level-``results`` — ``parse_wlo_cards`` gab 0 Karten zurück. Ruft das
    Modell es selbst auf (M06 bietet es an), sah der Nutzer nichts. Seit W5-2a
    ist es das Standard-Suchwerkzeug, also der Hauptpfad.

    Die Menge steht jetzt auf Modulebene: vorher wurde sie bei JEDEM Tool-Aufruf
    neu gebaut und war von außen nicht prüfbar.
    """
    assert "search_wlo_all" in tool_loop.CARD_YIELDING_TOOLS


def test_card_yielding_tools_covers_the_two_new_card_tools():
    for name in ("search_wlo_within_collection", "get_related_content"):
        assert name in tool_loop.CARD_YIELDING_TOOLS, name


# ── K1f-Fund: der Abschluss-Fallback bucht seine Token ───────────────────
# Vom AST-Waechter gefunden, nicht von der Messtabelle: dieser Aufruf haengt
# die GANZE bisherige Nachrichtenkette an, ist also kein kleiner Aufruf — und
# er lief bis 2026-08-11 ungebucht.

def test_fallback_bucht_in_den_merkposten(monkeypatch):
    from boerdi.obs import usage as usage_mod

    cap = _Capture(text="Kurz zusammengefasst.")
    acc = usage_mod.new_accumulator()
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    text, *_ = asyncio.run(tool_loop._max_iterations_fallback(
        [{"role": "user", "content": "finde X"}], [{"node_id": "a"}], [], [],
        usage_acc=acc,
    ))
    assert text == "Kurz zusammengefasst."
    assert acc["calls"] == 1
    assert acc["per_phase"]["fallback_summary"]["prompt"] == 50
