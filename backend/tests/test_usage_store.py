"""K2b — Schreibpfad der Verbrauchszeilen (``services/usage_store.py``).

Die Zeilen-Tests laufen gegen die echte Compose-Postgres: eine Attrappe würde
hier genau das nicht prüfen, worauf es ankommt — dass das Modell auf die
migrierte Tabelle passt. Der Fehlerpfad braucht keine DB und läuft immer.
"""

from __future__ import annotations

import asyncio

import pytest

from tests import pg_utils

_TEST_DB = "boerdi_k2b_test"
_TEST_URL_SQLA = pg_utils.sqlalchemy_url(_TEST_DB)


def _run(coro):
    return asyncio.run(coro)


def _acc(models: dict) -> dict:
    """Ein Merkposten, wie ihn ``obs/usage.py`` am Zugende hinterlässt."""
    return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0,
            "reasoning_tokens": 0, "calls": 0, "models": models, "per_phase": {}}


# ── Fehlerpfad: ohne DB, läuft immer ────────────────────────────────────

def test_schreibfehler_haelt_den_zug_nicht_an(caplog) -> None:
    """Pflicht aus dem Plan: eine kaputte Buchhaltung darf den Chat nicht
    anhalten. Der Fehler wird geloggt, nicht geworfen."""
    from boerdi.services import usage_store

    class _Rahmen:
        """Der SAVEPOINT als Nullkontext — er hält den Fehler nicht auf."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    class _KaputteSession:
        def add(self, obj):
            raise RuntimeError("DB weg")

        def begin_nested(self):
            return _Rahmen()

        async def commit(self):
            raise RuntimeError("DB weg")

        async def rollback(self):
            return None

    n = _run(usage_store.record_turn_usage(
        _KaputteSession(), "bb-1", _acc({"m": {"prompt": 1, "completion": 1,
                                               "cached": 0, "reasoning": 0,
                                               "calls": 1}})))
    assert n == 0
    assert any("usage" in r.message.lower() or "verbrauch" in r.message.lower()
               for r in caplog.records)


@pytest.mark.parametrize("acc", [None, {}, _acc({})])
def test_zug_ohne_llm_aufruf_schreibt_nichts(acc) -> None:
    from boerdi.services import usage_store

    class _Verboten:
        def add(self, obj):
            raise AssertionError("darf nicht schreiben")

        async def commit(self):
            raise AssertionError("darf nicht committen")

    assert _run(usage_store.record_turn_usage(_Verboten(), "bb-1", acc)) == 0


# ── Zeilen-Tests: gegen die echte Postgres ──────────────────────────────

_pg = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_TEST_DB)
    yield _TEST_URL_SQLA
    pg_utils.drop_db(_TEST_DB)


def _factory(url):
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.settings import Settings

    engine = make_engine(Settings(_env_file=None, database_url=url))
    return engine, make_session_factory(engine)


@pytest.mark.pg
@pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON)
def test_ein_schreibfehler_reisst_andere_offene_arbeit_nicht_mit(db) -> None:
    """Die Buchung ist der letzte Schreiber einer Anfrage — aber nicht der
    Eigentümer ihrer Transaktionsgrenze.

    Sie läuft auf der anfragegebundenen Sitzung. Nähme ihr Fehlerpfad die
    ganze Sitzung zurück, verschwände still, was sonst noch offen war: aus
    „die Buchhaltung ist kaputt" würde „ein fremder Schreibvorgang ist weg".
    Der SAVEPOINT begrenzt die Rücknahme auf die eigenen Zeilen.
    """
    from boerdi.db.models import ChatSession
    from boerdi.services import usage_store

    async def szenario() -> ChatSession | None:
        engine, factory = _factory(db)
        try:
            async with factory() as s:
                # Fremde, noch nicht committete Arbeit auf derselben Sitzung.
                s.add(ChatSession(session_id="bb-k2b-nachbar"))

                # Buchung auf eine Sitzung, die es nicht gibt → der Fremd-
                # schlüssel schlägt beim Schreiben zu (echte DB, keine Attrappe).
                n = await usage_store.record_turn_usage(s, "bb-gibt-es-nicht", _acc({
                    "m": {"prompt": 1, "completion": 1, "cached": 0,
                          "reasoning": 0, "calls": 1}}))
                assert n == 0, "die Buchung muss scheitern, sonst prüft der Test nichts"

                await s.commit()
            async with factory() as s:
                return await s.get(ChatSession, "bb-k2b-nachbar")
        finally:
            await engine.dispose()

    assert _run(szenario()) is not None, (
        "die fremde Zeile ist mit dem Buchungs-Rollback verschwunden"
    )


@pytest.mark.pg
@pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON)
def test_zwei_modelle_ergeben_zwei_zeilen(db) -> None:
    from sqlalchemy import select

    from boerdi.db.models import ChatSession, UsageEvent
    from boerdi.services import usage_store

    async def szenario() -> list[UsageEvent]:
        engine, factory = _factory(db)
        try:
            async with factory() as s:
                s.add(ChatSession(session_id="bb-k2b-1"))
                await s.commit()
            async with factory() as s:
                n = await usage_store.record_turn_usage(s, "bb-k2b-1", _acc({
                    "gpt-5.4-mini": {"prompt": 100, "completion": 20,
                                     "cached": 64, "reasoning": 8, "calls": 2},
                    "gpt-5.6-luna": {"prompt": 7, "completion": 3,
                                     "cached": 0, "reasoning": 0, "calls": 1},
                }))
                assert n == 2
            async with factory() as s:
                return list((await s.execute(
                    select(UsageEvent)
                    .where(UsageEvent.session_id == "bb-k2b-1")
                    .order_by(UsageEvent.model)
                )).scalars())
        finally:
            await engine.dispose()

    zeilen = _run(szenario())
    assert [z.model for z in zeilen] == ["gpt-5.4-mini", "gpt-5.6-luna"]
    erste = zeilen[0]
    # Die „davon"-Felder wandern unverändert durch — NICHT aufaddiert.
    assert erste.prompt_tokens == 100 and erste.cached_tokens == 64
    assert erste.completion_tokens == 20 and erste.reasoning_tokens == 8
    assert erste.calls == 2
