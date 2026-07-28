"""Eval service (P7) — HTTP-facing logic + eval_runs persistence for api/eval.py.

The router stays thin; everything DB- or config-touching lives here (spec rule 4).

Two run families, both live:

* **Golden** (``start_golden_eval_run``) reuses the ported, framework-free golden
  runner ``evals/run_golden.py`` (deterministic per-turn checks + scorecard, no
  LLM judge) exactly as ``tests/test_golden_runner.py`` loads it — by file path,
  since ``evals`` is not an installed package. The background job fires the flows
  at ``EVAL_CHAT_URL`` and persists the scorecard.
* **Generative** (``start_generative_run``) drives the engine in
  ``services/eval/`` (scenario generator, user simulator, LLM judge, metrics).
  This service owns the persistence around it: the run row, the throttled
  progress writes while the job runs, and the terminal write — including the
  failure path, which keeps the partial conversations.

Both write ``summary.classification_metrics``, which is what ``GET /eval/trends``
reads for its five series.

Persistence maps ALT's flat ``eval_runs`` columns onto NEU's JSONB layout
(``config``/``totals``/``summary``/``conversations``); read endpoints reproduce
ALT's response shapes from that layout.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import EvalRun, QualityLog
from boerdi.obs.tasks import _spawn_background
from boerdi.services.config_loader import (
    load_gold_flows,
    load_intents,
    load_persona_definitions,
)
from boerdi.services.eval import golden, runner

logger = logging.getLogger(__name__)

# Where the golden runner talks to the real chatbot (ALT default kept verbatim;
# NEU dev-compose sets EVAL_CHAT_URL=http://localhost:8100/api/chat).
_CHAT_URL_DEFAULT = "http://localhost:8000/api/chat"
# Stale 'running' rows older than this are swept to 'failed' by the start-guard
# so a crashed run cannot block new ones forever (ALT: 2h).
_STALE_RUN_HOURS = 2
# Every n-th progress write also stores the full transcript (ALT: 5). The
# summary is written every time; transcripts are the expensive part.
_PERSIST_CONV_EVERY = 5

# evals/run_golden.py lives at the repo root, NOT under src/ — it is a
# framework-free CLI, not an installed package. Load it by path, mirroring
# tests/test_golden_runner.py. parents[4]: services→boerdi→src→backend→repo.
_RUNNER_PATH = Path(__file__).resolve().parents[4] / "evals" / "run_golden.py"
_runner_mod: Any = None


def _chat_url() -> str:
    return os.getenv("EVAL_CHAT_URL") or _CHAT_URL_DEFAULT


def _load_golden_runner() -> Any:
    """Import the ported golden runner from its file path (evals is not a package).

    Cached after first load. Reused verbatim — never edited (READ-ONLY runner)."""
    global _runner_mod
    if _runner_mod is None:
        spec = importlib.util.spec_from_file_location(
            "boerdi_eval_run_golden", _RUNNER_PATH
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load golden runner from {_RUNNER_PATH}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _runner_mod = mod
    return _runner_mod


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ── Config snapshot + cost estimate (pure, no DB) ───────────────────


def list_personas_and_intents() -> dict[str, Any]:
    """Current config snapshot for the UI (ALT ``list_personas_and_intents``)."""
    return {
        "personas": load_persona_definitions(),
        "intents": load_intents(),
    }


def estimate_cost(
    n_personas: int, n_intents: int, scenarios_per_combo: int,
    mode: str, turns_per_conv: int,
) -> dict[str, Any]:
    """Rough cost + token estimate (verbatim port of ALT ``eval_metrics.estimate_cost``).

    Best-effort; actuals vary with prompt length, chat verbosity, tool payloads.
    Returns exact call counts plus a min/expected/max USD band.
    """
    combos = n_personas * n_intents
    n_scenarios = combos * scenarios_per_combo if mode in ("scenarios", "both") else 0
    n_convs = combos if mode in ("conversations", "both") else 0
    conv_turns = n_convs * turns_per_conv

    sim_gen_calls = combos if n_scenarios > 0 else 0
    sim_turn_calls = conv_turns
    judge_calls = n_scenarios + conv_turns
    chat_calls = n_scenarios + conv_turns

    mini_per_call = 0.0007
    chat_per_call = 0.005

    expected = (
        (sim_gen_calls + sim_turn_calls + judge_calls) * mini_per_call
        + chat_calls * chat_per_call
    )
    return {
        "scenarios": n_scenarios,
        "conversations": n_convs,
        "total_turns": n_scenarios + conv_turns,
        "chat_calls": chat_calls,
        "judge_calls": judge_calls,
        "simulator_calls": sim_gen_calls + sim_turn_calls,
        "est_usd": round(expected, 3),
        "est_usd_min": round(expected * 0.6, 3),
        "est_usd_max": round(expected * 2.0, 3),
    }


def estimate(
    mode: str, persona_ids: list[str], intent_ids: list[str],
    scenarios_per_combo: int, turns_per_conv: int,
) -> dict[str, Any]:
    """Pre-flight estimate (ALT ``estimate`` endpoint body)."""
    cfg = list_personas_and_intents()
    n_p = len(persona_ids) or len(cfg["personas"])
    n_i = len(intent_ids) or len(cfg["intents"])
    return estimate_cost(
        n_personas=n_p, n_intents=n_i,
        scenarios_per_combo=scenarios_per_combo,
        mode=mode, turns_per_conv=turns_per_conv,
    )


def _compute_target_turns(
    mode: str, n_personas: int, n_intents: int,
    scenarios_per_combo: int, turns_per_conv: int,
) -> int:
    """Max judged turns the run will produce (verbatim ALT port)."""
    combos = n_personas * n_intents
    scen_turns = combos * scenarios_per_combo if mode in ("scenarios", "both") else 0
    conv_turns = combos * turns_per_conv if mode in ("conversations", "both") else 0
    return scen_turns + conv_turns


def list_gold_flows() -> dict[str, Any]:
    """Parsed Gold-Standard flow specs (ALT ``get_gold_flows`` endpoint)."""
    flows = load_gold_flows()
    return {"flows": flows, "count": len(flows)}


# ── eval_runs read paths (pg, ALT response shapes) ──────────────────


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
        match_rate_trend.append({
            "run_id": run_id, "created_at": created_at,
            "value": cm.get("llm_engine_match_rate", 0.0),
            "judged": cm.get("llm_hint_present_count", 0),
        })
        persona_rate_trend.append({
            "run_id": run_id, "created_at": created_at,
            "value": cm.get("persona_correct_rate", 0.0),
            "total": cm.get("persona_total_judged", 0),
        })
        intent_rate_trend.append({
            "run_id": run_id, "created_at": created_at,
            "value": cm.get("intent_correct_rate", 0.0),
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


# ── eval_runs delete paths (pg) ─────────────────────────────────────


async def delete_run(session: AsyncSession, run_id: str) -> dict[str, Any]:
    await session.execute(delete(EvalRun).where(EvalRun.id == run_id))
    await session.commit()
    return {"deleted": run_id}


async def delete_runs(
    session: AsyncSession, status_filter: str | None,
    mode_filter: str | None, confirm: bool,
) -> dict[str, Any]:
    """Bulk-delete, optionally restricted by status and/or mode (combinable).

    ``mode=golden`` → only golden runs; ``mode=generative`` → mode != golden;
    any other value matches exactly. A wholly unrestricted delete needs
    ``confirm=true`` (ALT safety)."""
    conds: list[Any] = []
    if status_filter:
        conds.append(EvalRun.status == status_filter)
    if mode_filter == "golden":
        conds.append(EvalRun.mode == "golden")
    elif mode_filter == "generative":
        conds.append(EvalRun.mode != "golden")
    elif mode_filter:
        conds.append(EvalRun.mode == mode_filter)

    if not conds and not confirm:
        raise HTTPException(
            400,
            "Bulk delete without any filter requires ?confirm=true to prevent accidents.",
        )
    count = (
        await session.execute(select(func.count()).select_from(EvalRun).where(*conds))
    ).scalar_one()
    await session.execute(delete(EvalRun).where(*conds))
    await session.commit()
    return {"deleted": count, "filter": {"status": status_filter, "mode": mode_filter}}


async def clear_eval_quality_logs(session: AsyncSession) -> dict[str, Any]:
    """Delete quality_logs rows written by eval runs (session_id LIKE 'eval-%').

    Production chat traffic is preserved."""
    count = (
        await session.execute(
            select(func.count()).select_from(QualityLog)
            .where(QualityLog.session_id.like("eval-%"))
        )
    ).scalar_one()
    await session.execute(
        delete(QualityLog).where(QualityLog.session_id.like("eval-%"))
    )
    await session.commit()
    return {"deleted_eval_log_rows": count}


# ── Pattern / intent usage analytics (reads quality_logs) ───────────


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
    by_pattern = [
        dict(row._mapping)
        for row in await session.execute(
            text(
                "SELECT pattern_id, COUNT(*) AS count "
                f"FROM quality_logs {where_sql} "
                "GROUP BY pattern_id ORDER BY count DESC"
            ),
            params,
        )
    ]
    by_intent = [
        dict(row._mapping)
        for row in await session.execute(
            text(
                "SELECT intent_id, COUNT(*) AS count "
                f"FROM quality_logs {where_sql} "
                "GROUP BY intent_id ORDER BY count DESC"
            ),
            params,
        )
    ]
    total = sum(r.get("count", 0) for r in triples)
    return {
        "triples": triples,
        "by_pattern": by_pattern,
        "by_intent": by_intent,
        "total": total,
        "scope": scope,
    }


# ── Run start-guard + finalisation (pg) ─────────────────────────────


async def _ensure_no_running_run(session: AsyncSession) -> None:
    """Parallel-guard (ALT B4): two concurrent runs would share the chat backend
    and eval_runs writes and corrupt each other. Stale 'running' rows (crash
    leftovers) older than ``_STALE_RUN_HOURS`` are swept to 'failed' first so they
    don't block forever."""
    cutoff = datetime.now(UTC) - timedelta(hours=_STALE_RUN_HOURS)
    await session.execute(
        text(
            "UPDATE eval_runs SET status='failed', "
            "error_message='stale running-Run beim Start-Check abgeräumt' "
            "WHERE status='running' AND created_at < :cutoff"
        ),
        {"cutoff": cutoff},
    )
    await session.commit()
    row = (
        await session.execute(
            select(EvalRun.id).where(EvalRun.status == "running").limit(1)
        )
    ).first()
    if row:
        raise HTTPException(
            409,
            f"Eval-Run {row[0]} läuft bereits — bitte abwarten oder löschen. "
            "Parallele Runs teilen sich Chat-Backend und DB und würden sich "
            "gegenseitig verfälschen.",
        )


async def _finalize_run(
    session: AsyncSession, run_id: str, *, status: str,
    total_turns: int | None = None, avg_score: float | None = None,
    summary: dict[str, Any] | None = None,
    conversations: list[Any] | None = None,
    error_message: str | None = None,
    current_activity: str | None = None,
) -> None:
    """Terminal write for a run row (status + completed_at + JSONB fields)."""
    r = (
        await session.execute(select(EvalRun).where(EvalRun.id == run_id))
    ).scalar_one_or_none()
    if r is None:
        logger.warning("[eval %s] run row vanished before finalize", run_id)
        return
    r.status = status
    r.completed_at = datetime.now(UTC)
    if error_message is not None:
        r.error_message = error_message
    totals = dict(r.totals or {})
    if total_turns is not None:
        totals["total_turns"] = total_turns
    if avg_score is not None:
        totals["avg_score"] = avg_score
    r.totals = totals
    if summary is not None:
        r.summary = summary
    elif current_activity is not None:
        s = dict(r.summary or {})
        s["current_activity"] = current_activity
        r.summary = s
    if conversations is not None:
        r.conversations = conversations
    await session.commit()


# ── Generative run (HTTP contract faithful; execution NOT ported) ───


async def start_generative_run(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession] | None,
    req: Any,
) -> dict[str, Any]:
    """Validate + persist a generative run and spawn its background job.

    Validation, the running-guard and the ``status: running`` response are
    ALT-faithful. Unknown persona/intent ids are dropped with a ``warnings``
    entry rather than rejected; an empty intersection is a 400 that names what
    IS available. Nothing is silently clamped — the numeric bounds are enforced
    by ``StartRequest`` (422), so the caller's numbers are the numbers that run.
    """
    cfg = list_personas_and_intents()
    all_personas = cfg["personas"]
    all_intents = cfg["intents"]
    known_persona_ids = {p["id"] for p in all_personas}
    known_intent_ids = {i["id"] for i in all_intents}

    personas = all_personas
    intents = all_intents
    warnings: list[str] = []

    if req.persona_ids:
        requested = set(req.persona_ids)
        unknown = sorted(requested - known_persona_ids)
        if unknown:
            warnings.append(f"Unknown persona IDs ignored: {unknown}")
        personas = [p for p in all_personas if p["id"] in requested]

    if req.intent_ids:
        requested = set(req.intent_ids)
        unknown = sorted(requested - known_intent_ids)
        if unknown:
            warnings.append(f"Unknown intent IDs ignored: {unknown}")
        intents = [i for i in all_intents if i["id"] in requested]

    if not personas or not intents:
        raise HTTPException(
            400,
            "no personas or intents matched the filter. "
            f"Available personas: {sorted(known_persona_ids)}. "
            f"Available intents: {sorted(known_intent_ids)}.",
        )

    await _ensure_no_running_run(session)
    run_id = f"eval-{uuid.uuid4().hex[:12]}"
    persona_ids = [p["id"] for p in personas]
    intent_ids = [i["id"] for i in intents]
    target_turns = _compute_target_turns(
        req.mode, len(personas), len(intents),
        req.scenarios_per_combo, req.turns_per_conv,
    )
    session.add(EvalRun(
        id=run_id, status="running", mode="generative",
        config={
            "config_slug": req.config_slug,
            "personas": persona_ids, "intents": intent_ids,
            "mode": req.mode, "scenarios_per_combo": req.scenarios_per_combo,
            "turns_per_conv": req.turns_per_conv,
            "judge_model": "", "simulator_model": "",
        },
        totals={"total_turns": 0, "avg_score": None},
        summary={
            "target_turns": target_turns, "current_activity": "Wartet …",
            "matrix": {}, "pattern_usage": {},
            "avg_score": 0.0, "total_judged_turns": 0,
        },
    ))
    await session.commit()
    # The resolved persona/intent dicts go to the job as-is: re-reading them by
    # id in the background would silently pick up a config edit made mid-run.
    _spawn_background(_execute_generative_run(
        session_factory, run_id,
        mode=req.mode, personas=personas, intents=intents,
        scenarios_per_combo=req.scenarios_per_combo,
        turns_per_conv=req.turns_per_conv, target_turns=target_turns,
    ))
    return {
        "run_id": run_id,
        "status": "running",
        "personas_used": persona_ids,
        "intents_used": intent_ids,
        "warnings": warnings,
    }


def _progress_writer(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: str,
    target_turns: int,
) -> Any:
    """Build the runner's progress callback: a throttled partial-state write.

    Called after every scenario/dialogue so the UI shows live status and a crash
    mid-run does not lose finished conversations. The summary is cheap to
    recompute and written every time; the full transcript is an order of
    magnitude larger, so it goes along every ``_PERSIST_CONV_EVERY``-th write.

    ALT kept that counter in a module-global dict keyed by run id (which also
    never got cleaned up). Here it is a closure variable — per run, garbage
    collected with the job, and safe under two runs in one process.
    """
    written = 0

    async def progress(conversations: list[dict], activity: str) -> None:
        nonlocal written
        written += 1
        summary = runner.build_summary(conversations, target_turns, activity)
        include_conversations = written % _PERSIST_CONV_EVERY == 0
        try:
            async with session_factory() as s:
                r = (
                    await s.execute(select(EvalRun).where(EvalRun.id == run_id))
                ).scalar_one_or_none()
                if r is None:
                    return
                r.totals = {
                    **(r.totals or {}),
                    "total_turns": summary["total_judged_turns"],
                    "avg_score": summary["avg_score"],
                }
                r.summary = summary
                if include_conversations:
                    r.conversations = list(conversations)
                await s.commit()
        except Exception:
            # A lost progress write must never kill the run it reports on.
            logger.warning("[eval %s] progress write failed", run_id, exc_info=True)

    return progress


async def _execute_generative_run(
    session_factory: async_sessionmaker[AsyncSession] | None,
    run_id: str,
    *,
    mode: str,
    personas: list[dict[str, Any]],
    intents: list[dict[str, Any]],
    scenarios_per_combo: int,
    turns_per_conv: int,
    target_turns: int,
) -> None:
    """Background job: run the generative eval and persist its result.

    On failure the partial conversations collected so far are still persisted
    together with the error — a run that died after 100 of 144 combos is worth
    reading, and losing it would hide where it broke.
    """
    if session_factory is None:
        logger.error("[eval %s] no session factory — cannot run", run_id)
        return
    conversations: list[dict[str, Any]] = []
    progress = _progress_writer(session_factory, run_id, target_turns)
    try:
        summary = await runner.execute_run(
            chat_url=_chat_url(), run_id=run_id, conversations=conversations,
            mode=mode, personas=personas, intents=intents,
            scenarios_per_combo=scenarios_per_combo,
            turns_per_conv=turns_per_conv, target_turns=target_turns,
            progress=progress,
        )
        async with session_factory() as s:
            await _finalize_run(
                s, run_id, status="done",
                total_turns=summary["total_judged_turns"],
                avg_score=summary["avg_score"],
                summary=summary, conversations=conversations,
            )
        logger.info(
            "[eval %s] done, avg=%.2f, %d/%d turns", run_id,
            summary["avg_score"], summary["total_judged_turns"], target_turns,
        )
    except Exception as e:
        logger.exception("[eval %s] failed", run_id)
        try:
            summary = runner.build_summary(
                conversations, target_turns, f"Fehler: {str(e)[:200]}",
            )
        except Exception:
            summary = {"target_turns": target_turns}
        try:
            async with session_factory() as s:
                await _finalize_run(
                    s, run_id, status="failed", error_message=str(e)[:500],
                    total_turns=summary.get("total_judged_turns", 0),
                    summary=summary, conversations=conversations,
                )
        except Exception:
            logger.exception("[eval %s] failed to persist failure", run_id)


# ── Golden run (LIVE — reuses the ported evals/run_golden.py) ────────


async def start_golden_eval_run(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession] | None,
    req: Any,
) -> dict[str, Any]:
    """Validate + persist a golden run and spawn its live background job."""
    all_flows = load_gold_flows()
    if not all_flows:
        raise HTTPException(
            400,
            "Keine Gold-Flows konfiguriert (eval/gold-flows.yaml fehlt oder leer).",
        )
    flows = all_flows
    warnings: list[str] = []
    if req.flow_ids:
        requested = set(req.flow_ids)
        known = {str(f.get("id")) for f in all_flows}
        unknown = sorted(requested - known)
        if unknown:
            warnings.append(f"Unbekannte Flow-IDs ignoriert: {unknown}")
        flows = [f for f in all_flows if str(f.get("id")) in requested]
    if not flows:
        raise HTTPException(
            400,
            "Keine Flows matchten den Filter. Verfügbar: "
            f"{sorted({str(f.get('id')) for f in all_flows})}",
        )

    await _ensure_no_running_run(session)
    run_id = f"eval-{uuid.uuid4().hex[:12]}"
    persona_ids = sorted({str(f.get("persona") or "*") for f in flows})
    intent_ids = sorted({
        iid for f in flows for iid in (f.get("intents") or []) if iid
    })
    turns_total = sum(len(f.get("turns") or []) for f in flows)
    flow_ids_used = [str(f.get("id")) for f in flows]

    session.add(EvalRun(
        id=run_id, status="running", mode="golden",
        config={
            "config_slug": req.config_slug,
            "personas": persona_ids, "intents": intent_ids,
            "flows": flow_ids_used, "judge": bool(req.judge),
            "turns_per_conv": 0, "judge_model": "", "simulator_model": "",
        },
        totals={"total_turns": 0, "avg_score": None},
        summary={
            "target_turns": turns_total, "current_activity": "Starte Gold-Flows …",
            "matrix": {}, "pattern_usage": {},
            "avg_score": 0.0, "total_judged_turns": 0,
        },
    ))
    await session.commit()
    _spawn_background(
        _execute_golden_run(session_factory, run_id, flows, bool(req.judge))
    )
    return {
        "run_id": run_id,
        "status": "running",
        "mode": "golden",
        "flows_used": flow_ids_used,
        "turns_total": turns_total,
        "judge": bool(req.judge),
        "warnings": warnings,
    }


async def _execute_golden_run(
    session_factory: async_sessionmaker[AsyncSession] | None,
    run_id: str, flows: list[dict[str, Any]], judge_enabled: bool,
) -> None:
    """Background job: fire the flows at EVAL_CHAT_URL via the ported runner,
    add the optional judge layer, persist to eval_runs.

    The hard scorecard comes from the framework-free runner; ``judge=True`` adds
    the soft axes on top via ``eval/golden.py`` (C3). The headline ``avg_score``
    stays the deterministic pass rate either way.
    """
    if session_factory is None:
        logger.error("[golden %s] no session factory — cannot run", run_id)
        return
    target_turns = sum(len(f.get("turns") or []) for f in flows)
    # Bound outside the try: by the time judging or aggregation can fail, the
    # flows have already cost a full round of real chat turns. Losing that
    # transcript to a judge outage would be the expensive kind of data loss.
    conversations: list[dict[str, Any]] = []
    try:
        runner = _load_golden_runner()
        conversations = await runner.run_flows(_chat_url(), flows)
        if judge_enabled:
            judged = await golden.judge_conversations(conversations)
            logger.info("[golden %s] judged %d turn(s)", run_id, judged)
        summary = golden.summarize_golden_run(
            conversations,
            target_turns=target_turns,
            golden_metrics=runner.aggregate_golden(conversations),
        )
        golden_metrics = summary["golden_metrics"]
        async with session_factory() as s:
            await _finalize_run(
                s, run_id, status="done",
                total_turns=golden_metrics["turns"],
                avg_score=golden_metrics["overall_pass_rate"],
                summary=summary, conversations=conversations,
            )
        logger.info(
            "[golden %s] done, pass=%.2f, %d flows / %d turns",
            run_id, golden_metrics["overall_pass_rate"],
            golden_metrics["flows"], golden_metrics["turns"],
        )
    except Exception as e:
        logger.exception("[golden %s] failed", run_id)
        try:
            async with session_factory() as s:
                await _finalize_run(
                    s, run_id, status="failed",
                    error_message=str(e)[:500],
                    current_activity=f"Fehler: {str(e)[:200]}",
                    conversations=conversations,
                )
        except Exception:
            logger.exception("[golden %s] failed to persist failure", run_id)
