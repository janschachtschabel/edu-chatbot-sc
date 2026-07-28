"""graph.nodes.respond — Standard-Antwortpfad P16-19 (R4c).

Port of ALT ``chat_turn_answer._produce_answer``: speculative-prefetch consume
(block-cascade / search_wlo_all envelope-split / extras), M16-skip pre-fill, the
CE-gate + set_request_hints + speculative-QR + generate_response call with
error-degrade & card-salvage, then the policy-disclaimer / medium-risk /
outcome-confidence text post-processing.

Only the boundaries are patched — the pure branch logic runs for real. Top-level
boundaries (patched on THIS module): ``generate_response`` / ``generate_quick_replies``
/ ``parse_wlo_cards`` / ``_qr_default_count`` / ``_spec_qr_response_block``.
Function-local boundaries (patched at their source module): ``rerank_gate_envelope``
/ ``set_request_hints`` / ``adjust_confidence`` / ``derive_state_hint``.

Two NEU deviations over ALT are pinned here: (1) ``rerank_gate_envelope`` is called
DIRECTLY (sync) instead of through the dropped ``run_in_rerank_pool`` — the gate
still mutates the payload before ``generate_response`` sees it; (2)
``resolve_discipline_labels`` is dropped entirely (No-op stub in NEU) — the
salvage path completes without it and the symbol is not imported on the module.
"""

from __future__ import annotations

import asyncio
import json

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    Environment,
    PolicyDecision,
    SafetyDecision,
)
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import respond as respond_mod
from boerdi.graph.nodes.respond import respond
from boerdi.obs.progress import TurnProgress

_SESSION = object()


class _Rec:
    def __init__(self) -> None:
        self.gen_called = False
        self.gen_kwargs: dict | None = None
        self.qr_called = False
        self.hints: dict | None = None
        self.gate_calls: list = []


async def _mktask(val):
    return val


def _install(
    monkeypatch,
    rec,
    *,
    gen_result=("ANSWER", [{"title": "A"}], ["search_wlo_content"], []),
    gen_raises=None,
    parse_cards=None,
    gate=None,
    adjust=1.0,
    hint="",
):
    async def _fake_gen(session, **kw):
        rec.gen_called = True
        rec.gen_kwargs = kw
        if gen_raises is not None:
            raise gen_raises
        return gen_result

    monkeypatch.setattr(respond_mod, "generate_response", _fake_gen)

    async def _fake_qr(**kw):
        rec.qr_called = True
        return ["QR1", "QR2"]

    monkeypatch.setattr(respond_mod, "generate_quick_replies", _fake_qr)
    monkeypatch.setattr(
        respond_mod, "parse_wlo_cards",
        lambda t: list(parse_cards) if parse_cards is not None else [{"title": "salv"}],
    )
    monkeypatch.setattr(respond_mod, "_qr_default_count", lambda: 3)
    monkeypatch.setattr(respond_mod, "_spec_qr_response_block", lambda *a, **k: "")

    def _fake_gate(query, rt, *, tool_name="", allow_soft_fallback=True):
        rec.gate_calls.append((tool_name, rt))
        return (gate(rt) if gate else rt, None)

    monkeypatch.setattr(
        "boerdi.services.card_reranker.rerank_gate_envelope", _fake_gate
    )

    def _fake_hints(h):
        rec.hints = h

    monkeypatch.setattr(
        "boerdi.services.mcp.arg_resolvers.set_request_hints", _fake_hints
    )
    monkeypatch.setattr(
        "boerdi.services.outcome_service.adjust_confidence", lambda b, o: adjust
    )
    monkeypatch.setattr(
        "boerdi.services.outcome_service.derive_state_hint", lambda o: hint
    )


def _ctx(
    *,
    winner_id="M03",
    pattern_output=None,
    spec_task=None,
    spec_tool_name="search_wlo_content",
    spec_is_search_all=False,
    search_all_extras=None,
    extra_spec_tasks=None,
    lp_routed=False,
    canvas_routed=False,
    qr_mode=None,
    qr_max=None,
    safety=None,
    policy=None,
    cls_entities=None,
    fp_response_text=None,
    fp_wlo_cards_raw=None,
    message="Photosynthese",
    state_id="S3",
) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(
        req=ChatRequest(session_id="bb-1", message=message, environment=Environment())
    )
    ctx.history = []
    ctx.session_state = {"entities": {"fach": "Biologie"}, "persona_id": "P-AND"}
    ctx.env = {"page": "/", "device": "desktop"}
    ctx.usage = {}
    ctx.safety = safety if safety is not None else SafetyDecision()
    ctx.classification = ClassificationResult(
        intent_id="I03",
        intent_confidence=0.8,
        entities=dict(cls_entities) if cls_entities is not None else {"fach": "Biologie"},
    )
    ctx.policy = policy if policy is not None else PolicyDecision()
    ctx.winner_id = winner_id
    ctx.winner_label = "M03-Label"
    ctx.pattern_output = (
        pattern_output
        if pattern_output is not None
        else {"sources": ["mcp"], "tools": ["search_wlo_content"]}
    )
    ctx.rag_config = {}
    ctx.available_rag_areas = []
    ctx.memory_context = ""
    ctx.spec_task = spec_task
    ctx.spec_tool_name = spec_tool_name
    ctx.spec_tool_args = {"query": "Photosynthese"}
    ctx.spec_query = "Photosynthese"
    ctx.extra_spec_tasks = extra_spec_tasks or []
    ctx.spec_is_search_all = spec_is_search_all
    ctx.search_all_extras = search_all_extras or []
    ctx.qr_mode = qr_mode
    ctx.qr_max = qr_max
    ctx.qr_spec_task = None
    ctx.lp_routed = lp_routed
    ctx.canvas_routed = canvas_routed
    ctx.effective_pattern_id = winner_id
    ctx.tools_called = []
    ctx.state_id = state_id
    ctx.fp_response_text = fp_response_text
    ctx.fp_wlo_cards_raw = fp_wlo_cards_raw
    return ctx


def _run(ctx, *, drain=False):
    async def _go():
        out = await respond(ctx, _SESSION)
        if drain and out.qr_spec_task is not None:
            try:
                await out.qr_spec_task
            except Exception:
                pass
        return out
    return asyncio.run(_go())


# ── standard path ────────────────────────────────────────────────

def test_standard_path_calls_generate_and_stores_outputs(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec, gen_result=("ANSWER", [{"title": "A"}], ["search_wlo_content"], []))
    out = _run(_ctx())
    assert rec.gen_called is True
    assert out.response_text == "ANSWER"
    assert out.wlo_cards_raw == [{"title": "A"}]
    assert out.tools_called == ["search_wlo_content"]


def test_standard_path_sets_request_hints_dropping_underscore_keys(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    _run(_ctx(cls_entities={"fach": "Biologie", "_page": "x"}))
    # underscore-prefixed page metadata is stripped before hinting the MCP client
    assert rec.hints == {"fach": "Biologie"}


def test_confidence_and_state_hint_applied(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec, adjust=0.42, hint="S5")
    out = _run(_ctx(state_id="S3"))
    assert out.debug.confidence == 0.42
    assert out.state_id == "S5"  # derive_state_hint overrides new_state when it differs


# ── M16 skip + fast-path passthrough ─────────────────────────────

def test_m16_skips_generate_response(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    out = _run(_ctx(winner_id="M16"))
    assert rec.gen_called is False
    assert out.response_text == ""
    assert out.wlo_cards_raw == []
    assert out.tools_called == ["search_wlo_collections", "get_topic_page_content"]


def test_fast_path_passthrough_skips_generate(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    out = _run(_ctx(lp_routed=True, fp_response_text="LP answer",
                    fp_wlo_cards_raw=[{"title": "lp"}]))
    assert rec.gen_called is False
    assert out.response_text == "LP answer"
    assert out.wlo_cards_raw == [{"title": "lp"}]


# ── speculative-prefetch consume ─────────────────────────────────

def test_spec_blocked_discards_prefetch(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)

    async def _go():
        task = asyncio.create_task(_mktask("SPECTEXT"))
        ctx = _ctx(spec_task=task,
                   safety=SafetyDecision(blocked_tools=["search_wlo_content"]))
        return await respond(ctx, _SESSION)

    out = asyncio.run(_go())
    # blocked → prefetched_tool never populated
    assert out is not None
    assert rec.gen_kwargs["prefetched_tool"] is None


def test_spec_result_passed_to_generate_response(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)

    async def _go():
        task = asyncio.create_task(_mktask("SPECTEXT"))
        return await respond(_ctx(spec_task=task), _SESSION)

    asyncio.run(_go())
    assert rec.gen_kwargs["prefetched_tool"]["name"] == "search_wlo_content"
    assert rec.gen_kwargs["prefetched_tool"]["result_text"] == "SPECTEXT"


def test_search_all_envelope_split(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    envelope = json.dumps({
        "content": {"results": [{"title": "c1"}]},
        "collections": {"results": [{"title": "col1"}]},
        "topicPages": {"results": [{"title": "tp1"}]},
    })

    async def _go():
        task = asyncio.create_task(_mktask(envelope))
        return await respond(_ctx(spec_task=task, spec_is_search_all=True), _SESSION)

    asyncio.run(_go())
    assert rec.gen_kwargs["prefetched_tool"]["name"] == "search_wlo_content"
    names = [p["name"] for p in rec.gen_kwargs["prefetched_extras"]]
    assert names == ["search_wlo_collections", "search_wlo_topic_pages"]


# ── CE-gate: direct sync call (run_in_rerank_pool dropped, V13) ───

def test_ce_gate_called_directly_and_mutates_payload(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec, gate=lambda rt: rt + "::GATED")

    async def _go():
        task = asyncio.create_task(_mktask("RAW"))
        return await respond(_ctx(spec_task=task), _SESSION)

    asyncio.run(_go())
    # rerank_gate_envelope ran (sync, no pool) and gated the payload pre-LLM
    assert rec.gate_calls == [("search_wlo_content", "RAW")]
    assert rec.gen_kwargs["prefetched_tool"]["result_text"] == "RAW::GATED"


# ── error degrade + salvage (resolve_discipline_labels dropped) ───

def test_generate_error_degrades_and_salvages_cards(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec, gen_raises=RuntimeError("boom"),
             parse_cards=[{"title": "salv"}])

    async def _go():
        task = asyncio.create_task(_mktask("SPECTEXT"))
        return await respond(_ctx(spec_task=task), _SESSION)

    out = asyncio.run(_go())
    assert out.response_text.startswith("Ich konnte gerade keine Antwort erzeugen")
    assert out.tools_called == ["error"]
    assert out.wlo_cards_raw == [{"title": "salv"}]


def test_resolve_discipline_labels_not_imported(monkeypatch):
    # ALT imported resolve_discipline_labels at module level and awaited it in the
    # salvage path; NEU drops it (No-op stub). Guard the deviation.
    assert not hasattr(respond_mod, "resolve_discipline_labels")


# ── text post-processing ─────────────────────────────────────────

def test_policy_disclaimers_appended(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    out = _run(_ctx(policy=PolicyDecision(required_disclaimers=["Disc A"])))
    assert "_Disc A_" in out.response_text


def test_medium_risk_note_appended(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    out = _run(_ctx(safety=SafetyDecision(risk_level="medium", legal_flags=["strafrecht"])))
    assert "strafrechtlich relevante" in out.response_text


# ── speculative QR start ─────────────────────────────────────────

def test_speculative_qr_started(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)

    async def _go():
        task = asyncio.create_task(_mktask("SPECTEXT"))
        ctx = _ctx(spec_task=task, qr_mode="speculative")
        out = await respond(ctx, _SESSION)
        if out.qr_spec_task is not None:
            await out.qr_spec_task
        return out

    out = asyncio.run(_go())
    assert out.qr_spec_task is not None
    assert rec.qr_called is True


def test_returns_same_ctx(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    ctx = _ctx()
    out = _run(ctx)
    assert out is ctx


# ── C9: Fortschritts-Meldung ────────────────────────────────────────

def test_reports_wlo_search_then_response_when_a_prefetch_runs(monkeypatch):
    """Die zwei langen Abschnitte im Antwort-Pfad (ALT ``chat_turn_answer``:114
    und :418). ``wlo_search`` steht, solange die spekulative Suche awaitet,
    ``response`` sobald das Antwort-LLM startet."""
    rec = _Rec()
    _install(monkeypatch, rec)
    seen: list[dict] = []

    async def _go():
        task = asyncio.create_task(_mktask("SPECTEXT"))
        return await respond(_ctx(spec_task=task), _SESSION,
                             progress=TurnProgress(seen.append))

    asyncio.run(_go())
    assert [e["step"] for e in seen] == ["wlo_search", "response"]


def test_no_wlo_search_report_without_a_prefetch(monkeypatch):
    """Ohne spekulative Suche gibt es nichts zu durchsuchen — ein Label
    "Durchsuche WLO-Inhalte" wäre dann gelogen (ALT-Guard verbatim)."""
    rec = _Rec()
    _install(monkeypatch, rec)
    seen: list[dict] = []
    _run(_ctx())  # kein spec_task
    asyncio.run(respond(_ctx(), _SESSION, progress=TurnProgress(seen.append)))
    assert [e["step"] for e in seen] == ["response"]


def test_m16_reports_nothing_because_it_skips_generate(monkeypatch):
    """M16 überspringt ``generate_response`` — dann darf auch kein
    "Formuliere Antwort" behauptet werden."""
    rec = _Rec()
    _install(monkeypatch, rec)
    seen: list[dict] = []
    asyncio.run(respond(_ctx(winner_id="M16"), _SESSION,
                        progress=TurnProgress(seen.append)))
    assert seen == []
