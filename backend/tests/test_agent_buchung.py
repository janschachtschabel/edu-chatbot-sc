"""Die Agent-API bucht auch abgebrochene und gescheiterte Aufträge (Review Paket 7, A-5).

Bis zum Review buchte ``_lauf_mit_buchung`` nur nach einem erfolgreichen Lauf. Legt
der Client bei ``/api/agent/stream`` auf, bricht ``sse_turn`` den Lauf ab — die bis
dahin verbrauchten Token erschienen nirgends, genau die Lücke, die P3 schließen
sollte. Gebucht wird jetzt im ``finally``, abgeschirmt gegen den Abbruch und auf einer
eigenen Sitzung: die anfragegebundene schließt FastAPI, sobald der Strom endet (A-1).
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from boerdi.api import agent as agent_api
from boerdi.api.schemas_agent import AgentRequest, AgentResponse

_SITZUNG = object()


def _fabrik(log: list):
    @contextlib.asynccontextmanager
    async def _sitzung():
        log.append("open")
        try:
            yield _SITZUNG
        finally:
            log.append("close")

    return _sitzung


def _buchung(monkeypatch) -> list:
    gebucht: list = []

    async def _buchen(session, session_id, acc, engine=None, quelle=None):
        gebucht.append((session, session_id, (acc.get("models") or {}).get("m", {}).get("prompt"),
                        engine, quelle))
        return 1

    monkeypatch.setattr(agent_api, "record_turn_usage", _buchen)
    return gebucht


def _verbrauch(acc) -> None:
    acc["models"] = {"m": {"prompt": 10, "completion": 5, "cached": 0, "reasoning": 0, "calls": 1}}


async def test_ein_abgebrochener_auftrag_bucht_was_er_verbraucht_hat(monkeypatch):
    gebucht = _buchung(monkeypatch)
    gestartet = asyncio.Event()

    async def _run(req, *, progress=None, usage_acc=None):
        _verbrauch(usage_acc)              # die erste Runde ist gelaufen
        gestartet.set()
        await asyncio.Event().wait()       # … und dann legt der Client auf

    monkeypatch.setattr(agent_api, "run_agent", _run)
    log: list = []
    lauf = asyncio.create_task(agent_api._lauf_mit_buchung(
        AgentRequest(instruction="x"), _fabrik(log)))
    await gestartet.wait()
    lauf.cancel()
    with pytest.raises(asyncio.CancelledError):
        await lauf
    assert gebucht == [(_SITZUNG, None, 10, "agent", "agent-api")]
    assert log == ["open", "close"]


async def test_ein_gescheiterter_auftrag_bucht_ebenso(monkeypatch):
    gebucht = _buchung(monkeypatch)

    async def _run(req, *, progress=None, usage_acc=None):
        _verbrauch(usage_acc)
        raise RuntimeError("Werkzeug kaputt")

    monkeypatch.setattr(agent_api, "run_agent", _run)
    with pytest.raises(RuntimeError):
        await agent_api._lauf_mit_buchung(AgentRequest(instruction="x"), _fabrik([]))
    assert [g[2] for g in gebucht] == [10]


async def test_ein_erfolgreicher_auftrag_bucht_einmal(monkeypatch):
    gebucht = _buchung(monkeypatch)
    antwort = AgentResponse(text="ok", stop_reason="submit", iterations=1)

    async def _run(req, *, progress=None, usage_acc=None):
        _verbrauch(usage_acc)
        return antwort

    monkeypatch.setattr(agent_api, "run_agent", _run)
    assert await agent_api._lauf_mit_buchung(AgentRequest(instruction="x"), _fabrik([])) is antwort
    assert len(gebucht) == 1
