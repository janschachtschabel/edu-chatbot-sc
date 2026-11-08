"""``POST /api/ui/vorgaenge/offen`` — wartende Vorgänge der Person in anderen Gesprächen (K2a).

Das Widget fragt hier nach der Anmeldung oder beim Öffnen, ob ein Ablauf der Person in einem
**anderen** Gespräch wartet — auf einen b-api-Auftrag oder auf ihre Antwort. Dann bietet es
„Gespräch fortsetzen“ an und wechselt auf dessen Kennung (Plan 2026-11-08, Entscheid F2: über die
Anmeldung, keine Gesprächs-ID zum Eintippen).

Die Kennung eines Gesprächs ist dessen Geheimnis (wer sie hat, liest den Verlauf). Deshalb:
- nur mit **bestätigter Anmeldung** (403 ``nur_angemeldet``) — Aufträge starten ohnehin nur
  angemeldete Personen;
- die Besitzerin ist die Kennung der Anmeldung (``aufrufer_kennung``), nie eine mitgeschickte ID;
- die Antwort wird nicht zwischengespeichert (``no-store``), und kein Log nennt eine Kennung.

Angeboten wird nur der jüngste wartende Vorgang (Review K2a, Befund 7: das Widget nutzt nur ihn —
eine Kennung weniger, die hinausgeht), und nie der, auf den das aktuelle Gespräch schon verweist
(Befund 1: eine neue Sitzung übernimmt den jüngsten offenen Vorgang ohnehin, ``arbeitsstand.
auffrischen`` — dann führt er schon hier weiter).

Kein Zug, nichts wird geschrieben. IP-Drossel wie die übrigen Modul-Abrufe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session
from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import adopt_turn_auth_block, pruefe_oeffentliche_kennung
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.db_sessions import sitzung_entities
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth

public_router = APIRouter(prefix="/api/ui/vorgaenge", tags=["ui"])


class OffenAnfrage(BaseModel):
    #: Das aktuelle Gespräch — nach ihm fragt das Widget nicht.
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")


class OffenerVorgang(BaseModel):
    titel: str
    #: Der wartende Ablauf (für „Stand prüfen“ nach dem Wechsel), ohne Lauf ``None``.
    ablauf: str | None
    #: ``wartet_auftrag`` oder ``wartet_person``.
    status: str
    #: Die Kennung des Gesprächs — nur für die Besitzerin.
    session_id: str
    geaendert: datetime


class OffeneVorgaenge(BaseModel):
    #: Höchstens einer: der jüngste.
    vorgaenge: list[OffenerVorgang]


@public_router.post("/offen", response_model=OffeneVorgaenge)
@public_rate_limit
async def offen(anfrage: OffenAnfrage, request: Request, response: Response,
                session: Annotated[AsyncSession, Depends(get_session)]) -> OffeneVorgaenge:
    pruefe_oeffentliche_kennung(request, anfrage.session_id)
    # Wie ``ui_auftrag``: die Bestätigung kann ein MCP-Rundlauf sein — ohne offene Lese-Transaktion.
    await verbindung_freigeben(session)
    adopt_turn_auth_block(request)
    await bestaetige_anmeldung()
    if not has_personal_auth():
        raise HTTPException(status_code=403, detail="nur_angemeldet")
    kennung = aufrufer_kennung()
    entities = await sitzung_entities(session, anfrage.session_id) or {}
    hier = (arbeitsstand.verweis(entities, kennung) or {}).get("id")
    liste = [v for v in await vorgaenge.offene(session, kennung, ohne=anfrage.session_id)
             if v.id != hier]
    response.headers["Cache-Control"] = "private, no-store"
    aus = []
    for v in liste[:1]:
        lauf = (v.akte or {}).get("lauf")
        ablauf = lauf.get("ablauf") if isinstance(lauf, dict) else None
        aus.append(OffenerVorgang(titel=v.titel, ablauf=ablauf if isinstance(ablauf, str) else None,
                                  status=v.status, session_id=v.session_id, geaendert=v.geaendert))
    return OffeneVorgaenge(vorgaenge=aus)
