"""Vorübergehende Fehler des Anbieters beim Strukturentwurf (Plan 2026-11-19, A1, E3).

Befund S1: ein 503 beim Aufruf für Ebene 1 wurde zum Sammelgrund ``fehler`` — dessen Text schickt
die KI in die Sackgasse („antworte ohne Entwurf“). ``gpt-6-luna`` läuft über die Responses-Brücke,
dort wiederholt das SDK nur 1–2 Mal (``services/llm``, Modulkopf). Deshalb hier: **einmal** nach
:data:`PAUSE_S` wiederholen, wenn die Frist es erlaubt; bleibt der Fehler, entscheidet der Aufrufer
(Ebene 1: Grund ``voruebergehend``, tiefer: ``ausstehend``).

Eine Zeitüberschreitung der eigenen Frist (``TimeoutError``) gehört nicht dazu — sie ist ``frist``.

Review Paket A, MINOR 4: EINE Regel mit dem übrigen Transport — vorübergehend ist, was
``llm_ereignisse.ist_voruebergehend`` so nennt (``openai.APITimeoutError`` samt
``litellm.Timeout``, 429, ``APIConnectionError`` nur mit einem Netzfehler in der Kette — LiteLLM
bildet JEDE Ausnahme ohne Status darauf ab), dazu jede Antwort mit Status ≥ 500
(``openai.APIStatusError``: 500, 502, 503).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Final

import openai

from boerdi.services.llm_ereignisse import ist_voruebergehend

PAUSE_S: Final = 2.0


def voruebergehend(fehler: BaseException) -> bool:
    """Ist ``fehler`` ein vorübergehender Fehler des Anbieters (5xx, Verbindung, Zeit beim
    Anbieter)? Die eigene Frist (``TimeoutError``) nie."""
    if isinstance(fehler, TimeoutError):
        return False
    status = getattr(fehler, "status_code", None)
    fuenfhundert = isinstance(fehler, openai.APIStatusError) and isinstance(status, int) and (
        status >= 500)
    return fuenfhundert or ist_voruebergehend(fehler)


async def einmal_wiederholt[T](aufruf: Callable[[], Awaitable[T]], rest: Callable[[], float],
                               mindest_rest_s: float) -> T:
    """``aufruf()`` — bei einem vorübergehenden Fehler genau ein zweites Mal nach
    :data:`PAUSE_S`, sofern danach noch ``mindest_rest_s`` bleiben. Sonst geht der Fehler weiter."""
    try:
        return await aufruf()
    except Exception as e:
        if not voruebergehend(e) or rest() - PAUSE_S < mindest_rest_s:
            raise
    await asyncio.sleep(PAUSE_S)
    return await aufruf()
