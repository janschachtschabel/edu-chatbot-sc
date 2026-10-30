"""Paket 18E (C1): abgebrochene Aufgaben abwarten — ohne den eigenen Abbruch zu verschlucken.

Bis 18E stand an vier Stellen ``task.cancel(); try: await task; except (CancelledError,
Exception): pass``. Das fing auch die Abbruch-Anforderung an den AUFRUFER: legte der Client auf
oder fuhr der Server herunter, rechnete der Zug weiter. Und es gab keine Frist — ignorierte eine
Aufgabe den Abbruch, hing der Aufrufer mit ihr.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from boerdi.obs import tasks as obs_tasks
from boerdi.obs.tasks import cancel_and_drain, cancel_run_task, register_run_task


async def _langsam_beim_abbruch() -> None:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        await asyncio.sleep(0.05)  # räumt noch auf
        raise


async def _stur(dauer: float = 0.3) -> None:
    """Ignoriert jeden Abbruch, bis ``dauer`` um ist (hinge sonst in Sync-Code fest)."""
    ende = asyncio.get_running_loop().time() + dauer
    while asyncio.get_running_loop().time() < ende:
        try:
            await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            continue


def test_der_eigene_abbruch_kommt_beim_aufrufer_an():
    async def szenario() -> list[str]:
        spaeter: list[str] = []
        innen = asyncio.create_task(_langsam_beim_abbruch())
        await asyncio.sleep(0)

        async def aufrufer() -> None:
            await cancel_and_drain([innen])
            spaeter.append("lief weiter")

        aussen = asyncio.create_task(aufrufer())
        await asyncio.sleep(0.01)
        aussen.cancel()
        with pytest.raises(asyncio.CancelledError):
            await aussen
        await asyncio.gather(innen, return_exceptions=True)
        return spaeter

    assert asyncio.run(szenario()) == []


def test_eine_haengende_aufgabe_haelt_hoechstens_die_frist_auf(caplog):
    async def szenario() -> float:
        innen = asyncio.create_task(_stur())
        await asyncio.sleep(0)
        start = asyncio.get_running_loop().time()
        zahl = await cancel_and_drain([innen, None], frist_s=0.05)
        dauer = asyncio.get_running_loop().time() - start
        assert zahl == 1
        await asyncio.gather(innen, return_exceptions=True)
        return dauer

    with caplog.at_level(logging.WARNING, logger=obs_tasks.__name__):
        dauer = asyncio.run(szenario())
    assert dauer < 0.2  # _stur hält 0,3 s — ohne Frist läge die Dauer darüber
    assert any("nicht beendet" in r.getMessage() for r in caplog.records)


def test_ein_fehler_der_aufgabe_kommt_nicht_beim_aufrufer_an(caplog):
    async def kaputt_beim_abbruch() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise ValueError("beim Aufräumen") from None

    async def szenario() -> int:
        innen = asyncio.create_task(kaputt_beim_abbruch())
        await asyncio.sleep(0)
        return await cancel_and_drain([innen])

    with caplog.at_level(logging.DEBUG, logger=obs_tasks.__name__):
        assert asyncio.run(szenario()) == 1
    assert any("ValueError" in r.getMessage() for r in caplog.records)


def test_ohne_aufgaben_nichts_zu_tun():
    assert asyncio.run(cancel_and_drain([None])) == 0


def test_cancel_run_task_reicht_den_eigenen_abbruch_weiter():
    async def szenario() -> list[str]:
        spaeter: list[str] = []
        lauf = asyncio.create_task(_langsam_beim_abbruch())
        register_run_task("lt-1", lauf)
        await asyncio.sleep(0)

        async def stopp() -> None:
            await cancel_run_task("lt-1", label="loadtest")
            spaeter.append("lief weiter")

        aussen = asyncio.create_task(stopp())
        await asyncio.sleep(0.01)
        aussen.cancel()
        with pytest.raises(asyncio.CancelledError):
            await aussen
        await asyncio.gather(lauf, return_exceptions=True)
        return spaeter

    assert asyncio.run(szenario()) == []


def test_cancel_run_task_nennt_den_lauf_wenn_er_haengt(monkeypatch, caplog):
    monkeypatch.setattr(obs_tasks, "_CANCEL_WAIT_S", 0.05)

    async def szenario() -> bool:
        lauf = asyncio.create_task(_stur())
        register_run_task("lt-2", lauf)
        await asyncio.sleep(0)
        ergebnis = await cancel_run_task("lt-2", label="loadtest")
        await asyncio.gather(lauf, return_exceptions=True)
        return ergebnis

    with caplog.at_level(logging.WARNING, logger=obs_tasks.__name__):
        assert asyncio.run(szenario()) is True
    assert any("loadtest lt-2" in r.getMessage() for r in caplog.records)


def test_eine_spaete_ausnahme_wird_trotzdem_abgeholt():
    """Review 18E-1: eine Aufgabe, die erst nach der Frist mit einem Fehler endet, darf kein
    „Task exception was never retrieved“ auslösen."""
    import gc

    gesehen: list[dict] = []

    async def spaet_kaputt() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(0.05)
            raise ValueError("zu spät") from None

    async def szenario() -> None:
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: gesehen.append(ctx))
        innen = asyncio.create_task(spaet_kaputt())
        await asyncio.sleep(0)
        await cancel_and_drain([innen], frist_s=0.01)
        await asyncio.sleep(0.1)
        del innen
        gc.collect()

    asyncio.run(szenario())
    assert gesehen == []


def test_doppelt_uebergeben_zaehlt_einmal():
    async def szenario() -> int:
        innen = asyncio.create_task(asyncio.sleep(10))
        return await cancel_and_drain([innen, innen])

    assert asyncio.run(szenario()) == 1


def test_auf_debug_nur_der_typ_der_ausnahme(caplog):
    """Paket 18C: auch auf DEBUG keine Inhalte — ein Ausnahmetext kann die Eingabe tragen."""
    async def kaputt() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise ValueError("geheime Eingabe") from None

    async def szenario() -> None:
        innen = asyncio.create_task(kaputt())
        await asyncio.sleep(0)
        await cancel_and_drain([innen])

    with caplog.at_level(logging.DEBUG, logger=obs_tasks.__name__):
        asyncio.run(szenario())
    assert any("ValueError" in r.getMessage() for r in caplog.records)
    assert not any("geheime Eingabe" in r.getMessage() for r in caplog.records)
