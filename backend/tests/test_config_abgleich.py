"""Config-Abgleich zwischen den Kopien (Paket 19, Audit 2026-10-31: M-1, N-29).

Bis hier hing jede Kopie allein an NOTIFY:

* scheiterte der Refresh nach einer Benachrichtigung, blieb es bei einer Warnung —
  kein zweiter Versuch, kein periodischer Abgleich;
* die LISTEN-Verbindung wurde nur über ``is_closed()`` geprüft — eine still gekappte
  (NAT, Failover) blieb unerkannt, ``_resync`` lief nie;
* ``/ready`` sah den Listener nicht.

Folge: eine Kopie las dauerhaft alte Konfiguration, auch ``privacy-config``
(``messages: false`` wirkte nicht) — fail-open im Datenschutz, ohne Logzeile.

Ohne Datenbank: ``_fetch``/``_versionen`` sind Attrappen, die Verbindung des Listeners
ebenso (wie in ``test_notify_reconnect.py``).
"""

from __future__ import annotations

import asyncio
import time

from boerdi.db import notify
from boerdi.services import config_store as store_mod
from boerdi.services.config_store import ConfigStore


def _store() -> ConfigStore:
    return ConfigStore(engine=None, listen_dsn="postgresql://attrappe")


async def _bis(bedingung, frist_s: float = 3.0) -> None:
    # Nach der Uhr, nicht nach Schritten: unter Windows löst die Uhr der Schleife nur
    # ~15,6 ms auf, ``sleep(0.005)`` kehrt dort oft sofort zurück.
    ende = time.monotonic() + frist_s
    while time.monotonic() < ende:
        if bedingung():
            return
        await asyncio.sleep(0.005)


def test_ein_gescheiterter_refresh_wird_mit_pause_nachgeladen(monkeypatch):
    monkeypatch.setattr(store_mod, "_NACHLADEN_START_S", 0.01)
    store = _store()
    store._cache["01-base/privacy-config"] = {"messages": True}
    store._versions["01-base/privacy-config"] = 1
    versuche: list[str] = []

    async def fetch(area):
        versuche.append(area)
        if len(versuche) < 3:
            raise OSError("Verbindung weg")
        return {"messages": False}, 2

    monkeypatch.setattr(store, "_fetch", fetch)

    async def lauf():
        store._on_area_changed("01-base/privacy-config")
        await _bis(lambda: store._cache["01-base/privacy-config"] == {"messages": False})

    asyncio.run(lauf())
    assert store._cache["01-base/privacy-config"] == {"messages": False}
    assert len(versuche) == 3
    assert not store._schmutzig


def test_nach_den_versuchen_bleibt_der_bereich_fuer_den_abgleich_gemerkt(monkeypatch):
    monkeypatch.setattr(store_mod, "_NACHLADEN_START_S", 0.001)
    store = _store()

    async def fetch(area):
        raise OSError("Verbindung weg")

    monkeypatch.setattr(store, "_fetch", fetch)

    async def lauf():
        store._on_area_changed("01-base/a")
        await _bis(lambda: not store._fetching)

    asyncio.run(lauf())
    assert store._schmutzig == {"01-base/a"}


def test_der_versionsabgleich_laedt_nur_veraltete_bereiche(monkeypatch):
    store = _store()
    store._cache.update({"a": {"v": 1}, "b": {"v": 5}, "weg": {"v": 1}})
    store._versions.update({"a": 1, "b": 5, "weg": 1})
    geholt: list[str] = []

    async def versionen():
        return {"a": 2, "b": 5, "neu": 1}

    async def fetch(area):
        geholt.append(area)
        if area == "weg":
            return None
        return {"v": 9}, 9

    monkeypatch.setattr(store, "_versionen", versionen)
    monkeypatch.setattr(store, "_fetch", fetch)

    async def lauf():
        assert await store.abgleichen() is True
        await _bis(lambda: not store._fetching)

    asyncio.run(lauf())
    assert sorted(geholt) == ["a", "neu", "weg"]
    assert "weg" not in store._cache
    assert store._cache["b"] == {"v": 5}


def test_ein_gemerkter_bereich_wird_beim_abgleich_nachgeladen(monkeypatch):
    store = _store()
    store._cache["a"] = {"v": 1}
    store._versions["a"] = 3
    store._schmutzig.add("a")
    geholt: list[str] = []

    async def versionen():
        return {"a": 3}

    async def fetch(area):
        geholt.append(area)
        return {"v": 3}, 3

    monkeypatch.setattr(store, "_versionen", versionen)
    monkeypatch.setattr(store, "_fetch", fetch)

    async def lauf():
        await store.abgleichen()
        await _bis(lambda: not store._fetching)

    asyncio.run(lauf())
    assert geholt == ["a"]
    assert not store._schmutzig


def test_ein_gescheiterter_abgleich_wirft_nicht(monkeypatch):
    store = _store()

    async def versionen():
        raise OSError("Verbindung weg")

    monkeypatch.setattr(store, "_versionen", versionen)
    assert asyncio.run(store.abgleichen()) is False


def test_bereit_heisst_listener_verbunden_oder_abgleich_frisch(monkeypatch):
    store = _store()
    uhr = [1000.0]
    monkeypatch.setattr(store, "_jetzt", lambda: uhr[0])
    store._listener._connected.set()
    assert store.bereit()
    store._listener._connected.clear()
    store._letzter_abgleich = 1000.0 - store._takt_s
    assert store.bereit()  # der Abgleich trägt, der Listener verbindet sich gerade neu
    store._letzter_abgleich = 1000.0 - 4 * store._takt_s
    assert not store.bereit()


def test_die_wiederverbindung_haelt_ihren_abgleich_fest(monkeypatch):
    """N-29: ``create_task(self._resync())`` ohne starke Referenz — die Schleife hält
    nur schwache, die Aufgabe konnte eingesammelt werden, bevor sie lief."""
    store = _store()
    gesehen: list[bool] = []

    async def list_areas():
        gesehen.append(any(not t.done() for t in store._hintergrund))
        return []

    monkeypatch.setattr(store, "list_areas", list_areas)

    async def lauf():
        store._on_reconnect()
        assert len(store._hintergrund) == 1
        await _bis(lambda: not store._hintergrund)

    asyncio.run(lauf())
    assert gesehen == [True]


class _Verbindung:
    def __init__(self, *, ping_haengt: bool = False) -> None:
        self._ping_haengt = ping_haengt

    async def add_listener(self, _channel, _callback):
        return None

    def is_closed(self) -> bool:
        return False

    async def fetchval(self, _sql):
        if self._ping_haengt:
            await asyncio.sleep(30)
        return 1

    async def close(self, **_kw):
        return None

    def terminate(self) -> None:
        return None


def _schnell(monkeypatch, verbindungen) -> None:
    monkeypatch.setattr(notify, "_HEALTH_POLL_S", 0.001)
    monkeypatch.setattr(notify, "_RECONNECT_DELAY_S", 0.001)
    monkeypatch.setattr(notify, "_PING_TAKT_S", 0.01)
    monkeypatch.setattr(notify, "_PING_FRIST_S", 0.05)
    folge = iter(verbindungen)

    async def _connect(_dsn):
        return next(folge)

    monkeypatch.setattr(notify.asyncpg, "connect", _connect)


def test_eine_still_gekappte_verbindung_wird_am_ping_erkannt(monkeypatch):
    _schnell(monkeypatch, [_Verbindung(ping_haengt=True), _Verbindung()])
    gemeldet: list[str] = []

    async def lauf():
        hoerer = notify.ConfigChangeListener("postgresql://attrappe")
        await hoerer.start(lambda _a: None, on_reconnect=lambda: gemeldet.append("neu"))
        await _bis(lambda: bool(gemeldet))
        await hoerer.stop()

    asyncio.run(lauf())
    assert gemeldet == ["neu"]


def test_herunterfahren_beendet_abgleich_und_nachladen_in_der_frist(monkeypatch):
    _schnell(monkeypatch, [_Verbindung()])
    store = ConfigStore(engine=None, listen_dsn="postgresql://attrappe", abgleich_takt_s=0.01)

    async def versionen():
        return {}

    async def fetch(area):
        await asyncio.sleep(30)  # ein hängendes Nachladen

    monkeypatch.setattr(store, "_versionen", versionen)
    monkeypatch.setattr(store, "_fetch", fetch)

    async def lauf():
        await store.start()
        store._on_area_changed("a")
        await asyncio.sleep(0.05)
        uhr = asyncio.get_running_loop()
        beginn = uhr.time()
        await store.stop(frist_s=1.0)
        return uhr.time() - beginn

    dauer = asyncio.run(lauf())
    assert dauer < 1.0
    assert store._abgleich_aufgabe is None or store._abgleich_aufgabe.done()
    assert not store._fetching


def test_nach_dem_anhalten_startet_kein_nachladen_mehr(monkeypatch):
    """Review 19-4: eine Benachrichtigung während der Abbruchfrist startete neue Aufgaben —
    „Task was destroyed“, ``_fetch`` gegen die schon entsorgte Engine."""
    store = _store()

    async def fetch(area):
        return {"v": 1}, 1

    async def list_areas():
        return [{"area": "a"}]

    async def versionen():
        return {"a": 1}

    monkeypatch.setattr(store, "_fetch", fetch)
    monkeypatch.setattr(store, "list_areas", list_areas)
    monkeypatch.setattr(store, "_versionen", versionen)

    async def lauf():
        await store.stop(frist_s=0.5)
        store._on_area_changed("a")
        store._on_reconnect()
        return await store.abgleichen()

    assert asyncio.run(lauf()) is False
    assert not store._fetching
    assert not store._hintergrund
