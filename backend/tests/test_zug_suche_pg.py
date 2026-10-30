"""Paket 18C/D, Phase 1 (1.8): ein Zug lässt sich über seine Fehlernummer finden.

Die Fehlernummer ist der Anfang der Trace-ID (Phase 3). Gesucht wird per Präfix über den Index
``ix_messages_trace_id``; ein Zug zählt einmal, auch wenn Frage und Antwort dieselbe ID tragen —
der Treffer zeigt auf seine letzte Nachricht (die Antwort, sonst die Frage).
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from boerdi.obs import trace_id
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p18_zug_suche_test"


@pytest.fixture(scope="module", autouse=True)
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


def _lauf(zuege, praefix):
    """``zuege`` = [(sitzung, trace_id, rollen)]; gibt die Treffer und die IDs je Zug zurück."""
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.services.db_sessions import get_or_create_session, save_message, zuege_mit_nummer
    from boerdi.settings import Settings

    async def szenario():
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))
        ids: dict[str, int] = {}
        try:
            async with make_session_factory(engine)() as session:
                await session.execute(text("TRUNCATE messages, sessions RESTART IDENTITY CASCADE"))
                await session.commit()
                for sitzung, tid, rollen in zuege:
                    await get_or_create_session(session, sitzung)
                    token = trace_id.setze(tid)
                    try:
                        for rolle in rollen:
                            ids[tid] = await save_message(session, sitzung, rolle, "x")
                    finally:
                        trace_id.zuruecksetzen(token)
                return await zuege_mit_nummer(session, praefix), ids
        finally:
            await engine.dispose()

    return asyncio.run(szenario())


def test_ein_treffer_je_zug_auf_seine_letzte_nachricht():
    treffer, ids = _lauf([
        ("bb-a", "4f2a9c01d3b7e6a8", ["user", "assistant"]),
        ("bb-b", "4f2a9c01ffff0000", ["user"]),          # Zug ohne gespeicherte Antwort
        ("bb-c", "77aa9c01d3b7e6a8", ["user", "assistant"]),
    ], "4f2a9c01")
    assert [(t["session_id"], t["message_id"], t["trace_id"]) for t in treffer] == [
        ("bb-b", ids["4f2a9c01ffff0000"], "4f2a9c01ffff0000"),
        ("bb-a", ids["4f2a9c01d3b7e6a8"], "4f2a9c01d3b7e6a8"),
    ]
    assert all(t["created_at"] is not None for t in treffer)


def test_der_unterstrich_ist_ein_zeichen_kein_platzhalter():
    treffer, _ = _lauf([
        ("bb-a", "4f2a_c01-zug", ["assistant"]),
        ("bb-b", "4f2a9c01-zug", ["assistant"]),
    ], "4f2a_c01")
    assert [t["trace_id"] for t in treffer] == ["4f2a_c01-zug"]


def test_hoechstens_zwanzig_treffer_die_neuesten_zuerst():
    treffer, _ = _lauf([("bb-a", f"abcdef01-{i:02d}", ["assistant"]) for i in range(25)],
                       "abcdef01")
    assert [t["trace_id"] for t in treffer] == [f"abcdef01-{i:02d}" for i in range(24, 4, -1)]
