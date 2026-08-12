"""Setup node — turn-init base state (P4-2 / R4b), the graph entry.

Port of the base half of ALT ``chat_turn_setup._setup_turn`` (P0-3): the work that
runs unconditionally before any early-exit — clear the per-request MCP query-meta
accumulator, load-or-create the session, load the last 20 messages as history,
parse the stored ``session_state``, dump ``env``, and resolve ``client_ip``.

What ALT's ``_setup_turn`` also did but this node deliberately does NOT, because
each is its own graph node or a later slice:

* the website-tour early-exit → ``graph/nodes/tour`` (R2c, built),
* page-context inject + MCP resolve → R6 (``page_context_service`` deferred),
* the context-greeting early-exit → R6,
* the user-message persist → runs between tour and preflight in the graph, so it
  belongs to the graph-wiring slice (persisting it here would wrongly persist on
  a tour/greeting early-exit turn),
* the preflight direct-action dispatch → ``graph/nodes/preflight`` (R2a, built).

DI (Regel 3): ``session`` and ``peer_ip`` are injected — the graph-build (P4-6)
binds the request ``AsyncSession`` and the real peer IP, mirroring ALT
``_setup_turn(req, peer_ip)`` and how ``assess``/``preflight`` take their seams.

NEU deviations over ALT, both forced by the SQLite→Postgres move:

* ``get_or_create_session`` returns ``entities``/``signal_history``/``tour_state``
  already parsed as native jsonb (dict/list), so ALT's ``json.loads`` wrappers are
  dropped — the row values are used directly.
* ``tour_state`` is carried inside ``session_state`` (ALT kept it out and passed
  the raw session row to the tour handler): the NEU tour node reads
  ``ctx.session_state['tour_state']``, so setup seeds it here.

Tests patch the two DB boundaries + ``reset_query_metas`` on THIS module.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.graph.state import TurnContext
from boerdi.obs.usage import bind_turn_usage
from boerdi.services.db_sessions import get_messages, get_or_create_session
from boerdi.services.mcp.client import reset_prepared_writes, reset_query_metas

logger = logging.getLogger(__name__)


async def setup(ctx: TurnContext, session: AsyncSession, peer_ip: str = "") -> TurnContext:
    """Establish the turn's base state on ``ctx``; never sets ``early_response``.

    Fills ``session_state`` (jsonb-native, incl. ``tour_state``), ``history`` (last
    20), ``env`` (the environment model dump) and ``client_ip`` (real peer IP,
    falling back to the client-supplied ``page_context.ip`` only when the server
    saw none). Returns the same mutated ``ctx``.
    """
    req = ctx.req

    # Clear the per-request MCP query-meta accumulator so each turn starts fresh.
    reset_query_metas()
    # Dasselbe für die vorbereiteten Schreibzugriffe (E3): eine Änderung, die
    # im vorigen Zug beschrieben und dort ausgeliefert wurde, darf im nächsten
    # nicht ein zweites Mal auftauchen.
    reset_prepared_writes()

    # Den Merkposten dieses Zuges binden (K1e). Er ist der einzige Weg, auf dem
    # Blätter ohne Zug-Kontext buchen können — allen voran der Vokabular-
    # Abgleich hinter ``call_mcp_tool``. Hier, weil dieser Knoten der Eingang
    # des Graphen ist (``START → setup``): jeder spätere Knoten und jede von
    # ihm erzeugte Task erbt die Bindung. Wie ``reset_query_metas`` gehört das
    # zur Grundhygiene des Zuges — ein Zug darf nie am Merkposten des vorigen
    # hängen.
    bind_turn_usage(ctx.usage)

    row = await get_or_create_session(session, req.session_id)
    ctx.history = await get_messages(session, req.session_id, limit=20)

    ctx.session_state = {
        "persona_id": row.get("persona_id") or "",
        "state_id": row.get("state_id") or "S1",
        "entities": row.get("entities") or {},
        "signal_history": row.get("signal_history") or [],
        "turn_count": row.get("turn_count") or 0,
        "tour_state": row.get("tour_state") or {},
    }

    ctx.env = req.environment.model_dump()

    # Prefer the real connection IP; the client-supplied page_context.ip is a
    # spoofable fallback (tests / proxies) and must not drive safety-log or
    # rate-limit decisions when a server-side peer IP is available.
    page_ip = (ctx.env.get("page_context") or {}).get("ip", "") or ""
    ctx.client_ip = peer_ip or page_ip or ""

    return ctx
