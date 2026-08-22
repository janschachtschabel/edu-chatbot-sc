"""Read paths over ``eval_runs`` and the pattern analytics over ``quality_logs``.

Split out of ``eval_service`` unchanged. Every function here reconstructs an ALT
response shape from NEU's JSONB layout (``config``/``totals``/``summary``/
``conversations``) — that mapping is the single reason this module changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import EvalRun


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def list_runs(session: AsyncSession, limit: int) -> dict[str, Any]:
    """Recent runs, newest first. ALT list shape reconstructed from JSONB."""
    rows = (
        await session.execute(
            select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    runs: list[dict[str, Any]] = []
    for r in rows:
        config = r.config or {}
        totals = r.totals or {}
        summary = r.summary or {}
        runs.append({
            "id": r.id,
            "created_at": _iso(r.created_at),
            "completed_at": _iso(r.completed_at),
            "status": r.status,
            "mode": r.mode,
            "config_slug": config.get("config_slug", ""),
            "total_turns": totals.get("total_turns", 0),
            "avg_score": totals.get("avg_score"),
            "personas": config.get("personas", []),
            "intents": config.get("intents", []),
            "error_message": r.error_message,
            "target_turns": summary.get("target_turns", 0),
            "current_activity": summary.get("current_activity", ""),
        })
    return {"runs": runs}


async def get_run(session: AsyncSession, run_id: str) -> dict[str, Any]:
    """Full run detail (ALT ``get_run``; heavy JSON expanded, raw blobs dropped)."""
    r = (
        await session.execute(select(EvalRun).where(EvalRun.id == run_id))
    ).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "run not found")
    config = r.config or {}
    totals = r.totals or {}
    return {
        "id": r.id,
        "created_at": _iso(r.created_at),
        "completed_at": _iso(r.completed_at),
        "status": r.status,
        "mode": r.mode,
        "config_slug": config.get("config_slug", ""),
        "personas": config.get("personas", []),
        "intents": config.get("intents", []),
        "turns_per_conv": config.get("turns_per_conv", 0),
        "judge_model": config.get("judge_model", ""),
        "simulator_model": config.get("simulator_model", ""),
        "total_turns": totals.get("total_turns", 0),
        "avg_score": totals.get("avg_score"),
        "error_message": r.error_message,
        "summary": r.summary or {},
        "conversations": r.conversations or [],
    }


async def get_trends(session: AsyncSession, limit: int) -> dict[str, Any]:
    """Cross-run trend series over the last ``limit`` completed runs (ALT port).

    Reads only summaries (``classification_metrics``); transcripts stay untouched.
    """
    rows = (
        await session.execute(
            select(EvalRun)
            .where(EvalRun.status == "done")
            .order_by(EvalRun.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    runs_meta: list[dict[str, Any]] = []
    pattern_trend: dict[str, list[dict[str, Any]]] = {}
    cache_hit_trend: list[dict[str, Any]] = []
    match_rate_trend: list[dict[str, Any]] = []
    persona_rate_trend: list[dict[str, Any]] = []
    intent_rate_trend: list[dict[str, Any]] = []

    # Oldest → newest so the timeline reads left-to-right (UI-friendly).
    for r in reversed(rows):
        summary = r.summary or {}
        cm = summary.get("classification_metrics") or {}
        config = r.config or {}
        totals = r.totals or {}
        run_id = r.id
        created_at = _iso(r.created_at)
        runs_meta.append({
            "id": run_id,
            "created_at": created_at,
            "completed_at": _iso(r.completed_at),
            "mode": r.mode,
            "config_slug": config.get("config_slug", ""),
            "total_turns": totals.get("total_turns", 0),
            "avg_score": totals.get("avg_score"),
        })

        per_pattern = cm.get("tool_compliance_per_pattern") or {}
        for pid, stats in per_pattern.items():
            if not isinstance(stats, dict):
                continue
            ok = int(stats.get("ok") or 0)
            total = int(stats.get("total") or 0)
            rate = round(ok / total, 3) if total else 0.0
            pattern_trend.setdefault(pid, []).append({
                "run_id": run_id, "created_at": created_at,
                "ok": ok, "total": total, "rate": rate,
            })

        tua = cm.get("token_usage_aggregate") or {}
        cache_hit_trend.append({
            "run_id": run_id, "created_at": created_at,
            "value": tua.get("cache_hit_rate", 0.0),
            "prompt_tokens": tua.get("prompt_tokens", 0),
            "cached_tokens": tua.get("cached_tokens", 0),
        })
        # GV6: None = in diesem Lauf strukturell unmessbar (kein Hint, z. B.
        # Agent-Engine) — der Punkt entfällt und die Serie zeigt eine Lücke
        # statt eines 0.0-„Absturzes". Alt gespeicherte 0.0-Läufe bleiben, wie
        # sie sind; rückwirkend ist die Unterscheidung nicht rekonstruierbar.
        match_value = cm.get("llm_engine_match_rate", 0.0)
        if match_value is not None:
            match_rate_trend.append({
                "run_id": run_id, "created_at": created_at,
                "value": match_value,
                "judged": cm.get("llm_hint_present_count", 0),
            })
        # Dieselbe Skip-Regel für Persona/Intent (Review-Befund 1, 2026-08-22):
        # Golden-v2-Läufe tragen kein Klassifikator-Soll und lieferten hier
        # 0.0-Punkte — nach drei Engine-Läufen sah die Persona-Serie aus wie
        # ein Klassifikator-Absturz.
        persona_value = cm.get("persona_correct_rate", 0.0)
        if persona_value is not None:
            persona_rate_trend.append({
                "run_id": run_id, "created_at": created_at,
                "value": persona_value,
                "total": cm.get("persona_total_judged", 0),
            })
        intent_value = cm.get("intent_correct_rate", 0.0)
        if intent_value is not None:
            intent_rate_trend.append({
                "run_id": run_id, "created_at": created_at,
                "value": intent_value,
                "total": cm.get("intent_total_judged", 0),
            })

    # Pad each pattern series with implicit zeros for runs it never appeared in,
    # then order by run timeline — keeps sparklines honest about coverage.
    run_ids_in_order = [m["id"] for m in runs_meta]
    for series in pattern_trend.values():
        present_runs = {entry["run_id"] for entry in series}
        for rid in run_ids_in_order:
            if rid not in present_runs:
                series.append({
                    "run_id": rid,
                    "created_at": next(
                        (m["created_at"] for m in runs_meta if m["id"] == rid), ""
                    ),
                    "ok": 0, "total": 0, "rate": 0.0,
                })
        order_index = {rid: i for i, rid in enumerate(run_ids_in_order)}
        series.sort(key=lambda e: order_index.get(e["run_id"], 0))

    return {
        "runs": runs_meta,
        "pattern_trend": pattern_trend,
        "cache_hit_trend": cache_hit_trend,
        "llm_engine_match_trend": match_rate_trend,
        "persona_correct_trend": persona_rate_trend,
        "intent_correct_trend": intent_rate_trend,
    }


async def pattern_usage_stats(
    session: AsyncSession, since: str | None, scope: str,
) -> dict[str, Any]:
    """Pattern × intent × persona counts from quality_logs, scoped (ALT port).

    NEU folds ALT's flat ``persona_id``/``final_confidence`` columns into the
    ``data`` jsonb, so those are read via ``data->>...`` (cast for the average).
    ``scope`` drives branch selection only (never interpolated); ``since`` is a
    bound param.
    """
    scope = (scope or "all").lower().strip()
    conds: list[str] = []
    params: dict[str, Any] = {}
    if since:
        # NEU created_at is timestamptz — bind a datetime (asyncpg rejects a bare
        # string here), so Postgres compares timestamp-to-timestamp. ALT compared
        # ISO strings lexicographically on a sqlite TEXT column.
        try:
            params["since"] = datetime.fromisoformat(since)
        except ValueError as e:
            raise HTTPException(400, f"invalid 'since' timestamp: {since!r}") from e
        conds.append("created_at >= :since")
    if scope == "eval":
        conds.append("session_id LIKE 'eval-%'")
    elif scope == "production":
        conds.append("session_id NOT LIKE 'eval-%'")
    where_sql = ("WHERE " + " AND ".join(conds)) if conds else ""

    triples = [
        dict(row._mapping)
        for row in await session.execute(
            text(
                "SELECT pattern_id, intent_id, data->>'persona_id' AS persona_id, "
                "COUNT(*) AS count, AVG((data->>'final_confidence')::float) AS avg_conf "
                f"FROM quality_logs {where_sql} "
                "GROUP BY pattern_id, intent_id, data->>'persona_id' "
                "ORDER BY count DESC"
            ),
            params,
        )
    ]
    # Review-Runde 3 (2026-08-22, Nutzer-Entscheid): die ALT-Aggregate
    # by_pattern/by_intent sind entfernt. Seit dem Betriebsart-Filter leitet
    # das Studio — der einzige Konsument — beide Verteilungen client-seitig
    # aus den Kombinationen ab; der Server rechnete zwei GROUP-BYs ins Leere.
    total = sum(r.get("count", 0) for r in triples)
    return {
        "triples": triples,
        "total": total,
        "scope": scope,
    }
