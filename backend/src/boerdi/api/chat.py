"""Chat endpoints (spec §5.1): POST /api/chat, POST /api/chat/stream (SSE),
GET /api/debug/mcp-test.

``POST /api/chat`` (R4f-1) is the turn's HTTP entry: it builds the per-request
LangGraph turn graph (``graph/build.build_turn_graph``), runs it under the
per-session lock, and returns ``early_response or response`` after the widget-modes
postprocess — the same shape ALT's ``_chat_impl`` produced, now graph-driven. Any
unhandled error inside the turn is converted into a graceful chat bubble, never an
HTTP 500 (ALT ``chat.py`` top-level safety net) — for the widget's background
turns (``domain/hintergrund_zug``) into an empty answer instead.

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

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.api.chat_handschlag import handschlag
from boerdi.api.deps import get_session, get_session_factory, require_studio_key, todo
from boerdi.api.ratelimit import peer_ip, public_rate_limit
from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.session_locks import sitzung_sperren
from boerdi.api.sse import sse_turn
from boerdi.api.turn_auth import uebernimm_zugang
from boerdi.domain.hintergrund_zug import ist_hintergrund_anfrage
from boerdi.graph.build import build_turn_graph, run_turn
from boerdi.graph.state import TurnContext
from boerdi.i18n import bot_text, msg, resolve_locale
from boerdi.obs import metrics
from boerdi.obs.log_inhalt import kennung
from boerdi.obs.progress import TurnProgress
from boerdi.obs.trace_id import fehlernummer
from boerdi.services import betriebsschalter, prompt_ablage
from boerdi.services.db_sessions import save_message
from boerdi.services.engine_choice import ENGINE_HEADER, choose_engine
from boerdi.services.mcp.anmeldung import abgelehnt_in_diesem_zug
from boerdi.services.sitzungssperre import SitzungBeschaeftigt
from boerdi.services.token_stream import TokenStrom
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

    Die Maschine (AG-1) kommt aus dem Debug-Block der Antwort und nicht noch
    einmal aus der Kopfzeile: so sagen Buchung und Debug-Block dasselbe, und
    ein Frühausstieg (leeres ``engine``) bucht ohne Maschine.
    """
    try:
        antwort = state.get("early_response") or state.get("response")
        debug = getattr(antwort, "debug", None)
        engine = getattr(debug, "engine", "") or None
        metrics.zug(engine)  # Paket 17 (D3): derselbe Trichter, den jeder Zug passiert
        await record_turn_usage(session, session_id, state.get("usage"), engine=engine)
        # Paket 13 (A5): neue Prompt-Fassungen dieses Zuges — derselbe Trichter, dieselbe Sitzung.
        await prompt_ablage.speichere(session, state.get("usage"))
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

    Serialised per ``session_id`` across all replicas (Paket 7, P1:
    ``sitzung_sperren``) so two turns of one session never read/write
    ``session_state`` in parallel; a second one waits briefly, then gets 409.
    Different sessions still run fully in parallel. The compiled graph yields a
    state dict — ``early_response`` (tour/preflight/fast-path early exit) wins over
    ``response`` (normal path). Any unhandled error becomes a graceful bubble
    instead of an HTTP 500 so the widget shows something actionable.
    """
    await uebernimm_zugang(request)
    try:
        async with sitzung_sperren(request, req.session_id):
            try:
                graph = build_turn_graph(
                    session=session, peer_ip=peer_ip(request),
                    engine=choose_engine(request.headers.get(ENGINE_HEADER)),
                )
                result = await run_turn(graph, TurnContext(req=req))
                await _record_usage(session, req.session_id, result)
                resp = _anmeldestand(result.get("early_response") or result.get("response"))
                return await _postprocess_response_for_widget_modes(req, resp)
            except Exception as impl_err:
                # Top-level safety net: a config bug, a pattern-engine attribute
                # error, a DB hiccup — a chat bubble with the error number (Paket 18C/D)
                # rather than letting the frontend swallow an HTTP 500.
                logger.exception("chat endpoint unhandled exception: %s", impl_err)
                return await _fehlerblase(session, req, impl_err)
    except SitzungBeschaeftigt:
        # Paket 7 (P1, P5-1): ein anderer Zug derselben Sitzung läuft noch, auch
        # auf einer anderen Kopie. Kein Graph, kein Verlauf — das Widget zeigt
        # dazu seinen eigenen Text; Hintergrund-Pings schluckt es still.
        raise HTTPException(status_code=409, detail=msg(
            resolve_locale(getattr(req.environment, "locale", None)),
            "chat.sessionBusy")) from None
    except Exception as sperr_err:
        # Paket 9 (Review Paket 7, MINOR 30): die Sperre selbst scheiterte (etwa die
        # Datenbank weg) — bis dahin HTTP 500. Die Freigabe fängt ihre Fehler selbst
        # (``services/sitzungssperre``); hier landet also keine fertige Antwort.
        logger.exception("chat endpoint: Sitzungssperre gescheitert: %s", sperr_err)
        return await _fehlerblase(session, req, sperr_err)


def _anmeldestand(resp: ChatResponse | None) -> ChatResponse | None:
    """Wies der MCP-Server den Block dieses Zuges ab (Paket 10, Kurzaudit A-3)? Dann
    erfährt es das Widget. Im Task des Zuges gelesen — der Stand gilt über alle
    Knoten (``services/mcp/auth._ZugStand``)."""
    if resp is not None and abgelehnt_in_diesem_zug():
        resp.auth_invalid = True
    return resp


async def _fehlerblase(
    session: AsyncSession, req: ChatRequest, fehler: BaseException,
) -> ChatResponse:
    """Die Antwort auf einen gescheiterten Zug — beide Wege (Paket 9: bis dahin nur
    ``POST /api/chat``; ein Strom, der nach dem Auflegen weiterlief und scheiterte,
    ließ die Frage im Verlauf ohne Antwort).

    Gespeichert wird, was die Person sieht (Audit 2026-09-29, 6.3): der Verlauf zeigt
    nach einem Neuladen dieselbe Blase, und der Modell-Verlauf bekommt keine interne
    Marke wie ``[unhandled error: …]``.
    """
    err_debug = DebugInfo(pattern="ERROR: unhandled_chat_exception", tools_called=["error"])
    if ist_hintergrund_anfrage(req.environment):
        # Kontext-Ping und Tour-Tick schickt das Widget von sich aus und schluckt
        # ihre Fehler still — eine Blase zeigte es trotzdem an: eine Antwort auf
        # eine Frage, die niemand gestellt hat, und ein sichtbarer Zug, der einen
        # offenen Schreibvorgang nicht verfallen lässt (Befund 2026-10-08). Also
        # stumm und ohne Eintrag im Verlauf.
        return ChatResponse(session_id=req.session_id, content="", follow_up="none",
                            debug=err_debug)
    lang = resolve_locale(getattr(req.environment, "locale", None))
    err_text = bot_text(lang, "error.internal", nummer=fehlernummer())
    try:
        # Nach einem Fehler steht die Transaktion womöglich auf „abgebrochen“.
        await session.rollback()
    except Exception:
        logger.debug("Rollback vor der Fehlerblase gescheitert", exc_info=True)
    try:
        await save_message(session, req.session_id, "assistant", err_text,
                           debug=err_debug.model_dump())
    except Exception:
        # Never let a DB-write failure mask the original error.
        logger.debug("Fehlerblase nicht gespeichert", exc_info=True)
    return ChatResponse(
        session_id=req.session_id,
        content=err_text,
        quick_replies=[bot_text(lang, "error.retryChip")],
        debug=err_debug,
    )


async def _stream_turn(
    req: ChatRequest, request: Request, sitzungen: async_sessionmaker[AsyncSession],
    engine: str = "pattern",
) -> AsyncIterator[str]:
    """Yield the SSE frames for one streamed turn: connected → phase* → result | error.

    The turn runs as a task. Since Paket 7 (P2) an abandoned connection lets it run
    to the end — the answer lands in the history and the widget fetches it there,
    instead of asking a second time (``sse_turn(nach_abbruch="zu_ende")``); the
    ``connected`` frame tells it whether the history is kept and from which message
    on (``chat_handschlag``). While it runs, this
    generator drains the progress queue the graph writes into (C9) and forwards each
    event as a ``phase`` frame (answer text as ``text_delta``, behind
    ``CHAT_TOKEN_STREAMING``) — that is what turns the widget's bare 6-10 s spinner
    into "Verstehe deine Anfrage …" → "Durchsuche WLO-Inhalte …" → "Formuliere
    Antwort …" (``ui/stream/phase-label.ts``).

    Loop shape ported from ALT ``chat.py:448``: block on the queue with a keepalive
    timeout, and end on a ``_DONE`` sentinel the turn queues in its ``finally``. The
    sentinel needs a guaranteed slot, so the sink stops one short of the cap —
    otherwise a flood of progress could crowd out ``_DONE`` and delay the answer by
    a whole keepalive interval.

    The turn opens its OWN session from ``sitzungen`` (Review Paket 7, A-1): after
    a hang-up it runs to the end (P2), but FastAPI closes the request-scoped session
    as soon as the response ends — the turn would keep writing on a session that is
    being closed under it.
    """
    # Token-Streaming (Plan 2026-10-01, T12): ein Strom je Anfrage, nur mit
    # Schalter. ``respond`` öffnet oder sperrt ihn; ``_to_payload`` misst ihn.
    strom: TokenStrom | None = None

    async def _run_impl(progress: TurnProgress) -> ChatResponse | Exception:
        nonlocal strom
        # Serialised per session_id, exactly like POST /api/chat. A busy session
        # raises ``SitzungBeschaeftigt`` out of here; ``sse_turn`` turns it into an
        # ``error`` frame carrying its ``sse_code`` (Paket 7, P1).
        async with sitzung_sperren(request, req.session_id), sitzungen() as session:
            try:
                if betriebsschalter.token_streaming():  # Paket 7, S2
                    strom = TokenStrom(progress)
                graph = build_turn_graph(
                    session=session,
                    peer_ip=peer_ip(request),
                    progress=progress,
                    engine=engine,
                    on_token=strom,
                )
                state = await run_turn(graph, TurnContext(req=req))
                await _record_usage(session, req.session_id, state)
                return _anmeldestand(state.get("early_response") or state.get("response"))
            except Exception as impl_err:
                logger.exception("chat_stream impl failed: %s", impl_err)
                # In den Verlauf wie beim POST-Weg — legte der Client auf, holt das
                # Widget die Antwort dort (P2); der Strom meldet seinen ``error``-Rahmen.
                await _fehlerblase(session, req, impl_err)
                return impl_err

    async def _to_payload(result: ChatResponse) -> dict:
        # Apply the widget-embed modes here too — the /api/chat wrapper does not
        # run on this path since the stream drives the graph directly.
        try:
            result = await _postprocess_response_for_widget_modes(req, result)
        except Exception as pp_err:
            logger.warning("stream widget-modes postprocess failed: %s", pp_err)
        if strom is not None:
            strom.abschluss(result.content or "")  # Kennzahlen + Drift-Logzeile
        return result.model_dump()

    # Paket 7 (P2, P5-2): legt der Client auf, rechnet der Zug sauber zu Ende —
    # die Antwort landet im Verlauf, und das Widget holt sie dort, statt die
    # Frage noch einmal zu schicken. Die Sitzungssperre hält bis zum Ende. Nur,
    # wenn der Verlauf gespeichert wird; gelesen VOR dem Start des Zuges
    # (Review A-7/C-4, ``chat_handschlag``).
    verbunden = await handschlag(req.session_id, sitzungen)
    async for frame in sse_turn(
        request, _run_impl, _to_payload, label=f"chat_stream session={kennung(req.session_id)}",
        nach_abbruch="zu_ende" if verbunden["history"] else "abbrechen",
        verbunden=verbunden,
    ):
        yield frame


@public_router.post("/api/chat/stream")
@public_rate_limit
async def chat_stream(
    req: ChatRequest,
    request: Request,
    sitzungen: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
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
    await uebernimm_zugang(request)
    return StreamingResponse(
        _stream_turn(req, request, sitzungen,
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
