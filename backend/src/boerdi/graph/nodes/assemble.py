"""Assemble node — P20-24 adapter (R4g).

Thin adapter that wraps the verbatim ``turn_assembly._assemble_cards_and_qrs``
(P20-24: card enrichment + ``_build_cards`` + pagination + the QR cascade +
guide-marker strip + ``page_action``) as a graph node. It reads the raw cards and
routing decision off ``ctx`` — respond produced ``wlo_cards_raw`` + ``response_text``,
route produced the pattern/QR/canvas fields — calls the service, and writes the
finished ``(cards, quick_replies, page_action, pagination, response_text)`` back.

Two NEU seams: the service takes a ``winner`` object but reads only ``winner.id``
(the discovery-pattern check), while route stores ``winner_id``/``winner_label`` as
plain strings on ``ctx`` — so a one-field ``SimpleNamespace`` shim carries the id.
``classification_dict`` is ``classification.model_dump()`` (ALT parity). No
session/DB is reached here (the QR LLM call needs none), so the node takes no
injected deps. The service is a top-level import so tests patch it on this module.
"""

from __future__ import annotations

from types import SimpleNamespace

from boerdi.graph.state import TurnContext
from boerdi.services.turn_assembly import _assemble_cards_and_qrs


async def assemble(ctx: TurnContext) -> TurnContext:
    """Karten + Quick-Replies + ``page_action`` bauen (P20-24). Mutiert ``ctx``
    in-place und gibt ihn zurück."""
    cards, quick_replies, page_action, pagination, response_text = (
        await _assemble_cards_and_qrs(
            req=ctx.req,
            env=ctx.env,
            session_state=ctx.session_state,
            usage_acc=ctx.usage,
            classification=ctx.classification,
            classification_dict=ctx.classification.model_dump(),
            # turn_assembly liest nur ``winner.id`` (Discovery-Pattern-Check);
            # route hält id/label als Strings → 1-Feld-Shim.
            winner=SimpleNamespace(id=ctx.winner_id),
            pattern_output=ctx.pattern_output,
            _canvas_payload_out=ctx.canvas_payload,
            _canvas_forced_quick_replies=ctx.canvas_forced_quick_replies,
            _qr_mode=ctx.qr_mode,
            _qr_max=ctx.qr_max,
            _qr_spec_task=ctx.qr_spec_task,
            _effective_pattern_id=ctx.effective_pattern_id,
            response_text=ctx.response_text,
            wlo_cards_raw=ctx.wlo_cards_raw,
        )
    )
    ctx.cards = cards
    ctx.quick_replies = quick_replies
    ctx.page_action = page_action
    ctx.pagination = pagination
    ctx.response_text = response_text
    return ctx
