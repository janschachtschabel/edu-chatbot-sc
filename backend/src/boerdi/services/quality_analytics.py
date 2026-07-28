"""Quality analytics: aggregations + breakdowns over ``quality_logs`` (studio).

pg-**REWRITE** of ALT ``app/services/db_analytics.py`` + the quality half of
``app/services/db_logs.py``. The function names, arguments and returned dict
shapes are ALT-identical (the Studio frontend consumes them); only the storage
layer changes.

The core seam is sqlite-flat-columns → a single ``data`` jsonb per row. ALT read
each metric from its own column (``final_confidence``, ``degradation``,
``entities`` …); NEU reads them from ``data`` via Postgres jsonb accessors, with
``session_id``/``pattern_id``/``intent_id`` still promoted columns (see
``obs/quality_events.py`` for the authoritative payload shape):

* scalar metric   ``col``            → ``(data->>'key')::float|int``
* boolean flag    ``degradation=1``  → ``(data->>'degradation')::boolean IS TRUE``
* jsonb container ``entities='{}'``  → ``data->'entities' = '{}'::jsonb``
* array grouping  ``missing_slots``  → group by the ``->>`` text form (ALT grouped
  the JSON string), ``json.loads`` for the display list.

Only bound parameters carry user values; the WHERE fragments interpolated into
the SQL are static constants (``_scope_clause`` returns one of three fixed
strings — its ``'eval-%'`` literal is not user input). ``created_at`` is a native
timestamptz here (ALT stored ISO text), so it is serialised to ISO on the way out
to keep the ALT response shape.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Static jsonb WHERE fragments reused across queries (no user data, no params).
_DEGRADATION_TRUE = "(data->>'degradation')::boolean IS TRUE"
_ENTITIES_EMPTY = "data->'entities' = '{}'::jsonb"


def _scope_clause(scope: str) -> str:
    """WHERE fragment for the ``quality_logs`` scope filter (static SQL, no params).

    scope='production' → session_id NOT LIKE 'eval-%'
    scope='eval'       → session_id LIKE 'eval-%'
    scope='all'/unknown → '' (no restriction)
    """
    s = (scope or "all").strip().lower()
    if s == "production":
        return "session_id NOT LIKE 'eval-%'"
    if s == "eval":
        return "session_id LIKE 'eval-%'"
    return ""


def _iso(value: Any) -> Any:
    """Serialise a timestamptz to ISO text (ALT returned sqlite TEXT)."""
    return value.isoformat() if value is not None else None


# ── Quality-log CRUD ────────────────────────────────────────────────────

def _flatten_log_row(m: dict[str, Any]) -> dict[str, Any]:
    """Rebuild ALT's flat row from the NEU (columns + ``data`` jsonb) layout.

    The writer folded every non-promoted column into ``data`` under its ALT
    column name, so ``{**columns, **data}`` reproduces the flat dict. Two ALT
    contract fixups: ``data['debug']`` is exposed as ``debug_json`` (ALT's column
    name), and ``degradation`` is coerced back to the 1/0 int ALT stored.
    """
    data = dict(m.get("data") or {})
    row: dict[str, Any] = {
        "id": m.get("id"),
        "session_id": m.get("session_id"),
        "pattern_id": m.get("pattern_id"),
        "intent_id": m.get("intent_id"),
        "created_at": _iso(m.get("created_at")),
        **data,
    }
    row["debug_json"] = row.pop("debug", {})
    row["degradation"] = int(bool(row.get("degradation")))
    return row


async def get_quality_logs(
    session: AsyncSession,
    limit: int = 100,
    session_id: str = "",
    pattern_id: str = "",
    intent_id: str = "",
    scope: str = "all",
) -> list[dict]:
    """Recent quality-log rows (newest id first) with optional filters."""
    where: list[str] = []
    params: dict[str, Any] = {}
    if session_id:
        where.append("session_id = :session_id")
        params["session_id"] = session_id
    if pattern_id:
        where.append("pattern_id LIKE :pattern_id")
        params["pattern_id"] = f"{pattern_id}%"
    if intent_id:
        where.append("intent_id LIKE :intent_id")
        params["intent_id"] = f"{intent_id}%"
    sc = _scope_clause(scope)
    if sc:
        where.append(sc)
    sql = "SELECT id, session_id, pattern_id, intent_id, data, created_at FROM quality_logs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = limit
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [_flatten_log_row(dict(r)) for r in rows]


async def delete_quality_log(session: AsyncSession, log_id: int) -> int:
    """Delete a single quality-log row by id. Returns the row count (0 or 1)."""
    res = await session.execute(
        text("DELETE FROM quality_logs WHERE id = :id"), {"id": log_id}
    )
    await session.commit()
    return res.rowcount or 0


async def clear_quality_logs(
    session: AsyncSession,
    session_id: str = "",
    pattern_id: str = "",
    intent_id: str = "",
    scope: str = "all",
) -> int:
    """Bulk-delete quality logs by the same filter shape as ``get_quality_logs``.

    With no filter AND scope='all' this deletes every row — the caller (router)
    is responsible for demanding confirmation. Returns the number of rows removed.
    """
    where: list[str] = []
    params: dict[str, Any] = {}
    if session_id:
        where.append("session_id = :session_id")
        params["session_id"] = session_id
    if pattern_id:
        where.append("pattern_id LIKE :pattern_id")
        params["pattern_id"] = f"{pattern_id}%"
    if intent_id:
        where.append("intent_id LIKE :intent_id")
        params["intent_id"] = f"{intent_id}%"
    sc = _scope_clause(scope)
    if sc:
        where.append(sc)
    sql = "DELETE FROM quality_logs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    res = await session.execute(text(sql), params)
    await session.commit()
    return res.rowcount or 0


# ── Aggregations ────────────────────────────────────────────────────────

async def get_quality_stats(session: AsyncSession, scope: str = "all") -> dict:
    """Aggregate quality metrics for the dashboard / offline analysis."""
    sc = _scope_clause(scope)
    where_sql = f"WHERE {sc}" if sc else ""
    and_where = "AND" if where_sql else "WHERE"
    stats: dict[str, Any] = {"scope": scope}

    total = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}")
    )).scalar_one()
    stats["total_turns"] = total

    rows = (await session.execute(text(
        f"SELECT pattern_id, COUNT(*) AS cnt FROM quality_logs {where_sql} "
        f"GROUP BY pattern_id ORDER BY cnt DESC LIMIT 20"
    ))).all()
    stats["pattern_distribution"] = {r.pattern_id: r.cnt for r in rows}

    rows = (await session.execute(text(
        f"SELECT intent_id, COUNT(*) AS cnt FROM quality_logs {where_sql} "
        f"GROUP BY intent_id ORDER BY cnt DESC LIMIT 20"
    ))).all()
    stats["intent_distribution"] = {r.intent_id: r.cnt for r in rows}

    avg_conf = (await session.execute(text(
        f"SELECT AVG((data->>'final_confidence')::float) AS v FROM quality_logs {where_sql}"
    ))).scalar_one()
    stats["avg_confidence"] = round(avg_conf or 0, 3)

    avg_gap = (await session.execute(text(
        f"SELECT AVG((data->>'phase2_score_gap')::float) AS v FROM quality_logs {where_sql}"
    ))).scalar_one()
    stats["avg_score_gap"] = round(avg_gap or 0, 4)

    deg = (await session.execute(text(
        f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql} {and_where} {_DEGRADATION_TRUE}"
    ))).scalar_one()
    stats["degradation_rate"] = round(deg / max(total, 1), 3)

    # Welle-E: with LLM-Hint-Primary phase2_score_gap is 0 for every turn (no
    # score phase), so also require a real runner-up or the metric == total_turns.
    tight = (await session.execute(text(
        f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql} {and_where} "
        f"(data->>'phase2_score_gap')::float < 0.02 "
        f"AND data->>'phase2_runner_up' IS NOT NULL AND data->>'phase2_runner_up' != ''"
    ))).scalar_one()
    stats["tight_races"] = tight

    empty_ent = (await session.execute(text(
        f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql} {and_where} {_ENTITIES_EMPTY}"
    ))).scalar_one()
    stats["empty_entity_rate"] = round(empty_ent / max(total, 1), 3)

    avg_len = (await session.execute(text(
        f"SELECT AVG((data->>'response_length')::float) AS v FROM quality_logs {where_sql}"
    ))).scalar_one()
    stats["avg_response_length"] = round(avg_len or 0, 0)

    return stats


async def get_state_transitions(
    session: AsyncSession, scope: str = "all", min_count: int = 1, days: int = 30,
) -> dict:
    """Aggregate (prev_state → next_state) transitions per session, plus a
    state-frequency distribution. Feeds the Studio Conversation-Flow view."""
    where_parts = ["data->>'state_id' != ''"]
    params: dict[str, Any] = {}
    sc = _scope_clause(scope)
    if sc:
        where_parts.append(sc)
    if days and days > 0:
        # int-arg make_interval avoids asyncpg's interval-param inference (a bound
        # text/interval param under CAST is read as a timedelta, not text).
        where_parts.append("created_at >= now() - make_interval(days => :days)")
        params["days"] = int(days)
    where_sql = "WHERE " + " AND ".join(where_parts)

    total_turns = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}"), params
    )).scalar_one()

    dist_rows = (await session.execute(text(
        f"SELECT data->>'state_id' AS state_id, COUNT(*) AS cnt "
        f"FROM quality_logs {where_sql} GROUP BY data->>'state_id' ORDER BY cnt DESC"
    ), params)).all()
    state_distribution = {r.state_id: r.cnt for r in dist_rows}

    # turn_count sorts the sequence — created_at can tie within a session.
    seq_rows = (await session.execute(text(
        f"SELECT session_id, data->>'state_id' AS state_id, "
        f"(data->>'turn_count')::int AS turn_count "
        f"FROM quality_logs {where_sql} "
        f"ORDER BY session_id, (data->>'turn_count')::int ASC"
    ), params)).all()
    session_seqs: dict[str, list[str]] = {}
    for row in seq_rows:
        session_seqs.setdefault(row.session_id, []).append(row.state_id)

    pair_counts: dict[tuple[str, str], int] = {}
    for seq in session_seqs.values():
        for i in range(1, len(seq)):
            key = (seq[i - 1], seq[i])
            pair_counts[key] = pair_counts.get(key, 0) + 1

    transitions = [
        {"prev": prev, "next": nxt, "count": cnt}
        for (prev, nxt), cnt in pair_counts.items()
        if cnt >= min_count
    ]
    transitions.sort(key=lambda t: t["count"], reverse=True)

    return {
        "scope": scope,
        "days": days,
        "total_turns": total_turns,
        "total_transitions": sum(t["count"] for t in transitions),
        "state_distribution": state_distribution,
        "transitions": transitions,
    }


async def get_routing_matrix(session: AsyncSession, scope: str = "all", min_count: int = 1) -> dict:
    """Persona × Intent → Pattern matrix with top pattern, share, alternatives."""
    sc = _scope_clause(scope)
    where_sql = f"WHERE {sc}" if sc else ""
    and_where = "AND" if where_sql else "WHERE"

    total_turns = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}")
    )).scalar_one()

    rows = (await session.execute(text(
        f"SELECT data->>'persona_id' AS persona_id, intent_id, pattern_id, COUNT(*) AS cnt "
        f"FROM quality_logs {where_sql} {and_where} "
        f"data->>'persona_id' != '' AND intent_id != '' AND pattern_id != '' "
        f"GROUP BY data->>'persona_id', intent_id, pattern_id "
        f"ORDER BY data->>'persona_id', intent_id, cnt DESC"
    ))).all()

    grouped: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        grouped.setdefault((r.persona_id, r.intent_id), []).append(
            {"pattern_id": r.pattern_id, "cnt": r.cnt}
        )

    cells: list[dict] = []
    for (pid, iid), items in grouped.items():
        total = sum(it["cnt"] for it in items)
        if total < min_count:
            continue
        items.sort(key=lambda x: x["cnt"], reverse=True)
        top = items[0]
        cells.append({
            "persona_id": pid,
            "intent_id": iid,
            "top_pattern": top["pattern_id"],
            "top_pattern_count": top["cnt"],
            "total_count": total,
            "share": round(top["cnt"] / total, 3) if total else 0.0,
            "alternatives": [
                {"pattern_id": it["pattern_id"], "count": it["cnt"]}
                for it in items[1:5]  # cap to 4 alternatives for the UI
            ],
        })

    return {"scope": scope, "total_turns": total_turns, "cells": cells}


async def _example_row(session: AsyncSession, example_id: Any, *, with_intent: bool) -> Any:
    """Fetch the (message, persona, state[, intent]) sample for a breakdown group."""
    intent_col = "intent_id, " if with_intent else ""
    return (await session.execute(text(
        f"SELECT data->>'message' AS message, {intent_col}"
        f"data->>'persona_id' AS persona_id, data->>'state_id' AS state_id "
        f"FROM quality_logs WHERE id = :id"
    ), {"id": example_id})).one_or_none()


async def get_degradation_breakdown(
    session: AsyncSession, scope: str = "all", limit: int = 50,
) -> dict:
    """Group degradations by (pattern, missing-slots combo) with an example each."""
    where = [_DEGRADATION_TRUE, "pattern_id != ''"]
    params: dict[str, Any] = {}
    sc = _scope_clause(scope)
    if sc:
        where.append(sc)
    where_sql = "WHERE " + " AND ".join(where)

    # ALT grouped by the missing_slots JSON string — identical arrays group
    # without parsing. The ->> text form gives the same canonical grouping.
    grp = (await session.execute(text(
        f"SELECT pattern_id, data->>'missing_slots' AS missing_slots, "
        f"COUNT(*) AS count, MAX(id) AS example_id "
        f"FROM quality_logs {where_sql} "
        f"GROUP BY pattern_id, data->>'missing_slots' "
        f"ORDER BY count DESC LIMIT :limit"
    ), {**params, "limit": limit})).all()

    groups: list[dict] = []
    for row in grp:
        try:
            slots = json.loads(row.missing_slots or "[]")
            if not isinstance(slots, list):
                slots = []
        except (ValueError, TypeError):
            slots = []
        sample = await _example_row(session, row.example_id, with_intent=True)
        entry: dict[str, Any] = {
            "pattern_id": row.pattern_id,
            "missing_slots": slots,
            "count": row.count,
        }
        if sample is not None:
            entry["example_message"] = (sample.message or "")[:200]
            entry["example_intent"] = sample.intent_id
            entry["example_persona"] = sample.persona_id
            entry["example_state"] = sample.state_id
        groups.append(entry)

    total = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}"), params
    )).scalar_one()

    return {"groups": groups, "total": total, "scope": scope}


async def get_empty_entities_breakdown(
    session: AsyncSession, scope: str = "all", limit: int = 50,
) -> dict:
    """Group empty-entity turns by (intent, pattern) with an example each."""
    where = [_ENTITIES_EMPTY]
    params: dict[str, Any] = {}
    sc = _scope_clause(scope)
    if sc:
        where.append(sc)
    where_sql = "WHERE " + " AND ".join(where)

    grp = (await session.execute(text(
        f"SELECT intent_id, pattern_id, COUNT(*) AS count, MAX(id) AS example_id "
        f"FROM quality_logs {where_sql} "
        f"GROUP BY intent_id, pattern_id ORDER BY count DESC LIMIT :limit"
    ), {**params, "limit": limit})).all()

    groups: list[dict] = []
    for row in grp:
        sample = await _example_row(session, row.example_id, with_intent=False)
        entry: dict[str, Any] = {
            "intent_id": row.intent_id,
            "pattern_id": row.pattern_id,
            "count": row.count,
        }
        if sample is not None:
            entry["example_message"] = (sample.message or "")[:200]
            entry["example_persona"] = sample.persona_id
            entry["example_state"] = sample.state_id
        groups.append(entry)

    total = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}"), params
    )).scalar_one()

    return {"groups": groups, "total": total, "scope": scope}


async def get_low_confidence_turns(
    session: AsyncSession, scope: str = "all", max_confidence: float = 0.60, limit: int = 30,
) -> dict:
    """Individual turns below a confidence threshold, worst-first (raw, ungrouped)."""
    where = ["(data->>'final_confidence')::float < :maxc", "(data->>'final_confidence')::float > 0"]
    params: dict[str, Any] = {"maxc": max_confidence}
    sc = _scope_clause(scope)
    if sc:
        where.append(sc)
    where_sql = "WHERE " + " AND ".join(where)

    rows = (await session.execute(text(
        f"SELECT id, data->>'message' AS message, intent_id, pattern_id, "
        f"data->>'persona_id' AS persona_id, "
        f"(data->>'final_confidence')::float AS final_confidence, "
        f"(data->>'phase2_winner_score')::float AS phase2_winner_score, "
        f"(data->>'phase2_score_gap')::float AS phase2_score_gap, "
        f"data->>'state_id' AS state_id, created_at "
        f"FROM quality_logs {where_sql} "
        f"ORDER BY (data->>'final_confidence')::float ASC, "
        f"(data->>'phase2_score_gap')::float ASC LIMIT :limit"
    ), {**params, "limit": limit})).all()

    turns = [
        {
            "id": r.id,
            "message": (r.message or "")[:200],
            "intent_id": r.intent_id,
            "pattern_id": r.pattern_id,
            "persona_id": r.persona_id,
            "final_confidence": round(r.final_confidence or 0, 3),
            "phase2_winner_score": round(r.phase2_winner_score or 0, 3),
            "phase2_score_gap": round(r.phase2_score_gap or 0, 4),
            "state_id": r.state_id,
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]

    total = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}"), params
    )).scalar_one()

    return {"turns": turns, "total": total, "scope": scope, "max_confidence": max_confidence}


_TIGHT_RACES_UNAVAILABLE = (
    "Metrik nicht erhebbar: keine der ausgewerteten Zeilen trägt einen "
    "Zweitplatzierten. Seit Welle E v4 wählt die Engine das Pattern aus einem "
    "LLM-Hinweis statt aus einer Score-Phase, deshalb enthält phase2_scores "
    "genau einen Eintrag und es gibt kein Rennen, das eng sein könnte."
)


async def get_tight_races_breakdown(
    session: AsyncSession, scope: str = "all", threshold: float = 0.02, limit: int = 50,
) -> dict:
    """Group tight races by (winner, runner_up) pattern pair, with an example each.

    Answers with ``unavailable_reason`` + ``scanned`` instead of a bare
    ``total_tight: 0`` when the scanned rows carry no runner-up at all — see the
    note at the bottom of this function for why that is the normal case.
    """
    filters = [
        "(data->>'phase2_score_gap')::float < :threshold",
        "(data->>'phase2_score_gap')::float >= 0",
        "pattern_id != ''",
        "data->>'phase2_runner_up' != ''",
    ]
    params: dict[str, Any] = {"threshold": threshold}
    sc = _scope_clause(scope)
    if sc:
        filters.append(sc)
    where_sql = "WHERE " + " AND ".join(filters)

    grp = (await session.execute(text(
        f"SELECT pattern_id AS winner, data->>'phase2_runner_up' AS runner_up, "
        f"COUNT(*) AS count, AVG((data->>'phase2_score_gap')::float) AS avg_gap, "
        f"MAX(id) AS example_id "
        f"FROM quality_logs {where_sql} "
        f"GROUP BY pattern_id, data->>'phase2_runner_up' "
        f"ORDER BY count DESC, avg_gap ASC LIMIT :limit"
    ), {**params, "limit": limit})).all()

    pairs: list[dict] = []
    for row in grp:
        sample = await _example_row(session, row.example_id, with_intent=True)
        pair: dict[str, Any] = {
            "winner": row.winner,
            "runner_up": row.runner_up,
            "count": row.count,
            "avg_gap": round(row.avg_gap or 0, 4),
        }
        if sample is not None:
            pair["example_message"] = (sample.message or "")[:200]
            pair["example_intent"] = sample.intent_id
            pair["example_persona"] = sample.persona_id
            pair["example_state"] = sample.state_id
        pairs.append(pair)

    total_tight = (await session.execute(
        text(f"SELECT COUNT(*) AS cnt FROM quality_logs {where_sql}"), params
    )).scalar_one()

    out = {"pairs": pairs, "total_tight": total_tight, "threshold": threshold,
           "scope": scope}
    if not total_tight:
        # A bare 0 reads as "your data holds no tight races", which would be a
        # claim this query cannot support: the pair grouping requires a
        # runner-up, and ``select_pattern`` returns ``{winner.id: 1.0}`` at every
        # return site, so ``phase2_runner_up`` is '' on every row the live engine
        # writes. Measured rather than hardcoded — reinstate a score phase and
        # the note disappears by itself.
        counts = (await session.execute(text(
            f"SELECT COUNT(*) AS scanned, COUNT(*) FILTER "
            f"(WHERE data->>'phase2_runner_up' <> '') AS with_runner_up "
            f"FROM quality_logs {f'WHERE {sc}' if sc else ''}"
        ))).one()
        if counts.scanned and not counts.with_runner_up:
            out["scanned"] = counts.scanned
            out["unavailable_reason"] = _TIGHT_RACES_UNAVAILABLE
    return out
