"""obs.tasks — Fire-and-forget-Task-Helfer.

Charakterisierungs-Netz für ``_retrieve_task_exception`` (in ALT unter
``chat_session_utils`` beheimatet, dort ohne eigenen Unit-Test — hier frisch
gepinnt): der Done-Callback muss die Task-Exception abrufen (damit asyncio nicht
"Task exception was never retrieved" loggt) und darf selbst NIE werfen — weder
bei einer echten Exception, noch bei Erfolg (exc=None), noch bei einem
pending/cancelled Task (``InvalidStateError``/``CancelledError``).
"""

from __future__ import annotations

import asyncio

import boerdi.obs.tasks as obs_tasks
from boerdi.obs.tasks import _retrieve_task_exception, _spawn_background


def test_retrieve_consumes_and_swallows_exception():
    async def _boom():
        raise RuntimeError("x")

    async def _run():
        t = asyncio.ensure_future(_boom())
        await asyncio.gather(t, return_exceptions=True)  # Task fertig, wirft
        _retrieve_task_exception(t)  # darf NICHT propagieren

    asyncio.run(_run())


def test_retrieve_handles_successful_task():
    async def _ok():
        return 42

    async def _run():
        t = asyncio.ensure_future(_ok())
        await t
        _retrieve_task_exception(t)  # exc None → kein Log, kein Wurf

    asyncio.run(_run())


def test_retrieve_swallows_invalid_state_on_pending_task():
    async def _run():
        t = asyncio.ensure_future(asyncio.sleep(10))
        _retrieve_task_exception(t)  # pending → InvalidStateError geschluckt
        t.cancel()
        await asyncio.gather(t, return_exceptions=True)

    asyncio.run(_run())


def test_retrieve_swallows_cancelled_task():
    async def _run():
        t = asyncio.ensure_future(asyncio.sleep(10))
        t.cancel()
        await asyncio.gather(t, return_exceptions=True)
        _retrieve_task_exception(t)  # cancelled → CancelledError geschluckt

    asyncio.run(_run())


# ── _spawn_background: strong-ref + auto-discard + exception-safe ──

def test_spawn_background_runs_holds_ref_then_discards():
    ran: list[int] = []

    async def _work():
        ran.append(1)

    async def _run():
        before = set(obs_tasks._BG_TASKS)
        _spawn_background(_work())
        new = set(obs_tasks._BG_TASKS) - before
        assert len(new) == 1  # strong ref held while pending (GC-Schutz)
        t = new.pop()
        await asyncio.gather(t, return_exceptions=True)
        await asyncio.sleep(0)  # done-callback (discard) auf nächstem Loop-Tick
        assert ran == [1]
        assert t not in obs_tasks._BG_TASKS  # nach Abschluss verworfen

    asyncio.run(_run())


def test_spawn_background_discards_on_exception():
    async def _boom():
        raise RuntimeError("x")

    async def _run():
        before = set(obs_tasks._BG_TASKS)
        _spawn_background(_boom())
        t = (set(obs_tasks._BG_TASKS) - before).pop()
        await asyncio.gather(t, return_exceptions=True)
        await asyncio.sleep(0)
        # Exception vom Callback abgerufen (kein "never retrieved") + verworfen.
        assert t not in obs_tasks._BG_TASKS

    asyncio.run(_run())
