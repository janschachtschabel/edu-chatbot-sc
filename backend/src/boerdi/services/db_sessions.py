"""Session, message and memory persistence (Postgres, SQLAlchemy-async).

pg-**REWRITE** of ALT ``app/services/db_sessions.py`` (213 Z.). The function
names and the dict shapes callers see are ALT-identical; the storage layer is
rewritten for Postgres and a request-scoped ``AsyncSession`` (spec rule 3/4: no
module-global engine, DB access stays in the service layer). The already-built
``assess`` node injects ``get_memory`` here as its ``memory_fetch`` seam.

Deviations from ALT, each forced by the SQLite→Postgres move:

* ``session: AsyncSession`` is injected as the first argument.
* ``messages.cards``/``debug`` are native ``jsonb`` — stored and read back as
  list/dict, never ``json.dumps``-ed. ALT's corrupt-JSON degrade in
  ``get_messages`` is dropped: Postgres cannot hold invalid JSON, so there is
  nothing to degrade.
* ``get_or_create_session`` returns ``entities``/``signal_history``/``tour_state``
  already parsed (dict/list) and the timestamps as ``datetime`` — ALT returned
  the raw sqlite TEXT. The R4 turn-setup consumes this parsed shape.
* ``save_memory`` upserts via ``ON CONFLICT (session_id, key, memory_type)`` —
  exactly the UNIQUE constraint ALT added in its A3 migration so its
  ``INSERT OR REPLACE`` could finally replace instead of duplicate.
* ``get_or_create_session`` idempotency via ``ON CONFLICT (session_id) DO
  NOTHING`` + re-select — ALT's ``INSERT OR IGNORE`` TOCTOU fix, same result on
  a concurrent first request.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import (
    ChatMessage,
    ChatSession,
    MemoryItem,
    QualityLog,
    SafetyLog,
)

logger = logging.getLogger(__name__)


def _session_to_dict(obj: ChatSession) -> dict[str, Any]:
    """All session columns as a plain dict (JSONB parsed, timestamps native)."""
    return {
        "session_id": obj.session_id,
        "persona_id": obj.persona_id,
        "state_id": obj.state_id,
        "entities": obj.entities,
        "signal_history": obj.signal_history,
        "turn_count": obj.turn_count,
        "tour_state": obj.tour_state,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }


# ── Session helpers ─────────────────────────────────────────────

async def get_or_create_session(session: AsyncSession, session_id: str) -> dict[str, Any]:
    """Return the session row, creating it with schema defaults if absent.

    Hot path (existing session) is a single primary-key lookup. On a miss the
    insert is ``ON CONFLICT DO NOTHING`` so two concurrent first-requests for the
    same id both succeed — the loser is ignored, not an IntegrityError — and the
    re-select then returns the identical default row to both (ALT TOCTOU fix).
    """
    obj = await session.get(ChatSession, session_id)
    if obj is None:
        await session.execute(
            pg_insert(ChatSession)
            .values(session_id=session_id)
            .on_conflict_do_nothing(index_elements=["session_id"])
        )
        await session.commit()
        obj = await session.get(ChatSession, session_id)
    return _session_to_dict(obj)


async def update_session(session: AsyncSession, session_id: str, **kwargs: Any) -> None:
    """Patch the given session columns and bump ``updated_at`` to now."""
    await session.execute(
        update(ChatSession)
        .where(ChatSession.session_id == session_id)
        .values(**kwargs, updated_at=func.now())
    )
    await session.commit()


# ── Message helpers ────────────────────────────────────────────

async def save_message(
    session: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    cards: list | None = None,
    debug: dict | None = None,
) -> int:
    """Append one chat message. ``cards``/``debug`` land as native JSONB.

    Returns the new row's id so a caller can complete the row afterwards with
    ``finalize_message`` — see the F-6 note there.
    """
    obj = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        cards=cards or [],
        debug=debug or {},
    )
    session.add(obj)
    await session.commit()
    return obj.id


async def finalize_message(
    session: AsyncSession, message_id: int, *, cards: list, debug: dict
) -> bool:
    """Overwrite ``cards``/``debug`` of an already-saved message. Returns whether
    the update went through.

    Why a second write instead of saving once at the end (audit 2026-08-12, F-6):
    the assistant message is stored before the card group-trim and before the M16
    resolver runs, and that resolver is not wrapped in a ``try/except``. Saving
    only afterwards would mean an M16 failure loses the WHOLE turn, which is
    worse than the display mismatch it fixes. So the first write keeps the turn
    safe and this one aligns what ``GET /messages`` replays on restore.

    Never raises: the message is already on disk. A failed completion may cost
    the restore view, never the turn — and it leaves the shared session usable
    (F-1).
    """
    try:
        await session.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(cards=cards, debug=debug)
        )
        await session.commit()
        return True
    except Exception:
        logger.warning(
            "message %s could not be finalized; the restore view keeps the "
            "pre-trim state", message_id, exc_info=True,
        )
        try:
            await session.rollback()
        except Exception:
            logger.debug("finalize: rollback failed too", exc_info=True)
        return False


async def get_messages(session: AsyncSession, session_id: str, limit: int = 50) -> list[dict]:
    """Message history for a session, newest LAST, ``cards``/``debug`` parsed.

    The frontend needs ``cards`` to re-render bot answers on session restore; the
    Studio uses ``debug`` for per-turn pattern display. Selects newest-first with
    the LIMIT, then reverses — so the newest ``limit`` messages come back in
    chronological order (ALT semantics).
    """
    stmt = (
        select(
            ChatMessage.id,
            ChatMessage.role,
            ChatMessage.content,
            ChatMessage.cards,
            ChatMessage.debug,
            ChatMessage.created_at,
        )
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "cards": r.cards if r.cards is not None else [],
            "debug": r.debug if r.debug is not None else {},
            "created_at": r.created_at,
        }
        for r in reversed(rows)
    ]


async def delete_messages_for_session(session: AsyncSession, session_id: str) -> int:
    """Delete only the chat messages for a session (session row + memory +
    quality/safety logs stay). Returns the number of rows removed."""
    res = await session.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    await session.commit()
    return res.rowcount or 0


async def delete_session(session: AsyncSession, session_id: str) -> dict[str, int]:
    """Fully delete a session and every dependent row, counts per table.

    ``messages``/``memory`` would cascade via their FK, but ``safety_logs`` and
    ``quality_logs`` carry only a plain ``session_id`` column (no FK) — so every
    table is deleted explicitly, both to clear the log rows and to report an
    accurate per-table count. A missing session is a safe no-op (all counts 0).
    """
    counts: dict[str, int] = {}
    for model, name in (
        (ChatMessage, "messages"),
        (MemoryItem, "memory"),
        (QualityLog, "quality_logs"),
        (SafetyLog, "safety_logs"),
    ):
        res = await session.execute(delete(model).where(model.session_id == session_id))
        counts[name] = res.rowcount or 0
    res = await session.execute(
        delete(ChatSession).where(ChatSession.session_id == session_id)
    )
    counts["sessions"] = res.rowcount or 0
    await session.commit()
    return counts


async def purge_all(
    session: AsyncSession,
    messages: bool = True,
    memory: bool = True,
    quality_logs: bool = True,
    safety_logs: bool = False,
    sessions: bool = False,
) -> dict[str, int]:
    """Wholesale-delete chat-related tables, one opt-in flag each.

    ``safety_logs`` and ``sessions`` default to False: safety logs are
    legally/operationally sensitive, and wiping ``sessions`` disconnects active
    users mid-conversation. ``sessions=True`` forces ``messages``+``memory`` (ALT
    A5): those are the session's FK children, so their counts must be reported
    alongside — and the cascade would remove them regardless.
    """
    if sessions:
        messages = True
        memory = True
    counts: dict[str, int] = {}
    if messages:
        counts["messages"] = (await session.execute(delete(ChatMessage))).rowcount or 0
    if memory:
        counts["memory"] = (await session.execute(delete(MemoryItem))).rowcount or 0
    if quality_logs:
        counts["quality_logs"] = (await session.execute(delete(QualityLog))).rowcount or 0
    if safety_logs:
        counts["safety_logs"] = (await session.execute(delete(SafetyLog))).rowcount or 0
    if sessions:
        counts["sessions"] = (await session.execute(delete(ChatSession))).rowcount or 0
    await session.commit()
    return counts


# ── Memory helpers ─────────────────────────────────────────────

async def save_memory(
    session: AsyncSession,
    session_id: str,
    key: str,
    value: str,
    memory_type: str = "short",
) -> None:
    """Upsert one memory item, keyed on ``(session_id, key, memory_type)``.

    A repeat write of the same triple replaces the value (and refreshes the
    stamp) instead of piling up rows — the behaviour ALT's UNIQUE index gave its
    ``INSERT OR REPLACE``. A different ``memory_type`` for the same key is a
    distinct row.
    """
    stmt = pg_insert(MemoryItem).values(
        session_id=session_id, key=key, value=value, memory_type=memory_type
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["session_id", "key", "memory_type"],
        set_={"value": stmt.excluded.value, "created_at": func.now()},
    )
    await session.execute(stmt)
    await session.commit()


async def get_memory(
    session: AsyncSession, session_id: str, memory_type: str | None = None
) -> list[dict]:
    """Memory items for a session as ``{key, value, memory_type}`` dicts,
    optionally filtered to one ``memory_type``.

    The ``assess`` node deliberately swallows a failure here and carries on with
    no memories. For that to stay harmless the session must remain usable: a
    failed statement leaves the transaction aborted, and every later write of the
    SAME turn would then fail too — the turn's state and the assistant reply
    would be lost to a transient read blip (audit 2026-08-12, F-1).

    A plain ``rollback()`` is right here, unlike in ``usage_store`` where a
    SAVEPOINT is used: this read holds no pending write of its own, and the
    services that ran before it commit their own work.
    """
    stmt = select(
        MemoryItem.key, MemoryItem.value, MemoryItem.memory_type
    ).where(MemoryItem.session_id == session_id)
    if memory_type:
        stmt = stmt.where(MemoryItem.memory_type == memory_type)
    try:
        rows = (await session.execute(stmt)).all()
    except Exception:
        await session.rollback()
        raise
    return [
        {"key": r.key, "value": r.value, "memory_type": r.memory_type} for r in rows
    ]
