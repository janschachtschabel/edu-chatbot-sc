"""Fire-and-forget-Task-Helfer (Port der ALT ``chat_session_utils``-Utilities).

``_retrieve_task_exception`` ist der Done-Callback, den jeder Fire-and-forget-/
Spekulativ-``asyncio.Task`` bekommt: er ruft die Exception eines verworfenen
Tasks ab (und debug-loggt sie), statt sie als asyncio-Warnung "Task exception was
never retrieved" auflaufen zu lassen. Reine Infrastruktur (asyncio + Logging) →
``obs/``.

``_spawn_background``/``_BG_TASKS`` (die ALT ebenfalls hier beheimatete) sind mit
ihrem Konsumenten — dem Quality-Log-Spawner des ``persist``-Node — hinzugekommen:
create_task + starke Referenz (der Loop hält nur Weak-Refs) + Exception-Retrieval.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)


async def cancel_and_drain(tasks: Iterable[asyncio.Task | None]) -> int:
    """Spekulative Tasks abbrechen und ihr Ende abwarten; gibt ihre Zahl zurück.

    ``None`` wird übersprungen, damit der Aufrufer nicht erst filtern muss — ein
    Zug ohne Vorabruf trägt ``spec_task=None``. Abwarten statt bloßem
    ``cancel()``: sonst räumt die Aufgabe erst irgendwann später ab, und ihre
    Ausnahme liefe als „Task exception was never retrieved" auf.

    Dieselbe Bauart, die ``graph/nodes/respond`` für seine beiden Verwurf-Fälle
    inline trägt (LP-/Canvas-Route). Hier steht sie, seit mit dem Agent-Modus
    (A4c-2b) ein dritter Fall dazukam.
    """
    verworfen = 0
    for task in tasks:
        if task is None:
            continue
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        verworfen += 1
    return verworfen


def _retrieve_task_exception(task: asyncio.Task) -> None:
    """Done-Callback für fire-and-forget-/Spekulativ-Tasks (B1, 2026-06-10).

    Ruft die Exception ab, damit asyncio kein "Task exception was never
    retrieved" loggt, wenn ein Task verworfen wird (z.B. Spekulativ-Suche
    auf LP-/Canvas-Routen oder Exception vor dem Konsum)."""
    try:
        exc = task.exception()
        if exc is not None:
            logger.debug("background task ended with %s: %s", type(exc).__name__, exc)
    except (asyncio.CancelledError, asyncio.InvalidStateError):
        pass


# Starke Referenzen auf fire-and-forget-Tasks: der Event-Loop hält nur
# Weak-Refs — ohne dieses Set kann ein create_task()-Task vor seiner
# Ausführung garbage-collected werden (Quality-Log ginge still verloren).
_BG_TASKS: set[asyncio.Task] = set()


def _spawn_background(coro: Any) -> None:
    """create_task + starke Referenz + Exception-Retrieval (B1/Robustheit)."""
    t = asyncio.create_task(coro)
    _BG_TASKS.add(t)
    t.add_done_callback(lambda task: (_BG_TASKS.discard(task),
                                      _retrieve_task_exception(task)))
