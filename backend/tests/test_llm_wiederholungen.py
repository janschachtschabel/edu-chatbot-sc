"""Höchstens drei Versuche je LLM-Aufruf (Paket 4, B3; externes Audit F04).

``num_retries=2`` ergab in LiteLLM 1.91.5 zwei Wiederholungsschichten: das SDK
(``max_retries``) und LiteLLMs eigene Schleife (``acompletion_with_retries``).
Gemessen 2026-10-03: Chat-Completions 5 Versuche (bis ≈ 375 s bei 75 s
Lesefrist), die Responses-Brücke 6 bei Verbindungsfehlern. Gewollt waren 3 wie
in ALT, das sich auf die SDK-Vorgabe ``max_retries=2`` verließ.

Gefälscht wird allein der Draht (``httpx.AsyncClient.send``): er zählt und wirft.
Alles darüber — LiteLLM, SDK, unsere Verdrahtung — läuft echt.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from boerdi.services import llm


def _zaehle_und_wirf(monkeypatch, fehler: type[Exception]) -> list[str]:
    versuche: list[str] = []

    async def gezaehlt(self, request, *args, **kwargs):
        versuche.append(str(request.url))
        raise fehler("kein Netz im Test", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", gezaehlt)
    return versuche


def _scheitert(aufruf) -> None:
    try:
        asyncio.run(aufruf)
    except Exception:  # noqa: BLE001 — gezählt werden die Versuche, nicht die Fehlerform
        return
    pytest.fail("Der Aufruf hätte ohne Netz scheitern müssen")


@pytest.mark.parametrize("fehler", [httpx.ConnectError, httpx.ReadTimeout])
@pytest.mark.parametrize("modell", ["openai/gpt-4o-mini", "openai/responses/gpt-4o-mini"])
def test_hoechstens_drei_versuche_je_chat_aufruf(monkeypatch, modell, fehler):
    versuche = _zaehle_und_wirf(monkeypatch, fehler)
    monkeypatch.setattr(
        llm, "route", lambda _m: (modell, "http://127.0.0.1:9/v1", "sk-test", None))

    _scheitert(llm.chat_completion(
        messages=[{"role": "user", "content": "x"}], model="gpt-4o-mini"))

    assert 1 <= len(versuche) <= 3, f"{len(versuche)} Versuche"


def test_der_chat_weg_wiederholt_wie_alt_zweimal(monkeypatch):
    # Gegenprobe: Nicht „gar nicht wiederholen“ ist das Ziel, sondern eine
    # Schicht. Auf dem Chat-Weg sind es wie in ALT 1 + 2 Versuche.
    versuche = _zaehle_und_wirf(monkeypatch, httpx.ConnectError)
    monkeypatch.setattr(
        llm, "route",
        lambda _m: ("openai/gpt-4o-mini", "http://127.0.0.1:9/v1", "sk-test", None))

    _scheitert(llm.chat_completion(
        messages=[{"role": "user", "content": "x"}], model="gpt-4o-mini"))

    assert len(versuche) == 3


def test_hoechstens_drei_versuche_je_embedding(monkeypatch):
    versuche = _zaehle_und_wirf(monkeypatch, httpx.ConnectError)
    monkeypatch.setattr(
        llm, "route",
        lambda _m: ("openai/text-embedding-3-small", "http://127.0.0.1:9/v1", "sk-test", None))

    _scheitert(llm.embedding("x", model="text-embedding-3-small"))

    assert 1 <= len(versuche) <= 3, f"{len(versuche)} Versuche"
