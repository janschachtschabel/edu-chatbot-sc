"""Persist node — P25-33 adapter (R4a Sub-Slice 3).

Thin graph node that runs the three verbatim turn-persist phases in order and maps
every argument off ``ctx``:

  1. ``build_debug_and_update_session`` (P25-26) — assemble ``DebugInfo`` + the turn's
     single ``update_session`` DB write.
  2. ``_finalize_links_and_metas`` (P27-28, ``services/turn_links`` #82) — post-answer
     card/text rewriters + web-link extraction + query-metas. Returns the 7-tuple
     ``(cards, response_text, _final_text, _web_links, _raw_metas, _query_meta_entries,
     _type_focus_label)`` that P29-33 consumes.
  3. ``persist_and_build_response`` (P29-33) — assistant-persist + quality-log + QR
     polish + inline-document routing + the final ``ChatResponse``.

The finished response lands on ``ctx.response`` (the endpoint returns
``early_response or response``). Runs only on the normal-answer path — early-exit
turns (preflight/tour/fast-path) set ``ctx.early_response`` and skip this node.

Two NEU seams, both established by sibling nodes:
* ``winner``: the two verbatim callees read only ``winner.id`` (assemble precedent) →
  a one-field ``SimpleNamespace`` shim carries ``ctx.winner_id``.
* the tracer: NEU dropped the ALT ``Tracer`` (Sub-Slice 1 → ``debug.trace=[]``), but the
  verbatim ``_finalize_links_and_metas`` still calls ``tracer.record`` → a no-op
  ``_NullTracer`` keeps the port unchanged while the trace entry is intentionally dropped.

The main safety-log (ALT ``chat_turn_setup``) is deliberately NOT here — it is a
turn_setup/merge concern (fires before any route fast-path early-exit) and is wired in
that area at R4e, not in this terminal node.

The three phase functions are top-level imports so tests patch them on this module.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from boerdi.graph.state import TurnContext
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.services.tool_loop import GELIEFERTE_DOKUMENTE_KEY
from boerdi.services.turn_links import _finalize_links_and_metas
from boerdi.services.turn_persist import (
    build_debug_and_update_session,
    persist_and_build_response,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _ProgressTracer:
    """Tracer-Attrappe für den verbatim portierten ``_finalize_links_and_metas``,
    der darin ``tracer.record("query_meta", …)`` ruft.

    Bis C9 war das ein No-op — der Aufruf lief ins Leere, und das Widget bekam sein
    ``query_meta``-Label nie. Jetzt leitet er auf die Fortschritts-Naht um, ohne den
    Port anzufassen. ``debug.trace`` bleibt weiterhin leer: Einträge zu sammeln ist
    Aufgabe des zurückgestellten Tracer-Subsystems, nicht des Fortschritts.
    """

    def __init__(self, progress: TurnProgress) -> None:
        self._progress = progress

    def record(self, step: str, label: str = "", data: dict[str, Any] | None = None,
               duration_ms: int = 0) -> None:
        self._progress.record(step, label, data)


async def persist(
    ctx: TurnContext, session: AsyncSession, progress: TurnProgress = NO_PROGRESS,
) -> TurnContext:
    """Turn-Persistenz P25-33: DebugInfo + update_session (P25-26) → Links/Metas-
    Finalisierung (P27-28) → Assistant-Persist + finale ``ChatResponse`` (P29-33).
    Schreibt die fertige Antwort nach ``ctx.response`` und gibt ``ctx`` zurück."""
    debug = await build_debug_and_update_session(
        session,
        req=ctx.req,
        session_state=ctx.session_state,
        classification=ctx.classification,
        safety=ctx.safety,
        policy=ctx.policy,
        context_snapshot=ctx.context_snapshot,
        usage_acc=ctx.usage,
        winner_id=ctx.winner_id,
        pattern_output=ctx.pattern_output,
        new_state=ctx.state_id,
        new_signals=ctx.signals,
        signal_history=ctx.signal_history,
        _trans_check=ctx.trans_check,
        _effective_pattern_id=ctx.effective_pattern_id,
        _effective_pattern_label=ctx.effective_pattern_label,
        tools_called=ctx.tools_called,
        eliminated=ctx.eliminated,
        scores=ctx.scores,
        # Terminal-Felder: respond stasht sie in debug (state.py) → hier auslesen,
        # build_debug baut die volle DebugInfo damit neu.
        response_outcomes=ctx.debug.outcomes,
        final_confidence=ctx.debug.confidence,
    )

    (
        cards,
        response_text,
        _final_text,
        _web_links,
        _raw_metas,
        _query_meta_entries,
        _type_focus_label,
    ) = await _finalize_links_and_metas(
        req=ctx.req,
        session_state=ctx.session_state,
        classification_dict=ctx.classification.model_dump(),
        # finalize liest nur ``winner.id`` (assemble-Präzedenz) → 1-Feld-Shim.
        winner=SimpleNamespace(id=ctx.winner_id),
        pattern_output=ctx.pattern_output,
        tracer=_ProgressTracer(progress),
        tools_called=ctx.tools_called,
        _effective_pattern_id=ctx.effective_pattern_id,
        cards=ctx.cards,
        response_text=ctx.response_text,
    )

    # Die gelieferten Ergebnis-Boxen haben zwei Zuflüsse und ab hier eine Naht:
    # die Schleifen-Maschinen tragen sie am ``ctx`` (``respond_agent``), der
    # Tool-Loop kennt kein ``ctx`` und legt sie nach seiner eigenen Konvention
    # im ``session_state`` ab. ``pop`` in jedem Fall — bliebe der Merker stehen,
    # zeigte der nächste Zug dieselbe Box noch einmal (wie ``_write_preview``).
    _aus_dem_musterweg = ctx.session_state.pop(GELIEFERTE_DOKUMENTE_KEY, [])
    ctx.response = await persist_and_build_response(
        session,
        req=ctx.req,
        env=ctx.env,
        session_state=ctx.session_state,
        classification=ctx.classification,
        winner_id=ctx.winner_id,
        pattern_output=ctx.pattern_output,
        spec_query=ctx.spec_query,
        new_state=ctx.state_id,
        debug=debug,
        response_text=response_text,
        cards=cards,
        quick_replies=ctx.quick_replies,
        page_action=ctx.page_action,
        pagination=ctx.pagination,
        _final_text=_final_text,
        _web_links=_web_links,
        _raw_metas=_raw_metas,
        _query_meta_entries=_query_meta_entries,
        _type_focus_label=_type_focus_label,
        _qr_mode=ctx.qr_mode,
        _qr_max=ctx.qr_max,
        _effective_pattern_id=ctx.effective_pattern_id,
        gelieferte_dokumente=ctx.gelieferte_dokumente or _aus_dem_musterweg,
    )
    # Das maschinenlesbare Ergebnis der Agent-Schleife (2026-08-14). NACH dem
    # Bau angehängt statt durch die Signatur gereicht: die trägt schon zwanzig
    # Parameter, und diese zwei gehen durch keine der Stufen darin hindurch —
    # sie werden gesetzt und weitergegeben. Nur wenn ein Schema galt: sonst
    # stünde in jeder Antwort ein leeres Feldpaar.
    if ctx.result is not None or ctx.result_stop_reason:
        ctx.response.result = ctx.result
        ctx.response.result_stop_reason = ctx.result_stop_reason
    return ctx
