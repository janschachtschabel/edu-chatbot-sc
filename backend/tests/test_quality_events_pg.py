"""P3/R3b: safety + quality log writers against the REAL Postgres.

Mirrors ``test_db_sessions_pg.py``. These pins prove the pg-rewrite of ALT's
``db_logs.py`` writers: ALT's flat columns are folded into the ``data`` jsonb
with ``risk_level``/``pattern_id``/``intent_id`` promoted, the message is
truncated, and the score maths / dict-vs-object decision handling hold. The
enabled/privacy GATE is a caller concern (R2/R4) and is not exercised here — the
writers are dumb by design. Skipped unless the Compose-Postgres is up.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p3_qualityevents_test"


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
    """Run ``fn(session)`` against a freshly truncated log tables."""
    from boerdi.db.session import make_session_factory

    async def scenario():
        engine = _engine(_DB)
        try:
            factory = make_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text("TRUNCATE safety_logs, quality_logs RESTART IDENTITY")
                )
                await session.commit()
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def _one_safety(session):
    from boerdi.db.models import SafetyLog

    async def go():
        return (await session.execute(select(SafetyLog))).scalars().one()

    return go()


def _one_quality(session):
    from boerdi.db.models import QualityLog

    async def go():
        return (await session.execute(select(QualityLog))).scalars().one()

    return go()


# ── safety writer ───────────────────────────────────────────────

def test_log_safety_event_object_decision_promotes_risk_and_folds_data(test_db) -> None:
    from boerdi.api.schemas_debug import SafetyDecision
    from boerdi.obs.quality_events import log_safety_event

    async def scenario(session):
        dec = SafetyDecision(
            risk_level="high",
            blocked_tools=["search_wlo"],
            enforced_pattern="M01",
            reasons=["crisis term"],
            stages_run=["regex", "llm_legal"],
            categories={"violence": 0.9},
            flagged_categories=["violence"],
            legal_flags=["strafrecht"],
            escalated=True,
        )
        await log_safety_event(session, "bb-s", "böse Nachricht", dec, ip="1.2.3.4")
        return await _one_safety(session)

    row = _run(scenario)
    assert row.session_id == "bb-s"
    assert row.ip == "1.2.3.4"
    assert row.risk_level == "high"  # promoted column
    assert row.data["stages_run"] == ["regex", "llm_legal"]
    assert row.data["reasons"] == ["crisis term"]
    assert row.data["legal_flags"] == ["strafrecht"]
    assert row.data["flagged_categories"] == ["violence"]
    assert row.data["blocked_tools"] == ["search_wlo"]
    assert row.data["enforced_pattern"] == "M01"
    assert row.data["escalated"] is True
    assert row.data["rate_limited"] is False
    assert row.data["message"] == "böse Nachricht"
    assert row.data["categories"] == {"violence": 0.9}


def test_log_safety_event_accepts_dict_decision(test_db) -> None:
    # ALT's direct-action path passed decision as ``model_dump()`` (a dict); ALT's
    # getattr-only writer silently logged defaults. The NEU writer reads it right.
    from boerdi.obs.quality_events import log_safety_event

    async def scenario(session):
        await log_safety_event(
            session, "bb-s2", "x",
            {"risk_level": "medium", "flagged_categories": ["hate"], "escalated": True},
            ip="9.9.9.9",
        )
        return await _one_safety(session)

    row = _run(scenario)
    assert row.risk_level == "medium"
    assert row.data["flagged_categories"] == ["hate"]
    assert row.data["escalated"] is True


def test_log_safety_event_none_decision_is_rate_limit_row(test_db) -> None:
    # The rate-limit call site passes decision=None, rate_limited=True.
    from boerdi.obs.quality_events import log_safety_event

    async def scenario(session):
        await log_safety_event(session, "bb-s3", "zu schnell", None, ip="", rate_limited=True)
        return await _one_safety(session)

    row = _run(scenario)
    assert row.risk_level == "low"  # default when no decision
    assert row.data["rate_limited"] is True
    assert row.data["message"] == "zu schnell"
    assert row.data["stages_run"] == [] and row.data["categories"] == {}


def test_log_safety_event_truncates_message(test_db) -> None:
    from boerdi.obs.quality_events import log_safety_event

    async def scenario(session):
        await log_safety_event(session, "bb-s4", "x" * 600, None)
        return await _one_safety(session)

    assert len(_run(scenario).data["message"]) == 500


# ── quality writer ──────────────────────────────────────────────

_DEBUG_INFO = {
    "persona": "P-AND (Andi)",
    "intent": "I01 (Suche)",
    "confidence": 0.8,
    "turn_type": "initial",
    "state": "S1 (Start)",
    "signals": ["greeting"],
    "entities": {"thema": "Bio"},
    "pattern": "M04 (Fakten-Bulletin)",
    "phase2_scores": {"M04": 1.0, "M03": 0.6},
    "phase1_eliminated": ["M02"],
    "tools_called": ["search_wlo"],
    "outcomes": [{"tool": "search_wlo", "status": "ok"}],
    "phase3_modulations": {"length": "kurz", "degradation": True, "missing_slots": ["fach"]},
}


def test_log_quality_event_promotes_ids_and_folds_metrics(test_db) -> None:
    from boerdi.obs.quality_events import log_quality_event

    async def scenario(session):
        await log_quality_event(
            session, "bb-q", "wie funktioniert photosynthese", 3, dict(_DEBUG_INFO),
            response_length=120, cards_count=4, page="/bio", device="mobile",
        )
        return await _one_quality(session)

    row = _run(scenario)
    # promoted columns: pattern_id is the CODE only; intent_id is ALT's full string
    assert row.pattern_id == "M04"
    assert row.intent_id == "I01 (Suche)"
    assert row.session_id == "bb-q"
    d = row.data
    assert d["persona_id"] == "P-AND (Andi)"
    assert d["turn_count"] == 3
    assert d["intent_confidence"] == 0.8 and d["final_confidence"] == 0.8
    assert d["turn_type"] == "initial" and d["state_id"] == "S1 (Start)"
    assert d["pattern_label"] == "M04 (Fakten-Bulletin)"
    # score maths from phase2_scores
    assert d["phase2_winner_score"] == 1.0
    assert d["phase2_runner_up"] == "M03"
    assert d["phase2_score_gap"] == 0.4
    assert d["eliminated_count"] == 1 and d["candidate_count"] == 2
    assert d["response_length"] == 120 and d["cards_count"] == 4
    assert d["tools_called"] == ["search_wlo"]
    assert d["tool_outcomes"] == [{"tool": "search_wlo", "status": "ok"}]
    assert d["length_setting"] == "kurz" and d["degradation"] is True
    assert d["missing_slots"] == ["fach"]
    assert d["page"] == "/bio" and d["device"] == "mobile"
    assert d["message"] == "wie funktioniert photosynthese"
    # full debug blob retained for deep-dive analysis
    assert d["debug"]["pattern"] == "M04 (Fakten-Bulletin)"


def test_log_quality_event_empty_scores_and_message_truncation(test_db) -> None:
    from boerdi.obs.quality_events import log_quality_event

    async def scenario(session):
        await log_quality_event(
            session, "bb-q2", "y" * 600, 1, {"pattern": "", "phase2_scores": {}}
        )
        return await _one_quality(session)

    row = _run(scenario)
    # no pattern → empty promoted id; no scores → zeroed maths, no runner-up
    assert row.pattern_id == ""
    assert row.data["phase2_winner_score"] == 0.0
    assert row.data["phase2_runner_up"] == ""
    assert row.data["phase2_score_gap"] == 0.0
    assert row.data["candidate_count"] == 0
    assert len(row.data["message"]) == 500
