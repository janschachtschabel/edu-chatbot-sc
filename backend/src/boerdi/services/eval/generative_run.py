"""The generative run: validation, the run row, and the background job.

Split out of ``eval_service`` unchanged. The execution itself lives in
``eval/runner.py``; this module owns only the persistence around it — the
running row, the throttled progress writes, and the terminal write including the
failure path, which keeps the partial conversations.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import EvalRun
from boerdi.obs.tasks import _spawn_background
from boerdi.services.eval import runner
from boerdi.services.eval.cost import _compute_target_turns, list_personas_and_intents
from boerdi.services.eval.run_store import (
    _chat_url,
    _ensure_chat_reachable,
    _ensure_no_running_run,
    _finalize_run,
)

logger = logging.getLogger(__name__)

# Every n-th progress write also stores the full transcript (ALT: 5). The
# summary is written every time; transcripts are the expensive part.
_PERSIST_CONV_EVERY = 5


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

    await _ensure_chat_reachable()
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
