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
from boerdi.services.eval.run_store import _cancel_run_task, _finalize_run


async def cancel_run(session: AsyncSession, run_id: str) -> dict[str, Any]:
    """Bricht einen laufenden Lauf ab: Task beenden, Status → ``cancelled``.

    Der zuletzt geschriebene Zwischenstand (Teiltranskripte, Zähler) bleibt
    stehen — ein halber Lauf ist lesenswert. Nutzer-Befund 2026-08-22: bis
    dahin gab es GAR KEINEN Weg, einen Lauf zu stoppen.

    **Zwei Wege, und beide werden gebraucht.** ``task_stopped=True`` heißt:
    der Task lief in DIESEM Prozess und ist sofort tot. ``False`` heißt nur,
    dass er hier nicht lag — bei ``BACKEND_REPLICAS > 1`` (Compose-Default 3)
    läuft er dann in einer anderen Replika weiter, denn eine
    ``asyncio``-Registry endet am Prozessrand. Deshalb ist der Status hier
    kein Etikett, sondern das SIGNAL: beide Lauf-Familien lesen ihre Zeile an
    ihren Fortschritts-Prüfpunkten mit (je Flow bzw. je Szenario/Dialog) und
    hören von selbst auf, sobald sie nicht mehr ``running`` ist. Der Abbruch
    kostet damit höchstens noch einen Flow — auf jeder Replika.
    """
    status = (
        await session.execute(
            select(EvalRun.status).where(EvalRun.id == run_id)
        )
    ).scalar_one_or_none()
    if status is None:
        raise HTTPException(404, f"Lauf {run_id} nicht gefunden.")
    if status != "running":
        raise HTTPException(
            409,
            f"Lauf {run_id} läuft nicht (Status: {status}) — nichts abzubrechen.",
        )
    # Die Prüfung oben ist der schnelle Weg für offensichtliche Fälle; die
    # VERBINDLICHE Entscheidung fällt unten in ``_finalize_run``. Dazwischen
    # liegt ein Warten von bis zu 10 s, und ein Lauf kann in dieser Zeit von
    # selbst fertig werden. Vorher die Transaktion schließen: sonst hinge eine
    # Datenbank-Verbindung die ganze Wartezeit „idle in transaction".
    await session.rollback()
    stopped = await _cancel_run_task(run_id)
    if not await _finalize_run(
        session, run_id, status="cancelled", current_activity="Abgebrochen",
    ):
        raise HTTPException(
            409,
            f"Lauf {run_id} wurde in der Zwischenzeit beendet — "
            "nichts abgebrochen.",
        )
    return {"cancelled": run_id, "task_stopped": stopped}


async def delete_run(session: AsyncSession, run_id: str) -> dict[str, Any]:
    # Erst den Task beenden, dann die Zeile: bis 2026-08-22 lief der
    # Hintergrund-Task nach dem Löschen einfach weiter (siehe cancel_run).
    await _cancel_run_task(run_id)
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
    # Kennungen statt bloßem COUNT: laufende Treffer haben einen lebenden
    # Hintergrund-Task, der VOR dem Zeilen-Löschen enden muss (cancel_run).
    ids = (
        await session.execute(select(EvalRun.id).where(*conds))
    ).scalars().all()
    for rid in ids:
        await _cancel_run_task(rid)
    await session.execute(delete(EvalRun).where(*conds))
    await session.commit()
    return {"deleted": len(ids), "filter": {"status": status_filter, "mode": mode_filter}}


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
