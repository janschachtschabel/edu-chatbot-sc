"""Kostenschau (Studio) — dünne HTTP-Schicht über ``services/usage_analytics``.

Der Router trägt die StudioKey-Sicherung auf Router-Ebene (nicht je Route
wiederholen). Die Zahlen sind für den Betrieb, nicht für die Nutzerin: es gibt
bewusst **keinen** öffentlichen Gegenpart und keinen Kostenwert im Widget.

Diese beiden Routen sind der erste bewusste Zusatz zum eingefrorenen
OpenAPI-Vertrag; Entscheid und Begründung stehen in
``docs/plans/2026-08-11-kostenueberwachung.md`` §5.5, die benannte Liste in
``docs/api/bewusste-vertragszusaetze.md`` (bewacht von
``tests/test_openapi_additions.py``).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import Lang, get_session, require_studio_key
from boerdi.i18n import msg
from boerdi.services.usage_analytics import period_usage, session_usage

router = APIRouter(
    prefix="/api/usage", tags=["usage"],
    dependencies=[Security(require_studio_key)],
)


# Ein volles Jahr (mit Schalttag) ist die längste Frage, die die Kostenschau
# beantworten können muss; die Ansicht fragt standardmäßig 30 Tage. Ohne
# Deckel zöge ein Vertipper („2000" statt „2026") die Gruppierung der ganzen
# Tabelle nach Python — je Sitzung UND Modell, ohne LIMIT. Die Tabelle wächst
# etwa wie ``messages``, die Wirkung also mit der Laufzeit.
MAX_PERIOD_DAYS = 366


def _as_utc(moment: datetime) -> datetime:
    """Zeitzonenlose Angaben als UTC lesen.

    ``created_at`` ist ``timestamptz``. Ohne diese Festlegung legte Postgres
    eine zonenlose Grenze in der Zeitzone der Sitzung aus — dieselbe Abfrage
    lieferte auf zwei Servern verschiedene Zahlen, ohne Fehlermeldung.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


@router.get("/session/{session_id}")
async def usage_for_session(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Token, Aufrufe und Betrag einer Sitzung, je Modell aufgeschlüsselt.

    Eine Sitzung ohne LLM-Aufruf antwortet mit Nullen und ``empty: true`` —
    kein 404, denn genau das ist bei Tour und Kontext-Begrüßung der Normalfall.
    ``amount`` ist eine Zeichenkette (oder ``null``, wenn für kein Modell ein
    Preis gepflegt ist); ``price_unavailable`` nennt die Modelle ohne Preis.
    """
    return await session_usage(session, session_id)


@router.get("/period")
async def usage_for_period(
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Lang,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
) -> dict:
    """Dasselbe über einen Zeitraum, Grenzen einschließlich.

    Zeitzonenlose Angaben gelten als UTC. Vertauschte Grenzen sind ein
    Eingabefehler (422) und ausdrücklich **kein** leeres Ergebnis: das läse
    sich wie „keine Kosten" statt wie „so herum ergibt die Frage keinen Sinn".
    Zu weite Zeiträume ebenso (``MAX_PERIOD_DAYS``).
    """
    start, end = _as_utc(start), _as_utc(end)
    if start > end:
        raise HTTPException(
            status_code=422, detail=msg(lang, "usage.periodReversed"),
        )
    if (end - start) > timedelta(days=MAX_PERIOD_DAYS):
        raise HTTPException(
            status_code=422,
            detail=msg(lang, "usage.periodTooLong", max=MAX_PERIOD_DAYS),
        )
    return await period_usage(session, start, end)
