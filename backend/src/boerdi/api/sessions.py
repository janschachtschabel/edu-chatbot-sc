"""Session management (studio) + widget history restore (public, rate-limited).

Ported in P7 from ALT ``app/routers/sessions.py`` (memory API included). The
studio ``router`` carries router-level ``require_studio_key``; the ``public_router``
holds the single unauthenticated endpoint — ``GET /{session_id}/messages``, which
the embedded widget calls on every page load to restore history.

The endpoint bodies are ALT-verbatim in shape; only the storage seam moved to
Postgres. Reused straight from services/db_sessions.py: ``get_or_create_session``,
``get_messages``, ``get_memory``, ``save_memory``, ``delete_session``,
``delete_messages_for_session``, ``purge_all``. The three studio-only admin queries
(list / db-stats / optimize) live in services/session_admin.py.

FOOTGUN: the DI dependency ``boerdi.api.deps.get_session`` is imported UNDER THE
ALIAS ``get_db_session`` because the endpoint ``get_session`` (GET /{session_id})
would otherwise shadow it and break ``Depends(get_session)``.

STATIC routes (``/``, ``/db-stats``, ``/optimize``, ``/purge``) are declared BEFORE
the dynamic ``/{session_id}`` routes so FastAPI does not match ``db-stats`` as a
``session_id`` and 405/404.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, Security
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.api.deps import Lang, OriginScope, get_session_factory, require_studio_key
from boerdi.api.deps import get_session as get_db_session
from boerdi.api.publikum import verlauf_fuer
from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import darf_diagnose
from boerdi.domain.write_anzeige import entities_for_display
from boerdi.i18n import msg
from boerdi.services import aufbewahrung
from boerdi.services.config_loader import load_privacy_config
from boerdi.services.config_loader.safety import melde_datenschutz_unlesbar
from boerdi.services.db_sessions import (
    delete_messages_for_session,
    get_memory,
    get_messages,
    get_or_create_session,
    purge_all,
    save_memory,
    zuege_mit_nummer,
)
from boerdi.services.db_sessions import delete_session as db_delete_session
from boerdi.services.session_admin import db_stats as get_db_stats
from boerdi.services.session_admin import list_sessions_admin, optimize_database

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/sessions", tags=["sessions"],
    dependencies=[Security(require_studio_key)],
)
public_router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# T2 (ALT Audit 2026-07-05): input hygiene on the ONE open session read. Real
# widget ids are ``bb-<uuid>`` (URL-safe, <=39 chars); any URL-safe id up to 128
# chars is accepted (back-compat), but control/special chars and absurd lengths
# are rejected. This is NOT ownership proof — anyone holding a valid high-entropy
# id can still read that history (architectural, ALT T2) — only shape + DoS bound.
# The same shape as the chat entrance (``schemas.SITZUNGSKENNUNG``, Paket 9);
# ``fullmatch``, because ``$`` let a trailing newline through.
_SESSION_ID_RE = re.compile(SITZUNGSKENNUNG)
_MAX_MESSAGES_LIMIT = 200


def _validate_session_id(session_id: str) -> None:
    """Raise 400 for a malformed/oversized session id on the open endpoint."""
    if not _SESSION_ID_RE.fullmatch(session_id or ""):
        raise HTTPException(status_code=400, detail="Invalid session id")


# ── STATIC routes FIRST ──────────────────────────────────────────────────

@router.get("/")
async def list_sessions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    scope: OriginScope = "all",
) -> list[dict]:
    """List the most recently active sessions (newest first, capped at 100)."""
    return await list_sessions_admin(session, scope=scope)


@router.get("/db-stats")
async def db_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """DB size + reclaimable-space estimate (read-only): when is a VACUUM due?"""
    return await get_db_stats(session)


@router.post("/purge")
async def purge_sessions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    lang: Lang,
    messages: bool = True,
    memory: bool = True,
    quality_logs: bool = True,
    safety_logs: bool = False,
    sessions: bool = False,
    confirm: bool = False,
) -> dict:
    """Bulk-delete chat rows across ALL sessions. Per-table counts returned.

    Defaults to a sensible subset (messages+memory+quality_logs); ``safety_logs``
    is kept for audit and ``sessions`` is kept so active users aren't disconnected
    unless explicitly requested. ``confirm=true`` is REQUIRED (ALT safety floor)
    to guard against accidental calls from dev tooling.
    """
    if not confirm:
        raise HTTPException(400, msg(lang, "sessions.purgeNeedsConfirm"))
    counts = await purge_all(
        session,
        messages=messages,
        memory=memory,
        quality_logs=quality_logs,
        safety_logs=safety_logs,
        sessions=sessions,
    )
    return {"status": "purged", "deleted": counts}


@router.post("/optimize")
async def optimize_db(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    lang: Lang,
) -> dict:
    """Compact/maintain the DB (VACUUM). Under load the lock may fail → 503.

    NOTE (deviation, flagged): ALT additionally refused with 409 while an
    eval/loadtest run was active (``_ensure_db_idle_for_vacuum``). Those services
    do not exist in NEU yet, so that idle guard is intentionally omitted here.
    """
    try:
        result = await optimize_database(session)
    except Exception as e:  # noqa: BLE001 — surface lock/IO errors to the UI
        raise HTTPException(503, msg(lang, "sessions.optimizeFailed", error=e)) from e
    return {"status": "optimized", **result}


@router.get("/retention")
async def retention_overview(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Retention per log: period in days (0 = unlimited), entries due now, oldest entry."""
    return {"fristen": await aufbewahrung.ueberblick(session)}


@router.post("/retention")
async def retention_run(
    request: Request,
    lang: Lang,
    sitzungen: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict:
    """Delete the entries due now — the same run the backend makes every 6 hours."""
    geloescht = await aufbewahrung.lauf(request.app.state.engine, sitzungen)
    if geloescht is None:
        raise HTTPException(409, msg(lang, "retention.busy"))
    return {"status": "done", "deleted": geloescht}


@router.get("/zug/{nummer}")
async def zug_suchen(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    nummer: Annotated[str, Path(pattern=r"^[A-Za-z0-9._:\-]{1,128}$")],
) -> list[dict]:
    """Paket 18C/D: Fehlernummer (Anfang der Trace-ID) → Züge, neueste zuerst, höchstens 20 —
    je Treffer Sitzung, Nachricht, Trace-ID und Zeitpunkt. Ab 8 Zeichen als Präfix, kürzere
    genau (eine kurze Client-Trace-ID ist ganz die Nummer) — so trifft keine Nummer die halbe
    Datenbank; der Zeichenvorrat ist der der Trace-ID. Steht vor den Routen mit
    ``{session_id}``: ``/zug/messages`` gehört hierher, nicht in den Verlauf."""
    return await zuege_mit_nummer(session, nummer)


# ── Dynamic routes ───────────────────────────────────────────────────────

@router.get("/{session_id}")
async def get_session(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Get session state. ``entities``/``signal_history`` come back already parsed
    from db_sessions (dict/list) — NOT re-``json.loads``ed as ALT did over sqlite
    TEXT."""
    s = await get_or_create_session(session, session_id)
    return {
        "session_id": s["session_id"],
        "persona_id": s.get("persona_id", ""),
        "state_id": s.get("state_id", "S1"),
        # Ohne Bestätigungsschlüssel eines offenen Vorgangs (Review Paket 2).
        "entities": entities_for_display(s.get("entities") or {}),
        "signal_history": s.get("signal_history") or [],
        "turn_count": s.get("turn_count", 0),
    }


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Fully delete a session: messages, memory, quality + safety logs, and the
    session row. Per-table row counts returned."""
    counts = await db_delete_session(session, session_id)
    return {"status": "deleted", "session_id": session_id, "deleted": counts}


@router.get("/{session_id}/memory")
async def get_session_memory(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    memory_type: str | None = None,
) -> list[dict]:
    """Get memory entries for a session, optionally filtered by ``memory_type``."""
    return await get_memory(session, session_id, memory_type)


@router.post("/{session_id}/memory")
async def set_session_memory(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    key: str,
    value: str,
    memory_type: str = "short",
) -> dict:
    """Save a memory entry.

    Honors 01-base/privacy-config.yaml: when ``logging.memory`` is false the write
    is silently dropped (HTTP 200, ``persisted=false``). The session is created
    first (N-1 ALT audit): ``memory.session_id`` has an FK to ``sessions``, so a
    write for a never-created session would otherwise raise an uncaught 500.
    """
    try:
        if not load_privacy_config().get("memory", True):
            return {
                "status": "skipped",
                "persisted": False,
                "key": key,
                "reason": "memory logging disabled in privacy-config",
            }
    except Exception as fehler:  # noqa: BLE001 — any failure: do not store (Paket 18E, F1)
        melde_datenschutz_unlesbar("memory", fehler)
        return {"status": "skipped", "persisted": False, "key": key,
                "reason": "privacy-config unreadable"}
    await get_or_create_session(session, session_id)
    await save_memory(session, session_id, key, value, memory_type)
    return {"status": "saved", "persisted": True, "key": key, "memory_type": memory_type}


@router.delete("/{session_id}/messages")
async def delete_session_messages(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Delete only the chat messages (keep session + memory + logs). Useful to
    reset a conversation while preserving analytics."""
    n = await delete_messages_for_session(session, session_id)
    return {"status": "cleared", "session_id": session_id, "deleted_messages": n}


@public_router.get("/{session_id}/messages")
@public_rate_limit
async def get_session_messages(
    session_id: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 50,
) -> list[dict]:
    """Public: widget history restore — rate-limited (spec §5.1 / V7).

    Unauthenticated by design (the widget restores history on every page load).
    ``session_id`` is a client-held high-entropy bearer secret; its shape is
    validated and ``limit`` is bounded to 1..200 (trust-boundary hygiene + DoS
    cap, ALT Audit T2). ``request``/``response`` are required by the rate-limit
    decorator: the peer-IP key and the ``X-RateLimit-*`` header injection.
    """
    # ``response`` must be a declared param (not just the return value): slowapi
    # injects the rate-limit headers into it — without it this list-returning
    # endpoint 500s the moment the limiter is active (V7 default ON).
    _validate_session_id(session_id)
    limit = max(1, min(limit, _MAX_MESSAGES_LIMIT))
    # Paket 18C/D: Debug-Block, Zugakte (Werkzeug-Argumente, Fehlertexte, umgeschriebene
    # Entwürfe) und Trace-ID sind Diagnose fürs Studio, das diesen Weg über den Proxy liest; das
    # Widget stellt aus ``ui`` wieder her.
    intern = darf_diagnose(request)
    return verlauf_fuer(await get_messages(session, session_id, limit, zugakte=intern), intern)
