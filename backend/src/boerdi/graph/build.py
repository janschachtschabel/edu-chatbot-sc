"""Turn-graph assembly (R4e) — compose the nine turn nodes into a LangGraph
``StateGraph`` and compile it into the runnable pipeline the chat endpoint drives.

This is the composition root of the turn: the one place that knows the concrete
services and the request-scoped seams. ALT ran the turn as a linear ``_chat_impl``
(``chat.py`` + ``chat_turn_setup.py``); NEU expresses the same sequence — and the
same two early exits — as a graph:

    START → setup → tour ──early?──▶ END
                     └─▶ page_context_enrich → context_greeting ──early?──▶ END
                            └─▶ persist_user → preflight ──early?──▶ END
                                   └─▶ assess → safety_log → pruefung_fehlt ──early?──▶ END
                                          └─▶ merge → route
                                          → respond → assemble → persist → END

``page_context_enrich`` (inject page IDs + best-effort MCP metadata resolve) runs
AFTER tour — so a tour tick skips the resolve latency (ALT returns before the resolve
block) — and never short-circuits. Only ``tour``, ``context_greeting``,
``preflight`` and ``pruefung_fehlt`` short-circuit (they set ``ctx.early_response``);
the last one only with ``MODERATION_FAILURE_MODE=closed`` (Paket 18A). The LP-/Canvas-fast-paths
do NOT: ``route`` records ``fp_*`` markers that
``respond`` consumes, so the normal chain still flows through respond→assemble→
persist. The endpoint returns ``early_response or response`` (``.ainvoke`` yields a
dict; None-default fields are omitted — read via ``.get``).

Two inline glue steps live here because they are pure turn-sequencing side effects
that only make sense between the major nodes (ALT emitted them inline in
``_chat_impl`` too):

* ``_persist_user_message`` — ALT ``chat_turn_setup.py:128``. Runs AFTER tour and the
  context-greeting check (so an early-exit never persists here — tour saves its own
  user turn; a context-open ping is intentionally never persisted) and BEFORE
  preflight (so a direct-action turn still records the user message). Bare await,
  faithful to ALT: a DB failure propagates to the endpoint's top-level safety net.
* ``_log_turn_safety`` — ALT ``chat_turn_setup.py:202-212``. The main per-turn
  safety-log, config-gated. Runs after assess and BEFORE route, so route-fast-path
  early exits are still audited (this is why it is not in the terminal persist
  node). Wrapped in try/except like ALT — telemetry must never break a turn.

DI (Regel 3 — no module-global engine): the request ``AsyncSession``, the real peer
IP and the streaming ``on_token`` hook are bound per request via ``functools.partial``
at build time; ``memory_fetch`` for ``assess`` is likewise the concrete
``get_memory`` bound to this session. Building + compiling per request is cheap next
to a turn's LLM latency and keeps every seam request-scoped.

Connection release (Paket 19, H-5): every node is wrapped so that a read-only
transaction it leaves open is committed before the next node starts, and
``memory_fetch`` releases right after reading — the shared session must not hold its
pooled connection over MCP, moderation or LLM calls (``db/verbindung``).

simplify: compiled WITHOUT a checkpointer. Turn state is durable in our own tables
(``setup`` loads session_state, ``persist`` writes it); a LangGraph checkpointer
would duplicate that and buys only interrupt/resume/time-travel, none of which the
run-to-completion turn needs. Upgrade path: pass an ``AsyncPostgresSaver`` to
``compile(checkpointer=...)`` if durable mid-turn resume is ever required.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.verbindung import verbindung_freigeben
from boerdi.graph.nodes.assemble import assemble
from boerdi.graph.nodes.assess import assess
from boerdi.graph.nodes.context_greeting import context_greeting
from boerdi.graph.nodes.merge import merge
from boerdi.graph.nodes.page_context_enrich import page_context_enrich
from boerdi.graph.nodes.persist import persist
from boerdi.graph.nodes.preflight import preflight
from boerdi.graph.nodes.pruefung_fehlt import nach_der_pruefung, pruefung_fehlt
from boerdi.graph.nodes.respond import respond
from boerdi.graph.nodes.route import route
from boerdi.graph.nodes.setup import setup
from boerdi.graph.nodes.tour import tour
from boerdi.graph.state import TurnContext
from boerdi.obs.progress import TurnProgress
from boerdi.obs.quality_events import log_safety_event
from boerdi.obs.tasks import binde_zug_aufgaben, raeume_zug_aufgaben
from boerdi.obs.usage import bind_turn_usage
from boerdi.obs.zeiten import messe_knoten
from boerdi.services.config_loader import load_safety_config
from boerdi.services.db_sessions import get_memory, save_message
from boerdi.services.llm_parallel import binde_zug as binde_llm_zug
from boerdi.services.mcp.client import reset_prepared_writes, reset_query_metas
from boerdi.services.zugakte import binde_zugakte

logger = logging.getLogger(__name__)


async def _persist_user_message(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Persist the user turn (ALT ``chat_turn_setup.py:128``) between tour and
    preflight. Bare await like ALT — a DB failure propagates to the endpoint."""
    await save_message(session, ctx.req.session_id, "user", ctx.req.message)
    return ctx


async def _gedaechtnis_lesen(
    session: AsyncSession, session_id: str, *args: Any, **kwargs: Any,
) -> list[dict]:
    """``memory_fetch`` für ``assess``: ``get_memory``, danach die Verbindung frei.

    Paket 19 (Audit 2026-10-31, H-5): ``assess`` liest das Gedächtnis und ruft danach die
    Klassifikation — die Lese-Transaktion hielt die Verbindung über alle LLM-Aufrufe bis
    ``persist`` (``db/verbindung``)."""
    try:
        return await get_memory(session, session_id, *args, **kwargs)
    finally:
        await verbindung_freigeben(session)


def _mit_freigabe(action: Any, session: AsyncSession) -> Any:
    """Einen Knoten so umhüllen, dass er die Verbindung des Zugs frei zurücklässt.

    Paket 19 (H-5): zwischen den Knoten liegen MCP (``page_context_enrich``), Moderation
    und LLM (``preflight``, ``assess``, ``respond``). Was ein Knoten nur gelesen hat, darf
    die Verbindung nicht über den nächsten tragen. Nur nach regulärem Ende — eine Ausnahme
    behandelt der Endpunkt (Rollback in ``_fehlerblase``). ``functools.wraps`` hält die
    Signatur für LangGraph sichtbar (wie ``obs/zeiten.messe_knoten``)."""

    @functools.wraps(action)
    async def huelle(ctx: Any, *args: Any, **kwargs: Any) -> Any:
        ergebnis = await action(ctx, *args, **kwargs)
        await verbindung_freigeben(session)
        return ergebnis

    return huelle


async def _log_turn_safety(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Main per-turn safety-log (ALT ``chat_turn_setup.py:202-212``): every safety
    decision, gated by ``safety-config.logging.{enabled,log_all_turns}`` and
    ``risk_level``. After assess, before route — so fast-path early exits are audited
    too. Telemetry only: never let a log failure break the turn."""
    try:
        log_cfg = load_safety_config().get("logging") or {}
        if log_cfg.get("enabled", True) and (
            log_cfg.get("log_all_turns", False) or ctx.safety.risk_level != "low"
        ):
            await log_safety_event(
                session, ctx.req.session_id, ctx.req.message, ctx.safety, ip=ctx.client_ip,
            )
    except Exception as err:
        # The ``commit`` inside ``log_safety_event`` can fail and leave the
        # shared session in an aborted transaction; without the rollback the
        # turn's own persistence (state + assistant reply) fails afterwards.
        # Telemetry must not stop the turn — and must not take the real work
        # down with it either (audit 2026-08-12, F-1).
        logger.warning("safety log failed: %s", err)
        try:
            await session.rollback()
        except Exception:
            # No re-raise: this function promises never to break the turn.
            logger.debug("safety log: rollback failed too", exc_info=True)
    return ctx


def _after_tour(ctx: TurnContext) -> str:
    """Tour set an answer ⇒ end the turn; otherwise resolve page context, then greet."""
    return END if ctx.early_response is not None else "page_context_enrich"


def _after_context_greeting(ctx: TurnContext) -> str:
    """A context-open greeting (or its empty short-circuit) ⇒ end the turn; otherwise
    persist the user turn and continue the normal flow."""
    return END if ctx.early_response is not None else "persist_user"


def _after_preflight(ctx: TurnContext) -> str:
    """A direct action answered (or was blocked) ⇒ end; otherwise assess."""
    return END if ctx.early_response is not None else "assess"


def build_turn_graph(
    *,
    session: AsyncSession,
    peer_ip: str = "",
    on_token: Any = None,
    progress: TurnProgress | None = None,
    engine: str = "pattern",
) -> CompiledStateGraph:
    """Compose + compile the per-request turn graph with its seams bound.

    ``session`` is threaded into every DB-touching node; ``peer_ip`` reaches
    ``setup`` (client-IP resolution); ``on_token`` reaches ``respond`` (SSE token
    streaming). ``progress`` (C9) reaches the four nodes that report a step to the
    SSE stream; omitted (``POST /api/chat``) it becomes a sink-less no-op, so the
    nodes call it unconditionally. ``memory_fetch`` for ``assess`` is ``get_memory``
    bound to this session (releasing the connection afterwards, H-5). ``engine`` (A4)
    picks the machine that answers this turn — ``"pattern"`` (the default, and the
    shipped one) or ``"agent"``;
    ``services/engine_choice.choose_engine`` resolves it at the HTTP edge. It
    reaches ``assess`` (no classifier), ``merge`` (the type slots last one
    turn), ``route`` (no pattern selection, no fast-paths), ``respond``
    (delegates to ``respond_agent``) and ``persist`` (records it in the debug
    block, AG-1); every other node runs the same either way. A pattern enforced by the safety gate
    (M01/M02) overrides it in ``route`` and ``respond``: that turn is answered
    by the pattern path whatever the engine (SF-1).
    Returns a compiled graph whose
    ``.ainvoke(TurnContext(req=...))`` runs the turn and yields a state dict — read
    ``early_response or response`` from it.
    """
    memory_fetch = functools.partial(_gedaechtnis_lesen, session)
    progress = progress or TurnProgress()

    g: StateGraph = StateGraph(TurnContext)

    def knoten(name: str, action: Any) -> None:
        # Jeder Knoten bucht seine Dauer in den Debug-Block (Plan 2026-09-30, T8) und
        # lässt die Verbindung frei zurück (Paket 19, H-5).
        g.add_node(name, messe_knoten(name, _mit_freigabe(action, session)))

    knoten("setup", functools.partial(setup, session=session, peer_ip=peer_ip))
    knoten("tour", functools.partial(tour, session=session))
    knoten("page_context_enrich", page_context_enrich)
    knoten("context_greeting", functools.partial(context_greeting, session=session))
    knoten("persist_user", functools.partial(_persist_user_message, session=session))
    knoten("preflight", functools.partial(preflight, session=session))
    knoten("assess", functools.partial(
        assess, memory_fetch=memory_fetch, progress=progress, engine=engine))
    knoten("safety_log", functools.partial(_log_turn_safety, session=session))
    knoten("pruefung_fehlt", functools.partial(pruefung_fehlt, session=session))
    knoten("merge", functools.partial(merge, engine=engine))
    knoten("route", functools.partial(route, progress=progress, engine=engine))
    knoten("respond", functools.partial(
        respond, session=session, on_token=on_token, progress=progress,
        engine=engine))
    knoten("assemble", assemble)
    knoten("persist", functools.partial(
        persist, session=session, progress=progress, engine=engine))

    g.add_edge(START, "setup")
    g.add_edge("setup", "tour")
    g.add_conditional_edges(
        "tour", _after_tour, {"page_context_enrich": "page_context_enrich", END: END}
    )
    g.add_edge("page_context_enrich", "context_greeting")
    g.add_conditional_edges(
        "context_greeting", _after_context_greeting, {"persist_user": "persist_user", END: END}
    )
    g.add_edge("persist_user", "preflight")
    g.add_conditional_edges("preflight", _after_preflight, {"assess": "assess", END: END})
    g.add_edge("assess", "safety_log")
    g.add_edge("safety_log", "pruefung_fehlt")
    g.add_conditional_edges(
        "pruefung_fehlt", nach_der_pruefung, {"merge": "merge", END: END}
    )
    g.add_edge("merge", "route")
    g.add_edge("route", "respond")
    g.add_edge("respond", "assemble")
    g.add_edge("assemble", "persist")
    g.add_edge("persist", END)

    return g.compile()


def begin_turn(ctx: TurnContext) -> None:
    """Die Zug-Sammler binden — VOR dem Graphen, nicht in einem seiner Knoten.

    Drei Sammler leben in ContextVars, weil ihre Erzeuger tief unten ohne
    Zug-Kontext laufen: die Query-Metas und die vorbereiteten Schreibzugriffe
    (``services/mcp/client``) und der Verbrauchs-Merkposten, in den der
    Vokabular-Abgleich bucht (``obs/usage``). **LangGraph startet jeden Knoten
    in einer Kopie des Kontexts.** Was ein Knoten bindet, sieht der nächste
    deshalb nicht — bis 2026-09-29 band ``setup`` die drei, und was ``respond``
    sammelte, kam in ``persist`` nie an (Audit 2026-09-29, gemessen an
    LangGraph 1.2.9): keine Facetten-Chips aus Query-Metas, kein
    vorbereiteter Schreibzugriff aus dem Tool-Loop, keine Buchung des
    Vokabular-Abgleichs.

    Hier gebunden, erbt jeder Knoten dieselben Objekte: seine Kopie zeigt auf
    die Liste bzw. das Dict dieses Zuges, und Anhängen/Buchen landet dort. Seit
    Paket 18C/D gehört die Zugakte dazu (``services/zugakte``), seit Paket 18F der Merker der
    LLM-Engstelle (``services/llm_parallel``: ein Zug ohne Platz scheitert danach sofort),
    seit Paket 19 (N-30) die Liste seiner Hintergrund-Aufgaben (``obs/tasks``).
    """
    reset_query_metas()
    reset_prepared_writes()
    bind_turn_usage(ctx.usage)
    binde_zugakte()
    binde_llm_zug()
    binde_zug_aufgaben()


async def run_turn(graph: CompiledStateGraph, ctx: TurnContext) -> dict[str, Any]:
    """Einen Zug durch ``graph`` laufen lassen — mit gebundenen Sammlern.

    Der einzige Weg, auf dem die Endpunkte den Graphen starten
    (``api/chat.py``: ``POST /api/chat`` und der Stream). Gibt das Zustands-Dict
    von ``ainvoke`` zurück.

    Im ``finally`` (Paket 19, N-30): was der Zug an Aufgaben gestartet und nicht
    verbraucht hat — etwa den spekulativen Schnellantwort-Aufruf, wenn ein Knoten
    scheiterte oder der Zug abgebrochen wurde —, wird abgebrochen.
    """
    begin_turn(ctx)
    try:
        return await graph.ainvoke(ctx)
    finally:
        await raeume_zug_aufgaben()
