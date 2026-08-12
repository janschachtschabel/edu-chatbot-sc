"""Loadtest endpoints (studio, gated by ``allow_loadtest``). Implemented in P7
with improvement V9 (runs persisted in ``loadtest_runs`` instead of memory).
Caps (spec §5.7): MAX_STAGES=6, MAX_CONCURRENCY=32, MAX_REQUESTS_PER_STAGE=60,
MAX_TOTAL=200, one run at a time.

A run fires the REAL /api/chat pipeline (LLM + MCP) in-process — real cost and
staging load — so the profile is hard-capped in ``services/loadtest`` and only a
single run may be in flight. The heavy lifting lives in the service; this router
stays HTTP-only. Studio-key auth is applied at the router level (do not re-add).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import Lang, get_session, require_studio_key
from boerdi.i18n import Locale, msg
from boerdi.obs.tasks import _spawn_background
from boerdi.services.loadtest import (
    MIX_TEMPLATES,
    any_run_running,
    create_run,
    delete_run,
    execute_load_test,
    list_runs,
    load_run,
    validate_profile,
)
from boerdi.settings import get_settings

router = APIRouter(
    prefix="/api/loadtest", tags=["loadtest"],
    dependencies=[Security(require_studio_key)],
)

_Session = Annotated[AsyncSession, Depends(get_session)]


class LoadTestProfile(BaseModel):
    stages: list[int] = Field(default=[1, 2, 4], description="Parallelität je Stufe")
    requests_per_stage: int = Field(default=6, description="Requests pro Stufe")
    mix: dict[str, int] = Field(
        default={"wissen": 1, "suche": 1, "orientierung": 1},
        description="Gewichte je Kategorie (wissen/suche/orientierung/lernpfad)",
    )
    p95_threshold_s: float = Field(
        default=20.0, description="p95-Schwelle für 'stabil' im Fazit",
    )


def _ensure_loadtest_allowed(lang: Locale) -> None:
    """Guard: the loadtest drives the REAL ``/api/chat`` pipeline in-process (up
    to 32 parallel) and shares the LLM pool with live users (Audit 2026-07-03
    #6). Disable on a prod instance via ``BOERDI_ALLOW_LOADTEST=false``. Default:
    allowed (opt-out — no behaviour change without the env var set)."""
    if not get_settings().allow_loadtest:
        raise HTTPException(403, msg(lang, "loadtest.disabled"))


@router.get("/mix-options")
async def mix_options() -> dict:
    """Available mix categories with description (for the Studio form)."""
    return {
        "options": [
            {"key": k, "label": v["label"], "prompt": v["prompt"]}
            for k, v in MIX_TEMPLATES.items()
        ]
    }


@router.get("/runs")
async def list_loadtest_runs(session: _Session) -> dict:
    return {"runs": await list_runs(session)}


@router.post("/runs")
async def start_loadtest_run(
    profile: LoadTestProfile, request: Request, session: _Session, lang: Lang,
) -> dict:
    _ensure_loadtest_allowed(lang)
    running = await any_run_running(session)
    if running:
        raise HTTPException(409, msg(lang, "loadtest.alreadyRunning", id=running))
    try:
        norm = validate_profile(profile.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    run_id = f"lt-{uuid.uuid4().hex[:12]}"
    await create_run(session, run_id, norm)
    _spawn_background(execute_load_test(request.app, run_id, norm))
    return {"id": run_id, "status": "running", "profile": norm}


@router.get("/runs/{run_id}")
async def get_loadtest_run(run_id: str, session: _Session, lang: Lang) -> dict:
    run = await load_run(session, run_id)
    if not run:
        raise HTTPException(404, msg(lang, "loadtest.runMissing"))
    return run


@router.delete("/runs/{run_id}")
async def delete_loadtest_run(run_id: str, session: _Session, lang: Lang) -> dict:
    run = await load_run(session, run_id)
    if run and run.get("status") == "running":
        raise HTTPException(409, msg(lang, "loadtest.runIsRunning"))
    if not await delete_run(session, run_id):
        raise HTTPException(404, msg(lang, "loadtest.runMissing"))
    return {"deleted": run_id}
