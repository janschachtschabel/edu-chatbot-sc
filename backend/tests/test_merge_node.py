"""graph.nodes.merge — P5-9 entity-side merge (R4d).

Port of the entity half of ALT ``chat_turn_setup._classify_and_merge`` that neither
``assess`` nor ``route`` covers: placeholder-topic filter, turn_type entity-merge
(topic_switch carry-over v3 / correction / default), material_typ + type-focus
heuristics, I05 slot enrichment, and the speculative-prefetch launch. Runs
``assess → MERGE → route`` — ``route.select_pattern`` reads the MERGED entities.

The pure merge logic runs for real; only the four boundaries (the prefetch launch,
the two material-type helpers, the placeholder-config load) are patched on the
module. The prefetch launch returns a canned ``SpeculativePrefetch``.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, ClassificationResult, Environment, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import merge as merge_mod
from boerdi.graph.nodes.merge import merge
from boerdi.services.prefetch import SpeculativePrefetch

_EMPTY_SP = SpeculativePrefetch(None, None, None, "", [], False, [])


def _patch(monkeypatch, sp=None, mt=None, wanted=None, placeholders=None):
    # ``engine`` (H5) gehört zur echten Signatur — dieselbe A4b-Regel wie
    # überall: eine Attrappe wird nach der ECHTEN Signatur gebaut, nicht nach
    # dem eigenen Aufruf.
    async def _fake_prefetch(req, classification, safety, *, engine="pattern"):
        return sp if sp is not None else _EMPTY_SP

    monkeypatch.setattr(merge_mod, "run_speculative_prefetch", _fake_prefetch)
    monkeypatch.setattr(merge_mod, "extract_material_type_from_message", lambda m: mt)
    monkeypatch.setattr(
        merge_mod, "_resolve_wanted_content_types", lambda *a, **k: set(wanted or [])
    )
    monkeypatch.setattr(
        merge_mod, "load_placeholder_topics_config",
        lambda: {"topics": set(placeholders or {"thema", "etwas", "material"}), "min_length": 3},
    )


def _ctx(turn_type="initial", cls_entities=None, ss_entities=None,
         intent_id="I03", message="was ist X?") -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(
        req=ChatRequest(session_id="bb-1", message=message, environment=Environment())
    )
    ctx.classification = ClassificationResult(
        turn_type=turn_type,
        entities=dict(cls_entities or {}),
        intent_id=intent_id,
        persona_id="P-AND",
        next_state="S1",
    )
    ctx.safety = SafetyDecision()
    ctx.session_state = {
        "entities": dict(ss_entities) if ss_entities is not None else {},
        "persona_id": "", "state_id": "S1", "signal_history": [], "turn_count": 0,
    }
    return ctx


def _run(ctx):
    return asyncio.run(merge(ctx))


# ── placeholder-topic filter ─────────────────────────────────────

def test_placeholder_thema_filtered_to_empty(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(cls_entities={"thema": "etwas"})
    out = _run(ctx)
    # "etwas" is a placeholder → thema blanked, so it never seeds a search
    assert out.classification.entities["thema"] == ""


def test_real_thema_kept_and_merged(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(cls_entities={"thema": "Photosynthese"})
    out = _run(ctx)
    assert out.classification.entities["thema"] == "Photosynthese"
    assert out.session_state["entities"]["thema"] == "Photosynthese"


def test_stale_session_placeholder_removed(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(cls_entities={}, ss_entities={"thema": "thema"})
    out = _run(ctx)
    assert out.session_state["entities"]["thema"] == ""


# ── turn_type entity merge ───────────────────────────────────────

def test_initial_merges_new_slots(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(turn_type="initial", cls_entities={"thema": "Goethe", "fach": "Deutsch"})
    out = _run(ctx)
    assert out.session_state["entities"]["thema"] == "Goethe"
    assert out.session_state["entities"]["fach"] == "Deutsch"


def test_correction_merges_values(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(turn_type="correction", ss_entities={"stufe": "3"},
               cls_entities={"stufe": "5"})
    out = _run(ctx)
    assert out.session_state["entities"]["stufe"] == "5"


def test_topic_switch_drops_carry_over(monkeypatch):
    # Classifier echoes the SAME thema on a topic_switch → carry-over, discard.
    _patch(monkeypatch)
    ctx = _ctx(turn_type="topic_switch", ss_entities={"thema": "Bruchrechnung"},
               cls_entities={"thema": "Bruchrechnung"})
    out = _run(ctx)
    assert "thema" not in out.session_state["entities"]


def test_topic_switch_accepts_new_value(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(turn_type="topic_switch", ss_entities={"thema": "Bruchrechnung"},
               cls_entities={"thema": "Goethe Faust"})
    out = _run(ctx)
    assert out.session_state["entities"]["thema"] == "Goethe Faust"


def test_topic_switch_preserves_underscore_markers(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx(turn_type="topic_switch",
               ss_entities={"_canvas_id": "abc", "thema": "Bruchrechnung"},
               cls_entities={})
    out = _run(ctx)
    assert out.session_state["entities"]["_canvas_id"] == "abc"
    assert "thema" not in out.session_state["entities"]


# ── heuristics ───────────────────────────────────────────────────

def test_material_typ_heuristic_injected(monkeypatch):
    _patch(monkeypatch, mt="arbeitsblatt")
    ctx = _ctx(cls_entities={})
    out = _run(ctx)
    assert out.classification.entities["material_typ"] == "arbeitsblatt"
    assert out.session_state["entities"]["material_typ"] == "arbeitsblatt"


def test_medientyp_type_focus_injected(monkeypatch):
    _patch(monkeypatch, mt=None, wanted=["video"])
    ctx = _ctx(cls_entities={})
    out = _run(ctx)
    assert out.classification.entities["medientyp"] == "video"
    assert out.session_state["entities"]["medientyp"] == "video"


# ── I05 slot enrichment ──────────────────────────────────────────

def test_i05_lifts_sticky_material_typ_into_classification(monkeypatch):
    _patch(monkeypatch, mt=None)  # no fresh type this turn
    ctx = _ctx(intent_id="I05", cls_entities={}, ss_entities={"material_typ": "quiz"})
    out = _run(ctx)
    # I05 lifts the sticky session material_typ into classification.entities
    assert out.classification.entities["material_typ"] == "quiz"


# ── speculative prefetch launch ──────────────────────────────────

def test_spec_prefetch_fields_set_on_ctx(monkeypatch):
    _task = object()
    _extra = [("search_wlo_topic_pages", object())]
    sp = SpeculativePrefetch(
        _task, "search_wlo_content", {"query": "x"}, "x", _extra, True, [{"a": 1}],
    )
    _patch(monkeypatch, sp=sp)
    out = _run(_ctx())
    assert out.spec_task is _task
    assert out.spec_tool_name == "search_wlo_content"
    assert out.spec_tool_args == {"query": "x"}
    assert out.spec_query == "x"
    assert out.extra_spec_tasks == _extra
    assert out.spec_is_search_all is True
    assert out.search_all_extras == [{"a": 1}]


def test_returns_same_ctx(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx()
    out = _run(ctx)
    assert out is ctx
