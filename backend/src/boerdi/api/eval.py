"""Eval endpoints — generative + golden (studio). Implemented in P7.

The runner core is ported standalone under ``evals/run_golden.py`` (loaded by the
service). Studio auth is applied at the router level (do not re-add per route).

Two run families are deliberately unequal in NEU:

* **Golden** (POST /runs/golden) is LIVE — it reuses the ported golden runner and
  persists the deterministic scorecard.
* **Generative** (POST /runs) keeps ALT's HTTP contract (validation, running-guard,
  ``status: running`` response, run row) but its background job marks the run
  *failed*: ALT's scenario/simulator/judge/metrics engine
  (``eval_scenario_gen``/``eval_judge``/``eval_metrics``) is NOT yet ported to NEU.
  This is honest — no fake success. Porting that engine is the remaining live work.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Security
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session, require_studio_key
from boerdi.services.eval_service import (
    clear_eval_quality_logs,
    delete_run,
    delete_runs,
    estimate,
    get_run,
    get_trends,
    list_gold_flows,
    list_personas_and_intents,
    list_runs,
    pattern_usage_stats,
    start_generative_run,
    start_golden_eval_run,
)

router = APIRouter(
    prefix="/api/eval", tags=["eval"],
    dependencies=[Security(require_studio_key)],
)

_Session = Annotated[AsyncSession, Depends(get_session)]


def _factory(request: Request) -> Any:
    """The lifespan's session factory for background jobs (absent in offline
    tests, where the service is faked anyway)."""
    return getattr(request.app.state, "session_factory", None)


# ── Config snapshot ─────────────────────────────────────────────────


@router.get("/config")
async def eval_config() -> dict:
    """Current personas + intents from the active chatbot config."""
    return list_personas_and_intents()


# ── Cost estimate (pre-flight) ──────────────────────────────────────


class EstimateRequest(BaseModel):
    mode: str = Field("both", pattern="^(scenarios|conversations|both)$")
    persona_ids: list[str] = Field(default_factory=list)
    intent_ids: list[str] = Field(default_factory=list)
    scenarios_per_combo: int = Field(2, ge=1, le=10)
    turns_per_conv: int = Field(3, ge=1, le=10)


@router.post("/estimate")
async def eval_estimate(req: EstimateRequest) -> dict:
    return estimate(
        req.mode, req.persona_ids, req.intent_ids,
        req.scenarios_per_combo, req.turns_per_conv,
    )


# ── Start / list / detail ───────────────────────────────────────────


class StartRequest(BaseModel):
    mode: str = Field("both", pattern="^(scenarios|conversations|both)$")
    persona_ids: list[str] = Field(default_factory=list, description="empty = all")
    intent_ids: list[str] = Field(default_factory=list, description="empty = all")
    scenarios_per_combo: int = Field(2, ge=1, le=10)
    turns_per_conv: int = Field(3, ge=1, le=10)
    config_slug: str = ""


@router.get("/runs")
async def list_eval_runs(
    session: _Session,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    return await list_runs(session, limit)


@router.post("/runs")
async def start_eval_run(
    req: StartRequest, request: Request, session: _Session,
) -> dict:
    return await start_generative_run(session, _factory(request), req)


@router.delete("/runs")
async def delete_eval_runs(
    session: _Session,
    status_filter: str | None = Query(
        None, alias="status",
        description="Optional: 'done', 'failed', or 'running' to restrict deletion",
    ),
    mode_filter: str | None = Query(
        None, alias="mode",
        description=(
            "Optional: 'golden' | 'generative' (= mode != golden) | exact mode value"
        ),
    ),
    confirm: bool = Query(False, description="Must be true for unrestricted bulk delete"),
) -> dict:
    return await delete_runs(session, status_filter, mode_filter, confirm)


# ── Golden-Flow Eval (deterministic, checked multi-turn flows) ──────


class GoldenRunRequest(BaseModel):
    flow_ids: list[str] = Field(default_factory=list, description="empty = all flows")
    judge: bool = Field(True, description="run the LLM judge for soft quality dims")
    config_slug: str = ""


@router.get("/gold-flows")
async def get_gold_flows() -> dict:
    """Parsed Gold-Standard flow specs (eval/gold-flows.yaml)."""
    return list_gold_flows()


@router.post("/runs/golden")
async def start_golden_run(
    req: GoldenRunRequest, request: Request, session: _Session,
) -> dict:
    """Start a deterministic Gold-Flow run in the background (reproducible)."""
    return await start_golden_eval_run(session, _factory(request), req)


@router.get("/trends")
async def eval_trends(
    session: _Session,
    limit: int = Query(
        10, ge=2, le=100,
        description="Number of most-recent completed runs to compare",
    ),
) -> dict:
    return await get_trends(session, limit)


@router.get("/runs/{run_id}")
async def get_eval_run(run_id: str, session: _Session) -> dict:
    return await get_run(session, run_id)


@router.delete("/runs/{run_id}")
async def delete_eval_run(run_id: str, session: _Session) -> dict:
    return await delete_run(session, run_id)


# ── quality-logs cleanup + analytics (read quality_logs) ────────────


@router.delete("/quality-logs")
async def delete_eval_quality_logs(session: _Session) -> dict:
    """Delete quality_logs rows written by eval runs (session_id LIKE 'eval-%')."""
    return await clear_eval_quality_logs(session)


@router.get("/analytics/pattern-usage")
async def pattern_usage(
    session: _Session,
    since: str | None = Query(None, description="ISO timestamp floor"),
    scope: str = Query(
        "all",
        description="'all' | 'eval' (session_id LIKE eval-%) | 'production' (not eval-)",
    ),
) -> dict:
    """Pattern × intent × persona counts from quality_logs, scoped."""
    return await pattern_usage_stats(session, since, scope)
