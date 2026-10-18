"""Paket 13 (A5): Ablage der festen Prompt-Bausteine.

Während eines Zuges merkt sich ``merke`` Prüfsumme und Text im Prozess und trägt die Prüfsumme
in den Merkposten des Zuges (``acc["prompts"]``). Am Zugende schreibt ``speichere`` neue
Fassungen in ``prompt_versions`` — einmal je Fassung und Prozess, auf der Sitzung der Anfrage,
ohne den Zug je scheitern zu lassen.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from boerdi.services import prompt_ablage
from tests import pg_utils

_TEST_DB = "boerdi_p13_ablage_test"


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setattr(prompt_ablage, "_OFFEN", {})
    monkeypatch.setattr(prompt_ablage, "_GESCHRIEBEN", set())


def test_merke_traegt_die_pruefsumme_in_den_zug() -> None:
    acc: dict = {}
    h = prompt_ablage.merke(acc, "agent.kopf", "Du bist Boerdi.")
    assert h == prompt_ablage.pruefsumme("Du bist Boerdi.")
    assert len(h) == 12
    assert acc["prompts"] == {"agent.kopf": h}


def test_leerer_text_wird_nicht_gemerkt() -> None:
    acc: dict = {}
    assert prompt_ablage.merke(acc, "agent.master_skill", "") is None
    assert "prompts" not in acc


def test_ohne_merkposten_bleibt_nur_die_ablage() -> None:
    h = prompt_ablage.merke(None, "classify.system", "Klassifiziere.")
    assert h in prompt_ablage._OFFEN


def test_die_offene_ablage_ist_gedeckelt(monkeypatch) -> None:
    monkeypatch.setattr(prompt_ablage, "_MAX_OFFEN", 2)
    for i in range(5):
        prompt_ablage.merke({}, "art", f"Text {i}")
    assert len(prompt_ablage._OFFEN) == 2


def test_ein_schreibfehler_haelt_den_zug_nicht_an(caplog) -> None:
    class _Rahmen:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    class _Kaputt:
        def begin_nested(self):
            return _Rahmen()

        async def execute(self, *_a, **_k):
            raise RuntimeError("DB weg")

        async def commit(self):
            raise AssertionError("darf nicht erreicht werden")

        async def rollback(self):
            return None

    acc: dict = {}
    prompt_ablage.merke(acc, "agent.kopf", "Kopf")
    assert asyncio.run(prompt_ablage.speichere(_Kaputt(), acc)) == 0
    assert "Prompt-Fassungen nicht geschrieben" in caplog.text


@pytest.fixture(scope="module")
def db():
    if not pg_utils.pg_available():
        pytest.skip(pg_utils.SKIP_REASON)
    pg_utils.create_migrated_db(_TEST_DB)
    yield pg_utils.sqlalchemy_url(_TEST_DB)
    pg_utils.drop_db(_TEST_DB)


def _factory(url):
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.settings import Settings

    engine = make_engine(Settings(_env_file=None, database_url=url))
    return engine, make_session_factory(engine)


@pytest.mark.pg
def test_jede_fassung_wird_einmal_geschrieben(db) -> None:
    async def szenario() -> tuple[int, int, list]:
        engine, factory = _factory(db)
        try:
            acc: dict = {}
            prompt_ablage.merke(acc, "agent.kopf", "Kopf A")
            prompt_ablage.merke(acc, "seitenregeln", "Regeln")
            async with factory() as s:
                erst = await prompt_ablage.speichere(s, acc)
            async with factory() as s:
                zweit = await prompt_ablage.speichere(s, acc)
            async with factory() as s:
                zeilen = (await s.execute(text(
                    "SELECT art, text FROM prompt_versions ORDER BY art"))).all()
            return erst, zweit, [tuple(z) for z in zeilen]
        finally:
            await engine.dispose()

    erst, zweit, zeilen = asyncio.run(szenario())
    assert (erst, zweit) == (2, 0)
    assert zeilen == [("agent.kopf", "Kopf A"), ("seitenregeln", "Regeln")]


@pytest.mark.pg
def test_eine_schon_vorhandene_fassung_stoert_nicht(db) -> None:
    """Ein zweiter Prozess (Replik, Neustart) kennt die Fassung nicht und schreibt sie erneut."""
    async def szenario() -> int:
        engine, factory = _factory(db)
        try:
            acc: dict = {}
            prompt_ablage.merke(acc, "agent.kopf", "Kopf B")
            async with factory() as s:
                await prompt_ablage.speichere(s, acc)
            prompt_ablage._GESCHRIEBEN.clear()
            prompt_ablage.merke(acc, "agent.kopf", "Kopf B")
            async with factory() as s:
                return await prompt_ablage.speichere(s, acc)
        finally:
            await engine.dispose()

    assert asyncio.run(szenario()) == 1
