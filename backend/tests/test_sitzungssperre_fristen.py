"""Sitzungssperre: Fristen je Abfrage und Abbruch nach dem Nehmen (Paket 19, M-10/N-28).

Audit 2026-10-31:

* **M-10** — ``_nehmen``, ``_verlaengern`` und ``_FREIGEBEN`` liefen ohne Frist. Bei einer
  Netzpartition ohne RST hing der Zug unbegrenzt; ``warten_s`` wird nur zwischen zwei
  Versuchen geprüft.
* **N-28** — die Sperre wurde VOR dem ``try`` genommen: ein Abbruch nach dem Commit von
  ``_nehmen`` erreichte kein ``finally``, die Sitzung blieb bis zur TTL (60 s) „beschäftigt“.

Ohne Datenbank: die Engine ist eine Attrappe, die jede Anweisung mitschreibt.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from boerdi.services import sitzungssperre as sperre_mod
from boerdi.services.sitzungssperre import sitzungssperre


class _Ergebnis:
    def __init__(self, zeile, rowcount: int = 1) -> None:
        self._zeile = zeile
        self.rowcount = rowcount

    def first(self):
        return self._zeile


class _Verbindung:
    def __init__(self, engine: _Engine) -> None:
        self._engine = engine

    async def execute(self, anweisung, werte):
        art = str(anweisung).split()[0]
        self._engine.log.append((art, werte.get("owner")))
        if art in self._engine.haengt:
            await asyncio.sleep(30)
        if art == "INSERT" and not self._engine.nehmen_gelingt:
            return _Ergebnis(None)
        return _Ergebnis(("owner",), rowcount=self._engine.rowcount)


class _Begin:
    def __init__(self, engine: _Engine) -> None:
        self._engine = engine

    async def __aenter__(self) -> _Verbindung:
        return _Verbindung(self._engine)

    async def __aexit__(self, *exc) -> None:
        return None


class _Engine:
    def __init__(self, *haengt: str, rowcount: int = 1, nehmen_gelingt: bool = True) -> None:
        self.log: list[tuple[str, str | None]] = []
        self.haengt = set(haengt)
        self.rowcount = rowcount
        self.nehmen_gelingt = nehmen_gelingt

    def begin(self) -> _Begin:
        return _Begin(self)


def test_ein_abbruch_nach_dem_nehmen_gibt_die_sperre_frei(monkeypatch):
    engine = _Engine()
    echt = sperre_mod._nehmen

    async def _nehmen_dann_abbruch(*args, **kwargs):
        await echt(*args, **kwargs)  # der Eintrag steht schon
        raise asyncio.CancelledError

    monkeypatch.setattr(sperre_mod, "_nehmen", _nehmen_dann_abbruch)

    async def _zug():
        async with sitzungssperre(engine, "s-1"):
            pytest.fail("der Block darf nicht laufen")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_zug())
    arten = [art for art, _ in engine.log]
    assert arten == ["INSERT", "DELETE"]
    assert engine.log[0][1] == engine.log[1][1]  # freigegeben mit demselben owner


def test_ein_haengendes_nehmen_endet_nach_der_frist():
    engine = _Engine("INSERT", "DELETE")

    async def _zug():
        async with sitzungssperre(engine, "s-2", db_frist_s=0.1):
            pytest.fail("der Block darf nicht laufen")

    beginn = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(_zug())
    assert time.monotonic() - beginn < 1.0


def test_eine_haengende_freigabe_haelt_den_zug_nicht_auf():
    engine = _Engine("DELETE")

    async def _zug():
        async with sitzungssperre(engine, "s-3", db_frist_s=0.1, takt_s=60):
            pass

    beginn = time.monotonic()
    asyncio.run(_zug())  # Freigabe-Fehler wird geloggt, nicht geworfen
    assert time.monotonic() - beginn < 1.0


def test_eine_haengende_verlaengerung_kostet_nur_einen_takt():
    engine = _Engine("UPDATE")

    async def _lauf():
        aufgabe = asyncio.create_task(sperre_mod._verlaengern(
            engine, "s-4", "o", 60, 0.01, frist_s=0.05))
        await asyncio.sleep(0.3)
        engine.haengt.clear()
        engine.rowcount = 0  # verloren → die Verlängerung endet
        await asyncio.wait_for(aufgabe, 1.0)

    asyncio.run(_lauf())
    assert sum(1 for art, _ in engine.log if art == "UPDATE") >= 3


def test_wer_nie_genommen_hat_gibt_nicht_frei():
    """Review 19-4: „beschäftigt“ kostete eine überflüssige DELETE-Abfrage."""
    engine = _Engine(nehmen_gelingt=False)

    async def _zug():
        async with sitzungssperre(engine, "s-5", warten_s=0.0):
            pytest.fail("der Block darf nicht laufen")

    with pytest.raises(sperre_mod.SitzungBeschaeftigt):
        asyncio.run(_zug())
    assert [art for art, _ in engine.log] == ["INSERT"]
