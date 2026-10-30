"""Paket 18F, Aufgabe 3.3: die „ausgelastet“-Blase.

Bekam ein Zug binnen ``LLM_SLOT_WAIT_S`` keinen LLM-Platz, ist seine Antwort ein freundlicher
Satz (de/en) mit „Nochmal versuchen“ — keine Fehlernummer-Blase, denn es ist kein Fehler,
den jemand im Studio nachschlagen müsste. Muster-Weg (Antwort, Werkzeugschleife), Agent-Weg.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.i18n.bot_text import bot_text
from boerdi.services import llm_parallel
from boerdi.services.agent_abschluss import antwort_oder_ersatz
from boerdi.services.agent_loop import AgentRun
from boerdi.services.fehlertext import antwort_fehlertext


@pytest.fixture
def ausgelastet():
    """Ein Zug, dessen Platz-Frist abgelaufen ist (``llm_parallel._anstellen``)."""
    llm_parallel.binde_zug()
    llm_parallel._zug.get().ausgelastet = True
    yield
    llm_parallel._zug.set(None)


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_ausgelastet_ergibt_den_eigenen_satz_ohne_fehlernummer(ausgelastet, sprache):
    text = antwort_fehlertext(sprache, "error.answerFailed")
    assert text == bot_text(sprache, "error.llmBusy")
    assert "{nummer}" not in bot_text(sprache, "error.llmBusy")


def test_sonst_der_fehler_mit_nummer():
    llm_parallel._zug.set(None)
    assert antwort_fehlertext("de", "error.answerFailed") == bot_text(
        "de", "error.answerFailed", nummer="-")


def test_der_satz_ist_zweisprachig_und_verschieden():
    de, en = bot_text("de", "error.llmBusy"), bot_text("en", "error.llmBusy")
    assert de and en and de != en


def test_agent_weg(ausgelastet):
    lauf = AgentRun(stop_reason="error")
    assert antwort_oder_ersatz(lauf, "en") == bot_text("en", "error.llmBusy")


def test_ohne_merker_bleibt_der_agent_satz_mit_fehlernummer():
    llm_parallel._zug.set(None)
    lauf = AgentRun(stop_reason="error")
    assert antwort_oder_ersatz(lauf, "de") == bot_text("de", "error.answerFailed", nummer="-")


def test_der_merker_reist_in_die_knoten(monkeypatch):
    """Paket 10 / R6: LangGraph startet jeden Knoten als eigene Task mit Kontextkopie. Der
    Merker ist ein geteiltes Objekt — was ein Knoten markiert, sieht der nächste."""
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0.05")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    from boerdi.settings import get_settings
    get_settings.cache_clear()
    llm_parallel.reset()

    async def zug() -> bool:
        llm_parallel.binde_zug()
        sem = llm_parallel._semaphore("live")
        for _ in range(2):
            await sem.acquire()

        async def knoten() -> None:
            with pytest.raises(llm_parallel.LlmAusgelastet):
                async with llm_parallel.platz("live"):
                    pass

        await asyncio.create_task(knoten())
        return llm_parallel.ausgelastet()

    try:
        assert asyncio.run(zug()) is True
    finally:
        llm_parallel.reset()
        get_settings.cache_clear()
