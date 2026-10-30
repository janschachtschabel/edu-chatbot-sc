"""Der SSE-Rahmen: connected → (phase | text_delta)* → result | error (A3b1).

Herausgezogen aus ``api/chat.py``. Anlass war der zweite Verbraucher
(``api/agent.py``): die knifflige Hälfte dieser Schleife — der für ``_DONE``
reservierte Warteschlangenplatz, der Keepalive gegen Zwischenspeicher, der Umgang
mit aufgelegten Verbindungen, das Nachlaufen der Warteschlange — zweimal zu
führen hieße, sie zweimal zu pflegen und einmal zu vergessen.

Seit Paket 7 (P2) bricht eine aufgelegte Verbindung nur noch den Agent-Endpunkt
ab; der Chat rechnet zu Ende und speichert die Antwort im Verlauf
(:data:`NachAbbruch`), beim Herunterfahren abgewartet von
:func:`nachlaeufer_abwarten` (Paket 9). ``connected`` trägt ``history`` und
``after_id``, ein ``error`` kann ``code: "session_busy"`` tragen.

**Was hier NICHT wohnt:** was ein Zug *ist*. Sitzungssperre, Graph,
Kostenbuchung, Widget-Nachbereitung bleiben beim Aufrufer. Dieser Rahmen weiß
nur, dass etwas läuft, dabei Fortschritt meldet und am Ende ein Ergebnis oder
eine Ausnahme hat.

Die Rahmennamen sind Vertrag (Spezifikation Regel 6): ``connected`` /
``phase`` / ``result`` / ``error``. ``end`` sendet NEU bewusst nicht. Dazu kommt
``text_delta`` mit ``{"text", "pos"}`` für das Token-Streaming (Name und ``text``
wie ALT, ``pos`` neu; Plan ``2026-10-01-token-streaming``) — ein Client, der ihn
nicht kennt, verhält sich wie zuvor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

from fastapi import Request

from boerdi.obs.progress import TurnProgress

logger = logging.getLogger(__name__)

# Keepalive-Takt: eine Kommentarzeile in stillen Strecken (z.B. eine langsame
# MCP-Suche), damit Zwischenspeicher, die untätige Verbindungen nach ~30 s
# kappen, sie offen halten. Modulweit, damit Tests ihn verkleinern können.
KEEPALIVE_SECONDS = 10.0

# Deckel der Fortschritts-Warteschlange (ALT ``chat.py:401``): ohne Grenze
# könnten ein langsamer Client und ein redseliger Zug sie im Speicher wachsen
# lassen. 200 liegt weit über dem, was ein echter Zug meldet; beim Überlauf
# fällt Fortschritt weg — die Labels sind wiederholbar und verlierbar, die
# Antwort ist es nicht.
PROGRESS_QUEUE_MAX = 200

#: Was der Aufrufer beisteuert: eine Arbeit, die Fortschritt melden kann, und
#: eine Übersetzung ihres Ergebnisses in die Nutzlast des ``result``-Rahmens.
RunTurn = Callable[[TurnProgress], Awaitable[Any]]
ToPayload = Callable[[Any], Awaitable[dict[str, Any]]]

#: Was eine aufgelegte Verbindung mit der laufenden Arbeit macht (Paket 7, P2).
#: ``abbrechen`` spart LLM-/MCP-Kosten für niemanden (``/api/agent``: es gibt
#: keinen Verlauf, aus dem jemand nachlädt). ``zu_ende`` rechnet sauber fertig —
#: der Chat speichert die Antwort im Verlauf, und das Widget holt sie dort.
NachAbbruch = Literal["abbrechen", "zu_ende"]

#: Zu Ende laufende Arbeiten ohne Zuhörer. Die Referenz hält sie am Leben:
#: asyncio führt Aufgaben nur schwach, eine verwaiste könnte mitten im Zug
#: verschwinden.
_NACHLAEUFER: set[asyncio.Task[Any]] = set()


def _nachlaufen_lassen(task: asyncio.Task[Any], label: str) -> None:
    _NACHLAEUFER.add(task)
    task.add_done_callback(_NACHLAEUFER.discard)
    logger.info("%s: Verbindung aufgelegt — Zug rechnet zu Ende (Antwort im Verlauf)",
                label or "sse_turn")


#: Wie lange das Herunterfahren auf nachlaufende Züge wartet (Paket 9). Das Warten
#: beginnt erst NACH dem von uvicorn (``--timeout-graceful-shutdown`` 30 s im
#: Dockerfile): beides zusammen, dazu Abbruch und Aufräumen, muss unter die
#: Gnadenfrist des Containers passen (``stop_grace_period`` 65 s in
#: ``compose.prod.yml``; Review Paket 9, Wächter in ``tests/test_deploy_compose.py``).
NACHLAUF_FRIST_S = 25.0


async def nachlaeufer_abwarten(frist_s: float = NACHLAUF_FRIST_S) -> int:
    """Beim Herunterfahren: nachlaufende Züge zu Ende rechnen lassen, höchstens
    ``frist_s`` lang; was dann noch läuft, wird abgebrochen. Gibt deren Zahl zurück.

    Review Paket 7 (MINOR 29): bis dahin wartete niemand — bei jedem Deploy konnte
    eine Antwort fehlen, die das Widget danach vergeblich im Verlauf suchte.
    """
    offen = set(_NACHLAEUFER)
    if not offen:
        return 0
    logger.info("Herunterfahren: warte auf %d nachlaufende Züge (höchstens %ss)",
                len(offen), frist_s)
    _fertig, haengend = await asyncio.wait(offen, timeout=frist_s)
    for aufgabe in haengend:
        aufgabe.cancel()
    if haengend:
        await asyncio.wait(haengend, timeout=5)
        logger.warning("Herunterfahren: %d nachlaufende Züge abgebrochen — ihre Antwort "
                       "fehlt im Verlauf", len(haengend))
    return len(haengend)


def _frame(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _aufgelegt(task: asyncio.Task[Any], nach_abbruch: NachAbbruch, label: str) -> None:
    """Die Verbindung ist weg (beim Keepalive bemerkt)."""
    if nach_abbruch == "zu_ende":
        _nachlaufen_lassen(task, label)
        return
    task.cancel()
    logger.info("%s: Verbindung aufgelegt — Zug abgebrochen", label)
    # Auf den Abbruch warten, damit das ``finally`` der Arbeit (etwa eine
    # Sperre) gelaufen ist, bevor wir den Strom aufgeben.
    try:
        await task
    except asyncio.CancelledError:
        pass


def _rahmen_fuer(evt: dict[str, Any]) -> str:
    """Ein Sink-Ereignis als Rahmen: Antworttext wird ``text_delta``, alles
    andere ``phase``."""
    if evt.get("kind") == "text":
        return _frame("text_delta", evt.get("data") or {})
    return _frame("phase", evt)


async def sse_turn(
    request: Request,
    run: RunTurn,
    to_payload: ToPayload,
    *,
    label: str = "",
    nach_abbruch: NachAbbruch = "abbrechen",
    verbunden: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Führe ``run`` als Aufgabe und sende ihren Verlauf als SSE.

    Legt der Client auf, entscheidet ``nach_abbruch``: abbrechen (Vorgabe) oder
    zu Ende rechnen lassen — bemerkt beim Keepalive-Takt wie beim Schließen des
    Generators. Ausnahmen aus ``run`` werden zum ``error``-Rahmen; ``to_payload``
    darf ebenfalls scheitern, ohne den Strom zu zerreißen. ``verbunden`` ist die
    Nutzlast des ``connected``-Rahmens (Vorgabe ``{}``; der Chat meldet dort, ob
    und ab wo er den Verlauf schreibt — ``api/chat_handschlag``).
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=PROGRESS_QUEUE_MAX)
    _DONE = object()

    def _sink(event: dict) -> None:
        # Synchron und nicht blockierend: läuft in der Zug-Aufgabe, wartet nie.
        if queue.qsize() >= PROGRESS_QUEUE_MAX - 1:
            return  # der reservierte Platz gehört ``_DONE``
        queue.put_nowait(event)

    async def _runner() -> Any:
        try:
            return await run(TurnProgress(_sink))
        except Exception as impl_err:
            if getattr(impl_err, "sse_code", None):
                # Ein erwarteter Ausgang mit eigener Kennung (Paket 7, P1: Sitzung
                # beschäftigt) — kein Fehler, der einen Stacktrace verdient.
                logger.info("%s: %s", label or "sse_turn", impl_err.sse_code)
            else:
                logger.exception("%s impl failed: %s", label or "sse_turn", impl_err)
            return impl_err
        finally:
            queue.put_nowait(_DONE)  # Platz von ``_sink`` freigehalten

    impl_task = asyncio.create_task(_runner())
    try:
        # Handschlag zuerst — leert die Puffer der Zwischenspeicher, damit der
        # Client weiß, dass die Leitung steht.
        yield _frame("connected", verbunden or {})
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
            except TimeoutError:
                if await request.is_disconnected():
                    await _aufgelegt(impl_task, nach_abbruch, label)
                    return
                yield ": keepalive\n\n"
                if impl_task.done():
                    break  # starb, bevor sein finally ``_DONE`` einreihen konnte
                continue
            if evt is _DONE:
                break
            yield _rahmen_fuer(evt)
    except (GeneratorExit, asyncio.CancelledError):
        # Der Server schließt den Strom, weil das Senden scheiterte — derselbe
        # Abbruch auf anderem Weg. Bis Paket 7 lief die Arbeit hier verwaist
        # weiter, ohne Referenz und ohne Absicht.
        if not impl_task.done():
            if nach_abbruch == "zu_ende":
                _nachlaufen_lassen(impl_task, label)
            else:
                impl_task.cancel()
        raise
    # Was zwischen dem letzten ``get()`` und ``_DONE`` einging (der Zug meldet
    # ohne zu warten, ein Schwall kann also noch hier liegen).
    while not queue.empty():
        evt = queue.get_nowait()
        if evt is not _DONE:
            yield _rahmen_fuer(evt)

    result = await impl_task
    if isinstance(result, Exception):
        nachricht = f"{type(result).__name__}: {result}"[:400]
        # Audit 2026-09-29 A-M4: Typ und Text der Ausnahme bleiben im Log — der
        # Rahmen geht auch an anonyme Clients. Das Widget zeigt ohnehin seinen
        # eigenen, übersetzten Fehlertext; eine ``sse_code`` der Ausnahme sagt
        # ihm, welchen (Paket 7, P1: ``session_busy``). Ein solcher Fall ist
        # erwartbar (ein Doppelversand) und steht auf INFO (Paket 9).
        code = getattr(result, "sse_code", None)
        logger.log(logging.INFO if code else logging.WARNING,  # log-ok: Fehlertext
                   "%s END status=error %s", label or "sse_turn", nachricht)
        yield _frame("error", {"message": "internal error", **({"code": code} if code else {})})
        return
    try:
        payload = await to_payload(result)
    except Exception as dump_err:
        logger.warning("%s: Ergebnis nicht serialisierbar: %s", label, dump_err)
        payload = {"content": "(serialise error)"}
    yield _frame("result", payload)
