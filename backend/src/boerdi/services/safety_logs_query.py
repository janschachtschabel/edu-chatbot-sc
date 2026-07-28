"""P7: read side of the safety-log store for the Studio safety dashboard.

pg-**REWRITE** of the reader half of ALT ``app/services/db_logs.py``
(``get_safety_logs``). ALT's sqlite ``safety_logs`` carried every decision field
as its own flat column and returned ``dict(SELECT *)``; NEU promotes only
``id``/``session_id``/``ip``/``risk_level``/``created_at`` and folds the rest into a
single ``data`` jsonb blob (see ``obs/quality_events.py`` for the writer). The
accessors are rewritten for that schema but the returned dict is ALT-identical —
same 15 keys, in particular the leaked ``categories_json`` key (ALT's sqlite
column name, which the Studio's ``SafetyLogsView.tsx`` reads verbatim) is emitted
from ``data["categories"]``.

Two representation notes kept faithful to ALT's wire output:
  * ``escalated``/``rate_limited`` — stored as native booleans in ``data`` (the
    writer coerces with ``bool(...)``), surfaced as ``0``/``1`` ints because ALT's
    sqlite kept them as ints and the Studio types them ``number``.
  * ``created_at`` — a real ``timestamptz`` here, ISO-serialised so the body stays
    a plain dict (ALT stored the ISO string directly).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import SafetyLog


def _row_to_dict(row: SafetyLog) -> dict:
    """Flatten one NEU ``SafetyLog`` row into ALT's flat response shape."""
    data = row.data or {}
    return {
        "id": row.id,
        "session_id": row.session_id or "",
        "ip": row.ip or "",
        "risk_level": row.risk_level or "low",
        "stages_run": data.get("stages_run", []),
        "reasons": data.get("reasons", []),
        "legal_flags": data.get("legal_flags", []),
        "flagged_categories": data.get("flagged_categories", []),
        "blocked_tools": data.get("blocked_tools", []),
        "enforced_pattern": data.get("enforced_pattern", ""),
        "escalated": int(bool(data.get("escalated", False))),
        "rate_limited": int(bool(data.get("rate_limited", False))),
        "message": data.get("message", ""),
        # ALT's leaked column name, sourced from the NEU ``data`` blob's key.
        "categories_json": data.get("categories", {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def get_safety_logs(
    session: AsyncSession,
    limit: int = 100,
    risk_min: str = "",
    session_id: str = "",
) -> list[dict]:
    """Return recent safety-log rows, newest first.

    ``risk_min``: ``''`` (all) | ``'medium'`` (medium+high) | ``'high'`` (high only).
    ``session_id``: restrict to a single session when non-empty.
    """
    stmt = select(SafetyLog)
    if session_id:
        stmt = stmt.where(SafetyLog.session_id == session_id)
    if risk_min == "medium":
        stmt = stmt.where(SafetyLog.risk_level.in_(("medium", "high")))
    elif risk_min == "high":
        stmt = stmt.where(SafetyLog.risk_level == "high")
    stmt = stmt.order_by(SafetyLog.id.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_dict(r) for r in rows]
