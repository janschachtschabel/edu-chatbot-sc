"""``POST /api/ui/auftrag/stand`` — der Stand eines Ablauf-Auftrags für ``ui_fortschritt`` (K1b).

Das Modul fragt hier in wachsenden Abständen nach, ob der b-api-Auftrag des wartenden
``auftrag``-Schritts fertig ist. Kein Zug, keine KI, **nichts wird geschrieben**: die Antwort ist
nur ``laeuft``, ``fertig`` oder ``fehler`` (nie Ausgaben, nie die Job-ID). Abgeholt wird danach im
Zug der Person über die Direktaktion ``ablauf_auftrag_pruefen`` (``services/ablauf/auftrag_zug``) —
erst dort werden die Ausgaben Teil des Vorgangs und der Treiber setzt fort.

Bremsen, vor jeder b-api-Abfrage: Sitzung (404), **bestätigte Anmeldung** (403 ``nur_angemeldet``),
der Lauf dieser Person wartet auf genau diesen Auftrag — Ablauf, Fassung, Schritt und Kürzel der
Job-ID passen (409 ``kein_auftrag``; ein alter Block im Verlauf hört damit auf), der
**durchgereichte** Schlüssel der Person (503 ``nicht_abrufbar`` — mit ``B_API_KEY`` sähe der Chatbot
den Auftrag nicht, K22). Antwortet die b-api endgültig (Auftrag unbekannt, Aufträge aus, Schlüssel
abgewiesen), wird daraus 409 bzw. 403 — das Modul hört dann auf zu fragen. IP-Drossel wie die
übrigen Modul-Abrufe.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session
from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import (
    adopt_turn_auth_block,
    pruefe_oeffentliche_kennung,
    uebernimm_llm_schluessel,
)
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.config_models.ablauf import ID_FORM
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.auftraege import ablage, client
from boerdi.services.db_sessions import sitzung_entities
from boerdi.services.llm_auth import hat_zug_schluessel
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)
public_router = APIRouter(prefix="/api/ui/auftrag", tags=["ui"])


class StandAnfrage(BaseModel):
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    ablauf: str = Field(pattern=ID_FORM)
    kuerzel: str = Field(pattern=r"^[0-9a-f]{12}$")


#: Review K1b, Befund 4: endgültige Gründe des Clients beenden das Nachfragen des Moduls (409 →
#: „abgeschlossen“, 403 → Halt); ``fehler``/``voll`` bleiben 503 (neuer Versuch hilft).
_GRUENDE: dict[str, tuple[int, str]] = {
    "unbekannt": (409, "kein_auftrag"), "aus": (409, "kein_auftrag"),
    "abgewiesen": (403, "abgewiesen"),
}


def _kein_auftrag() -> HTTPException:
    return HTTPException(status_code=409, detail="kein_auftrag")


async def _wartender_auftrag(session: AsyncSession, anfrage: StandAnfrage,
                             entities: dict[str, Any]) -> Any:
    """Der offene Auftrag, auf den der Lauf dieser Person wartet — sonst 409. Prüft dasselbe wie
    ``auftrag_zug.pruefen``, bricht aber nichts ab (dieser Abruf schreibt nie)."""
    aufrufer = arbeitsstand.aufrufer_fuer(anfrage.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != anfrage.ablauf
            or lauf.get("status") != treiber.WARTET_AUFTRAG):
        raise _kein_auftrag()
    ablauf = laden(anfrage.ablauf)
    if ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf):
        raise _kein_auftrag()
    auftrag = await ablage.offen(session, v.id)
    if (auftrag is None or auftrag.schritt != lauf.get("schritt")
            or client.kuerzel(auftrag.job_id) != anfrage.kuerzel):
        raise _kein_auftrag()
    return auftrag


@public_router.post("/stand")
@public_rate_limit
async def stand(anfrage: StandAnfrage, request: Request, response: Response,
                session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    pruefe_oeffentliche_kennung(request, anfrage.session_id)
    entities = await sitzung_entities(session, anfrage.session_id)
    if entities is None:
        raise HTTPException(status_code=404, detail="sitzung_unbekannt")
    # Review K1b, Befund 2: die Bestätigung der Anmeldung kann ein MCP-Rundlauf sein — ohne offene
    # Lese-Transaktion (``_wartender_auftrag`` öffnet danach eine neue).
    await verbindung_freigeben(session)
    adopt_turn_auth_block(request)
    uebernimm_llm_schluessel(request, pflicht=False)
    await bestaetige_anmeldung()
    if not has_personal_auth():
        raise HTTPException(status_code=403, detail="nur_angemeldet")
    auftrag = await _wartender_auftrag(session, anfrage, entities)
    if not hat_zug_schluessel():
        raise HTTPException(status_code=503, detail="nicht_abrufbar")
    job_id = auftrag.job_id
    await verbindung_freigeben(session)      # die b-api-Abfrage hält keine DB-Verbindung
    try:
        ergebnis = await client.stand(job_id)
    except client.AuftragFehler as fehler:
        logger.info("Auftrag: Stand für das Modul nicht abrufbar (%s)", fehler.grund)
        status, code = _GRUENDE.get(fehler.grund, (503, "nicht_abrufbar"))
        raise HTTPException(status_code=status, detail=code) from None
    return {"stand": ergebnis.status}
