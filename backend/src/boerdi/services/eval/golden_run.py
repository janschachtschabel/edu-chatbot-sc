"""The golden run: validation, the run row, and the background job.

Split out of ``eval_service`` unchanged. The deterministic half is executed by
the framework-free ``evals/run_golden.py`` (loaded by path, never edited); the
optional soft layer comes from ``eval/golden.py``. This module owns only the
persistence around both.
"""

from __future__ import annotations

import importlib.util
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import EvalRun
from boerdi.obs.tasks import _spawn_background
from boerdi.services.config_loader import load_gold_flows
from boerdi.services.eval import golden
from boerdi.services.eval.run_store import (
    _chat_url,
    _ensure_no_running_run,
    _finalize_run,
)

logger = logging.getLogger(__name__)

# evals/run_golden.py lives at the repo root, NOT under src/ — it is a
# framework-free CLI, not an installed package. Load it by path, mirroring
# tests/test_golden_runner.py. parents[5]: eval→services→boerdi→src→backend→repo.
_RUNNER_PATH = Path(__file__).resolve().parents[5] / "evals" / "run_golden.py"
_runner_mod: Any = None


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
