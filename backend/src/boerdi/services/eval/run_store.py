"""What both run families share: where they send traffic, and how a run row is
guarded at the start and closed at the end.

Split out of ``eval_service`` unchanged. Generative and golden runs differ in
everything except these three things, so they live here rather than being
duplicated or importing each other.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import EvalRun

logger = logging.getLogger(__name__)

# Where the golden runner talks to the real chatbot (ALT default kept verbatim;
# BEIDE NEU-Compose-Dateien setzen den Container-Selbstaufruf
# EVAL_CHAT_URL=http://127.0.0.1:8100/api/chat als Default — der Wert hier
# greift nur noch bei nacktem uvicorn ohne gesetzte Variable).
_CHAT_URL_DEFAULT = "http://localhost:8000/api/chat"
# Stale 'running' rows older than this are swept to 'failed' by the start-guard
# so a crashed run cannot block new ones forever (ALT: 2h).
_STALE_RUN_HOURS = 2


def _chat_url() -> str:
    return os.getenv("EVAL_CHAT_URL") or _CHAT_URL_DEFAULT


async def _ensure_chat_reachable() -> None:
    """Preflight vor jedem Eval-Start (Review-Nachlauf 2026-08-22).

    Ein Lauf gegen ein totes ``EVAL_CHAT_URL`` (Backend auf 8100, Default
    zeigt auf 8000) verbrannte alle Züge in "(chat error: All connection
    attempts failed)" und stand danach als „fertig" da. Ein 3-Sekunden-GET
    auf ``/api/health`` desselben Ursprungs bricht stattdessen den START ab
    und nennt URL und Stellschraube. Nur Transportfehler blocken — auch ein
    404 heißt: da antwortet etwas.
    """
    url = _chat_url()
    origin = url.split("/api/", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            await c.get(origin + "/api/health")
    except Exception as e:
        raise HTTPException(
            502,
            f"Chat-Backend nicht erreichbar unter {url} — EVAL_CHAT_URL "
            f"prüfen/setzen (Fehler: {type(e).__name__}). Der Lauf wurde "
            "NICHT gestartet.",
        ) from e


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
