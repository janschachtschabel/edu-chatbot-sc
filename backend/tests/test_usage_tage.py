"""Paket 16, D2: Kosten je Tag — `period_usage(...)["days"]` (``services/usage_tage.py``).

Gegen die echte Compose-Postgres: der Tag ist eine Rechnung in der Datenbank (Kalendertag in
Europe/Berlin, wie das Studio ihn liest), die Lücken füllt Python mit null Kosten.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p16_usage_tage"


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _tafel(**modelle):
    from boerdi.domain.config_models.pricing import PricingArea

    return PricingArea.model_validate({"currency": "EUR", "models": modelle})


def _zug(model: str, wann: datetime, prompt: int = 1_000_000, engine: str | None = None) -> dict:
    return {"model": model, "prompt_tokens": prompt, "cached_tokens": 0, "completion_tokens": 0,
            "reasoning_tokens": 0, "calls": 1, "created_at": wann, "engine": engine}


def _lauf(db, zeilen: list[dict], **kwargs):
    async def wrapper():
        from sqlalchemy import text

        from boerdi.db.models import ChatSession, UsageEvent
        from boerdi.db.session import make_engine, make_session_factory
        from boerdi.services.usage_analytics import period_usage
        from boerdi.settings import Settings

        engine = make_engine(Settings(_env_file=None, database_url=db))
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                await s.execute(text("DELETE FROM usage_events"))
                await s.execute(text("DELETE FROM sessions"))
                s.add(ChatSession(session_id="bb-tage"))
                await s.commit()
            async with factory() as s:
                for z in zeilen:
                    s.add(UsageEvent(session_id="bb-tage", **z))
                await s.commit()
            async with factory() as s:
                return await period_usage(
                    s, datetime(2026, 3, 9, tzinfo=UTC), datetime(2026, 3, 12, 12, tzinfo=UTC),
                    **kwargs)
        finally:
            await engine.dispose()
    return asyncio.run(wrapper())


def test_ein_tag_je_kalendertag_in_berlin_luecken_mit_null(db, monkeypatch):
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(a={"input": 2.0}))
    # 23:30 UTC am 10. ist in Berlin schon der 11. (MEZ, UTC+1).
    tage = _lauf(db, [_zug("a", datetime(2026, 3, 10, 23, 30, tzinfo=UTC))])["days"]
    assert [t["tag"] for t in tage] == ["2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12"]
    assert tage[2] == {"tag": "2026-03-11", "calls": 1, "amount": "2", "unvollstaendig": False}
    assert tage[0] == {"tag": "2026-03-09", "calls": 0, "amount": "0", "unvollstaendig": False}


def test_ohne_preis_kein_betrag_teilweise_bepreist_heisst_unvollstaendig(db, monkeypatch):
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(a={"input": 2.0}))
    tage = _lauf(db, [
        _zug("b", datetime(2026, 3, 9, 10, tzinfo=UTC)),
        _zug("a", datetime(2026, 3, 10, 10, tzinfo=UTC), prompt=500_000),
        _zug("b", datetime(2026, 3, 10, 11, tzinfo=UTC)),
    ])["days"]
    assert tage[0] == {"tag": "2026-03-09", "calls": 1, "amount": None, "unvollstaendig": True}
    assert tage[1] == {"tag": "2026-03-10", "calls": 2, "amount": "1", "unvollstaendig": True}


def test_die_tage_folgen_dem_maschinen_filter(db, monkeypatch):
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(a={"input": 2.0}))
    zeilen = [_zug("a", datetime(2026, 3, 10, 10, tzinfo=UTC), engine="agent"),
              _zug("a", datetime(2026, 3, 10, 11, tzinfo=UTC), engine="pattern")]
    tage = _lauf(db, zeilen, engine="agent")["days"]
    assert tage[1]["calls"] == 1 and tage[1]["amount"] == "2"
