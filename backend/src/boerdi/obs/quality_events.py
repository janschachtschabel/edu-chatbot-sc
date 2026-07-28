"""Safety- and quality-log writers (Postgres, SQLAlchemy-async).

pg-**REWRITE** of the writer half of ALT ``app/services/db_logs.py`` (284 Z.).
Same call signatures; the storage layer is rewritten for the NEU schema, which
collapses ALT's flat columns into a single ``data`` jsonb per row plus a few
promoted columns for the hot filter/index paths:

* ``safety_logs`` — promoted ``session_id``/``ip``/``risk_level``; everything
  else (stages_run, reasons, legal_flags, flagged_categories, blocked_tools,
  enforced_pattern, escalated, rate_limited, message, categories) → ``data``.
* ``quality_logs`` — promoted ``session_id``/``pattern_id``/``intent_id``; every
  other ALT metric + the full debug blob → ``data``.

**These writers are dumb** — the enabled/privacy GATE is a caller concern, and
must stay there because one writer serves several sites with different gating:
  * rate-limit safety event (ALT ``chat_pipeline_phases`` preflight) — ungated.
  * direct-action high-risk safety event (same file) — ungated.
  * main safety event (ALT ``chat_turn_setup``) — gated by
    ``safety-config.logging.{enabled, log_all_turns}`` + ``risk_level != low``.
  * quality event (ALT ``chat_turn_persist``) — gated by
    ``quality-log-config.logging.enabled`` AND ``privacy-config.logging.quality``.
Those gates are wired at the callers in R2 (preflight) and R4 (turn_setup +
persist). ``privacy-config.logging.safety`` is forced True by the loader (audit
trail), so safety writes are never privacy-suppressed.

Deviation from ALT worth naming: the safety writer reads ``decision`` fields via
``_field`` so a decision passed as a **dict** (ALT's direct-action path handed
``model_dump()`` to a ``getattr``-only writer and silently logged defaults) now
serialises correctly, alongside the object and ``None`` cases.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import QualityLog, SafetyLog


def _field(decision: Any, name: str, default: Any) -> Any:
    """Read one field from a safety ``decision`` that may be an object, a dict
    (ALT direct-action path), or ``None`` (rate-limit path)."""
    if decision is None:
        return default
    if isinstance(decision, dict):
        return decision.get(name, default)
    return getattr(decision, name, default)


async def log_safety_event(
    session: AsyncSession,
    session_id: str,
    message: str,
    decision: Any,
    ip: str = "",
    rate_limited: bool = False,
) -> None:
    """Persist one safety-decision row. ``risk_level`` is promoted; the rest of
    ALT's columns live in ``data``. Message is truncated to 500 chars."""
    session.add(
        SafetyLog(
            session_id=session_id,
            ip=ip,
            risk_level=_field(decision, "risk_level", "low"),
            data={
                "stages_run": _field(decision, "stages_run", []),
                "reasons": _field(decision, "reasons", []),
                "legal_flags": _field(decision, "legal_flags", []),
                "flagged_categories": _field(decision, "flagged_categories", []),
                "blocked_tools": _field(decision, "blocked_tools", []),
                "enforced_pattern": _field(decision, "enforced_pattern", ""),
                "escalated": bool(_field(decision, "escalated", False)),
                "rate_limited": bool(rate_limited),
                "message": (message or "")[:500],
                "categories": _field(decision, "categories", {}),
            },
        )
    )
    await session.commit()


async def log_quality_event(
    session: AsyncSession,
    session_id: str,
    message: str,
    turn_count: int,
    debug_info: dict,
    response_length: int = 0,
    cards_count: int = 0,
    page: str = "",
    device: str = "",
) -> None:
    """Persist one quality/analytics row for offline analysis.

    ``pattern_id`` (the code, e.g. ``M04``) and ``intent_id`` (ALT's full
    ``"I01 (Suche)"`` string) are promoted columns; the extracted metrics and the
    full ``debug_info`` blob are folded into ``data`` for deep-dive querying.
    """
    p3 = debug_info.get("phase3_modulations", {})
    scores = debug_info.get("phase2_scores", {})

    winner_score = 0.0
    runner_up_id = ""
    score_gap = 0.0
    if scores:
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        winner_score = sorted_scores[0][1] if sorted_scores else 0.0
        if len(sorted_scores) >= 2:
            runner_up_id = sorted_scores[1][0]
            score_gap = round(sorted_scores[0][1] - sorted_scores[1][1], 4)

    # ALT extracts the code from "M04 (Fakten-Bulletin)" but keeps the full
    # string as the label.
    pattern_str = debug_info.get("pattern", "")
    pattern_id = pattern_str.split(" ")[0] if pattern_str else ""
    pattern_label = pattern_str

    outcomes = debug_info.get("outcomes", [])
    outcome_dicts = [
        o if isinstance(o, dict) else (o.model_dump() if hasattr(o, "model_dump") else {})
        for o in outcomes
    ]

    eliminated = debug_info.get("phase1_eliminated", [])
    candidates_count = len(scores)

    session.add(
        QualityLog(
            session_id=session_id,
            pattern_id=pattern_id,
            intent_id=debug_info.get("intent", ""),
            data={
                "turn_count": turn_count,
                "persona_id": debug_info.get("persona", ""),
                # intent_confidence ≈ final after adjustments (ALT stored both)
                "intent_confidence": debug_info.get("confidence", 0.0),
                "final_confidence": debug_info.get("confidence", 0.0),
                "turn_type": debug_info.get("turn_type", ""),
                "state_id": debug_info.get("state", ""),
                "signals": debug_info.get("signals", []),
                "entities": debug_info.get("entities", {}),
                "pattern_label": pattern_label,
                "phase2_winner_score": winner_score,
                "phase2_runner_up": runner_up_id,
                "phase2_score_gap": score_gap,
                "eliminated_count": len(eliminated),
                "candidate_count": candidates_count,
                "response_length": response_length,
                "cards_count": cards_count,
                "tools_called": debug_info.get("tools_called", []),
                "tool_outcomes": outcome_dicts,
                "length_setting": p3.get("length", ""),
                "degradation": bool(p3.get("degradation")),
                "missing_slots": p3.get("missing_slots", []),
                "page": page,
                "device": device,
                "message": (message or "")[:500],
                "debug": debug_info,
            },
        )
    )
    await session.commit()
