"""``POST /api/auth/abmelden`` — Abmelden im Widget beendet den Zugang am MCP-Server (Plan
2026-11-07, R2/CB-9).

Bis hier löschte „Abmelden“ den Zugangsblock nur im Browser; wer ihn vorher kopiert hatte (ein
Skript der Gastseite), behielt einen gültigen Zugang. Der MCP-Server widerruft seit dem 07.11.
einen Block, den man ihm als ``Authorization: Bearer`` vorlegt — der Besitz ist der Nachweis.
``/auth*`` hat dort kein CORS, also ruft das Backend server-zu-server: das Widget schickt den Block
wie bei jedem Zug in ``WLO-Access-Block``, das Backend legt ihn dem MCP-Server vor.

Kein Zug, keine Sitzung, nichts wird gespeichert. Die Antwort sagt nur, ob widerrufen wurde
(``widerrufen``) und ob der Server zu fragen war (``erreicht``) — das Widget löscht den Block in
jedem Fall. IP-Drossel wie die übrigen öffentlichen Abrufe: jeder Widerruf kostet das Adress-
Budget des Backends an ``/auth*`` des MCP-Servers (30 je Minute).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.turn_auth import ACCESS_BLOCK_HEADER
from boerdi.services.mcp import anmelde_endpunkte, anmeldung, auth

public_router = APIRouter(prefix="/api/auth", tags=["auth"])


class Abgemeldet(BaseModel):
    widerrufen: bool
    erreicht: bool


@public_router.post("/abmelden", response_model=Abgemeldet)
@public_rate_limit
async def abmelden(request: Request, response: Response) -> Abgemeldet:
    block = (request.headers.get(ACCESS_BLOCK_HEADER) or "").strip()
    # Nur ein Block, der eine Person meinen kann — den anonymen Block widerruft niemand, und
    # Fremdes reicht das Backend nicht weiter (dieselbe Form-Prüfung wie bei jedem Zug).
    if not auth.is_personal_block(block):
        return Abgemeldet(widerrufen=False, erreicht=False)
    ergebnis = await anmelde_endpunkte.widerrufen(block)
    anmeldung.abgemeldet(block)
    return Abgemeldet(widerrufen=bool(ergebnis), erreicht=ergebnis is not None)
