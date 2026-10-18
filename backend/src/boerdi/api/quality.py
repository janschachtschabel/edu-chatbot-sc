"""Quality analytics (studio). Thin HTTP layer over
``services/quality_analytics.py`` (queries ported from ALT db_analytics.py /
db_logs.py against the quality_logs jsonb layout, spec §6).

The router carries StudioKey security at router level (do not re-add per route).
The two mutating service fns share names with their endpoint functions, so they
are imported under ``*_svc`` aliases.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import Lang, get_session, require_studio_key
from boerdi.i18n import msg
from boerdi.services.quality_analytics import (
    clear_quality_logs as clear_quality_logs_svc,
)
from boerdi.services.quality_analytics import (
    delete_quality_log as delete_quality_log_svc,
)
from boerdi.services.quality_analytics import (
    get_degradation_breakdown,
    get_empty_entities_breakdown,
    get_low_confidence_turns,
    get_quality_logs,
    get_quality_stats,
    get_routing_matrix,
    get_state_transitions,
    get_tight_races_breakdown,
)
from boerdi.services.session_origin import scope_sql

router = APIRouter(
    prefix="/api/quality", tags=["quality"],
    dependencies=[Security(require_studio_key)],
)

#: Paket 13 (E5): nur Züge einer Maschine (Agent-Züge tragen das Muster ``AGENT``); ohne Angabe
#: beide. ``Literal`` statt freiem Text: ein Tippfehler ist 422 statt still „alle“.
_Engine = Annotated[
    Literal["pattern", "agent"] | None,
    Query(description="Nur Züge dieser Maschine ('pattern' | 'agent'); ohne Angabe beide"),
]


@router.get("/logs")
async def list_quality_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=500),
    session_id: str = "",
    pattern_id: str = "",
    intent_id: str = "",
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
) -> dict:
    """Recent quality-log entries. ``pattern_id``/``intent_id`` are prefix
    matches (e.g. "M04", "I02"); ``scope`` splits production vs eval sessions."""
    rows = await get_quality_logs(
        session, limit=limit, session_id=session_id,
        pattern_id=pattern_id, intent_id=intent_id, scope=scope, engine=engine,
    )
    return {"count": len(rows), "logs": rows}


@router.delete("/logs/{log_id}")
async def delete_quality_log(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Lang,
) -> dict:
    """Delete a single quality-log entry by id (404 if it does not exist)."""
    n = await delete_quality_log_svc(session, log_id)
    if n == 0:
        raise HTTPException(
            status_code=404, detail=msg(lang, "quality.logNotFound"),
        )
    return {"status": "deleted", "id": log_id}


@router.post("/logs/clear")
async def clear_quality_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Lang,
    session_id: str = "",
    pattern_id: str = "",
    intent_id: str = "",
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    confirm: bool = False,
) -> dict:
    """Bulk-delete quality logs by filter. Deleting everything (no filter AND
    scope='all') demands ``confirm=true`` to avoid accidental nukes."""
    # A filter counts only if it RESTRICTS (Audit 2026-09-29): an unknown
    # ``scope`` ("prod", "ALL") maps to no WHERE clause in ``scope_sql``, and
    # ``pattern_id``/``intent_id`` made only of the LIKE wildcards ``%``/``_``
    # match every row — both used to count as a filter and wiped the table
    # without ``confirm``. (A comment, not the docstring: that is part of the
    # frozen OpenAPI contract.)
    has_filter = any([
        session_id,
        pattern_id.strip("%_"),
        intent_id.strip("%_"),
        scope_sql(scope),
        engine,  # Paket 13 (E5): die Maschine schränkt immer ein
    ])
    if not has_filter and not confirm:
        raise HTTPException(400, msg(lang, "quality.bulkDeleteNeedsConfirm"))
    n = await clear_quality_logs_svc(
        session, session_id=session_id, pattern_id=pattern_id,
        intent_id=intent_id, scope=scope, engine=engine,
    )
    return {
        "status": "cleared",
        "deleted": n,
        "filter": {
            "session_id": session_id, "pattern_id": pattern_id,
            "intent_id": intent_id, "scope": scope, "engine": engine,
        },
    }


@router.get("/stats")
async def quality_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
) -> dict:
    """Aggregate quality metrics (distributions, confidence, degradation …)."""
    return await get_quality_stats(session, scope=scope, engine=engine)


@router.get("/matrix")
async def quality_matrix(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    min_count: int = Query(1, ge=1, le=1000, description="Min samples per cell"),
) -> dict:
    """Persona × Intent → Pattern matrix; empty combinations are omitted."""
    return await get_routing_matrix(
        session, scope=scope, min_count=min_count, engine=engine,
    )


@router.get("/state-transitions")
async def state_transitions(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    days: int = Query(30, ge=1, le=365, description="Time window in days"),
    min_count: int = Query(1, ge=1, le=1000, description="Min count per transition"),
) -> dict:
    """Conversation State transitions (prev → next) for the Studio Flow view."""
    return await get_state_transitions(
        session, scope=scope, days=days, min_count=min_count, engine=engine,
    )


@router.get("/tight-races")
async def tight_races(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    threshold: float = Query(0.02, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Which (winner, runner_up) pattern pairs keep colliding, with examples."""
    return await get_tight_races_breakdown(
        session, scope=scope, threshold=threshold, limit=limit, engine=engine,
    )


@router.get("/degradations")
async def degradations(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Which (pattern × missing-slot) combos most often trigger a fallback."""
    return await get_degradation_breakdown(session, scope=scope, limit=limit, engine=engine)


@router.get("/empty-entities")
async def empty_entities(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Intents where entity extraction consistently yields nothing."""
    return await get_empty_entities_breakdown(
        session, scope=scope, limit=limit, engine=engine,
    )


@router.get("/low-confidence")
async def low_confidence(
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: str = Query("all", description="'all' | 'production' | 'eval'"),
    engine: _Engine = None,
    max_confidence: float = Query(0.60, ge=0.0, le=1.0),
    limit: int = Query(30, ge=1, le=200),
) -> dict:
    """Turns below a confidence threshold, worst-first, with the raw message."""
    return await get_low_confidence_turns(
        session, scope=scope, max_confidence=max_confidence, limit=limit, engine=engine,
    )
