"""Audit 2026-09-29 (C-M NOTIFY): nach einer Wiederverbindung neu laden.

Zwischen Abriss und neuem ``LISTEN`` gehen Benachrichtigungen verloren. Ohne
Abgleich nutzte eine Replik danach veraltete Konfiguration, auch
Datenschutz-Schalter, bis zum nächsten Neustart.

Ohne Datenbank: die Verbindung ist eine Attrappe, die nach einer
Gesundheitsprüfung als geschlossen gilt. Die echten LISTEN-Tests stehen in
``test_pg_locks_notify.py``.
"""

from __future__ import annotations

import asyncio

from boerdi.db import notify
from boerdi.services.config_store import ConfigStore


class _Verbindung:
    """``lebensdauer``: Gesundheitsprüfungen bis zum Abriss; ``None`` = hält."""

    def __init__(self, lebensdauer: int | None):
        self._rest = lebensdauer

    async def add_listener(self, _channel, _callback):
        return None

    def is_closed(self) -> bool:
        if self._rest is None:
            return False
        self._rest -= 1
        return self._rest < 0

    async def close(self):
        return None


def _schnell(monkeypatch, verbindungen):
    monkeypatch.setattr(notify, "_HEALTH_POLL_S", 0.001)
    monkeypatch.setattr(notify, "_RECONNECT_DELAY_S", 0.001)
    folge = iter(verbindungen)

    async def _connect(_dsn):
        return next(folge)

    monkeypatch.setattr(notify.asyncpg, "connect", _connect)


def test_das_erste_verbinden_meldet_keine_wiederverbindung(monkeypatch):
    _schnell(monkeypatch, [_Verbindung(None)])
    gemeldet: list[str] = []

    async def lauf():
        hoerer = notify.ConfigChangeListener("postgresql://attrappe")
        await hoerer.start(lambda _a: None, on_reconnect=lambda: gemeldet.append("neu"))
        await hoerer.wait_connected(timeout=2.0)
        await asyncio.sleep(0.02)
        await hoerer.stop()

    asyncio.run(lauf())
    assert gemeldet == []


def test_nach_einem_abriss_wird_die_wiederverbindung_gemeldet(monkeypatch):
    _schnell(monkeypatch, [_Verbindung(1), _Verbindung(None)])
    gemeldet: list[str] = []

    async def lauf():
        hoerer = notify.ConfigChangeListener("postgresql://attrappe")
        await hoerer.start(lambda _a: None, on_reconnect=lambda: gemeldet.append("neu"))
        for _ in range(400):
            if gemeldet:
                break
            await asyncio.sleep(0.005)
        await hoerer.stop()

    asyncio.run(lauf())
    assert gemeldet == ["neu"]


def test_der_store_laedt_nach_der_wiederverbindung_alle_bereiche(monkeypatch):
    # Bereiche aus dem Cache UND aus der Datenbank: einer kann während des
    # Abrisses neu angelegt worden sein und steht dann noch nicht im Cache.
    store = ConfigStore(engine=None, listen_dsn="postgresql://attrappe")
    store._cache["01-base/privacy-config"] = {"alt": True}
    benachrichtigt: list[str] = []
    store.subscribe(benachrichtigt.append)

    async def list_areas():
        return [{"area": "01-base/privacy-config"}, {"area": "01-base/neu"}]

    async def fetch(area):
        # ``(data, version)`` seit Paket 4 (D1)
        return {"stand": "neu", "area": area}, 1

    monkeypatch.setattr(store, "list_areas", list_areas)
    monkeypatch.setattr(store, "_fetch", fetch)

    async def lauf():
        store._on_reconnect()
        for _ in range(200):
            if len(store._cache) == 2 and all(
                    v.get("stand") == "neu" for v in store._cache.values()):
                break
            await asyncio.sleep(0.005)

    asyncio.run(lauf())
    assert sorted(benachrichtigt) == ["01-base/neu", "01-base/privacy-config"]
    assert store._cache["01-base/privacy-config"] == {
        "stand": "neu", "area": "01-base/privacy-config"}
