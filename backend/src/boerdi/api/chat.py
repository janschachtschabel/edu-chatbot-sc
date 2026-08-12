"""Chat endpoints (spec §5.1): POST /api/chat, POST /api/chat/stream (SSE),
GET /api/debug/mcp-test.

``POST /api/chat`` (R4f-1) is the turn's HTTP entry: it builds the per-request
LangGraph turn graph (``graph/build.build_turn_graph``), runs it under the
per-session lock, and returns ``early_response or response`` after the widget-modes
postprocess — the same shape ALT's ``_chat_impl`` produced, now graph-driven. Any
unhandled error inside the turn is converted into a graceful chat bubble, never an
HTTP 500 (ALT ``chat.py`` top-level safety net).

``POST /api/chat/stream`` (R4f-2) is the SSE sibling: the same turn, streamed as
Server-Sent-Events (``connected`` handshake → ``phase`` progress + keepalives →
``result``/``error``). The frame names are contract (spec rule 6): connected /
phase / result / error. ``/api/debug/mcp-test`` (P5-1) is still a stub.
Rate-limited at the HTTP layer since P1-4 (V7); ``request`` params exist for the
limiter key function.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session, require_studio_key, todo
from boerdi.api.ratelimit import peer_ip, public_rate_limit
from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.session_locks import _get_session_lock, _release_session_lock
from boerdi.api.sse import sse_turn
from boerdi.api.turn_auth import adopt_turn_auth_block
from boerdi.graph.build import build_turn_graph
from boerdi.graph.state import TurnContext
from boerdi.i18n import bot_text, resolve_locale
from boerdi.obs.progress import TurnProgress
from boerdi.services.db_sessions import save_message
from boerdi.services.engine_choice import ENGINE_HEADER, choose_engine
from boerdi.services.usage_store import record_turn_usage
from boerdi.services.widget_postprocess import _postprocess_response_for_widget_modes

logger = logging.getLogger(__name__)

public_router = APIRouter(tags=["chat"])
router = APIRouter(tags=["chat"], dependencies=[Security(require_studio_key)])


async def _record_usage(session: AsyncSession, session_id: str, state: dict) -> None:
    """Den Token-Verbrauch dieses Zuges ablegen (K2b).

    **Warum hier und nicht im persist-Knoten:** dies ist der einzige Punkt, den
    JEDER Zug passiert. Der persist-Knoten läuft nur auf dem Hauptweg — eine
    Direkt-Aktion und der Sicherheits-Block beenden den Zug schon im preflight,
    und beide geben nachweislich Token aus (Kuration, Lernpfad, Quick-Replies,
    Rechtsprüfung). Gemessen am 2026-08-11: **nur** diese beiden Ausstiege
    kosten etwas; Tour und Kontext-Begrüßung rufen kein LLM. Statt drei Stellen
    aufzuzählen — und die vierte zu vergessen, sobald jemand einen neuen
    Früh-Ausstieg baut — schreibt der Trichter einmal für alle.

    Der Aufruf ist nachrangig gegenüber der Antwort: schlägt er fehl, geht die
    Antwort trotzdem raus (``usage_store`` schluckt seine eigenen Fehler; das
    ``try`` hier fängt zusätzlich alles, was davor schiefgeht — etwa ein
    unerwartet geformter Zustand).
    """
    try:
        await record_turn_usage(session, session_id, state.get("usage"))
    except Exception:
        logger.warning("usage: Verbrauch dieses Zuges nicht erfasst", exc_info=True)


@public_router.post("/api/chat", response_model=ChatResponse)
@public_rate_limit
async def chat(
    req: ChatRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatResponse:
    """Run one chat turn through the LangGraph pipeline.

    Serialised per ``session_id`` via an ``asyncio.Lock`` so two concurrent
    requests from the same session never read/write ``session_state`` in parallel;
    different sessions still run fully in parallel. The compiled graph yields a
    state dict — ``early_response`` (tour/preflight/fast-path early exit) wins over
    ``response`` (normal path). Any unhandled error becomes a graceful bubble
    instead of an HTTP 500 so the widget shows something actionable.
    """
    adopt_turn_auth_block(request)
    lock = await _get_session_lock(req.session_id)
    try:
        async with lock:
            try:
                graph = build_turn_graph(
                    session=session, peer_ip=peer_ip(request),
                    engine=choose_engine(request.headers.get(ENGINE_HEADER)),
                )
                result = await graph.ainvoke(TurnContext(req=req))
                await _record_usage(session, req.session_id, result)
                resp = result.get("early_response") or result.get("response")
                return await _postprocess_response_for_widget_modes(req, resp)
            except Exception as impl_err:
                # Top-level safety net: a config bug, a pattern-engine attribute
                # error, a DB hiccup — surface the exception type to the user as a
                # chat bubble rather than letting the frontend swallow an HTTP 500.
                logger.exception("chat endpoint unhandled exception: %s", impl_err)
                err_debug = DebugInfo(
                    pattern="ERROR: unhandled_chat_exception", tools_called=["error"],
                )
                try:
                    await save_message(
                        session, req.session_id, "assistant",
                        f"[unhandled error: {type(impl_err).__name__}]",
                        debug=err_debug.model_dump(),
                    )
                except Exception:
                    pass  # never let a DB-write failure mask the original error
                _err_lang = resolve_locale(
                    getattr(req.environment, "locale", None))
                return ChatResponse(
                    session_id=req.session_id,
                    content=bot_text(
                        _err_lang, "error.internal",
                        kind=type(impl_err).__name__,
                    ),
                    quick_replies=[bot_text(_err_lang, "error.retryChip")],
                    debug=err_debug,
                )
    finally:
        # Cleanup MUST run AFTER ``async with lock`` exits; otherwise the lock is
        # still held and the refcount-pop check would leak entries.
        await _release_session_lock(req.session_id)


async def _stream_turn(
    req: ChatRequest, request: Request, session: AsyncSession,
    engine: str = "pattern",
) -> AsyncIterator[str]:
    """Yield the SSE frames for one streamed turn: connected → phase* → result | error.

    The turn runs as a cancellable task so an abandoned connection stops burning an
    LLM/MCP concurrency slot on work nobody is listening for. While it runs, this
    generator drains the progress queue the graph writes into (C9) and forwards each
    event as a ``phase`` frame — that is what turns the widget's bare 6-10 s spinner
    into "Verstehe deine Anfrage …" → "Durchsuche WLO-Inhalte …" → "Formuliere
    Antwort …" (``ui/stream/phase-label.ts``).

    Loop shape ported from ALT ``chat.py:448``: block on the queue with a keepalive
    timeout, and end on a ``_DONE`` sentinel the turn queues in its ``finally``. The
    sentinel needs a guaranteed slot, so the sink stops one short of the cap —
    otherwise a flood of progress could crowd out ``_DONE`` and delay the answer by
    a whole keepalive interval.
    """
    async def _run_impl(progress: TurnProgress) -> ChatResponse | Exception:
        # Serialised per session_id, exactly like POST /api/chat; the finally
        # frees the lock even when the task is cancelled on client disconnect.
        lock = await _get_session_lock(req.session_id)
        try:
            async with lock:
                try:
                    graph = build_turn_graph(
                        session=session,
                        peer_ip=peer_ip(request),
                        progress=progress,
                        engine=engine,
                    )
                    state = await graph.ainvoke(TurnContext(req=req))
                    await _record_usage(session, req.session_id, state)
                    return state.get("early_response") or state.get("response")
                except Exception as impl_err:
                    logger.exception("chat_stream impl failed: %s", impl_err)
                    return impl_err
        finally:
            await _release_session_lock(req.session_id)

    async def _to_payload(result: ChatResponse) -> dict:
        # Apply the widget-embed modes here too — the /api/chat wrapper does not
        # run on this path since the stream drives the graph directly.
        try:
            result = await _postprocess_response_for_widget_modes(req, result)
        except Exception as pp_err:
            logger.warning("stream widget-modes postprocess failed: %s", pp_err)
        return result.model_dump()

    async for frame in sse_turn(
        request, _run_impl, _to_payload, label=f"chat_stream session={req.session_id}"
    ):
        yield frame


@public_router.post("/api/chat/stream")
@public_rate_limit
async def chat_stream(
    req: ChatRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    """Stream one chat turn as Server-Sent-Events (connected → result | error).

    Same turn pipeline as POST /api/chat, wrapped so the frontend gets an
    immediate ``connected`` handshake and keepalives through proxies during the
    2–5 s classification + tool-loop, instead of a static spinner. See
    ``_stream_turn`` for the frame contract (no ``phase`` frames in NEU).
    """
    # Der Zugangsblock wird HIER übernommen, nicht in ``_stream_turn``: das ist
    # die HTTP-Grenze (symmetrisch zu ``chat``), und der Zug läuft ohnehin in
    # einer Task, die den Kontext beim Erzeugen erbt.
    #
    # Als Kommentar und NICHT im Docstring: FastAPI trägt Docstrings als
    # ``description`` in das eingefrorene OpenAPI-Dokument ein — der Zusatz hier
    # hat den Vertragstest brechen lassen. Gemessen 2026-08-10; die Kopfzeile
    # selbst blieb unsichtbar (``parameters`` bleibt ``None``).
    adopt_turn_auth_block(request)
    return StreamingResponse(
        _stream_turn(req, request, session,
                     engine=choose_engine(request.headers.get(ENGINE_HEADER))),
        media_type="text/event-stream",
        headers={
            # Proxies must not buffer or transform SSE.
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/api/debug/mcp-test")
def debug_mcp_test() -> dict:
    raise todo("P5-1")
