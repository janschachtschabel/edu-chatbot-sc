"""services.turn_persist — P25-26 + P29-33 (persist phases; port of ALT chat_turn_persist).

``build_debug_and_update_session`` (P25-26): assemble the DebugInfo, echo
``_last_pattern`` into entities, and do the turn's single ``update_session`` DB write.
NEU deviations pinned here: ``session`` injected first; ``winner_id: str`` instead of a
``winner`` object; ``trace=[]`` (NEU dropped the tracer); ``update_session`` is
jsonb-native (entities stay a dict, signal_history a list — NOT ``json.dumps``).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.api.schemas import (
    ChatRequest,
    ChatResponse,
    ClassificationResult,
    DebugInfo,
    Environment,
    PaginationInfo,
    QueryMetaEntry,
    SafetyDecision,
    TopicPageView,
    WloCard,
)
from boerdi.services import turn_persist as tp_mod
from boerdi.services.turn_persist import (
    build_debug_and_update_session,
    persist_and_build_response,
)

_SESSION = object()


class _UpdSpy:
    def __init__(self) -> None:
        self.args: tuple | None = None
        self.kwargs: dict | None = None


def _patch(monkeypatch, upd: _UpdSpy):
    async def _fake_update(session, session_id, **kwargs):
        upd.args = (session, session_id)
        upd.kwargs = kwargs

    monkeypatch.setattr(tp_mod, "update_session", _fake_update)
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_persona_definitions",
        lambda: [{"id": "P-AND", "label": "Alle"}],
    )
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_intents",
        lambda: [{"id": "I03", "label": "Info"}],
    )
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_states",
        lambda: [{"id": "S3", "label": "Kuration"}],
    )


def _run(monkeypatch, *, session_state=None, classification=None, winner_id="M09",
         eff_id="M09", eff_label="Lernpfad", new_state="S3", signal_history=None,
         final_confidence=0.77):
    upd = _UpdSpy()
    _patch(monkeypatch, upd)
    ss = session_state if session_state is not None else {
        "persona_id": "P-AND",
        "state_id": "S2",
        "entities": {"thema": "Photosynthese", "_selected_card_ids": ["a"]},
        "turn_count": 4,
        "_selected_card_ids": ["a", "b"],
        "_selected_card_reasoning": "weil",
    }
    cls = classification if classification is not None else ClassificationResult(
        persona_id="P-AND", intent_id="I03", turn_type="follow_up",
        pattern_id_hint="M09", pattern_reasoning="passt",
    )
    debug = asyncio.run(build_debug_and_update_session(
        _SESSION,
        ChatRequest(session_id="bb-1", message="x", environment=Environment()),
        ss,
        cls,
        SafetyDecision(risk_level="low"),
        None,   # policy
        None,   # context_snapshot
        {"calls": 3},  # usage_acc
        winner_id,
        {"tone": "warm", "format_follow_up": "quick_replies", "sources": ["mcp"]},
        new_state,
        ["signal_a"],           # new_signals
        signal_history if signal_history is not None else ["signal_a", "signal_old"],
        {"plausible": True, "reason": "ok", "prev_next_likely": ["S4"]},  # _trans_check
        eff_id, eff_label,
        ["search_wlo_content"],  # tools_called
        [],                      # eliminated
        {"M09": 1.0},            # scores
        [],                      # response_outcomes
        final_confidence,
    ))
    return debug, upd


# ── DebugInfo assembly ───────────────────────────────────────────

def test_debug_labels_resolved(monkeypatch):
    debug, _ = _run(monkeypatch)
    assert debug.persona == "P-AND (Alle)"
    assert debug.intent == "I03 (Info)"
    assert debug.state == "S3 (Kuration)"
    assert debug.pattern == "M09 (Lernpfad)"
    assert debug.turn_type == "follow_up"


def test_debug_entities_strip_underscore(monkeypatch):
    debug, _ = _run(monkeypatch)
    assert debug.entities == {"thema": "Photosynthese"}  # _selected_card_ids dropped


def test_debug_carries_scores_outcomes_confidence(monkeypatch):
    debug, _ = _run(monkeypatch, final_confidence=0.42)
    assert debug.phase2_scores == {"M09": 1.0}
    assert debug.phase1_eliminated == []
    assert debug.confidence == 0.42
    assert debug.tools_called == ["search_wlo_content"]


def test_debug_phase3_modulations_and_state_transition(monkeypatch):
    debug, _ = _run(monkeypatch)
    mod = debug.phase3_modulations
    assert mod["tone"] == "warm"
    assert mod["state_transition"] == {
        "prev": "S2", "next": "S3", "plausible": True,
        "reason": "ok", "expected_next_likely": ["S4"],
    }
    assert mod["selected_card_ids"] == ["a", "b"]
    assert mod["selected_card_reasoning"] == "weil"


def test_debug_trace_empty_tracer_dropped(monkeypatch):
    debug, _ = _run(monkeypatch)
    assert debug.trace == []  # NEU dropped the tracer → trace stays empty
    assert debug.token_usage == {"calls": 3}


def test_debug_llm_engine_match(monkeypatch):
    debug, _ = _run(monkeypatch, winner_id="M09")  # hint M09 == winner M09
    assert debug.llm_engine_match is True
    assert debug.pattern_id_hint == "M09"


def test_debug_llm_engine_match_none_without_hint(monkeypatch):
    cls = ClassificationResult(persona_id="P-AND", intent_id="I03", turn_type="initial")
    debug, _ = _run(monkeypatch, classification=cls)
    assert debug.llm_engine_match is None


# ── _last_pattern echo + update_session DB write ─────────────────

def test_last_pattern_echoed_into_entities(monkeypatch):
    # _effective_pattern_id is echoed into entities._last_pattern BEFORE update_session,
    # so it rides along in the (same-ref) entities dict passed to the DB write.
    _, upd = _run(monkeypatch, eff_id="M09")
    assert upd.kwargs["entities"]["_last_pattern"] == "M09"


def test_update_session_jsonb_native_and_session_injected(monkeypatch):
    _, upd = _run(monkeypatch, signal_history=["a", "b"])
    assert upd.args == (_SESSION, "bb-1")  # session injected first
    assert upd.kwargs["persona_id"] == "P-AND"
    assert upd.kwargs["state_id"] == "S3"
    assert upd.kwargs["turn_count"] == 5  # 4 + 1
    # jsonb-native: dict/list, NOT json.dumps strings
    assert isinstance(upd.kwargs["entities"], dict)
    assert upd.kwargs["signal_history"] == ["a", "b"]
    assert isinstance(upd.kwargs["signal_history"], list)


# ── persist_and_build_response (P29-33) ──────────────────────────────
# Faithful port of ALT ``_persist_and_build_response``. Pins the NEU deviations:
# session injected first · quality-log awaited inline (not spawned) · the main
# safety-log is NOT here (turn_setup/merge concern) · M16-resolver R6-wired
# (no-op for non-M16 → topic_page=None) · ``_display_rules()`` →
# ``load_display_rules_config()``.


class _ASpy:
    def __init__(self, ret=None):
        self.calls: list = []
        self._ret = ret

    async def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self._ret


class _Spy:
    def __init__(self, ret=None):
        self.calls: list = []
        self._ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self._ret


def _patch2(monkeypatch, *, dr=None, ql=None, privacy=None, narrow=None, inline=None):
    """Install spies on the persist boundaries. Top-imports (``save_message``,
    ``_attach_guide_urls``, ``_apply_state_auto_followup``, ``_build_inline_document``,
    ``load_display_rules_config``) patched on ``tp_mod``; lazy ones (config loaders,
    log writers, facet helpers) at their source module — ALT boundary convention."""
    sp = SimpleNamespace(
        save=_ASpy(), guide=_Spy(), quality=_ASpy(), safety=_ASpy(),
        auto_calls=[], inline_calls=[],
    )
    monkeypatch.setattr(tp_mod, "save_message", sp.save)
    monkeypatch.setattr(tp_mod, "_attach_guide_urls", sp.guide)

    def _fake_auto(*, state_id, quick_replies, has_cards):
        sp.auto_calls.append((state_id, list(quick_replies), has_cards))
        return list(quick_replies) + ["Hat das geholfen?"]

    monkeypatch.setattr(tp_mod, "_apply_state_auto_followup", _fake_auto)

    def _fake_inline(pattern_id, markdown, display_rules, topic="",
                     extra_meta=None, formality=""):
        sp.inline_calls.append((pattern_id, markdown, topic, formality))
        return inline if inline is not None else ([], markdown)

    monkeypatch.setattr(tp_mod, "_build_inline_document", _fake_inline)
    monkeypatch.setattr(
        tp_mod, "load_display_rules_config",
        lambda: dr if dr is not None else {
            "groups": {}, "quick_replies": {"max_count": 4},
            "single_content_box": {"enabled": True},
        },
    )
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_quality_log_config",
        lambda: ql if ql is not None else {"logging": {"enabled": True}},
    )
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_privacy_config",
        lambda: privacy if privacy is not None else {"quality": True},
    )
    monkeypatch.setattr("boerdi.obs.quality_events.log_quality_event", sp.quality)
    monkeypatch.setattr("boerdi.obs.quality_events.log_safety_event", sp.safety)
    monkeypatch.setattr(
        "boerdi.domain.facets.narrowing_quick_replies_from_metas",
        lambda metas, max_options=3: list(narrow) if narrow is not None else [],
    )
    monkeypatch.setattr(
        "boerdi.domain.facets.unresolved_filter_note",
        lambda metas, max_shown=2: "",
    )
    return sp


def _run2(monkeypatch, *, sp=None, **over):
    if sp is None:
        sp = _patch2(monkeypatch)
    kw = dict(
        session=_SESSION,
        req=ChatRequest(session_id="bb-1", message="hallo", environment=Environment()),
        env={"page": "/p", "device": "mobile"},
        session_state={"turn_count": 4, "entities": {"thema": "Bruch"}},
        classification=ClassificationResult(entities={"thema": "Bruch"}),
        winner_id="M04",
        pattern_output={"format_follow_up": "quick_replies", "formality": "du"},
        spec_query="Bruch",
        new_state="S3",
        debug=DebugInfo(),
        response_text="Antwort",
        cards=[WloCard(node_id="m1", node_type="content")],
        quick_replies=["A", "B"],
        page_action=None,
        pagination=PaginationInfo(total_count=99),
        _final_text="Antwort-Text",
        _web_links=[],
        _raw_metas=[],
        _query_meta_entries=[],
        _type_focus_label="",
        _qr_mode="llm",
        _qr_max=None,
        _effective_pattern_id="M04",
    )
    kw.update(over)
    resp = asyncio.run(persist_and_build_response(**kw))
    return resp, sp


def test_persist_save_message_session_injected_and_enriched(monkeypatch):
    sp = _patch2(monkeypatch)
    _run2(
        monkeypatch, sp=sp,
        _web_links=[{"title": "t", "url": "u"}],
        _query_meta_entries=[QueryMetaEntry(search_term="x")],
        _type_focus_label="Video",
    )
    assert len(sp.save.calls) == 1
    args, kwargs = sp.save.calls[0]
    assert args[0] is _SESSION and args[1] == "bb-1" and args[2] == "assistant"
    assert isinstance(kwargs["cards"][0], dict)                   # WloCard → dict
    dbg = kwargs["debug"]
    assert dbg["_web_links"] == [{"title": "t", "url": "u"}]      # raw dicts (jsonb-safe)
    assert dbg["_query_metas"][0]["search_term"] == "x"          # objects → model_dump
    assert dbg["_type_focus"] == "Video"


def test_persist_quality_log_awaited_with_session(monkeypatch):
    _, sp = _run2(monkeypatch)
    assert len(sp.quality.calls) == 1
    args, kwargs = sp.quality.calls[0]
    assert args[0] is _SESSION                       # session injected first
    assert args[1] == "bb-1" and args[2] == "hallo"  # session_id, message
    assert args[3] == 4                              # turn_count
    assert kwargs["page"] == "/p" and kwargs["device"] == "mobile"
    assert kwargs["cards_count"] == 1


def test_persist_quality_log_skipped_when_disabled(monkeypatch):
    _, sp = _run2(monkeypatch, sp=_patch2(monkeypatch, ql={"logging": {"enabled": False}}))
    assert sp.quality.calls == []


def test_persist_quality_log_skipped_when_privacy_off(monkeypatch):
    _, sp = _run2(monkeypatch, sp=_patch2(monkeypatch, privacy={"quality": False}))
    assert sp.quality.calls == []


def test_persist_never_logs_safety(monkeypatch):
    # Deviation pin: the main safety-log is a turn_setup/merge concern in ALT,
    # NOT part of P29-33 — persist must never touch log_safety_event.
    _, sp = _run2(monkeypatch)
    assert sp.safety.calls == []


def test_persist_attaches_guide_urls(monkeypatch):
    _, sp = _run2(monkeypatch)
    assert len(sp.guide.calls) == 1
    args, _ = sp.guide.calls[0]
    assert args[0].session_id == "bb-1"              # req


def test_persist_auto_followup_applied_when_qr_mode_on(monkeypatch):
    resp, sp = _run2(monkeypatch, _qr_mode="llm")
    assert sp.auto_calls and sp.auto_calls[0][0] == "S3"
    assert "Hat das geholfen?" in resp.quick_replies


def test_persist_auto_followup_skipped_when_qr_mode_none(monkeypatch):
    resp, sp = _run2(monkeypatch, _qr_mode="none")
    assert sp.auto_calls == []
    assert "Hat das geholfen?" not in resp.quick_replies


def test_persist_group_trim_order_and_pagination(monkeypatch):
    dr = {
        "groups": {"themenseiten_max": 1, "sammlungen_max": 2, "materialien_max": 2},
        "quick_replies": {"max_count": 4}, "single_content_box": {"enabled": True},
    }
    cards = [
        WloCard(node_id="ts1", node_type="topic_page"),
        WloCard(node_id="ts2", node_type="topic_page"),
        WloCard(node_id="co1", node_type="collection"),
        WloCard(node_id="co2", node_type="collection"),
        WloCard(node_id="co3", node_type="collection"),
        WloCard(node_id="ma1", node_type="content"),
        WloCard(node_id="ma2", node_type="content"),
        WloCard(node_id="ma3", node_type="content"),
    ]
    resp, _ = _run2(
        monkeypatch, sp=_patch2(monkeypatch, dr=dr),
        cards=cards, pagination=PaginationInfo(total_count=99),
    )
    ids = [c.node_id for c in resp.cards]
    assert ids == ["ts1", "co1", "co2", "ma1", "ma2"]  # 1 ts + 2 coll + 2 mat, in order
    assert resp.pagination.total_count == 5            # reflects the trimmed count


def test_persist_single_content_box_disabled_drops_materials(monkeypatch):
    dr = {
        "groups": {}, "quick_replies": {"max_count": 4},
        "single_content_box": {"enabled": False},
    }
    cards = [
        WloCard(node_id="co1", node_type="collection"),
        WloCard(node_id="ma1", node_type="content"),
    ]
    resp, _ = _run2(monkeypatch, sp=_patch2(monkeypatch, dr=dr), cards=cards)
    assert [c.node_id for c in resp.cards] == ["co1"]  # materials removed


def test_persist_facet_narrowing_prepended(monkeypatch):
    resp, _ = _run2(
        monkeypatch, sp=_patch2(monkeypatch, narrow=["Nur Video (10)"]),
        quick_replies=["A"], _qr_mode="none",
    )
    assert resp.quick_replies[0] == "Nur Video (10)"
    assert "A" in resp.quick_replies


def test_persist_qr_max_count_trim(monkeypatch):
    dr = {
        "groups": {}, "quick_replies": {"max_count": 2},
        "single_content_box": {"enabled": True},
    }
    resp, _ = _run2(
        monkeypatch, sp=_patch2(monkeypatch, dr=dr),
        quick_replies=["A", "B", "C", "D"], _qr_mode="none",
    )
    assert resp.quick_replies == ["A", "B"]


def test_persist_qr_max_policy_override(monkeypatch):
    resp, _ = _run2(
        monkeypatch, quick_replies=["A", "B", "C", "D"], _qr_mode="none", _qr_max=1,
    )
    assert resp.quick_replies == ["A"]


def test_persist_inline_document_routing_m09(monkeypatch):
    docs = [{"kind": "lernpfad", "title": "LP", "content": "BODY"}]
    sp = _patch2(monkeypatch, inline=(docs, "INTRO-LEAD"))
    resp, _ = _run2(
        monkeypatch, sp=sp,
        winner_id="M09", _effective_pattern_id="M09",
        _final_text="x" * 250,
        _web_links=[{"title": "t", "url": "u"}],
        page_action={"action": "canvas_open"},
        _qr_mode="none",
    )
    assert len(resp.inline_documents) == 1
    assert resp.inline_documents[0].content == "BODY"   # dict → InlineDocument coercion
    assert resp.content == "INTRO-LEAD"
    assert resp.web_links == []                          # cleared on routing
    assert resp.page_action is None                      # canvas action dropped
    assert sp.inline_calls and sp.inline_calls[0][0] == "M09"


def test_persist_non_m16_no_topic_page_and_full_build(monkeypatch):
    # winner_id="M04" (default) → the M16 resolver runs but no-ops (returns None +
    # inputs unchanged), so topic_page stays None and the full ChatResponse builds.
    resp, _ = _run2(
        monkeypatch,
        _query_meta_entries=[QueryMetaEntry(search_term="q")],
        pattern_output={"format_follow_up": "buttons", "formality": "du"},
    )
    assert isinstance(resp, ChatResponse)
    assert resp.topic_page is None            # non-M16 → resolver no-op, no crash
    assert resp.session_id == "bb-1"
    assert resp.content == "Antwort-Text"
    assert resp.follow_up == "buttons"        # echoed from pattern_output
    assert resp.query_metas[0].search_term == "q"
    assert resp.display_rules                  # echoed dict, non-empty


def test_persist_m16_resolver_wired(monkeypatch):
    # M16-active: the resolver's return values (topic_page + emptied cards +
    # excerpt text) thread through into the ChatResponse. The resolver logic is
    # unit-tested in test_topic_pages.py; here we pin only the wiring seam.
    async def _fake_resolve(req, classification, winner_id, spec_query, cards, final_text):
        assert winner_id == "M16"                       # threaded from the caller
        return TopicPageView(variant_title="Klima"), [], "M16-INTRO"

    monkeypatch.setattr(tp_mod, "_resolve_m16_topic_page_view", _fake_resolve)
    resp, _ = _run2(
        monkeypatch, winner_id="M16",
        cards=[WloCard(node_id="normal", node_type="content")],
    )
    assert resp.topic_page is not None
    assert resp.topic_page.variant_title == "Klima"
    assert resp.cards == []                              # normal boxes suppressed
    assert resp.content == "M16-INTRO"                   # resolver text (no unresolved note)


def test_persist_unresolved_filter_note_appended(monkeypatch):
    sp = _patch2(monkeypatch)
    monkeypatch.setattr(
        "boerdi.domain.facets.unresolved_filter_note",
        lambda metas, max_shown=2: "Hinweis: allgemeiner gesucht.",
    )
    resp, _ = _run2(monkeypatch, sp=sp, _final_text="Basis.")
    assert resp.content.endswith("Hinweis: allgemeiner gesucht.")
    assert "Basis." in resp.content
