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


def _spawn_background(coro: Any) -> asyncio.Task:
    """create_task + starke Referenz + Exception-Retrieval (B1/Robustheit).

    Gibt den Task zurück, damit ein Aufrufer ihn gezielt abbrechen kann —
    die Eval-Läufe registrieren ihn je run_id (Abbruch-Befund 2026-08-22)."""
    t = asyncio.create_task(coro)
    _BG_TASKS.add(t)
    t.add_done_callback(lambda task: (_BG_TASKS.discard(task),
                                      _retrieve_task_exception(task)))
    return t


# ── Registry benannter Lauf-Tasks (Eval- und Lasttest-Läufe) ─────────
# Nutzer-Befund 2026-08-22: „Alle Läufe löschen" entfernte nur die ZEILE eines
# laufenden Laufs — der Task feuerte weiter echte Chat- (und beim Eval:
# Judge-) Aufrufe, seine Zwischenstände liefen ins Leere, und ohne
# running-Zeile ließ der Ein-Lauf-Wächter einen zweiten Lauf zu. Über diese
# Registry beenden Stopp- und Löschweg den Task wirklich.
#
# Hier statt in einer der beiden Lauf-Familien, seit der Lasttest als zweiter
# Aufrufer dazukam — dieselbe Bewegung wie bei ``cancel_and_drain`` darüber.
# Die Kennungen kollidieren nicht (``eval-…`` gegen ``lt-…``), eine Registry
# genügt also; das ``label`` beschriftet nur das Protokoll.
#
# Sie ist der SCHNELLE Weg, nicht der verlässliche: ein Dict im Prozess endet
# am Prozessrand, und Prod fährt bis zu ``BACKEND_REPLICAS`` davon. Verlässlich
# ist der Status in der Datenbank, den beide Lauf-Familien an ihren
# Fortschritts-Prüfpunkten mitlesen (Eval: ``RunCancelled``; Lasttest: der
# abgewiesene Zwischenstand-Schreiber). Hier: sofortiger Stopp, wenn die
# Anfrage die richtige Replika trifft; dort: höchstens eine Stufe später.
RUN_TASKS: dict[str, asyncio.Task] = {}

# Ein Task, der auf cancel() nicht reagiert (er hinge dann in Sync-Code fest),
# darf den HTTP-Aufruf nicht ewig blockieren.
_CANCEL_WAIT_S = 10.0


def register_run_task(run_id: str, task: asyncio.Task) -> None:
    """Merkt den Hintergrund-Task eines Laufs; räumt sich bei Task-Ende selbst."""
    RUN_TASKS[run_id] = task

    def _cleanup(_done: asyncio.Task) -> None:
        if RUN_TASKS.get(run_id) is task:
            del RUN_TASKS[run_id]

    task.add_done_callback(_cleanup)


async def cancel_run_task(run_id: str, *, label: str = "run") -> bool:
    """Beendet den in DIESEM Prozess registrierten Task eines Laufs.

    True = es lebte einer und wurde abgebrochen; False = keiner (mehr) da —
    was das bedeutet, entscheidet der Aufrufer. Bewusst nicht
    ``cancel_and_drain`` darüber: das wartet ohne Frist, hier braucht das
    Warten eine Obergrenze.
    """
    task = RUN_TASKS.get(run_id)
    if task is None or task.done():
        return False
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=_CANCEL_WAIT_S)
    except asyncio.CancelledError:
        pass  # das erwartete Ende des abgebrochenen Tasks
    except TimeoutError:
        logger.warning("[%s %s] Task ignorierte den Abbruch binnen %.0f s",
                       label, run_id, _CANCEL_WAIT_S)
    except Exception as e:
        # Der Job starb im selben Moment aus eigenem Grund; sein Fehlerpfad
        # hat den Zustand bereits persistiert.
        logger.debug("[%s %s] Task endete beim Abbruch mit %s", label, run_id, e)
    return True
