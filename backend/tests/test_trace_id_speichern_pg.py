"""Paket 18C/D, Phase 1 (1.2): Nachricht, Qualitäts- und Sicherheitsprotokoll tragen die
Trace-ID der Anfrage, in der sie entstanden sind — gelesen aus dem Kontext, ohne dass ein
Aufrufer sie durchreicht. Ohne Anfrage (Hintergrundlauf) bleibt sie ``NULL``.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text

from boerdi.obs import trace_id
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p18_trace_speichern_test"
_TID = "4f2a9c01d3b7e6a8"


@pytest.fixture(scope="module", autouse=True)
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


def _lauf(fn, *, mit_trace: bool):
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.settings import Settings

    async def szenario():
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))
        token = trace_id.setze(_TID) if mit_trace else None
        try:
            async with make_session_factory(engine)() as session:
                await session.execute(text(
                    "TRUNCATE messages, safety_logs, quality_logs, sessions RESTART IDENTITY "
                    "CASCADE"))
                await session.commit()
                return await fn(session)
        finally:
            if token is not None:
                trace_id.zuruecksetzen(token)
            await engine.dispose()

    return asyncio.run(szenario())


async def _alle_drei(session):
    from boerdi.db.models import ChatMessage, QualityLog, SafetyLog
    from boerdi.obs.quality_events import log_quality_event, log_safety_event
    from boerdi.services.db_sessions import get_or_create_session, save_message

    await get_or_create_session(session, "bb-t")
    await save_message(session, "bb-t", "user", "hallo")
    await log_safety_event(session, "bb-t", "hallo", None)
    await log_quality_event(session, "bb-t", "hallo", 1, {"pattern": "", "phase2_scores": {}})
    await session.commit()
    return (
        (await session.execute(select(ChatMessage.trace_id))).scalars().all(),
        (await session.execute(select(SafetyLog.trace_id))).scalars().all(),
        (await session.execute(select(QualityLog.trace_id))).scalars().all(),
    )


def test_in_einer_anfrage_tragen_alle_drei_die_trace_id():
    assert _lauf(_alle_drei, mit_trace=True) == ([_TID], [_TID], [_TID])


def test_ohne_anfrage_bleibt_sie_leer():
    assert _lauf(_alle_drei, mit_trace=False) == ([None], [None], [None])
