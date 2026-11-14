"""Ein Werkzeugaufruf holt nicht nebenbei die ganze Werkzeugliste (2026-11-14).

Das MCP-SDK prüft eine erfolgreiche Antwort gegen das Ausgabeschema des Werkzeugs, wenn es eines
veröffentlicht — und holt, um das zu wissen, ``tools/list``, sobald die Sitzung das Werkzeug nicht
kennt. Der Chatbot öffnet je Aufruf eine frische Sitzung — die Liste kam also bei JEDEM Aufruf mit:
gemessen am Staging-MCP 0,25–0,33 s und 171 KiB je Werkzeugaufruf, 18 von 18 Aufrufen.
"""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp import ClientSession, types

from boerdi.services.mcp import transport


@asynccontextmanager
async def _stroeme() -> AsyncIterator[tuple]:
    """Zwei Speicher-Ströme wie vom SDK-Draht; alle vier Hälften werden wieder geschlossen."""
    sende, sende_gegen = anyio.create_memory_object_stream(1)
    lese_gegen, lese = anyio.create_memory_object_stream(1)
    try:
        yield lese, sende
    finally:
        for haelfte in (sende, sende_gegen, lese_gegen, lese):
            await haelfte.aclose()


async def _aufruf(klasse: type[ClientSession]) -> tuple[types.CallToolResult, list[str]]:
    """``call_tool`` auf einer Sitzung ohne Draht: ``send_request`` antwortet, ``list_tools`` wird
    gezählt."""
    gelistet: list[str] = []

    async def _antwort(*_a, **_k):
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")],
                                    structuredContent={"total": 0}, isError=False)

    async def _liste(*_a, **_k):
        gelistet.append("tools/list")
        return types.ListToolsResult(tools=[])

    async with _stroeme() as (lese, sende):
        sitzung = klasse(lese, sende)
        sitzung.send_request = _antwort  # type: ignore[method-assign]
        sitzung.list_tools = _liste      # type: ignore[method-assign]
        ergebnis = await sitzung.call_tool("search_wlo_content", {"query": "Optik"})
    return ergebnis, gelistet


def test_die_sdk_sitzung_holt_je_aufruf_die_werkzeugliste():
    """Der Grund für die eigene Klasse — fällt dieser Test, prüft das SDK anders als bisher,
    und :class:`transport._Sitzung` ist neu anzusehen."""
    _, gelistet = asyncio.run(_aufruf(ClientSession))
    assert gelistet == ["tools/list"]
    assert "_validate_tool_result" in inspect.getsource(ClientSession.call_tool)


def test_unsere_sitzung_holt_sie_nicht():
    ergebnis, gelistet = asyncio.run(_aufruf(transport._Sitzung))
    assert gelistet == []
    assert ergebnis.structuredContent == {"total": 0}      # die Antwort kommt unverändert an


def test_open_session_oeffnet_unsere_sitzung(monkeypatch):
    @asynccontextmanager
    async def _draht(url, **_kwargs):
        async with _stroeme() as (lese, sende):
            yield lese, sende, lambda: None

    async def _handschlag(self):
        return None

    monkeypatch.setattr(transport, "streamablehttp_client", _draht)
    monkeypatch.setattr(transport._Sitzung, "initialize", _handschlag)

    async def _lauf() -> type:
        async with transport._open_session("https://beispiel.test/mcp") as sitzung:
            return type(sitzung)

    assert asyncio.run(_lauf()) is transport._Sitzung


def test_die_werkzeugliste_bleibt_auf_wunsch_erreichbar():
    """„Server prüfen“ im Studio listet weiter — nur der Nebenaufruf je Werkzeug entfällt."""
    assert transport._Sitzung.list_tools is ClientSession.list_tools
