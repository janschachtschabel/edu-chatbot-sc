"""Der Konfig-Cache fällt nie auf einen älteren Stand zurück (Paket 4, D1).

Externes Audit F08: Jede NOTIFY startete einen eigenen Abruf, und ein Abruf
kannte nur ``data``. Ein langsamer alter Abruf überschrieb so einen schnelleren
neuen, und ein laufender Abruf überschrieb das Durchschreiben aus ``put``.

Ohne Datenbank: die Engine ist eine Attrappe, deren Lesezugriffe der Test
einzeln freigibt. Die echten Postgres-Tests stehen in ``test_config_store.py``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from boerdi.services.config_store import ConfigStore


class _Ergebnis:
    def __init__(self, zeile: Any = None, skalar: Any = None) -> None:
        self._zeile, self._skalar = zeile, skalar

    def first(self) -> Any:
        return self._zeile

    def scalar_one(self) -> Any:
        return self._skalar


class _Verbindung:
    def __init__(self, motor: _Motor) -> None:
        self._motor = motor

    async def __aenter__(self) -> _Verbindung:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, sql: Any, params: dict[str, Any]) -> _Ergebnis:
        return await self._motor.ausfuehren(str(sql).strip(), params)


class _Motor:
    """Lesen liefert ``staende`` der Reihe nach: je Eintrag ein Tor (``None`` =
    sofort) und die Zeile ``(data, version)`` oder ``None`` für „gelöscht“."""

    def __init__(self, staende: list[tuple[asyncio.Event | None, Any]],
                 version_beim_schreiben: int = 1) -> None:
        self.staende = staende
        self.version_beim_schreiben = version_beim_schreiben
        self.gelesen = 0

    def connect(self) -> _Verbindung:
        return _Verbindung(self)

    def begin(self) -> _Verbindung:
        return _Verbindung(self)

    async def ausfuehren(self, sql: str, params: dict[str, Any]) -> _Ergebnis:
        if sql.startswith("SELECT"):
            self.gelesen += 1
            tor, zeile = self.staende.pop(0)
            if tor is not None:
                await tor.wait()
            return _Ergebnis(zeile=zeile)
        if sql.startswith("INSERT INTO config_areas"):
            return _Ergebnis(skalar=self.version_beim_schreiben)
        if sql.startswith("DELETE"):
            return _Ergebnis(zeile=(params["area"],))
        return _Ergebnis()


def _store(motor: _Motor) -> ConfigStore:
    return ConfigStore(engine=motor, listen_dsn="postgresql://attrappe")  # type: ignore[arg-type]


async def _bis_gelesen(motor: _Motor, rest: int) -> None:
    """Warten, bis der Abruf seinen Lesezugriff begonnen hat."""
    for _ in range(100):
        if len(motor.staende) <= rest:
            return
        await asyncio.sleep(0)
    raise AssertionError("der Abruf hat nie gelesen")


async def _alle_abrufe_fertig() -> None:
    andere = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*andere)


def test_ein_langsamer_alter_abruf_ueberschreibt_den_neuen_nicht():
    tor = asyncio.Event()
    motor = _Motor([(tor, ({"stand": 1}, 1)), (None, ({"stand": 2}, 2))])
    store = _store(motor)

    async def lauf() -> None:
        store._on_area_changed("a")  # NOTIFY zu v1 — der Abruf hängt
        await _bis_gelesen(motor, rest=1)
        store._on_area_changed("a")  # NOTIFY zu v2
        await asyncio.sleep(0)
        tor.set()
        await _alle_abrufe_fertig()

    asyncio.run(lauf())
    assert store.get_cached("a") == {"stand": 2}


def test_aenderungen_waehrend_eines_abrufs_loesen_genau_einen_weiteren_aus():
    # Je Bereich ein Abruf zur Zeit; was währenddessen gemeldet wird, holt
    # EIN weiterer Abruf danach — nicht einer je Meldung.
    tor = asyncio.Event()
    motor = _Motor([(tor, ({"stand": 1}, 1)), (None, ({"stand": 3}, 3))])
    store = _store(motor)

    async def lauf() -> None:
        store._on_area_changed("a")
        await _bis_gelesen(motor, rest=1)
        store._on_area_changed("a")
        store._on_area_changed("a")
        tor.set()
        await _alle_abrufe_fertig()

    asyncio.run(lauf())
    assert motor.gelesen == 2
    assert store.get_cached("a") == {"stand": 3}


def test_ein_laufender_abruf_ueberschreibt_das_durchschreiben_nicht():
    tor = asyncio.Event()
    motor = _Motor([(tor, ({"stand": 2}, 2))], version_beim_schreiben=3)
    store = _store(motor)

    async def lauf() -> None:
        store._on_area_changed("a")  # Abruf liest v2 und hängt
        await _bis_gelesen(motor, rest=0)
        assert await store.put("a", {"stand": 3}) == 3
        tor.set()
        await _alle_abrufe_fertig()

    asyncio.run(lauf())
    assert store.get_cached("a") == {"stand": 3}


def test_loeschen_vergisst_die_version_des_caches():
    # Nach dem Löschen gilt der nächste Stand, auch mit kleinerer Nummer. Neu
    # angelegte Zeilen zählen zwar weiter (FIRST_VERSION), aber der Cache soll
    # einen gelöschten Bereich nicht an einer alten Nummer festhalten.
    motor = _Motor([(None, ({"stand": "neu"}, 1))], version_beim_schreiben=5)
    store = _store(motor)

    async def lauf() -> None:
        await store.put("a", {"stand": "alt"})
        assert await store.delete("a")
        store._on_area_changed("a")
        await _alle_abrufe_fertig()

    asyncio.run(lauf())
    assert store.get_cached("a") == {"stand": "neu"}


def test_ein_geleerter_cache_vergisst_auch_die_version():
    # Sonst verwürfe der nächste Abruf den Stand als „älter“, und synchrone
    # Leser hielten den Bereich für nicht vorhanden.
    motor = _Motor([(None, ({"stand": "neu"}, 1))], version_beim_schreiben=5)
    store = _store(motor)

    async def lauf() -> None:
        await store.put("a", {"stand": "alt"})
        store.clear_cache("a")
        assert await store.get("a") == {"stand": "neu"}

    asyncio.run(lauf())
    assert store.get_cached("a") == {"stand": "neu"}
