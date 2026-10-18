"""Paket 15 (A6): was ein generativer Lauf neben den Chat-Zügen verbraucht — Simulator,
Judge, Szenarien — landet je Rolle unter einer eigenen Quelle auf der Kosten-Seite."""

from __future__ import annotations

import asyncio

from boerdi.services.eval import verbrauch as v


def test_bucht_je_rolle_unter_eigener_quelle_ohne_sitzung(monkeypatch) -> None:
    gebucht: list = []

    async def buche(session, session_id, acc, engine=None, quelle=None):
        gebucht.append((session, session_id, acc, engine, quelle))
        return 1

    monkeypatch.setattr(v, "record_turn_usage", buche)
    lauf = v.EvalVerbrauch()
    asyncio.run(v.buche("S", lauf, engine="pattern"))

    assert [(g[0], g[1], g[3], g[4]) for g in gebucht] == [
        ("S", None, "pattern", "eval-simulator"),
        ("S", None, "pattern", "eval-judge"),
        ("S", None, "pattern", "eval-szenario"),
    ]
    assert [g[2] for g in gebucht] == [lauf.simulator, lauf.judge, lauf.szenario]
