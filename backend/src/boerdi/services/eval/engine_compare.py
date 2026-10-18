"""Comparing eval runs in the Studio (ST-7c) — K0-1's evaluation over chosen runs.

Until ST-7 only the measuring tool ``evals/engine_matrix.py`` compared engines,
as Markdown on disk. ``GET /api/eval/compare`` runs the same evaluation
(``engine_metrics.evaluate``: quality per axis, determinism across repeats,
speed, cost, robustness, rule R2(a)) over runs the Studio picks, grouped by the
engine each run recorded (``run_engine``).

A run counts only when it finished and its engine is known; everything else is
named in ``warnings`` instead of silently shrinking the sample. Warnings are
codes with values, not K0-1's German sentences: the Studio speaks two languages.

Paket 13 (D4) adds the judge v2 scales per run and engine, and what changed
between the runs against the first one (``vergleich_v2``).
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import EvalRun
from boerdi.domain.config_models import PricingArea
from boerdi.services.config_loader import load_pricing
from boerdi.services.eval import engine_metrics, vergleich_v2
from boerdi.services.eval.run_engine import run_engine
from boerdi.services.eval.run_profile import fallback_texts, price_from_table


async def compare_runs(session: AsyncSession, ids: list[str]) -> dict[str, Any]:
    """K0-1's evaluation over ``ids``, in the order given."""
    rows = (
        await session.execute(select(EvalRun).where(EvalRun.id.in_(ids)))
    ).scalars().all()
    # Plain data for the worker thread — no ORM instance leaves this task.
    by_id = {row.id: {"status": row.status, "config": dict(row.config or {}),
                      "summary": row.summary or {}, "conversations": row.conversations or []}
             for row in rows}
    table = load_pricing()
    # The text similarity compares every answer with every other (difflib,
    # quadratic): six real gold runs took 14.5 s. On the event loop every chat
    # turn of every user would wait that long.
    return await asyncio.to_thread(_compare, ids, by_id, table)


def _compare(
    ids: list[str], by_id: dict[str, dict[str, Any]], table: PricingArea | None,
) -> dict[str, Any]:
    """The CPU part over plain data — runs in a worker thread."""
    warnings: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    grouped: dict[str, list[list[engine_metrics.Turn]]] = {}
    counted: list[dict[str, Any]] = []
    details: dict[str, dict[str, Any]] = {}

    for run_id in ids:
        row = by_id.get(run_id)
        if row is None:
            warnings.append({"code": "not_found", "run": run_id})
            continue
        engine = run_engine(row["config"])
        usable = row["status"] == "done" and bool(engine)
        runs.append({"id": run_id, "engine": engine, "status": row["status"],
                     "label": str(row["config"].get("config_slug") or ""),
                     "counted": usable})
        if row["status"] != "done":
            warnings.append({"code": "not_done", "run": run_id, "status": row["status"]})
        elif not engine:
            warnings.append({"code": "engine_unknown", "run": run_id})
        if not usable:
            continue
        detail = {"summary": row["summary"], "conversations": row["conversations"]}
        details[run_id] = detail
        grouped.setdefault(engine, []).append(engine_metrics.turns_of(detail))
        counted.append({"engine": engine, "label": run_id, "run_id": run_id})

    price = price_from_table(table)
    result = engine_metrics.evaluate(grouped, price, fallback_texts())
    bewertungen: list[tuple[str, dict[str, Any] | None]] = []
    for run in runs:
        if run["counted"]:
            run["bewertung"] = vergleich_v2.bewertung(details[run["id"]], price)
            bewertungen.append((run["engine"], run["bewertung"]))
    # Only the groups: K0-1's sentences are German, and its "measured X" check
    # compares against a matrix plan the Studio does not have.
    _, conditions = engine_metrics.check_conditions(counted, details)
    warnings += _condition_warnings(table is None, result["engines"], conditions,
                                    counted, details)
    return {
        "engines": result["engines"],
        "rules": result["rules"],
        "currency": table.currency if table is not None else None,
        "conditions": conditions,
        "runs": runs,
        "bewertung_je_maschine": vergleich_v2.je_maschine(bewertungen),
        "unterschiede": vergleich_v2.unterschiede(list(details.items())),
        "warnings": warnings,
    }


def _condition_warnings(
    pricing_unreadable: bool,
    engines: dict[str, dict[str, Any]],
    conditions: list[dict[str, Any]],
    counted: list[dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """What makes the comparison weaker than it looks — as codes."""
    out: list[dict[str, Any]] = []
    if pricing_unreadable:
        out.append({"code": "pricing_unreadable"})
    else:
        # Without a readable table every model "lacks" a price; naming them
        # would send the reader to maintain prices that are already there.
        missing = sorted({model for summary in engines.values()
                          for model in summary["cost"]["price_unavailable"]})
        if missing:
            out.append({"code": "price_missing", "models": missing})
    if len(conditions) > 1:
        out.append({"code": "conditions_differ"})
    skill_off = [
        run["run_id"] for run in counted
        if run["engine"] == "agent" and engine_metrics.conditions_of(
            details[run["run_id"]]["summary"])["master_skill"]["enabled"] is False
    ]
    if skill_off:
        out.append({"code": "master_skill_off", "runs": skill_off})
    return out
