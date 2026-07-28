"""Safety-log endpoints (studio): recent safety-decision rows + aggregate stats.

Fidelity port of ALT ``app/routers/safety.py``. The DB query lives in
``services/safety_logs_query.py`` (spec rule 4: thin router); the ``/stats``
aggregation stays inline as it was in ALT — it is pure Python over the rows, not
DB logic. ALT stored each decision in flat sqlite columns; NEU folds the
non-promoted fields into a ``data`` jsonb blob (see ``obs/quality_events.py``).
The service rewrites the field accessors accordingly but reproduces ALT's exact
row shape, so the Studio's ``SafetyLogsView.tsx`` (which reads ``categories_json``,
``escalated``/``rate_limited`` as numbers, etc.) keeps working unchanged.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session, require_studio_key
from boerdi.services.safety_logs_query import get_safety_logs

router = APIRouter(
    prefix="/api/safety", tags=["safety"],
    dependencies=[Security(require_studio_key)],
)


@router.get("/logs")
async def list_safety_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 100,
    risk_min: str = "",
    session_id: str = "",
) -> dict:
    """Return recent safety-log entries.

    Query params:
      limit: max rows (default 100)
      risk_min: '' | 'medium' | 'high' — filter by minimum risk level
      session_id: filter to a single session
    """
    rows = await get_safety_logs(
        session, limit=limit, risk_min=risk_min, session_id=session_id,
    )
    return {"count": len(rows), "logs": rows}


@router.get("/stats")
async def safety_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Aggregate counts for the dashboard."""
    rows = await get_safety_logs(session, limit=1000)
    stats: dict = {
        "total": len(rows),
        "by_risk": {"low": 0, "medium": 0, "high": 0},
        "by_legal": {},
        "rate_limited": 0,
        "escalated": 0,
    }
    for r in rows:
        rl = r.get("risk_level", "low")
        stats["by_risk"][rl] = stats["by_risk"].get(rl, 0) + 1
        if r.get("rate_limited"):
            stats["rate_limited"] += 1
        if r.get("escalated"):
            stats["escalated"] += 1
        for lf in r.get("legal_flags", []) or []:
            stats["by_legal"][lf] = stats["by_legal"].get(lf, 0) + 1
    return stats
