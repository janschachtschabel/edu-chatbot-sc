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


def test_ein_absturz_im_hintergrund_steht_als_warnung_im_log(caplog):
    """Paket 19 (N-13): bis dahin nur DEBUG — ein abgestürzter Lauf-Job fiel niemandem auf.
    Die Zeile nennt Art und Aufgabe, nicht den Text der Ausnahme."""
    import logging

    async def _boom():
        raise RuntimeError("Thema KANARIE7Q")

    async def _run():
        before = set(obs_tasks._BG_TASKS)
        _spawn_background(_boom())
        t = (set(obs_tasks._BG_TASKS) - before).pop()
        await asyncio.gather(t, return_exceptions=True)
        await asyncio.sleep(0)

    with caplog.at_level(logging.DEBUG, logger="boerdi.obs.tasks"):
        asyncio.run(_run())
    warnungen = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnungen) == 1
    zeile = warnungen[0].getMessage()
    assert "RuntimeError" in zeile and "_boom" in zeile and "KANARIE7Q" not in zeile


def test_abgebrochene_aufgaben_bleiben_auf_debug(caplog):
    """``cancel_and_drain`` und die Vorab-Aufgaben: ihr Fehler ist erwartbar — DEBUG bleibt."""
    import logging

    async def _boom():
        raise RuntimeError("x")

    async def _run():
        t = asyncio.ensure_future(_boom())
        await asyncio.gather(t, return_exceptions=True)
        _retrieve_task_exception(t)
        await obs_tasks.cancel_and_drain([asyncio.ensure_future(_boom())])

    with caplog.at_level(logging.DEBUG, logger="boerdi.obs.tasks"):
        asyncio.run(_run())
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_eine_haengende_aufgabe_behaelt_eine_starke_referenz():
    """Review 2026-10-30: nach der Frist hielt nur noch die Schleife die Aufgabe — schwach."""
    from boerdi.obs import tasks as tasks_mod

    async def _stur():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(0.2)  # ignoriert den Abbruch eine Weile

    async def _ablauf():
        t = asyncio.create_task(_stur())
        await asyncio.sleep(0)
        await tasks_mod.cancel_and_drain([t], frist_s=0.01)
        assert t in tasks_mod._BG_TASKS
        await asyncio.wait([t], timeout=2)
        await asyncio.sleep(0)
        assert t not in tasks_mod._BG_TASKS

    asyncio.run(_ablauf())


def test_der_listener_haelt_sich_an_die_restfrist():
    """Review 2026-10-30: Herunterfahren mit EINER Abbruchfrist für Takte und Listener."""
    from boerdi.db.notify import ConfigChangeListener

    async def _stur():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(3)

    async def _ablauf() -> float:
        lauscher = ConfigChangeListener("postgresql://nicht-benutzt")
        lauscher._task = asyncio.create_task(_stur())
        await asyncio.sleep(0)
        uhr = asyncio.get_running_loop()
        t0 = uhr.time()
        await lauscher.stop(frist_s=0.1)
        return uhr.time() - t0

    assert asyncio.run(_ablauf()) < 1.0
