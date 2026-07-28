"""P7: ``get_safety_logs`` against the REAL Postgres.

Mirrors ``test_db_sessions_pg.py``: a fresh migrated throwaway DB, every scenario
runs against a truncated-then-used ``safety_logs``. These pins prove what the
offline router fake cannot — that the ``data`` jsonb round-trips back into ALT's
flat 15-key shape (in particular ``categories_json`` sourced from
``data["categories"]``, and ``escalated``/``rate_limited`` surfaced as ``0``/``1``
ints), that ``risk_min``/``session_id`` filter correctly, and that rows come back
newest-first under ``LIMIT``. Rows are seeded through the real writer
(``obs/quality_events.log_safety_event``) so the write→read contract is exercised
end to end. Skipped unless the Compose-Postgres is up.
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

_DB = "boerdi_p7_safety_test"

_ALT_KEYS = {
    "id", "session_id", "ip", "risk_level", "stages_run", "reasons",
    "legal_flags", "flagged_categories", "blocked_tools", "enforced_pattern",
    "escalated", "rate_limited", "message", "categories_json", "created_at",
}


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
    """Run ``fn(session)`` against a freshly truncated ``safety_logs``."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text("TRUNCATE safety_logs RESTART IDENTITY CASCADE")
                )
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def test_row_shape_round_trips_alt_keys_including_categories_json(test_db) -> None:
    from boerdi.obs.quality_events import log_safety_event
    from boerdi.services.safety_logs_query import get_safety_logs

    decision = {
        "risk_level": "high",
        "stages_run": ["regex", "llm_legal"],
        "reasons": ["crisis_signal_detected", "legal:jugendschutz 0.90"],
        "legal_flags": ["jugendschutz", "strafrecht"],
        "flagged_categories": ["self_harm"],
        "blocked_tools": ["search_wlo_content", "get_collection_contents"],
        "enforced_pattern": "M01",
        "escalated": True,
        "categories": {"self_harm": 0.91, "violence": 0.2},
    }

    async def scenario(session):
        await log_safety_event(
            session, "sess-x", "ich will mich umbringen", decision,
            ip="1.2.3.4", rate_limited=True,
        )
        return await get_safety_logs(session)

    rows = _run(scenario)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == _ALT_KEYS  # exact ALT key set, no more, no fewer
    assert row["session_id"] == "sess-x"
    assert row["ip"] == "1.2.3.4"
    assert row["risk_level"] == "high"
    assert row["stages_run"] == ["regex", "llm_legal"]
    assert row["reasons"] == ["crisis_signal_detected", "legal:jugendschutz 0.90"]
    assert row["legal_flags"] == ["jugendschutz", "strafrecht"]
    assert row["flagged_categories"] == ["self_harm"]
    assert row["blocked_tools"] == ["search_wlo_content", "get_collection_contents"]
    assert row["enforced_pattern"] == "M01"
    # native bool in ``data`` → ALT's int wire shape
    assert row["escalated"] == 1
    assert row["rate_limited"] == 1
    assert row["message"] == "ich will mich umbringen"
    # data["categories"] surfaces under ALT's leaked column name
    assert row["categories_json"] == {"self_harm": 0.91, "violence": 0.2}
    assert isinstance(row["id"], int)
    assert isinstance(row["created_at"], str) and row["created_at"]


def test_risk_min_filters_medium_and_high(test_db) -> None:
    from boerdi.obs.quality_events import log_safety_event
    from boerdi.services.safety_logs_query import get_safety_logs

    async def scenario(session):
        for rl in ("low", "medium", "high"):
            await log_safety_event(session, f"s-{rl}", "m", {"risk_level": rl})
        return (
            await get_safety_logs(session),
            await get_safety_logs(session, risk_min="medium"),
            await get_safety_logs(session, risk_min="high"),
        )

    all_rows, medium_up, high_only = _run(scenario)
    assert {r["risk_level"] for r in all_rows} == {"low", "medium", "high"}
    assert {r["risk_level"] for r in medium_up} == {"medium", "high"}
    assert {r["risk_level"] for r in high_only} == {"high"}


def test_session_filter_order_desc_and_limit(test_db) -> None:
    from boerdi.obs.quality_events import log_safety_event
    from boerdi.services.safety_logs_query import get_safety_logs

    async def scenario(session):
        await log_safety_event(session, "s1", "first", {"risk_level": "low"})
        await log_safety_event(session, "s1", "second", {"risk_level": "low"})
        await log_safety_event(session, "s2", "other", {"risk_level": "low"})
        return (
            await get_safety_logs(session, session_id="s1"),
            await get_safety_logs(session, limit=1),
        )

    s1_rows, limited = _run(scenario)
    # session_id isolates s1, newest-first within it (id DESC)
    assert [r["message"] for r in s1_rows] == ["second", "first"]
    # LIMIT keeps the single newest row overall (s2's "other", inserted last)
    assert len(limited) == 1
    assert limited[0]["message"] == "other"
