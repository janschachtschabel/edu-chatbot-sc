"""Hilfe für Leisten-Tests (Plan 2026-11-16, Review TG-4–6, Befund 10): ein Testfall der Simulation
mit der Leiste an jedem Halt — „Schritt n von m“, wie sie der Lauf trägt (``lauf["halte"]``).

Die Simulation nutzt den echten Treiber; eine Hülle um ``treiber._rechne`` merkt sich, wo der Lauf
hält und mit welcher Zahl. So prüfen die Tests den Lauf, nicht eine zweite Rechnung daneben.
"""

from __future__ import annotations

import asyncio
from typing import Any

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import fortschritt, simulation, treiber


def leiste(monkeypatch: Any, ablauf: AblaufArea, name: str) -> list[tuple[str, int, int]]:
    """``(schritt, n, m)`` an jedem Halt des Testfalls ``name`` (der Testfall muss bestehen)."""
    [test] = [t for t in ablauf.tests if t.name == name]
    gesehen: list[tuple[str, int]] = []
    echt = treiber._rechne

    async def mit_halt(a, lauf, start, umgebung):
        aus = await echt(a, lauf, start, umgebung)
        if aus.lauf.get("status") in treiber._HALT_STATUS:
            gesehen.append((str(aus.lauf["schritt"]), int(aus.lauf.get("halte") or 0)))
        return aus

    monkeypatch.setattr(treiber, "_rechne", mit_halt)
    ergebnis = asyncio.run(simulation.testen(ablauf, test))
    assert ergebnis.ok, ergebnis.abweichungen
    aus: list[tuple[str, int, int]] = []
    for schritt, halte in gesehen:
        pos = fortschritt.position(ablauf, schritt, halte)
        assert pos is not None
        aus.append((schritt, *pos))
    return aus


def ohne_sprung(halte: list[tuple[str, int, int]]) -> None:
    """Der Grundsatz der Leiste: ``n`` beginnt bei 1 und steigt je Halt um genau 1, ``n ≤ m``."""
    assert [n for _s, n, _m in halte] == list(range(1, len(halte) + 1)), halte
    assert all(n <= m for _s, n, m in halte), halte
