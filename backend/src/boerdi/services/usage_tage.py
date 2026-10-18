"""Kosten je Tag (Paket 16, D2) — die Zeitreihe zur Kosten-Seite, neben ``usage_analytics``.

Ein Tag ist ein Kalendertag in :data:`TAGES_ZONE`, gerechnet in Postgres
(``timezone(zone, created_at)``): das Abbild bringt keine Zeitzonen-Daten für Python mit, die
Datenbank ihre eigenen. Tage ohne Zug stehen mit null Kosten da — eine Lücke im Diagramm läse
sich wie „keine Daten“.

Je Tag dieselbe Preisregel wie die Summe (``domain.pricing.cost_for``): ``amount`` ist ``None``,
wenn an dem Tag kein Modell einen Preis hat, ``unvollstaendig``, wenn eines fehlt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import Date, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from boerdi.db.models import UsageEvent
from boerdi.domain.config_models.pricing import PricingArea
from boerdi.domain.pricing import TokenCounts, cost_for

TAGES_ZONE: Final = "Europe/Berlin"


@dataclass(slots=True)
class _Tag:
    calls: int = 0
    amount: Decimal | None = None
    unvollstaendig: bool = False
    modelle: list[str] = field(default_factory=list)


def _als_tag(wann: Any) -> Any:
    return cast(func.timezone(TAGES_ZONE, wann), Date)


async def tage(
    session: AsyncSession, start: datetime, end: datetime, table: PricingArea,
    *where: ColumnElement[bool],
) -> list[dict[str, Any]]:
    """Je Kalendertag von ``start`` bis ``end``: Züge, Betrag (Text wie die Summe) und ob ein
    Preis fehlte. ``where`` ist dieselbe Auswahl wie für die Summe."""
    tag = _als_tag(UsageEvent.created_at).label("tag")
    zeilen = (await session.execute(
        select(tag, UsageEvent.model,
               func.coalesce(func.sum(UsageEvent.prompt_tokens), 0),
               func.coalesce(func.sum(UsageEvent.cached_tokens), 0),
               func.coalesce(func.sum(UsageEvent.completion_tokens), 0),
               func.coalesce(func.sum(UsageEvent.calls), 0))
        .where(*where).group_by(tag, UsageEvent.model).order_by(tag, UsageEvent.model)
    )).all()
    erster, letzter = (await session.execute(
        select(_als_tag(literal(start)), _als_tag(literal(end))))).one()

    je_tag: dict[date, _Tag] = {}
    for tag_, model, prompt, cached, completion, calls in zeilen:
        eintrag = je_tag.setdefault(tag_, _Tag())
        eintrag.calls += calls
        betrag = cost_for(
            TokenCounts(model=model, prompt=prompt, cached=cached, completion=completion), table)
        if betrag is None:
            eintrag.unvollstaendig = True
        else:
            eintrag.amount = (eintrag.amount or Decimal(0)) + betrag

    antwort = []
    tag_ = erster
    while tag_ <= letzter:
        eintrag = je_tag.get(tag_, _Tag(amount=Decimal(0)))
        antwort.append({
            "tag": tag_.isoformat(), "calls": eintrag.calls,
            "amount": None if eintrag.amount is None else format(eintrag.amount.normalize(), "f"),
            "unvollstaendig": eintrag.unvollstaendig,
        })
        tag_ += timedelta(days=1)
    return antwort
