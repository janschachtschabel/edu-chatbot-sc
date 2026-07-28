"""graph.nodes.assemble — P20-24 adapter (R4g).

The node is a thin adapter over the verbatim ``turn_assembly._assemble_cards_and_qrs``
(#71, separately tested). These tests pin the adapter's contract: the correct ctx
fields flow into the service as the right arguments (incl. the ``winner`` shim and
``classification_dict``), and the returned 5-tuple lands on the right ctx fields.

The spy tests use ``**kwargs`` capture — which would silently swallow a mistyped
keyword name — so ``test_real_turn_assembly_runs`` calls the REAL service (only the
config/network seam ``get_repo_base_url`` patched) to prove the keyword names match
the service signature and the ``SimpleNamespace(id=...)`` shim satisfies it at runtime.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    Environment,
    PaginationInfo,
    WloCard,
)
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assemble as assemble_mod
from boerdi.graph.nodes.assemble import assemble


class _Rec:
    def __init__(self) -> None:
        self.kwargs: dict | None = None


def _install_spy(monkeypatch, rec, result):
    async def _fake(**kwargs):
        rec.kwargs = kwargs
        return result

    monkeypatch.setattr(assemble_mod, "_assemble_cards_and_qrs", _fake)


def _ctx(*, winner_id="M03", qr_mode="quick_replies", qr_max=None,
         wlo_cards_raw=None) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(
        req=ChatRequest(session_id="bb-1", message="Photosynthese", environment=Environment())
    )
    ctx.env = {"page": "/suche", "device": "desktop"}
    ctx.session_state = {"entities": {"thema": "Photosynthese"}, "persona_id": "P-AND"}
    ctx.usage = {"tokens": 5}
    ctx.classification = ClassificationResult(
        persona_id="P-AND", intent_id="I03", entities={"thema": "Photosynthese"}
    )
    ctx.winner_id = winner_id
    ctx.winner_label = "Winner-Label"
    ctx.pattern_output = {"format_follow_up": "quick_replies", "max_items": 5}
    ctx.canvas_payload = None
    ctx.canvas_forced_quick_replies = []
    ctx.qr_mode = qr_mode
    ctx.qr_max = qr_max
    ctx.qr_spec_task = None
    ctx.effective_pattern_id = winner_id
    ctx.response_text = "ANSWER"
    ctx.wlo_cards_raw = (
        wlo_cards_raw if wlo_cards_raw is not None
        else [{"node_id": "n1", "title": "T", "node_type": "collection"}]
    )
    return ctx


def _run(ctx):
    return asyncio.run(assemble(ctx))


_EMPTY_RESULT = ([], [], None, None, "ANSWER")


# ── arg-mapping contract ─────────────────────────────────────────

def test_maps_ctx_fields_to_service(monkeypatch):
    rec = _Rec()
    _install_spy(monkeypatch, rec, _EMPTY_RESULT)
    ctx = _ctx(qr_mode="quick_replies", qr_max=3)
    _run(ctx)
    kw = rec.kwargs
    assert kw["req"] is ctx.req
    assert kw["env"] is ctx.env
    assert kw["session_state"] is ctx.session_state
    assert kw["usage_acc"] is ctx.usage
    assert kw["classification"] is ctx.classification
    assert kw["pattern_output"] is ctx.pattern_output
    assert kw["_canvas_payload_out"] is ctx.canvas_payload
    assert kw["_canvas_forced_quick_replies"] is ctx.canvas_forced_quick_replies
    assert kw["_qr_mode"] == "quick_replies"
    assert kw["_qr_max"] == 3
    assert kw["_qr_spec_task"] is ctx.qr_spec_task
    assert kw["_effective_pattern_id"] == ctx.effective_pattern_id
    assert kw["response_text"] == "ANSWER"
    assert kw["wlo_cards_raw"] is ctx.wlo_cards_raw


def test_winner_shim_carries_winner_id(monkeypatch):
    rec = _Rec()
    _install_spy(monkeypatch, rec, _EMPTY_RESULT)
    _run(_ctx(winner_id="M09"))
    # route holds winner id/label as plain strings; turn_assembly reads winner.id
    assert rec.kwargs["winner"].id == "M09"


def test_classification_dict_is_model_dump(monkeypatch):
    rec = _Rec()
    _install_spy(monkeypatch, rec, _EMPTY_RESULT)
    ctx = _ctx()
    _run(ctx)
    assert rec.kwargs["classification_dict"] == ctx.classification.model_dump()


# ── writeback ────────────────────────────────────────────────────

def test_writes_five_tuple_to_ctx(monkeypatch):
    rec = _Rec()
    _cards = [WloCard(node_id="n1", title="T")]
    _pag = PaginationInfo(total_count=7, skip_count=0, page_size=5, has_more=False)
    _pa = {"action": "show_results"}
    _install_spy(monkeypatch, rec, (_cards, ["QR1", "QR2"], _pa, _pag, "STRIPPED"))
    out = _run(_ctx())
    assert out.cards == _cards
    assert out.quick_replies == ["QR1", "QR2"]
    assert out.page_action == _pa
    assert out.pagination is _pag
    assert out.response_text == "STRIPPED"  # guide-marker-strip rebind


def test_returns_same_ctx(monkeypatch):
    rec = _Rec()
    _install_spy(monkeypatch, rec, _EMPTY_RESULT)
    ctx = _ctx()
    assert _run(ctx) is ctx


# ── real service (validates keyword signature + shim at runtime) ──

def test_real_turn_assembly_runs(monkeypatch):
    # Only the config/network seam is patched; the rest of turn_assembly runs for
    # real — proving the keyword names match its signature and the SimpleNamespace
    # shim is accepted. A CONTENT card (not collection) avoids the deterministic
    # all-collection fallback QR, so qr_mode="none" yields no quick-replies; cards
    # present means winner.id is read at runtime (discovery-pattern check).
    monkeypatch.setattr(
        "boerdi.services.turn_assembly.get_repo_base_url", lambda: "http://test"
    )
    ctx = _ctx(
        qr_mode="none",
        wlo_cards_raw=[{"node_id": "n1", "title": "T", "node_type": "content"}],
    )
    out = _run(ctx)
    assert out is ctx
    assert isinstance(out.cards, list)
    assert out.quick_replies == []  # qr_mode="none", content card → no fallback QR
    assert out.response_text == "ANSWER"
