"""Der SSE-Rahmen: connected → phase* → result | error (A3b1).

Herausgezogen aus ``api/chat.py``, unverändert im Verhalten. Anlass ist der
zweite Verbraucher (``api/agent.py``): die knifflige Hälfte dieser Schleife —
der für ``_DONE`` reservierte Warteschlangenplatz, der Keepalive gegen
Zwischenspeicher, das Abbrechen bei aufgelegter Verbindung, das Nachlaufen der
Warteschlange — zweimal zu führen hieße, sie zweimal zu pflegen und einmal zu
vergessen.

**Was hier NICHT wohnt:** was ein Zug *ist*. Sitzungssperre, Graph,
Kostenbuchung, Widget-Nachbereitung bleiben beim Aufrufer. Dieser Rahmen weiß
nur, dass etwas läuft, dabei Fortschritt meldet und am Ende ein Ergebnis oder
eine Ausnahme hat.

Die Rahmennamen sind Vertrag (Spezifikation Regel 6): ``connected`` /
``phase`` / ``result`` / ``error``. ``end`` sendet NEU bewusst nicht.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

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


def _frame(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def sse_turn(
    request: Request,
    run: RunTurn,
    to_payload: ToPayload,
    *,
    label: str = "",
) -> AsyncIterator[str]:
    """Führe ``run`` als abbrechbare Aufgabe und sende ihren Verlauf als SSE.

    ``run`` läuft als Aufgabe, damit eine aufgegebene Verbindung aufhört, einen
    LLM-/MCP-Platz für Arbeit zu verbrennen, der niemand mehr zuhört. Ausnahmen
    aus ``run`` werden zum ``error``-Rahmen; ``to_payload`` darf ebenfalls
    scheitern, ohne den Strom zu zerreißen.
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
            logger.exception("%s impl failed: %s", label or "sse_turn", impl_err)
            return impl_err
        finally:
            queue.put_nowait(_DONE)  # Platz von ``_sink`` freigehalten

    impl_task = asyncio.create_task(_runner())
    # Handschlag zuerst — leert die Puffer der Zwischenspeicher, damit der
    # Client weiß, dass die Leitung steht.
    yield "event: connected\ndata: {}\n\n"
    while True:
        try:
            evt = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
        except TimeoutError:
            if await request.is_disconnected():
                impl_task.cancel()
                logger.info("%s: Verbindung aufgelegt — Zug abgebrochen", label)
                # Auf den Abbruch warten, damit das ``finally`` der Arbeit
                # (etwa eine Sperre) gelaufen ist, bevor wir den Strom aufgeben.
                try:
                    await impl_task
                except asyncio.CancelledError:
                    pass
                return
            yield ": keepalive\n\n"
            if impl_task.done():
                break  # starb, bevor sein finally ``_DONE`` einreihen konnte
            continue
        if evt is _DONE:
            break
        yield _frame("phase", evt)
    # Was zwischen dem letzten ``get()`` und ``_DONE`` einging (der Zug meldet
    # ohne zu warten, ein Schwall kann also noch hier liegen).
    while not queue.empty():
        evt = queue.get_nowait()
        if evt is not _DONE:
            yield _frame("phase", evt)

    result = await impl_task
    if isinstance(result, Exception):
        nachricht = f"{type(result).__name__}: {result}"[:400]
        logger.warning("%s END status=error %s", label or "sse_turn", nachricht)
        yield _frame("error", {"message": nachricht})
        return
    try:
        payload = await to_payload(result)
    except Exception as dump_err:
        logger.warning("%s: Ergebnis nicht serialisierbar: %s", label, dump_err)
        payload = {"content": "(serialise error)"}
    yield _frame("result", payload)
