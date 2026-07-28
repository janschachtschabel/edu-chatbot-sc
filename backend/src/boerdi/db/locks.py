"""Session serialization via Postgres advisory locks (spec §6, improvement V6).

``pg_advisory_xact_lock(hashtext(session_id))`` serializes chat turns on the
SAME session across all replicas; different sessions run fully parallel.
Transaction-scoped: the lock releases automatically at COMMIT/ROLLBACK —
no manual unlock, nothing leaks when a worker dies mid-turn.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


async def acquire_session_lock(
    conn: AsyncConnection | AsyncSession, session_id: str
) -> None:
    """Block until this transaction holds the per-session lock.

    Must be called INSIDE an open transaction (the caller owns begin/commit);
    outside one, Postgres would release the lock immediately.
    """
    await conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:sid))"), {"sid": session_id}
    )
