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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import EvalRun
from boerdi.obs.tasks import cancel_run_task, register_run_task

logger = logging.getLogger(__name__)

# Where the golden runner talks to the real chatbot: the server calls itself. Port 8100 like
# compose, the image (Dockerfile ENV) and the local launch config — ALT's 8000 let a container
# started without compose refuse every run with 502 (Paket 15, A2).
_CHAT_URL_DEFAULT = "http://127.0.0.1:8100/api/chat"
# Paket 17 (C2): a 'running' row without a heartbeat for this long is swept to 'failed' by
# the start-guard — its pod is gone (rollout, scale-down, crash). Until then: 2 h after
# ``created_at``, so a dead pod blocked every new run for up to 2 h. Rows from before 0014
# (no heartbeat) count by ``created_at``.
_VERWAIST_NACH = timedelta(minutes=3)


def _chat_url() -> str:
    return os.getenv("EVAL_CHAT_URL") or _CHAT_URL_DEFAULT


# Der Abbruch-Weg liegt in ``obs/tasks``, seit der Lasttest als zweiter
# Aufrufer dazukam (Prod-Befund 3, 2026-08-22). Hier bleiben nur die beiden
# Namen, unter denen der Eval-Zweig sie kennt — samt seiner Protokoll-Marke.
_register_run_task = register_run_task


async def _cancel_run_task(run_id: str) -> bool:
    """Beendet den registrierten Hintergrund-Task eines Eval-Laufs."""
    return await cancel_run_task(run_id, label="eval")


async def _ensure_chat_reachable() -> None:
    """Preflight vor jedem Eval-Start (Review-Nachlauf 2026-08-22).

    Ein Lauf gegen ein totes ``EVAL_CHAT_URL`` (Backend auf 8100, der Default zeigte
    damals auf 8000 — seit Paket 15 steht er auf 8100) verbrannte alle Züge in
    "(chat error: All connection attempts failed)" und stand danach als „fertig" da.
    Ein 3-Sekunden-GET auf ``/api/health`` desselben Ursprungs bricht stattdessen den START ab
    und nennt URL und Stellschraube. Nur Transportfehler blocken — auch ein
    404 heißt: da antwortet etwas.
    """
    url = _chat_url()
    origin = url.split("/api/", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            await c.get(origin + "/api/health")
    except Exception as e:
        # Paket 18E: der Betrieb sah den abgewiesenen Start bisher nur im Studio.
        logger.warning("Eval-Start abgewiesen: Chat-Backend %s nicht erreichbar (%s)",
                       url, type(e).__name__)
        raise HTTPException(
            502,
            f"Chat-Backend nicht erreichbar unter {url} — EVAL_CHAT_URL "
            f"prüfen/setzen (Fehler: {type(e).__name__}). Der Lauf wurde "
            "NICHT gestartet.",
        ) from e


async def _ensure_no_running_run(session: AsyncSession) -> None:
    """Parallel-guard (ALT B4): two concurrent runs would share the chat backend
    and eval_runs writes and corrupt each other. 'running' rows without a heartbeat for
    ``_VERWAIST_NACH`` are swept to 'failed' first so they don't block (Paket 17, C2)."""
    # Grenze nach der Uhr der Datenbank, die auch den Herzschlag schreibt (Review C, Befund 5).
    await session.execute(
        text(
            "UPDATE eval_runs SET status='failed', completed_at=now(), "
            "error_message='verwaister running-Run abgeräumt (kein Herzschlag mehr)' "
            "WHERE status='running' "
            "AND COALESCE(heartbeat_at, created_at) < now() - make_interval(secs => :s)"
        ),
        {"s": _VERWAIST_NACH.total_seconds()},
    )
    await session.commit()
    running = await _laufender_run(session)
    if running:
        raise _laeuft_schon(running)


async def _laufender_run(session: AsyncSession) -> str | None:
    row = (
        await session.execute(
            select(EvalRun.id).where(EvalRun.status == "running").limit(1)
        )
    ).first()
    return row[0] if row else None


def _laeuft_schon(run_id: str | None) -> HTTPException:
    return HTTPException(
        409,
        f"Eval-Run {run_id or '?'} läuft bereits — bitte abwarten oder abbrechen. "
        "Parallele Runs teilen sich Chat-Backend und DB und würden sich "
        "gegenseitig verfälschen.",
    )


async def _lauf_anlegen(session: AsyncSession, run: EvalRun) -> None:
    """Insert the new run row — the database decides a race (Paket 4, E2).

    ``_ensure_no_running_run`` checks first, but two starts at the same moment
    both passed that check and both inserted. The unique partial index from
    migration 0006 lets only one ``running`` row exist; the loser gets the same
    409 as the check, naming the run that won.
    """
    session.add(run)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise _laeuft_schon(await _laufender_run(session)) from e


async def _finalize_run(
    session: AsyncSession, run_id: str, *, status: str,
    total_turns: int | None = None, avg_score: float | None = None,
    summary: dict[str, Any] | None = None,
    conversations: list[Any] | None = None,
    error_message: str | None = None,
    current_activity: str | None = None,
) -> bool:
    """Terminal write for a run row (status + completed_at + JSONB fields).

    Gibt zurück, OB geschrieben wurde. Ein ``cancelled`` ist terminal
    (Review-Befund 2026-08-22): bis dahin schrieb diese Funktion den Status
    bedingungslos, und ein Job, der die Cancellation erst am nächsten
    Prüfpunkt bemerkte — oder in einer anderen Replika lief —, drehte den
    gestoppten Lauf auf ``done`` zurück. Die Gegenrichtung ist genauso
    gesperrt: ein Stopp darf keinen Lauf umetikettieren, der gerade regulär
    fertig geworden ist.
    """
    # Gesperrt gelesen (Gesamt-Review Paket 17, C4): Abräumen oder Stopp zwischen Lesen und
    # Schreiben warten auf diese Transaktion, statt überschrieben zu werden.
    r = (
        await session.execute(select(EvalRun).where(EvalRun.id == run_id).with_for_update())
    ).scalar_one_or_none()
    if r is None:
        logger.warning("[eval %s] run row vanished before finalize", run_id)
        return False
    if status == "cancelled":
        if r.status != "running":
            logger.info("[eval %s] Stopp kommt zu spät (Status: %s)", run_id, r.status)
            return False
    elif r.status != "running":
        # ``cancelled`` oder ein als verwaist abgeräumter Lauf, dessen Job nur den Herzschlag
        # verlor (Paket 17, Review Phase C): der Endstand bleibt.
        logger.info("[eval %s] Endstand '%s' bleibt — '%s' verworfen",
                    run_id, r.status, status)
        return False
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
    return True
