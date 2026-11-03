"""``POST /api/ui/themenbaum/zweig`` — Unterthemen im selben Baum aufklappen (Paket U1-h, §18).

Öffentlich wie Verlauf und Sprache: das Widget ruft es ohne Studio-Schlüssel, wenn die Person im
Themenbaum einen Knoten aufklappt, dessen Unterthemen noch fehlen. Kein Zug: keine KI, keine
Sitzungssperre, nichts gespeichert, keine Sicherheitsprüfung (die Anfrage trägt keinen Text —
nur zwei Kennungen in fester Form). Die Bremsen gelten trotzdem:

- außen ``@public_rate_limit`` (je IP-Netz, 429 vor jeder Arbeit),
- innen die Fenster der Redaktion (``check_rate_limit``) wie für jeden Zug — die Direktaktion
  ``show_collection_tree``, die das Aufklappen ersetzt, zählte dort auch,
- die Sitzung muss existieren: kein offener Durchgang zum MCP-Server ohne vorherigen Zug,
- Studio-Schalter und Angebot des Werkzeugs wie bei der Direktaktion (``themenbaum_zweig``) —
  vor der Anmeldung, die es nicht braucht (Review U1-h, Befund 7),
- ``node_id`` nur in der Form einer edu-sharing-Kennung (UUID, Review U1-h, Befund 8).

Nach dem Lesen der Sitzung geht die Verbindung in den Pool zurück (``verbindung_freigeben``,
Review U1-h, Befund 1): Anmeldung und Zweig fragen den MCP-Server (bis 5 s und 60 s), und eine
Verbindung „idle in transaction“ darüber war genau, was Paket 19 (H-5) für den Zug behob.

Tiefe und Menge setzt das Manifest (``datenquelle.vorgaben``), nicht der Aufrufer. Fehler kommen
ohne Text des Servers: 403 ``aus``/``nicht_angeboten`` (nochmal versuchen hilft nicht), 502
``nicht_geladen`` (vielleicht später), 404 für eine unbekannte Sitzung.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session
from boerdi.api.ratelimit import peer_ip, public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import adopt_turn_auth_block, pruefe_oeffentliche_kennung
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.i18n import resolve_locale
from boerdi.obs.quality_events import log_safety_event
from boerdi.services.db_sessions import sitzung_vorhanden
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.rate_limits import check_rate_limit
from boerdi.services.themenbaum_zweig import zweig_angebot, zweig_laden
from boerdi.ui_module.themenbaum import KNOTEN_UUID

public_router = APIRouter(prefix="/api/ui", tags=["ui"])

_FEHLER = {"aus": 403, "nicht_angeboten": 403, "nicht_geladen": 502}


class ThemenbaumZweigAnfrage(BaseModel):
    """Welcher Knoten, in welcher Sitzung, unter welchem Modus der Einbettung."""

    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    node_id: str = Field(pattern=KNOTEN_UUID)
    #: wie ``Environment.tool_mode`` (``read-only`` | ``curate`` | ``full``) — er entscheidet,
    #: ob ``browse_collection_tree`` angeboten ist.
    tool_mode: str | None = Field(default=None, max_length=32)


class ThemenbaumZweigAntwort(BaseModel):
    """Die Unterthemen in der Form der Block-Daten von ``ui_themenbaum`` (ohne Überschrift)."""

    daten: dict[str, Any]


@public_router.post("/themenbaum/zweig", response_model=ThemenbaumZweigAntwort)
@public_rate_limit
async def themenbaum_zweig(
    anfrage: ThemenbaumZweigAnfrage,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ThemenbaumZweigAntwort:
    """Lädt die Unterthemen eines Knotens für den Themenbaum im Widget.

    ``response`` braucht der Decorator der Drosselung für seine Kopfzeilen (wie beim Verlauf)."""
    pruefe_oeffentliche_kennung(request, anfrage.session_id)
    ip = peer_ip(request)
    urteil = await check_rate_limit(anfrage.session_id, ip,
                                    resolve_locale(request.headers.get("accept-language")))
    if not urteil.allowed:
        await log_safety_event(session, anfrage.session_id, "",
                               decision={"reasons": [f"rate_limit:{urteil.reason}"]},
                               ip=ip, rate_limited=True)
        raise HTTPException(status_code=429, detail=urteil.blocked_message)
    if not await sitzung_vorhanden(session, anfrage.session_id):
        raise HTTPException(status_code=404, detail="sitzung_unbekannt")
    await verbindung_freigeben(session)
    stand = zweig_angebot(tool_mode=anfrage.tool_mode)
    if stand != "ja":
        raise HTTPException(status_code=_FEHLER[stand], detail=stand)
    # Der Zweig sieht, was der Zug sah: dieselbe Anmeldung (ein LLM-Schlüssel ist unnötig).
    adopt_turn_auth_block(request)
    await bestaetige_anmeldung()
    zweig = await zweig_laden(anfrage.node_id)
    if zweig.daten is None:
        raise HTTPException(status_code=_FEHLER[zweig.status], detail=zweig.status)
    return ThemenbaumZweigAntwort(daten=zweig.daten)
