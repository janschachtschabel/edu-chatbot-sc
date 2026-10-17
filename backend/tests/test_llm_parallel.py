"""Wie viele LLM-Aufrufe gleichzeitig laufen — je Anbieter (Paket 7, L3; Review A-2/A-6).

Nutzer-Vorgabe 2026-10-09: bei OpenAI bis zu 20 gleichzeitige Aufrufe, bei
b-api-academiccloud erstmal nur 2. Die Grenze gilt dem ANBIETER: Chat, Hintergrund
(Judge, Simulator) und Import-Embeddings teilen sich einen Deckel. Damit ein Import
den Chat nicht verdrängt (Review A-2: hinter der b-api wartete jeder Chat-Aufruf
hinter allen Abschnitten eines Imports), stehen Hintergrund und Import zusätzlich
hinter einem gemeinsamen Deckel von höchstens Anbieter−1 — einer bleibt immer frei.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from boerdi.services import llm
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MAX_CONCURRENCY", "BG_LLM_MAX_CONCURRENCY",
                 "EMBED_INGEST_PARALLEL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    llm.reset()
    yield
    get_settings.cache_clear()
    llm.reset()


def _anbieter(monkeypatch, name: str) -> None:
    monkeypatch.setenv("LLM_PROVIDER", name)
    get_settings.cache_clear()


def _spitze(kanaele: dict[str, int]) -> int:
    """Startet je Kanal so viele Aufgaben gleichzeitig; liefert die höchste Zahl,
    die zugleich einen Platz hatte."""
    aktiv = 0
    spitze = 0

    async def arbeit(kanal: str) -> None:
        nonlocal aktiv, spitze
        async with llm.platz(kanal):
            aktiv += 1
            spitze = max(spitze, aktiv)
            await asyncio.sleep(0.01)
            aktiv -= 1

    async def alle() -> None:
        await asyncio.gather(*(arbeit(k) for k, n in kanaele.items() for _ in range(n)))

    asyncio.run(alle())
    return spitze


def test_auf_der_academiccloud_teilen_sich_alle_kanaele_zwei_plaetze(monkeypatch):
    _anbieter(monkeypatch, "b-api-academiccloud")
    assert _spitze({"live": 6, "bg": 6, "ingest": 6}) == 2


@pytest.mark.parametrize("anbieter", ["openai", "b-api-openai"])
def test_beide_openai_wege_haben_zwanzig_plaetze(monkeypatch, anbieter):
    """Paket 8 (Nutzer 2026-10-09): b-api-openai „wie openai (also 20 als default)“."""
    _anbieter(monkeypatch, anbieter)
    assert _spitze({"live": 25}) == 20
    assert _spitze({"live": 20, "bg": 6, "ingest": 6}) == 20


def test_ein_gesetzter_deckel_gilt_auch_hinter_der_b_api(monkeypatch):
    _anbieter(monkeypatch, "b-api-academiccloud")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "5")
    get_settings.cache_clear()
    assert _spitze({"live": 6, "bg": 6, "ingest": 6}) == 5


def test_bei_openai_direkt_gilt_der_deckel_ueber_alle_kanaele(monkeypatch):
    """Review A-6: vorher 20 + 4 + 4 = 28 zugleich, gegen „bis zu 20“."""
    _anbieter(monkeypatch, "openai")
    assert _spitze({"live": 25}) == 20
    assert _spitze({"live": 20, "bg": 6, "ingest": 6}) == 20
    # Hintergrund und Import behalten ihre eigenen Deckel (4 und 4).
    assert _spitze({"bg": 10}) == 4
    assert _spitze({"ingest": 10}) == 4


def test_der_chat_wartet_nicht_hinter_einem_import(monkeypatch):
    """Review A-2: hinter der b-api (zwei Plätze, FIFO) wartete der Chat hinter
    allen Abschnitten eines Imports — 200 Abschnitte legten ihn rund 50 s still."""
    _anbieter(monkeypatch, "b-api-academiccloud")
    wartezeit: list[float] = []

    async def abschnitt() -> None:
        async with llm.platz("ingest"):
            await asyncio.sleep(0.02)

    async def chat() -> None:
        t0 = time.perf_counter()
        async with llm.platz("live"):
            wartezeit.append(time.perf_counter() - t0)

    async def lauf() -> None:
        importe = [asyncio.create_task(abschnitt()) for _ in range(30)]
        await asyncio.sleep(0)              # der Import steht schon in der Schlange
        await chat()
        await asyncio.gather(*importe)

    asyncio.run(lauf())
    assert wartezeit[0] < 0.1, wartezeit    # nicht 30 × 20 ms


def test_die_lokale_einbettung_belegt_keinen_platz_beim_anbieter(monkeypatch):
    """Review A-2: ``EMBED_BACKEND=local`` ist CPU-Arbeit — sie nahm hinter der
    b-api trotzdem einen der zwei Plätze."""
    _anbieter(monkeypatch, "b-api-academiccloud")

    async def lauf() -> bool:
        async with llm.platz("live"), llm.platz("live"):     # beide Plätze belegt
            async with asyncio.timeout(1):
                async with llm.ingest_semaphore():
                    return True

    assert asyncio.run(lauf())


def test_llm_max_concurrency_hat_weiter_eine_untergrenze_von_zwei(monkeypatch):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    get_settings.cache_clear()
    assert get_settings().llm_max_concurrency == 2
    monkeypatch.delenv("LLM_MAX_CONCURRENCY")
    get_settings.cache_clear()
    assert get_settings().llm_max_concurrency is None  # ungesetzt: Vorgabe je Anbieter
