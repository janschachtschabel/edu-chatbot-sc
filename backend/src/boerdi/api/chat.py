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

import asyncio
import json
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
from boerdi.graph.build import build_turn_graph
from boerdi.graph.state import TurnContext
from boerdi.obs.progress import TurnProgress
from boerdi.services.db_sessions import save_message
from boerdi.services.widget_postprocess import _postprocess_response_for_widget_modes

logger = logging.getLogger(__name__)

public_router = APIRouter(tags=["chat"])
router = APIRouter(tags=["chat"], dependencies=[Security(require_studio_key)])

# Keepalive cadence for the SSE stream: emit a comment line during quiet
# stretches (e.g. a slow MCP search) so proxies that drop idle connections
# after ~30 s keep it open. Module-level so tests can shrink it.
_SSE_KEEPALIVE_SECONDS = 10.0

# Cap on the progress queue (ALT ``chat.py:401``): without a bound, a slow client
# plus a chatty turn could grow it without limit in RAM. 200 is far above the
# events a real turn emits; on overflow the sink drops progress — the labels are
# idempotent and losable, the answer is not.
_SSE_PROGRESS_QUEUE_MAX = 200


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
    lock = await _get_session_lock(req.session_id)
    try:
        async with lock:
            try:
                graph = build_turn_graph(session=session, peer_ip=peer_ip(request))
                result = await graph.ainvoke(TurnContext(req=req))
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
                return ChatResponse(
                    session_id=req.session_id,
                    content=(
                        "Da ist intern etwas schiefgelaufen "
                        f"({type(impl_err).__name__}). Versuch es nochmal — "
                        "wenn es bestehen bleibt, gib mir kurz Bescheid."
                    ),
                    quick_replies=["Nochmal versuchen"],
                    debug=err_debug,
                )
    finally:
        # Cleanup MUST run AFTER ``async with lock`` exits; otherwise the lock is
        # still held and the refcount-pop check would leak entries.
        await _release_session_lock(req.session_id)


async def _stream_turn(
    req: ChatRequest, request: Request, session: AsyncSession
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
    queue: asyncio.Queue = asyncio.Queue(maxsize=_SSE_PROGRESS_QUEUE_MAX)
    _DONE = object()

    def _sink(event: dict) -> None:
        # Sync, non-blocking: runs inside the turn task, never awaits it.
        if queue.qsize() >= _SSE_PROGRESS_QUEUE_MAX - 1:
            return  # reserved slot for _DONE (see docstring)
        queue.put_nowait(event)

    async def _run_impl() -> ChatResponse | Exception:
        # Serialised per session_id, exactly like POST /api/chat; the finally
        # frees the lock even when the task is cancelled on client disconnect.
        lock = await _get_session_lock(req.session_id)
        try:
            async with lock:
                try:
                    graph = build_turn_graph(
                        session=session,
                        peer_ip=peer_ip(request),
                        progress=TurnProgress(_sink),
                    )
                    state = await graph.ainvoke(TurnContext(req=req))
                    return state.get("early_response") or state.get("response")
                except Exception as impl_err:
                    logger.exception("chat_stream impl failed: %s", impl_err)
                    return impl_err
        finally:
            await _release_session_lock(req.session_id)
            queue.put_nowait(_DONE)  # slot reserved by _sink

    def _phase(event: dict) -> str:
        return f"event: phase\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    impl_task = asyncio.create_task(_run_impl())
    # Handshake first — flushes proxy buffers so the client knows we're live.
    yield "event: connected\ndata: {}\n\n"
    while True:
        try:
            evt = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
        except TimeoutError:
            if await request.is_disconnected():
                impl_task.cancel()
                logger.info(
                    "chat_stream client disconnected — cancelling turn (session=%s)",
                    req.session_id,
                )
                # Await the cancellation so _run_impl's finally (lock release) has
                # run before we abandon the stream (ALT fired-and-forgot the cancel).
                try:
                    await impl_task
                except asyncio.CancelledError:
                    pass
                return
            yield ": keepalive\n\n"
            if impl_task.done():
                break  # died before its finally could queue _DONE (e.g. lock error)
            continue
        if evt is _DONE:
            break
        yield _phase(evt)
    # Events queued between the last get() and _DONE (the turn emits without
    # awaiting, so a burst can still be sitting here) — ALT drains them too.
    while not queue.empty():
        evt = queue.get_nowait()
        if evt is not _DONE:
            yield _phase(evt)

    result = await impl_task
    if isinstance(result, Exception):
        err_payload = {"message": f"{type(result).__name__}: {result}"[:400]}
        logger.warning(
            "chat_stream END session=%s status=error %s",
            req.session_id, err_payload["message"],
        )
        yield f"event: error\ndata: {json.dumps(err_payload)}\n\n"
        return
    # Apply the widget-embed modes here too — the /api/chat wrapper does not run
    # on this path since the stream drives the graph directly.
    try:
        result = await _postprocess_response_for_widget_modes(req, result)
    except Exception as pp_err:
        logger.warning("stream widget-modes postprocess failed: %s", pp_err)
    try:
        payload = result.model_dump()
    except Exception as dump_err:
        logger.warning("stream result.model_dump failed: %s", dump_err)
        payload = {"content": "(serialise error)"}
    yield (
        "event: result\n"
        f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    )


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
    return StreamingResponse(
        _stream_turn(req, request, session),
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
