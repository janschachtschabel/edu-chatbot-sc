"""Zeiten eines Zuges im Debug-Block (Plan 2026-09-30, T8).

``messe_knoten`` umhüllt die Graph-Knoten, ``schritt`` misst Teilschritte tief
im Zug (Sicherheit, RAG). Beide buchen in ``usage["zeiten_ms"]``.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from types import SimpleNamespace

import pytest

from boerdi.obs import usage, zeiten


def test_ein_knoten_bucht_seine_dauer_in_den_zug():
    ctx = SimpleNamespace(usage={})

    async def knoten(c):
        return c

    out = asyncio.run(zeiten.messe_knoten("assess", knoten)(ctx))

    assert out is ctx
    assert isinstance(ctx.usage["zeiten_ms"]["assess"], int)
    assert ctx.usage["zeiten_ms"]["assess"] >= 0


def test_eine_ausnahme_wird_gemessen_und_weitergereicht():
    ctx = SimpleNamespace(usage={})

    async def knoten(c):
        raise RuntimeError("kaputt")

    with pytest.raises(RuntimeError, match="kaputt"):
        asyncio.run(zeiten.messe_knoten("respond", knoten)(ctx))
    assert "respond" in ctx.usage["zeiten_ms"]


def test_die_huelle_behaelt_die_signatur_fuer_langgraph():
    """LangGraph liest die Signatur eines Knotens: mit ``**kwargs`` schöbe es
    ``config`` ein, das kein Knoten annimmt. Die Hülle zeigt die Signatur des
    umhüllten Knotens, samt der per ``functools.partial`` gebundenen Nähte."""
    async def knoten(ctx, *, session=None):
        return ctx

    huelle = zeiten.messe_knoten("setup", functools.partial(knoten, session=object()))

    assert inspect.iscoroutinefunction(huelle)
    assert list(inspect.signature(huelle).parameters) == ["ctx", "session"]


def test_ein_schritt_bucht_in_den_gebundenen_zug():
    acc: dict = {}
    usage.bind_turn_usage(acc)
    try:
        with zeiten.schritt("respond.rag"):
            pass
    finally:
        usage.bind_turn_usage(None)

    assert acc["zeiten_ms"]["respond.rag"] >= 0


def test_ein_schritt_ohne_zug_bucht_nichts():
    usage.bind_turn_usage(None)
    with zeiten.schritt("respond.rag"):
        pass  # kein Zug gebunden (Start-Vorwärmung) — kein Fehler, keine Buchung


def test_ein_wiederholter_schritt_summiert():
    acc: dict = {}
    with zeiten.schritt("respond.rag", acc):
        pass
    acc["zeiten_ms"]["respond.rag"] = 40
    with zeiten.schritt("respond.rag", acc):
        pass

    assert acc["zeiten_ms"]["respond.rag"] >= 40


# ── T9: die Zeiten als Trace-Zeilen ─────────────────────────────────────
# Das Debug-Panel zeigt ``debug.trace`` schon heute als „· [step] label – N ms“
# (ALT-Port, bis 2026-09-30 im Muster-Weg leer). Die Zeiten kommen dorthin —
# ohne neue Oberfläche und ohne Widget-Neubau.

def test_die_zeiten_werden_zu_trace_zeilen_in_kettenreihenfolge():
    # Teilschritte buchen VOR ihrem Knoten (der Knoten endet später) — die
    # Zeilen stehen trotzdem unter ihrem Knoten.
    acc = {
        "zeiten_ms": {"setup": 2, "assess.safety": 300, "assess": 3500,
                      "respond.rag": 450, "respond": 4200},
        "per_phase": {"classify": {"calls": 1, "ms": 3400},
                      "response": {"calls": 2, "ms": 3700},
                      "vocab": {"calls": 1}},
    }

    zeilen = zeiten.spur_zeilen(acc)

    assert [(z["step"], z["label"], z["duration_ms"]) for z in zeilen] == [
        ("zeit", "gesamt", 7702),
        ("zeit", "setup", 2),
        ("zeit", "assess", 3500),
        ("zeit", "assess.safety", 300),
        ("zeit", "respond", 4200),
        ("zeit", "respond.rag", 450),
        ("llm", "classify · 1×", 3400),
        ("llm", "response · 2×", 3700),
    ]


def test_ein_schritt_ohne_knoten_geht_nicht_verloren():
    zeilen = zeiten.spur_zeilen({"zeiten_ms": {"respond.rag": 450}})

    assert [(z["label"], z["duration_ms"]) for z in zeilen] == [
        ("gesamt", 0), ("respond.rag", 450)]


def test_ohne_zeiten_keine_zeilen():
    assert zeiten.spur_zeilen({"calls": 3}) == []
    assert zeiten.spur_zeilen(None) == []
