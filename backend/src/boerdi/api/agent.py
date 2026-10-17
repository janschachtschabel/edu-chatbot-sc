"""Agent-Endpunkte (A3b): POST /api/agent, POST /api/agent/stream (SSE).

Der Weg für Gastgeber, die den Chat-Rahmen nicht haben — Browser-Plugin,
edu-sharing-Einbettung, jede Maschine, die eine Aufgabe auf dem WLO-Bestand
stellen und ein **maschinenlesbares** Ergebnis auswerten will. Keine Sitzung,
keine Begrüßung, keine Muster: Anweisung rein, Text plus freies JSON raus.

**Nicht auf ``public_router``.** Ein Lauf kostet bis zu einem Dutzend
LLM-Runden und darf mit persönlicher Anmeldung schreiben; er steht damit in
einer anderen Klasse als ein Chat-Zug.

**Wer herein darf, entscheidet ``require_agent_caller``** (Nutzer-Entscheid
2026-08-12): die **Anmeldung der Person** ist der normale Weg, der
Studio-Schlüssel bleibt für Server-zu-Server, ``AGENT_OPEN`` öffnet für
Testläufe. Vorher war der Studio-Schlüssel der einzige Weg — also der
Admin-Schlüssel, der in einem Browser-Plugin nichts zu suchen hat.

**Und deshalb jetzt mit Drosselung.** Der frühere Stand hier lautete „kein
zusätzliches Rate-Limit, den Kreis der Aufrufer schnürt schon der Schlüssel
zusammen" — und benannte den Tag, an dem das fällig wird: „wenn ein Gastgeber
ohne Studio-Schlüssel zugelassen wird". Der Tag ist da. Die Prüfung der
Kopfzeile ist eine **Form**-, keine Echtheitsprüfung (nur der MCP-Server kann
einen Block belegen), also ist sie keine Kostenschranke — die Mengenbremse ist
es. Die Kosten eines *einzelnen* Laufs decken weiterhin
``max_iterations``/``deadline_s``/``token_budget`` aus ``01-base/engine``.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.api.deps import get_session_factory
from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.schemas_agent import AgentRequest, AgentResponse
from boerdi.api.sse import sse_turn
from boerdi.api.studio_proxy import ueber_studio
from boerdi.api.turn_auth import require_agent_caller, uebernimm_zugang
from boerdi.obs.progress import TurnProgress
from boerdi.obs.usage import new_accumulator
from boerdi.services.agent_run import run_agent
from boerdi.services.session_origin import STUDIO_QUELLE
from boerdi.services.usage_store import record_turn_usage

router = APIRouter(tags=["agent"], dependencies=[Security(require_agent_caller)])


Sitzungen = async_sessionmaker[AsyncSession]


def _quelle(request: Request) -> str:
    """``studio-probe`` für den Auftragstester des Studios, sonst ``agent-api``
    (Paket 9: Probeläufe zählten in den Kosten als Betrieb)."""
    return STUDIO_QUELLE if ueber_studio(request) else "agent-api"


async def _lauf_mit_buchung(
    req: AgentRequest, sitzungen: Sitzungen, progress: TurnProgress | None = None,
    *, quelle: str = "agent-api",
) -> AgentResponse:
    """Ein Auftrag samt Buchung seiner Token (Paket 7, P3 — P5-3).

    Bis dahin lief ``run_agent`` ohne Merkposten: Aufträge der Gastanwendungen
    kosteten, erschienen aber nirgends. Sie gehören keiner Chat-Sitzung und
    buchen deshalb ohne sie, mit der Quelle ``agent-api``. Die Buchung schluckt
    ihre Fehler selbst (``usage_store``); die Antwort geht in jedem Fall raus.

    Gebucht wird auch, wenn der Lauf scheitert oder abgebrochen wird (Review
    Paket 7, A-5) — bis dahin hat er Token verbraucht. Abgeschirmt, damit der
    Abbruch (der Strom bricht beim Auflegen ab) die Buchung nicht mitreißt; auf
    einer eigenen Sitzung, weil FastAPI die anfragegebundene schließt, sobald
    der Strom endet (wie beim Chat, A-1).
    """
    acc = new_accumulator()
    try:
        return await (run_agent(req, usage_acc=acc) if progress is None
                      else run_agent(req, progress=progress, usage_acc=acc))
    finally:
        await asyncio.shield(_buchen(sitzungen, acc, quelle))


async def _buchen(sitzungen: Sitzungen, acc: dict[str, Any], quelle: str) -> None:
    async with sitzungen() as session:
        await record_turn_usage(session, None, acc, engine="agent", quelle=quelle)


@router.post("/api/agent", response_model=AgentResponse)
@public_rate_limit
async def agent(
    req: AgentRequest, request: Request, response: Response,
    sitzungen: Annotated[Sitzungen, Depends(get_session_factory)],
) -> AgentResponse:
    """Run one agent task and return its text plus structured result."""
    # ``response`` wird im Rumpf nicht gebraucht, im Vertrag aber schon: die
    # Drosselung hängt ihre ``X-RateLimit-*``-Kopfzeilen daran (headers_enabled).
    # Ohne den Parameter findet slowapi kein Antwort-Objekt und wirft — dieselbe
    # Deklaration steht aus demselben Grund an ``/api/chat``.
    await uebernimm_zugang(request)
    return await _lauf_mit_buchung(req, sitzungen, quelle=_quelle(request))


@router.post("/api/agent/stream")
@public_rate_limit
async def agent_stream(
    req: AgentRequest, request: Request,
    sitzungen: Annotated[Sitzungen, Depends(get_session_factory)],
) -> StreamingResponse:
    """Stream one agent task as Server-Sent-Events (connected → result | error)."""
    # Der Zugangsblock wird HIER übernommen, nicht im Generator: das ist die
    # HTTP-Grenze (symmetrisch zu ``agent``), und der Lauf startet in einer
    # Task, die den Kontext beim Erzeugen erbt.
    #
    # Als Kommentar und NICHT im Docstring: FastAPI trägt Docstrings als
    # ``description`` in das OpenAPI-Dokument ein.
    await uebernimm_zugang(request)

    async def _run(progress: TurnProgress) -> AgentResponse:
        return await _lauf_mit_buchung(req, sitzungen, progress, quelle=_quelle(request))

    async def _to_payload(result: AgentResponse) -> dict[str, Any]:
        return result.model_dump()

    return StreamingResponse(
        sse_turn(request, _run, _to_payload, label="agent_stream"),
        media_type="text/event-stream",
        headers={
            # Zwischenspeicher dürfen SSE weder puffern noch umformen.
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
