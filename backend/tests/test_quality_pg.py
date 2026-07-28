"""P7: quality analytics against the REAL Postgres — proof of the sqlite→jsonb
rewrite.

Rows are seeded through the real writer (``obs.quality_events.log_quality_event``)
so the jsonb payload the analytics read is exactly what production writes. Each
scenario runs against a freshly-truncated throwaway DB. These pins are where the
``data->>'key'`` casts, the ``degradation`` boolean, the ``entities='{}'`` jsonb
compare and the ``missing_slots`` grouping are actually verified — a fake cannot.
Skipped unless the Compose-Postgres is up.

Assertions mirror ALT ``tests/test_database_service.py`` (the analytics block),
with the NEU deltas made explicit: ``created_at`` comes back as ISO text and the
flat log row carries ``debug_json`` (not ``debug``) + an int ``degradation``.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p7_quality_test"


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
    """Run ``fn(session)`` against a freshly truncated quality_logs table."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(text("TRUNCATE quality_logs RESTART IDENTITY"))
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


async def _seed(
    session, *, session_id="s", turn=1, message="msg", persona="P-LEH", intent="I01",
    pattern="M04 (Fakten-Bulletin)", conf=0.9, state="S1", scores=None, p3=None,
    entities=None, eliminated=None, response_length=0,
):
    """Write one quality row via the real writer (ALT ``_log_quality`` shape)."""
    from boerdi.obs.quality_events import log_quality_event

    debug = {
        "persona": persona, "intent": intent, "pattern": pattern,
        "confidence": conf, "state": state, "turn_type": "frage",
        "signals": [], "entities": entities if entities is not None else {},
        "phase2_scores": scores or {}, "phase3_modulations": p3 or {},
        "tools_called": [], "outcomes": [], "phase1_eliminated": eliminated or [],
    }
    await log_quality_event(
        session, session_id, message, turn, debug, response_length=response_length
    )


# ── stats: the broad cast/boolean/jsonb-compare proof ────────────────────
def test_stats_aggregates_distributions_and_rates(test_db) -> None:
    from boerdi.services.quality_analytics import get_quality_stats

    async def scenario(session):
        await _seed(session, session_id="s-a", pattern="M04 (A)", intent="I01", conf=0.8,
                    scores={"M04": 0.5, "M15": 0.499},  # gap 0.001 → tight race
                    entities={}, response_length=10)
        await _seed(session, session_id="s-b", pattern="M15 (B)", intent="I02", conf=0.6,
                    scores={},  # runner_up '' → NOT a tight race
                    entities={"thema": "wasser"},
                    p3={"degradation": True, "missing_slots": ["thema"]},
                    response_length=20)
        return await get_quality_stats(session)

    stats = _run(scenario)
    assert stats["total_turns"] == 2
    assert stats["pattern_distribution"] == {"M04": 1, "M15": 1}
    assert stats["intent_distribution"] == {"I01": 1, "I02": 1}
    assert stats["avg_confidence"] == 0.7
    assert stats["avg_score_gap"] == 0.0005
    assert stats["degradation_rate"] == 0.5   # (data->>'degradation')::boolean
    assert stats["tight_races"] == 1
    assert stats["empty_entity_rate"] == 0.5  # data->'entities' = '{}'::jsonb
    assert stats["avg_response_length"] == 15.0


def test_stats_empty_db_returns_zero_defaults(test_db) -> None:
    from boerdi.services.quality_analytics import get_quality_stats

    stats = _run(lambda s: get_quality_stats(s, scope="production"))
    assert stats["total_turns"] == 0
    assert stats["avg_confidence"] == 0
    assert stats["degradation_rate"] == 0.0   # divide by max(total, 1)
    assert stats["avg_response_length"] == 0
    assert stats["scope"] == "production"


# ── logs: flatten shape + scope/prefix filters + newest-first ────────────
def test_logs_flatten_shape(test_db) -> None:
    from boerdi.services.quality_analytics import get_quality_logs

    async def scenario(session):
        await _seed(session, session_id="s", pattern="M04 (Fakten-Bulletin)", intent="I01",
                    conf=0.9, entities={"thema": "x"},
                    p3={"degradation": True, "missing_slots": ["thema"]})
        return (await get_quality_logs(session, session_id="s"))[0]

    row = _run(scenario)
    # promoted columns
    assert row["id"] > 0 and row["session_id"] == "s"
    assert row["pattern_id"] == "M04"
    assert row["intent_id"] == "I01"
    # folded metrics come back flat (ALT column names)
    assert row["pattern_label"] == "M04 (Fakten-Bulletin)"
    assert row["final_confidence"] == 0.9
    assert row["entities"] == {"thema": "x"}
    assert row["missing_slots"] == ["thema"]
    # NEU deltas: debug is exposed as debug_json; degradation coerced to int
    assert "debug" not in row
    assert row["debug_json"]["pattern"] == "M04 (Fakten-Bulletin)"
    assert row["degradation"] == 1
    # timestamptz serialised to ISO text (ALT returned sqlite TEXT)
    assert isinstance(row["created_at"], str)


def test_logs_scope_prefix_and_newest_first(test_db) -> None:
    from boerdi.services.quality_analytics import get_quality_logs

    async def scenario(session):
        await _seed(session, session_id="prod-1", pattern="M04 (A)", intent="I01")
        await _seed(session, session_id="eval-1", pattern="M15 (B)", intent="I02")
        await _seed(session, session_id="prod-1", pattern="M15 (B)", intent="I02")
        return (
            await get_quality_logs(session, scope="production"),
            await get_quality_logs(session, scope="eval"),
            await get_quality_logs(session, pattern_id="M15"),
            await get_quality_logs(session, intent_id="I01"),
            await get_quality_logs(session),
        )

    prod, ev, m15, i01, allrows = _run(scenario)
    assert len(prod) == 2
    assert [r["session_id"] for r in ev] == ["eval-1"]
    assert len(m15) == 2          # pattern_id LIKE 'M15%'
    assert len(i01) == 1          # intent_id LIKE 'I01%'
    assert allrows[0]["id"] > allrows[-1]["id"]  # newest id first


# ── state transitions ────────────────────────────────────────────────────
def test_state_transitions_counts_pairs_and_min_count(test_db) -> None:
    from boerdi.services.quality_analytics import get_state_transitions

    async def scenario(session):
        for turn, st in ((1, "S1"), (2, "S2"), (3, "S2")):
            await _seed(session, session_id="A", turn=turn, state=st)
        for turn, st in ((1, "S1"), (2, "S2")):
            await _seed(session, session_id="B", turn=turn, state=st)
        return await get_state_transitions(session), await get_state_transitions(
            session, min_count=2
        )

    out, out2 = _run(scenario)
    assert out["total_turns"] == 5
    assert out["state_distribution"] == {"S2": 3, "S1": 2}
    assert out["transitions"][0] == {"prev": "S1", "next": "S2", "count": 2}
    assert {"prev": "S2", "next": "S2", "count": 1} in out["transitions"]
    assert out["total_transitions"] == 3
    assert out2["transitions"] == [{"prev": "S1", "next": "S2", "count": 2}]
    assert out2["total_transitions"] == 2


def test_state_transitions_days_filter_excludes_old_rows(test_db) -> None:
    from boerdi.services.quality_analytics import get_state_transitions

    async def scenario(session):
        await _seed(session, session_id="neu", turn=1, state="S1")
        # an old row via raw insert (created_at 10y ago), state S9
        await session.execute(
            text(
                "INSERT INTO quality_logs (session_id, data, created_at) "
                "VALUES ('alt', CAST(:data AS jsonb), now() - CAST('3650 days' AS interval))"
            ),
            {"data": json.dumps({"state_id": "S9", "turn_count": 1})},
        )
        await session.commit()
        return (
            await get_state_transitions(session, days=30),
            await get_state_transitions(session, days=0),
        )

    out30, out_all = _run(scenario)
    assert "S9" not in out30["state_distribution"]
    assert out30["total_turns"] == 1
    assert "S9" in out_all["state_distribution"]  # days=0 → no time filter


# ── routing matrix ───────────────────────────────────────────────────────
def test_routing_matrix_top_share_alternatives_min_count(test_db) -> None:
    from boerdi.services.quality_analytics import get_routing_matrix

    async def scenario(session):
        for _ in range(3):
            await _seed(session, persona="P-LEH", intent="I01", pattern="M04 (A)")
        await _seed(session, persona="P-LEH", intent="I01", pattern="M15 (B)")
        await _seed(session, persona="P-SCH", intent="I02", pattern="M09 (C)")
        await _seed(session, persona="", intent="I01", pattern="M04 (A)")  # empty → no cell
        return await get_routing_matrix(session), await get_routing_matrix(session, min_count=2)

    out, out2 = _run(scenario)
    assert out["total_turns"] == 6  # counts ALL scope rows, even persona-less
    assert len(out["cells"]) == 2
    cell = next(c for c in out["cells"] if c["persona_id"] == "P-LEH")
    assert cell["intent_id"] == "I01"
    assert cell["top_pattern"] == "M04"
    assert cell["top_pattern_count"] == 3
    assert cell["total_count"] == 4
    assert cell["share"] == 0.75
    assert cell["alternatives"] == [{"pattern_id": "M15", "count": 1}]
    assert [c["persona_id"] for c in out2["cells"]] == ["P-LEH"]


# ── degradation breakdown (missing_slots grouping + example join) ────────
def test_degradation_breakdown_groups_and_examples(test_db) -> None:
    from boerdi.services.quality_analytics import get_degradation_breakdown

    async def scenario(session):
        for msg in ("m1", "m2"):
            await _seed(session, message=msg, pattern="M04 (A)",
                        p3={"degradation": True, "missing_slots": ["thema"]})
        await _seed(session, message="m3", pattern="M04 (A)",
                    p3={"degradation": True, "missing_slots": ["thema", "stufe"]})
        await _seed(session, message="ohne", pattern="M04 (A)")  # no degradation
        return await get_degradation_breakdown(session)

    out = _run(scenario)
    assert out["total"] == 3
    assert out["groups"][0]["missing_slots"] == ["thema"]
    assert out["groups"][0]["count"] == 2
    assert out["groups"][0]["example_message"] == "m2"  # MAX(id) of the group
    assert out["groups"][1]["missing_slots"] == ["thema", "stufe"]
    assert all(g["pattern_id"] == "M04" for g in out["groups"])


# ── empty entities breakdown ─────────────────────────────────────────────
def test_empty_entities_breakdown_groups(test_db) -> None:
    from boerdi.services.quality_analytics import get_empty_entities_breakdown

    async def scenario(session):
        for msg in ("e1", "e2"):
            await _seed(session, message=msg, intent="I01", pattern="M04 (A)", entities={})
        await _seed(session, message="e3", intent="I02", pattern="M15 (B)", entities={})
        await _seed(session, message="voll", intent="I01", pattern="M04 (A)",
                    entities={"thema": "x"})
        return await get_empty_entities_breakdown(session)

    out = _run(scenario)
    assert out["total"] == 3
    assert (out["groups"][0]["intent_id"], out["groups"][0]["count"]) == ("I01", 2)
    assert out["groups"][0]["example_message"] == "e2"
    assert (out["groups"][1]["intent_id"], out["groups"][1]["count"]) == ("I02", 1)


# ── low confidence (float-cast ordering + bounds) ────────────────────────
def test_low_confidence_turns_bounds_and_order(test_db) -> None:
    from boerdi.services.quality_analytics import get_low_confidence_turns

    async def scenario(session):
        await _seed(session, message="mittel", conf=0.5)
        await _seed(session, message="tief", conf=0.3)
        await _seed(session, message="null", conf=0.0)    # > 0 filter excludes
        await _seed(session, message="sicher", conf=0.9)  # >= max excludes
        return await get_low_confidence_turns(session)

    out = _run(scenario)
    assert [t["message"] for t in out["turns"]] == ["tief", "mittel"]  # confidence ASC
    assert out["total"] == 2
    assert out["max_confidence"] == 0.60


# ── tight races (winner/runner_up pairs + avg_gap) ───────────────────────
def test_tight_races_breakdown_pairs_avg_gap(test_db) -> None:
    from boerdi.services.quality_analytics import get_tight_races_breakdown

    async def scenario(session):
        for msg in ("t1", "t2"):
            await _seed(session, message=msg, pattern="M04 (A)",
                        scores={"M04": 0.5, "M15": 0.499})   # gap 0.001
        await _seed(session, message="klar", pattern="M04 (A)",
                    scores={"M04": 0.9, "M15": 0.7})          # gap 0.2 → excluded
        return await get_tight_races_breakdown(session)

    out = _run(scenario)
    assert out["total_tight"] == 2
    assert len(out["pairs"]) == 1
    pair = out["pairs"][0]
    assert (pair["winner"], pair["runner_up"], pair["count"]) == ("M04", "M15", 2)
    assert pair["avg_gap"] == 0.001
    assert pair["example_message"] == "t2"  # MAX(id) of the pair
    # A real measurement carries no excuse.
    assert "unavailable_reason" not in out


# The rows above are hand-built with TWO scored candidates. The live engine
# cannot produce that: ``select_pattern`` returns ``{winner.id: 1.0}`` at all
# three of its return sites (Welle E v4 dropped the score phase), so
# ``phase2_runner_up`` is '' on every row a real turn writes. These three tests
# pin that the endpoint says so instead of reporting a confident 0.
def test_tight_races_reports_metric_unavailable_on_live_shaped_rows(test_db) -> None:
    from boerdi.services.quality_analytics import get_tight_races_breakdown

    async def scenario(session):
        await _seed(session, message="a", pattern="M04 (A)", scores={"M04": 1.0})
        await _seed(session, message="b", pattern="M15 (B)", scores={"M15": 1.0})
        return await get_tight_races_breakdown(session)

    out = _run(scenario)
    assert out["total_tight"] == 0 and out["pairs"] == []
    assert out["scanned"] == 2
    assert "phase2_scores" in out["unavailable_reason"]


def test_tight_races_zero_stays_a_measurement_when_runner_ups_exist(test_db) -> None:
    from boerdi.services.quality_analytics import get_tight_races_breakdown

    async def scenario(session):
        # Runner-up present, but the gap is far above the threshold → the 0 is
        # a genuine result and must NOT be explained away.
        await _seed(session, message="klar", pattern="M04 (A)",
                    scores={"M04": 0.9, "M15": 0.2})
        return await get_tight_races_breakdown(session)

    out = _run(scenario)
    assert out["total_tight"] == 0
    assert "unavailable_reason" not in out and "scanned" not in out


def test_tight_races_empty_table_needs_no_excuse(test_db) -> None:
    from boerdi.services.quality_analytics import get_tight_races_breakdown

    out = _run(lambda session: get_tight_races_breakdown(session))
    assert out["total_tight"] == 0
    assert "unavailable_reason" not in out


# ── delete + clear ───────────────────────────────────────────────────────
def test_delete_and_clear(test_db) -> None:
    from boerdi.services.quality_analytics import (
        clear_quality_logs,
        delete_quality_log,
        get_quality_logs,
    )

    async def delete_scenario(session):
        await _seed(session, session_id="s")
        log_id = (await get_quality_logs(session, session_id="s"))[0]["id"]
        return await delete_quality_log(session, log_id), await delete_quality_log(session, log_id)

    async def clear_scenario(session):
        await _seed(session, session_id="eval-1", pattern="M04 (A)")
        await _seed(session, session_id="prod-1", pattern="M04 (A)")
        await _seed(session, session_id="prod-2", pattern="M15 (B)")
        n_eval = await clear_quality_logs(session, scope="eval")
        n_m15 = await clear_quality_logs(session, pattern_id="M15")
        n_all = await clear_quality_logs(session)  # no filter + scope all → the rest
        return n_eval, n_m15, n_all, await get_quality_logs(session)

    assert _run(delete_scenario) == (1, 0)
    n_eval, n_m15, n_all, remaining = _run(clear_scenario)
    assert (n_eval, n_m15, n_all) == (1, 1, 1)
    assert remaining == []
