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
from typing import Any

logger = logging.getLogger(__name__)


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
