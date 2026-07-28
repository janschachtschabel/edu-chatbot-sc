"""Session administration (P7): the studio's list / db-stats / optimize queries.

pg-**REWRITES, not ports** of ALT's SQLite session-admin (``routers/sessions.py``
list handler + ``db_core.db_stats``/``optimize_db``). Kept OUT of db_sessions.py
on purpose: that module is shared by the turn pipeline (turn_persist + graph
nodes) and must stay lean; these three are studio-only maintenance reads/ops.

``purge`` and ``delete`` are NOT here — ``purge_all`` / ``delete_session`` already
live in db_sessions.py (tested in test_db_sessions_pg.py); the router reuses them.

Two functions cross the SQLite→Postgres impedance gap and are rewrites, not ports:

* ``db_stats`` — ALT reported sqlite page/freelist counts. Those have no Postgres
  meaning. NEU reports ``pg_database_size`` (exact) plus live/dead tuple counts
  from ``pg_stat_user_tables`` and a coarse ``reclaimable_bytes`` bloat estimate
  (dead-tuple fraction of the DB size) — enough for the studio's "is a VACUUM
  worth it?" indicator, ALT's stated purpose.
* ``optimize_database`` — ALT ran ``WAL checkpoint + VACUUM`` to shrink the single
  SQLite file. NEU runs a plain ``VACUUM (ANALYZE)``: it refreshes the free-space
  map and planner stats without the ACCESS EXCLUSIVE lock a ``VACUUM FULL`` (the
  only thing that returns pages to the OS) would take. Postgres therefore usually
  reports ``reclaimed_bytes == 0`` — the file does not shrink — which is honest,
  not a bug. Deliberately NOT ``VACUUM FULL``: ALT guarded its exclusive-lock
  VACUUM against concurrent eval/loadtest runs, and NEU has no equivalent idle
  guard yet, so an unguarded table-freezing op is not shipped. VACUUM must run
  outside a transaction, so it uses an AUTOCOMMIT checkout of the request session.
"""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import ChatSession

_LIST_LIMIT = 100


async def list_sessions_admin(session: AsyncSession) -> list[dict]:
    """The 100 most-recently-updated sessions, newest first (ALT's list handler).

    Same column set and order ALT selected; timestamps are serialised to ISO
    strings (Postgres ``timestamptz`` vs ALT's sqlite TEXT) for a stable body.
    """
    stmt = (
        select(
            ChatSession.session_id,
            ChatSession.persona_id,
            ChatSession.state_id,
            ChatSession.turn_count,
            ChatSession.created_at,
            ChatSession.updated_at,
        )
        .order_by(ChatSession.updated_at.desc())
        .limit(_LIST_LIMIT)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "session_id": r.session_id,
            "persona_id": r.persona_id,
            "state_id": r.state_id,
            "turn_count": r.turn_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


async def _db_size_bytes(session: AsyncSession) -> int:
    """On-disk size of the current database, in bytes (constant SQL, no input)."""
    size = (
        await session.execute(text("SELECT pg_database_size(current_database())"))
    ).scalar_one()
    return int(size)


async def db_stats(session: AsyncSession) -> dict[str, int]:
    """DB size + reclaimable-space estimate so the studio can flag a due VACUUM.

    ``reclaimable_bytes`` is an estimate: the dead-tuple fraction of the total
    database size. Postgres has no cheap exact figure without ``pgstattuple``;
    this is a heuristic, matching ALT's intent (a "worth compacting?" hint), not
    a precise page count.
    """
    size = await _db_size_bytes(session)
    row = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(n_live_tup), 0) AS live, "
                "COALESCE(SUM(n_dead_tup), 0) AS dead FROM pg_stat_user_tables"
            )
        )
    ).one()
    live, dead = int(row.live), int(row.dead)
    total = live + dead
    reclaimable = int(size * dead / total) if total else 0
    return {
        "size_bytes": size,
        "live_tuples": live,
        "dead_tuples": dead,
        "reclaimable_bytes": reclaimable,
    }


async def optimize_database(session: AsyncSession) -> dict[str, int]:
    """Run ``VACUUM (ANALYZE)`` and report the size before/after.

    VACUUM cannot run inside a transaction block, so the request session's open
    read transaction is rolled back first and the statement runs on an AUTOCOMMIT
    checkout of the same connection. Plain (non-FULL) VACUUM does not shrink the
    file, so ``reclaimed_bytes`` is typically 0 (see module docstring).
    """
    before = await _db_size_bytes(session)
    await session.rollback()  # end the read txn so AUTOCOMMIT applies to VACUUM
    conn = await session.connection(
        execution_options={"isolation_level": "AUTOCOMMIT"}
    )
    await conn.execute(text("VACUUM (ANALYZE)"))
    after = await _db_size_bytes(session)
    return {
        "before_bytes": before,
        "after_bytes": after,
        "reclaimed_bytes": max(0, before - after),
    }
