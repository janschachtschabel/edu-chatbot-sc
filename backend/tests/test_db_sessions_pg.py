"""P3/R3a: session + message + memory persistence against the REAL Postgres.

Mirrors ``test_rag_admin_pg.py``: a fresh migrated throwaway DB, every scenario
runs against a truncated-then-used session. These pins prove what a fake cannot —
that ``ON CONFLICT`` really upserts memory, that the FK ``CASCADE`` and the
explicit deletes really clear a session's dependents, that ``cards``/``debug``
round-trip as native JSONB (list/dict), and that message order + limit hold.
Skipped unless the Compose-Postgres is up.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p3_dbsessions_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


def _run(fn):
    """Run ``fn(session)`` against a freshly truncated database."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text(
                        "TRUNCATE sessions, messages, memory, safety_logs, quality_logs "
                        "RESTART IDENTITY CASCADE"
                    )
                )
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


async def _count(session, table: str, where: str = "TRUE") -> int:
    return (
        await session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"))
    ).scalar_one()


def test_get_or_create_is_idempotent_and_returns_schema_defaults(test_db) -> None:
    from boerdi.services.db_sessions import get_or_create_session

    async def scenario(session):
        first = await get_or_create_session(session, "bb-1")
        second = await get_or_create_session(session, "bb-1")  # must not duplicate
        return first, second, await _count(session, "sessions")

    first, second, rows = _run(scenario)
    assert rows == 1  # INSERT ... ON CONFLICT DO NOTHING — single row
    assert first["session_id"] == "bb-1" == second["session_id"]
    # DB defaults come back parsed (JSONB → dict/list), not as TEXT strings.
    assert first["state_id"] == "S1"
    assert first["persona_id"] == ""
    assert first["turn_count"] == 0
    assert first["entities"] == {}
    assert first["signal_history"] == []
    assert first["tour_state"] == {}
    assert first["created_at"] is not None and first["updated_at"] is not None


def test_save_and_get_messages_roundtrip_order_limit_and_jsonb(test_db) -> None:
    from boerdi.services.db_sessions import (
        get_messages,
        get_or_create_session,
        save_message,
    )

    async def scenario(session):
        await get_or_create_session(session, "bb-2")
        await save_message(session, "bb-2", "user", "hallo")
        await save_message(
            session, "bb-2", "assistant", "hi",
            cards=[{"id": "c1"}], debug={"pattern": "M04"},
        )
        await save_message(session, "bb-2", "user", "und weiter?")
        all_msgs = await get_messages(session, "bb-2")
        last_two = await get_messages(session, "bb-2", limit=2)
        return all_msgs, last_two

    all_msgs, last_two = _run(scenario)
    # newest LAST (ALT order): insertion order preserved on the way out
    assert [m["content"] for m in all_msgs] == ["hallo", "hi", "und weiter?"]
    assert [m["role"] for m in all_msgs] == ["user", "assistant", "user"]
    # cards/debug are native JSONB — parsed structures, not JSON strings
    assert all_msgs[1]["cards"] == [{"id": "c1"}]
    assert all_msgs[1]["debug"] == {"pattern": "M04"}
    # a message with no cards/debug degrades to the empty containers
    assert all_msgs[0]["cards"] == [] and all_msgs[0]["debug"] == {}
    # LIMIT keeps the newest N, still returned oldest→newest
    assert [m["content"] for m in last_two] == ["hi", "und weiter?"]


def test_save_memory_upserts_on_key_and_type(test_db) -> None:
    from boerdi.services.db_sessions import (
        get_memory,
        get_or_create_session,
        save_memory,
    )

    async def scenario(session):
        await get_or_create_session(session, "bb-3")
        await save_memory(session, "bb-3", "name", "Anna", "short")
        await save_memory(session, "bb-3", "name", "Berta", "short")  # replaces Anna
        await save_memory(session, "bb-3", "name", "Anna-long", "long")  # distinct row
        await save_memory(session, "bb-3", "fach", "Bio", "short")
        rows = await _count(session, "memory")
        return (
            rows,
            await get_memory(session, "bb-3"),
            await get_memory(session, "bb-3", "short"),
        )

    rows, all_mem, short_mem = _run(scenario)
    # (name,short) replaced in place; (name,long) + (fach,short) added → 3 rows
    assert rows == 3
    by_key_type = {(m["key"], m["memory_type"]): m["value"] for m in all_mem}
    assert by_key_type[("name", "short")] == "Berta"  # latest write wins
    assert by_key_type[("name", "long")] == "Anna-long"
    assert by_key_type[("fach", "short")] == "Bio"
    # memory_type filter isolates 'short'
    assert {m["value"] for m in short_mem} == {"Berta", "Bio"}


def test_update_session_sets_fields(test_db) -> None:
    from boerdi.services.db_sessions import get_or_create_session, update_session

    async def scenario(session):
        await get_or_create_session(session, "bb-4")
        await update_session(session, "bb-4", persona_id="P-AND", state_id="S3", turn_count=2)
        return await get_or_create_session(session, "bb-4")

    out = _run(scenario)
    assert out["persona_id"] == "P-AND"
    assert out["state_id"] == "S3"
    assert out["turn_count"] == 2


def test_delete_session_clears_all_dependents_and_counts(test_db) -> None:
    from boerdi.services.db_sessions import (
        delete_session,
        get_or_create_session,
        save_memory,
        save_message,
    )

    async def scenario(session):
        await get_or_create_session(session, "bb-5")
        await get_or_create_session(session, "bb-keep")  # bystander, untouched
        await save_message(session, "bb-5", "user", "x")
        await save_message(session, "bb-5", "assistant", "y")
        await save_memory(session, "bb-5", "name", "Anna")
        await save_message(session, "bb-keep", "user", "z")
        # safety_logs/quality_logs have no FK to sessions — delete_session must
        # clear them explicitly. Their writers are R3b, so seed raw rows here.
        await session.execute(
            text("INSERT INTO safety_logs (session_id, data) VALUES ('bb-5', '{}')")
        )
        await session.execute(
            text("INSERT INTO quality_logs (session_id, data) VALUES ('bb-5', '{}')")
        )
        await session.commit()
        counts = await delete_session(session, "bb-5")
        return (
            counts,
            await _count(session, "sessions"),
            await _count(session, "messages", "session_id = 'bb-keep'"),
        )

    counts, sessions_left, keep_msgs = _run(scenario)
    assert counts == {
        "messages": 2,
        "memory": 1,
        "quality_logs": 1,
        "safety_logs": 1,
        "sessions": 1,
    }
    assert sessions_left == 1  # only bb-keep remains
    assert keep_msgs == 1  # bystander session fully intact


def test_purge_all_default_and_sessions_flag_forcing(test_db) -> None:
    from boerdi.services.db_sessions import (
        get_or_create_session,
        purge_all,
        save_memory,
        save_message,
    )

    async def seed(session):
        for sid in ("bb-a", "bb-b"):
            await get_or_create_session(session, sid)
            await save_message(session, sid, "user", "x")
            await save_memory(session, sid, "k", "v")
        await session.execute(
            text("INSERT INTO safety_logs (session_id, data) VALUES ('bb-a', '{}')")
        )
        await session.commit()

    def _default(session):
        async def go(s):
            await seed(s)
            counts = await purge_all(s)  # messages+memory+quality_logs, NOT safety/sessions
            return (
                counts,
                await _count(s, "messages"),
                await _count(s, "memory"),
                await _count(s, "safety_logs"),
                await _count(s, "sessions"),
            )

        return go(session)

    def _sessions_flag(session):
        async def go(s):
            await seed(s)
            counts = await purge_all(s, sessions=True)  # forces messages+memory
            return counts, await _count(s, "sessions"), await _count(s, "messages")

        return go(session)

    counts, msgs, mem, safety, sessions = _run(_default)
    assert (counts["messages"], counts["memory"]) == (2, 2)
    assert "safety_logs" not in counts and "sessions" not in counts
    assert (msgs, mem) == (0, 0)
    assert safety == 1  # default keeps safety logs
    assert sessions == 2  # default keeps session rows

    counts2, sessions_left, msgs_left = _run(_sessions_flag)
    # sessions=True forces messages+memory deletion (A5 count-parity)
    assert counts2["sessions"] == 2
    assert counts2["messages"] == 2 and counts2["memory"] == 2
    assert (sessions_left, msgs_left) == (0, 0)
