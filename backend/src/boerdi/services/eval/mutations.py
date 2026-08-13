"""Delete paths over ``eval_runs`` and the eval share of ``quality_logs``.

Split out of ``eval_service`` unchanged. Kept apart from ``queries`` because a
read that returns the wrong shape is a display bug, while a delete that matches
the wrong rows destroys data — the two deserve separate review attention.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import EvalRun, QualityLog


async def delete_run(session: AsyncSession, run_id: str) -> dict[str, Any]:
    await session.execute(delete(EvalRun).where(EvalRun.id == run_id))
    await session.commit()
    return {"deleted": run_id}


async def delete_runs(
    session: AsyncSession, status_filter: str | None,
    mode_filter: str | None, confirm: bool,
) -> dict[str, Any]:
    """Bulk-delete, optionally restricted by status and/or mode (combinable).

    ``mode=golden`` → only golden runs; ``mode=generative`` → mode != golden;
    any other value matches exactly. A wholly unrestricted delete needs
    ``confirm=true`` (ALT safety)."""
    conds: list[Any] = []
    if status_filter:
        conds.append(EvalRun.status == status_filter)
    if mode_filter == "golden":
        conds.append(EvalRun.mode == "golden")
    elif mode_filter == "generative":
        conds.append(EvalRun.mode != "golden")
    elif mode_filter:
        conds.append(EvalRun.mode == mode_filter)

    if not conds and not confirm:
        raise HTTPException(
            400,
            "Bulk delete without any filter requires ?confirm=true to prevent accidents.",
        )
    count = (
        await session.execute(select(func.count()).select_from(EvalRun).where(*conds))
    ).scalar_one()
    await session.execute(delete(EvalRun).where(*conds))
    await session.commit()
    return {"deleted": count, "filter": {"status": status_filter, "mode": mode_filter}}


async def clear_eval_quality_logs(session: AsyncSession) -> dict[str, Any]:
    """Delete quality_logs rows written by eval runs (session_id LIKE 'eval-%').

    Production chat traffic is preserved."""
    count = (
        await session.execute(
            select(func.count()).select_from(QualityLog)
            .where(QualityLog.session_id.like("eval-%"))
        )
    ).scalar_one()
    await session.execute(
        delete(QualityLog).where(QualityLog.session_id.like("eval-%"))
    )
    await session.commit()
    return {"deleted_eval_log_rows": count}
