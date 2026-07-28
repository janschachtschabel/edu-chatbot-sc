"""Page-context enrichment node (P4-2 / R6).

Port of the page-context prep in ALT ``chat_turn_setup._setup_turn`` (lines 92-110):
inject the IDs the widget supplies (``node_id``/``collection_id``/slug/…) into
``session_state['entities']`` so downstream entity-matching sees them, then
best-effort resolve the host page's metadata via MCP. ``resolve_page_context``
caches the result on ``session_state['entities']['_page_metadata']`` — the cache
that ``context_greeting`` reads (Gate 3) and that ``respond``'s ``render_for_prompt``
will read (a later R6 slice).

Placement (why a dedicated node between ``tour`` and ``context_greeting``):

* AFTER tour — ALT returns from the tour branch (``chat_turn_setup:90``) BEFORE this
  block (:92), so a tour tick never pays the MCP-resolve latency. Running it in the
  pre-tour ``setup`` node would resolve on every tick.
* NOT inside ``context_greeting`` — the resolved cache is a shared prerequisite
  (``respond``'s prompt consumes it on every normal turn), so it stays its own node
  on the normal path rather than coupling to the greeting.

Never sets ``early_response`` (normal-path node). No session DI: ``resolve_page_context``
talks to MCP, not the DB. ``resolve_page_context`` is best-effort by contract (returns
None, never raises) but the call is still wrapped defensively — a resolver bug must not
break the turn (ALT wrapped it too). Tests patch ``resolve_page_context`` on this module.
"""

from __future__ import annotations

import logging

from boerdi.graph.state import TurnContext
from boerdi.services.page_context import resolve_page_context

logger = logging.getLogger(__name__)

_PAGE_CONTEXT_ENTITY_KEYS = (
    "node_id",
    "collection_id",
    "search_query",
    "topic_page_slug",
    "subject_slug",
    "document_title",
    "page_type",
)


async def page_context_enrich(ctx: TurnContext) -> TurnContext:
    """Inject page-context IDs into entities and best-effort resolve page metadata."""
    page_ctx = ctx.env.get("page_context") or {}
    entities = ctx.session_state.setdefault("entities", {})
    for key in _PAGE_CONTEXT_ENTITY_KEYS:
        if page_ctx.get(key):
            entities[key] = page_ctx[key]

    try:
        await resolve_page_context(page_ctx, ctx.session_state)
    except Exception as err:  # pragma: no cover — resolver bug must not break the turn
        logger.warning("page_context auto-resolve skipped: %s", err)

    return ctx
