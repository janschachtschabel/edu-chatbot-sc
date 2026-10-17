"""Nachlaufende Züge beim Herunterfahren (Paket 9, Review Paket 7 MINOR 29).

Legt der Client auf, rechnet ein Chat-Zug zu Ende und speichert die Antwort im
Verlauf (Paket 7, P2). Beim Herunterfahren — jedem Deploy — wartete niemand auf
ihn: der Prozess endete, und die Antwort fehlte. Ohne Datenbank.
"""

from __future__ import annotations

import asyncio

from boerdi.api import sse


async def test_ein_nachlaeufer_rechnet_beim_herunterfahren_zu_ende():
    fertig: list[str] = []

    async def _zug():
        await asyncio.sleep(0.05)
        fertig.append("gespeichert")

    sse._nachlaufen_lassen(asyncio.create_task(_zug()), "test")
    assert await sse.nachlaeufer_abwarten(frist_s=2) == 0
    assert fertig == ["gespeichert"]


async def test_nach_der_frist_wird_abgebrochen():
    async def _haengt():
        await asyncio.sleep(60)

    aufgabe = asyncio.create_task(_haengt())
    sse._nachlaufen_lassen(aufgabe, "test")
    assert await sse.nachlaeufer_abwarten(frist_s=0.05) == 1
    assert aufgabe.cancelled()


async def test_ohne_nachlaeufer_wartet_nichts():
    assert await sse.nachlaeufer_abwarten(frist_s=30) == 0


def test_die_frist_passt_in_die_gnadenfrist_des_containers():
    """``compose.prod.yml`` gibt dem Backend 40 s, danach beendet Docker hart."""
    import re
    from pathlib import Path

    compose = (Path(__file__).resolve().parents[2] / "deploy" / "compose.prod.yml").read_text(
        encoding="utf-8")
    gnade = int(re.search(r"stop_grace_period:\s*(\d+)s", compose).group(1))
    assert sse.NACHLAUF_FRIST_S + 10 <= gnade
