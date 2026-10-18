"""Nutzung im Überblick (Paket 16, D3) — dünne HTTP-Schicht über ``services/nutzung``.

Studio-Schlüssel auf Router-Ebene wie bei den Kosten; Zeitraum, Herkunft und Maschine werden
genauso gelesen und geprüft (``api/usage.zeitraum``). ``protokoll_an`` sagt dem Studio, ob das
Qualitätsprotokoll gerade schreibt — sonst läse sich eine leere Seite wie „niemand da“.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import Lang, OriginScope, get_session, require_studio_key
from boerdi.api.usage import zeitraum
from boerdi.services.nutzung import ueberblick
from boerdi.services.turn_quality import qualitaetsprotokoll_an

router = APIRouter(
    prefix="/api/nutzung", tags=["nutzung"],
    dependencies=[Security(require_studio_key)],
)


@router.get("/ueberblick")
async def nutzung_ueberblick(
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Lang,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
    scope: OriginScope = "all",
    engine: Annotated[
        Literal["pattern", "agent"] | None,
        Query(description="Nur Züge dieser Maschine ('pattern' | 'agent'); ohne Angabe beide"),
    ] = None,
) -> dict:
    """Züge, Sitzungen, Tage, Wochentag × Stunde und Verteilungen eines Zeitraums."""
    start, end = zeitraum(start, end, lang)
    antwort = await ueberblick(session, start, end, scope=scope, engine=engine)
    return {**antwort, "protokoll_an": qualitaetsprotokoll_an()}
