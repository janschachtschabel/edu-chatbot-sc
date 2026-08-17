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


# ── Frame-Fortschreibung (B1–B3) ─────────────────────────────────
# Der offene Vorgang wird an derselben Stelle und aus derselben Quelle
# fortgeschrieben wie ``_last_pattern``: dem AUSGEFÜHRTEN Muster.

def test_klaerer_zaehlt_den_versuch_hoch(monkeypatch):
    ss = {"persona_id": "P-AND", "state_id": "S2", "turn_count": 1,
          "entities": {"material_typ": "arbeitsblatt"}}
    _, upd = _run(monkeypatch, session_state=ss, eff_id="M03")
    assert upd.kwargs["entities"]["_frame"]["attempts"] == 1


def test_zweiter_klaerer_ohne_fortschritt_zaehlt_weiter(monkeypatch):
    ss = {"persona_id": "P-AND", "state_id": "S2", "turn_count": 1,
          "entities": {"material_typ": "arbeitsblatt",
                       "_frame": {"slots": ["material_typ"], "attempts": 1}}}
    _, upd = _run(monkeypatch, session_state=ss, eff_id="M03")
    assert upd.kwargs["entities"]["_frame"]["attempts"] == 2


def test_jedes_andere_muster_schliesst_den_vorgang(monkeypatch):
    # Deckt zugleich den Themenwechsel ab: er landet bei einem anderen Muster,
    # also verfällt der Vorgang, ohne dass es dafür eine eigene Regel braucht.
    ss = {"persona_id": "P-AND", "state_id": "S2", "turn_count": 1,
          "entities": {"thema": "Photosynthese",
                       "_frame": {"slots": [], "attempts": 2}}}
    _, upd = _run(monkeypatch, session_state=ss, eff_id="M06")
    assert "_frame" not in upd.kwargs["entities"]


def test_offener_schreibvorgang_ueberlebt_den_zug(monkeypatch):
    # Der Test, der 2026-08-11 gefehlt hat. Die Naht im Tool-Loop legt den
    # offenen Bestaetigungsvorgang ab, DIESE Stelle schreibt ihn — und
    # dazwischen lag der Fehler: der Merkposten lag auf oberster Ebene von
    # ``session_state``, ``update_session`` schreibt aber nur die fuenf
    # Spalten. Er wurde nie gespeichert, ``setup`` baute den Zustand jeden Zug
    # neu, und damit war keine Bestaetigung je einloesbar.
    #
    # Gepinnt wird deshalb die VERBINDUNG, nicht eine der beiden Seiten:
    # gespeichert wird, was in ``entities`` steht.
    vorgang = {"tool": "wlo_create_collection", "fingerprint": "[]", "token": "geheim"}
    debug, upd = _run(monkeypatch, session_state={
        "persona_id": "P-AND", "state_id": "S2", "turn_count": 4,
        "entities": {"thema": "Bruch", "_pending_write": vorgang},
    })
    assert upd.kwargs["entities"]["_pending_write"] == vorgang
    assert "_pending_write" not in debug.entities, (
        "Der Schluessel darf nicht im Debug-Auszug landen — ``_``-Praefix haelt ihn heraus"
    )
    assert "geheim" not in str(debug.model_dump())


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
        auto_calls=[], inline_calls=[], facet_langs=[],
    )
    monkeypatch.setattr(tp_mod, "save_message", sp.save)
    monkeypatch.setattr(tp_mod, "_attach_guide_urls", sp.guide)

    def _fake_auto(*, state_id, quick_replies, has_cards, lang="de"):
        sp.auto_calls.append((state_id, list(quick_replies), has_cards, lang))
        return list(quick_replies) + ["Hat das geholfen?"]

    monkeypatch.setattr(tp_mod, "_apply_state_auto_followup", _fake_auto)

    def _fake_inline(pattern_id, markdown, display_rules, topic="",
                     extra_meta=None, formality="", lang="de"):
        sp.inline_calls.append((pattern_id, markdown, topic, formality, lang))
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
    def _fake_narrow(metas, max_options=3, lang="de"):
        sp.facet_langs.append(lang)
        return list(narrow) if narrow is not None else []

    def _fake_unresolved(metas, max_shown=2, lang="de"):
        sp.facet_langs.append(lang)
        return ""

    monkeypatch.setattr(
        "boerdi.domain.facets.narrowing_quick_replies_from_metas", _fake_narrow)
    monkeypatch.setattr(
        "boerdi.domain.facets.unresolved_filter_note", _fake_unresolved)
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


_VORSCHAU = (
    "Bitte prüfen — bisher wurde nichts geändert:\n"
    "Sammlung anlegen: „Bruchrechnung Klasse 6“\n"
    "Titel: (leer) → „Bruchrechnung Klasse 6“"
)


def test_persist_schreib_vorschau_wird_eine_box(monkeypatch):
    # S2: Der Server formuliert die Abnahme bereits vollständig und auf
    # Deutsch. Bisher endete sie in der Nachrichtenkette des Modells, und der
    # Nutzer las nur dessen Nacherzählung. Ab hier sieht er den Servertext —
    # unabhängig davon, was das Modell darüber sagt.
    resp, _ = _run2(
        monkeypatch,
        session_state={"turn_count": 4, "entities": {}, "_write_preview": _VORSCHAU},
        _final_text="Ich würde folgendes ändern:",
        _qr_mode="none",
    )
    assert len(resp.inline_documents) == 1
    doc = resp.inline_documents[0]
    assert doc.kind == "schreib_vorschau"
    assert "Titel: (leer) → „Bruchrechnung Klasse 6“" in doc.content
    assert doc.title
    assert resp.content == "Ich würde folgendes ändern:", (
        "Die Box BEGLEITET die Worte des Modells, sie ersetzt sie nicht"
    )


def test_persist_vorschau_fragt_und_bietet_beides_an(monkeypatch):
    # S3: „um Zustimmung ODER Anpassung fragen". Die Zustimmung bekommt einen
    # Knopf, weil sie die kuerzeste Antwort ist; die Anpassung bekommt einen
    # Satz, weil sie nur der Nutzer formulieren kann. Beides deterministisch —
    # eine Frage, die nur im Prompt steht, kann ausfallen.
    resp, _ = _run2(
        monkeypatch,
        session_state={"turn_count": 4, "entities": {}, "_write_preview": _VORSCHAU},
        _final_text="x", _qr_mode="none",
    )
    assert resp.quick_replies[0] == "Ja, so ausführen"
    inhalt = resp.inline_documents[0].content
    assert inhalt.rstrip().endswith(
        "Soll ich das so ausführen? Wenn etwas nicht stimmt, sag mir, was anders sein soll."
    )


def test_persist_vorschau_chip_beugt_sich_dem_deckel(monkeypatch):
    # ``max_count: 0`` heisst „keine Pillen" — eine Entscheidung der Redaktion
    # und kein Platzproblem. Auch die Zustimmung ist dann ein Satz, kein Knopf.
    dr = {"groups": {}, "quick_replies": {"max_count": 0},
          "single_content_box": {"enabled": True}}
    resp, _ = _run2(
        monkeypatch, sp=_patch2(monkeypatch, dr=dr),
        session_state={"turn_count": 4, "entities": {}, "_write_preview": _VORSCHAU},
        _final_text="x", _qr_mode="none",
    )
    assert resp.quick_replies == []
    assert resp.inline_documents, "Die Box bleibt — sie ist die Abnahme, nicht die Pille"


def test_persist_ohne_vorschau_keine_box(monkeypatch):
    resp, _ = _run2(monkeypatch, _final_text="nur Text", _qr_mode="none")
    assert resp.inline_documents == []


def test_persist_verbraucht_die_vorschau(monkeypatch):
    # Die Box gehört dem Zug, der sie erzeugt hat. Bliebe der Text stehen,
    # zeigte ihn jeder Folgezug erneut — auch einer, der von etwas ganz
    # anderem handelt.
    st = {"turn_count": 4, "entities": {}, "_write_preview": _VORSCHAU}
    _resp, _ = _run2(monkeypatch, session_state=st, _final_text="x", _qr_mode="none")
    assert "_write_preview" not in st


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
        lambda metas, max_shown=2, lang="de": "Hinweis: allgemeiner gesucht.",
    )
    resp, _ = _run2(monkeypatch, sp=sp, _final_text="Basis.")
    assert resp.content.endswith("Hinweis: allgemeiner gesucht.")
    assert "Basis." in resp.content


# ── C1-f2b4: Type-Focus-QR-Filter ist sprachabhaengig ────────────────
# Die Quick-Replies kommen (im ``llm``-Modus) vom Modell und sind seit
# C1-f2a in der Sprache des Nutzers. Der Filter wirft die QRs weg, die
# auf Sammlungen/Themenseiten zeigen, waehrend der Nutzer sich gerade
# WEG davon bewegt hat — mit den deutschen Mustern allein griff er auf
# Englisch nie, und der Widerspruch blieb stehen.


def _qr_filtered(monkeypatch, qrs, *, locale=None):
    env = Environment(locale=locale) if locale else Environment()
    resp, _ = _run2(
        monkeypatch,
        req=ChatRequest(session_id="bb-1", message="nur videos", environment=env),
        quick_replies=list(qrs), _qr_mode="none", _type_focus_label="Video",
    )
    return resp.quick_replies


def test_persist_type_focus_qr_filter_german(monkeypatch):
    assert _qr_filtered(
        monkeypatch, ["Mehr Sammlungen", "Passende Themenseiten", "Anderes Thema"],
    ) == ["Anderes Thema"]


def test_persist_type_focus_qr_filter_english(monkeypatch):
    assert _qr_filtered(
        monkeypatch, ["More collections", "Topic pages", "Another subject"],
        locale="en-GB",
    ) == ["Another subject"]


def test_persist_reicht_die_sprache_an_die_inline_box_durch(monkeypatch):
    """C1-f2b5: dieselbe Verdrahtungs-Probe wie bei den Direkt-Aktionen.

    ``persist_and_build_response`` ist die zweite und wichtigere Aufrufstelle
    von ``_build_inline_document`` — sie baut die Box im Haupt-Weg (M09/M10/M11).
    """
    sp = _patch2(monkeypatch)
    _run2(
        monkeypatch, sp=sp,
        req=ChatRequest(session_id="bb-1", message="mach mir was",
                        environment=Environment(locale="en-GB")),
        winner_id="M10", _effective_pattern_id="M10",
        _final_text="# Worksheet\n" + "word " * 60,   # >= 200 Zeichen, sonst kein Box-Zweig
    )
    assert sp.inline_calls and sp.inline_calls[-1][4] == "en"


# ── C1-f2b6a: Hinweise und Chips am Rand einer normalen Antwort ────────

def test_persist_auto_followup_bekommt_die_sprache(monkeypatch):
    sp = _patch2(monkeypatch)
    _run2(
        monkeypatch, sp=sp,
        req=ChatRequest(session_id="bb-1", message="was",
                        environment=Environment(locale="en-GB")),
        new_state="S3",
    )
    assert sp.auto_calls and sp.auto_calls[0][3] == "en"


def test_persist_reicht_die_sprache_an_beide_facetten_helfer(monkeypatch):
    """Beide Helfer aus ``domain.facets`` bekommen die Widget-Sprache.

    Was sie dann ausgeben, ist in ``tests/test_facets.py`` gepinnt — hier zaehlt
    nur, dass die Sprache ueberhaupt ankommt.
    """
    sp = _patch2(monkeypatch, narrow=["chip"])
    _run2(
        monkeypatch, sp=sp,
        req=ChatRequest(session_id="bb-1", message="was",
                        environment=Environment(locale="en-GB")),
    )
    assert sp.facet_langs == ["en", "en"]


def test_persist_type_focus_qr_filter_off_without_label(monkeypatch):
    resp, _ = _run2(
        monkeypatch, quick_replies=["Mehr Sammlungen"], _qr_mode="none",
        _type_focus_label="",
    )
    assert resp.quick_replies == ["Mehr Sammlungen"]   # kein Typ-Fokus → kein Filter


# ── E3: die vorbereitete Anfrage in der Antwort ──────────────────────────
# Der MCP-Server hat die bestätigte Änderung beschrieben statt sie zu schreiben;
# ausgeführt wird sie in der Repository-Seite. Die Antwort muss sie also tragen
# — sonst endet der ganze Weg still im Backend.


def test_die_vorbereitete_anfrage_faehrt_in_der_antwort_mit(monkeypatch):
    from boerdi.domain.prepared_write import PreparedWrite

    vorbereitet = PreparedWrite(
        method="PUT",
        path="/edu-sharing/rest/collection/v1/collections/-home-/c1/references/n1",
        body=None,
        done_message="„Arbeitsblatt“ ist jetzt in „Bruchrechnung“.",
    )
    sp = _patch2(monkeypatch)
    monkeypatch.setattr(tp_mod, "get_prepared_writes", lambda: [vorbereitet])
    resp, _ = _run2(monkeypatch, sp=sp)

    assert resp.prepared_write is not None
    assert resp.prepared_write.method == "PUT"
    assert resp.prepared_write.path.endswith("/references/n1")
    assert "Bruchrechnung" in resp.prepared_write.done_message


def test_ohne_vorbereitung_bleibt_das_feld_leer(monkeypatch):
    sp = _patch2(monkeypatch)
    monkeypatch.setattr(tp_mod, "get_prepared_writes", list)
    resp, _ = _run2(monkeypatch, sp=sp)
    assert resp.prepared_write is None


def test_bei_zwei_vorbereitungen_liefert_die_antwort_keine(monkeypatch):
    # Zwei sind ein gebrochener Zusicherungszustand (der Wall lässt je Zug einen
    # Schlüssel einlösen). Dann keine — welche der beiden zugestimmt wurde, ist
    # nicht feststellbar.
    from boerdi.domain.prepared_write import PreparedWrite

    zwei = [
        PreparedWrite(method="PUT", path="/edu-sharing/rest/a", body=None, done_message="a"),
        PreparedWrite(method="DELETE", path="/edu-sharing/rest/b", body=None, done_message="b"),
    ]
    sp = _patch2(monkeypatch)
    monkeypatch.setattr(tp_mod, "get_prepared_writes", lambda: zwei)
    resp, _ = _run2(monkeypatch, sp=sp)
    assert resp.prepared_write is None


# ── Gelieferte Box schlägt geratene Box (D4/D5) ────────────────────────────

_GELIEFERT = {"kind": "stundenplanung", "title": "Verlaufsplan Optik",
              "content": "Kurz, ohne Raute.", "meta": {"source": "tool"}}


def test_ein_geliefertes_dokument_wird_zur_box(monkeypatch):
    """DIE Zusage dieses Umbaus: die Box entsteht, obwohl **keine** der vier
    Bedingungen des geratenen Weges erfüllt ist — Muster M04 statt M09/M10/M11,
    Text weit unter 200 Zeichen, kein H1 im Markdown.

    Live gemessen 2026-08-17: genau daran fiel ein 8.000 Zeichen langer
    Verlaufsplan weg."""
    resp, _sp = _run2(monkeypatch,
                      winner_id="M04", _effective_pattern_id="M04",
                      _final_text="kurz",
                      gelieferte_dokumente=[dict(_GELIEFERT)])
    assert len(resp.inline_documents) == 1
    assert resp.inline_documents[0].title == "Verlaufsplan Optik"
    assert resp.inline_documents[0].content == "Kurz, ohne Raute."


def test_ohne_lieferung_bleibt_der_geratene_weg(monkeypatch):
    """Die Rückbau-Sicherheit: ruft das Modell das Werkzeug nicht, ändert sich
    am heutigen Verhalten nichts."""
    resp, _sp = _run2(monkeypatch, winner_id="M04", _effective_pattern_id="M04",
                      _final_text="kurz")
    assert resp.inline_documents == []


def test_die_lieferung_schlaegt_die_vermutung(monkeypatch):
    """Beide Wege könnten greifen (M09 + langer Text mit H1) — dann gilt das,
    was das Modell ausdrücklich geliefert hat, nicht was der Text vermuten lässt."""
    langer_text = "# Geratener Titel\n\n" + ("Fließtext. " * 60)
    resp, _sp = _run2(monkeypatch,
                      winner_id="M09", _effective_pattern_id="M09",
                      _final_text=langer_text,
                      gelieferte_dokumente=[dict(_GELIEFERT)])
    assert len(resp.inline_documents) == 1
    assert resp.inline_documents[0].title == "Verlaufsplan Optik"
    # Und der Fließtext bleibt UNANGETASTET. Ihn zu kürzen hieße zu raten,
    # welcher Teil die Box wiederholt — genau das, was dieser Umbau abschafft.
    # Die Anweisung sitzt am Werkzeug („deine Prosa daneben ist nur der
    # Begleitsatz"); hält das Modell sich nicht daran, ist das im Text sichtbar
    # statt in einer stillen Regex.
    assert resp.content == langer_text


def test_der_globale_schalter_gilt_auch_fuer_gelieferte_boxen(monkeypatch):
    """``inline_documents.enabled: false`` ist die Ansage einer Anlage, KEINE
    Boxen zu zeigen. Sie galt bisher nur für den geratenen Weg — eine
    gelieferte Box lief daran vorbei."""
    sp = _patch2(monkeypatch)
    monkeypatch.setattr(tp_mod, "load_display_rules_config",
                        lambda: {"inline_documents": {"enabled": False}})
    resp, _ = _run2(monkeypatch, sp=sp, winner_id="M04",
                    _effective_pattern_id="M04",
                    _final_text="Der Begleitsatz.",
                    gelieferte_dokumente=[dict(_GELIEFERT)])
    assert resp.inline_documents == []
    # Der Inhalt darf dabei NICHT verschwinden: das Modell hat ihn nicht in die
    # Prosa geschrieben, weil das Werkzeug ihm genau das untersagt.
    assert resp.content.startswith("Der Begleitsatz.")
    assert "Kurz, ohne Raute." in resp.content
