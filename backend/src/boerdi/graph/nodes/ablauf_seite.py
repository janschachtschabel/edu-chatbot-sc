"""Seiten-Ping eines wartenden Ablaufs (Paket AS-7a, Plan 2026-11-09 §5m, F-4).

Läuft nach ``tour`` und vor dem Speichern der Nutzernachricht: Der Ping ist kein Zug der Person.
Er endet hier immer, entweder mit dem nächsten Schritt (die Seite passt) oder mit einer leeren
Antwort, die das Widget nicht zeigt. So wird kein ``[ablauf-seite]`` gespeichert, und weder die
Sicherheitsprüfung noch ein Modell laufen.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.domain.hintergrund_zug import ist_seiten_ping
from boerdi.graph.state import TurnContext
from boerdi.services.ablauf import seite_zug


async def ablauf_seite(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    if not ist_seiten_ping(ctx.req.environment.page_event):
        return ctx
    ctx.early_response = await seite_zug.angekommen(session, ctx.req, ctx.session_state)
    return ctx
