"""Zeiten eines Zuges für den Debug-Block (Plan ``docs/plans/2026-09-30-muster-kette-zeit.md``).

Der Debug-Block zeigte bis 2026-09-30 nur Token je Phase; wo ein 16-s-Zug seine
Zeit ließ, war nur mit einem eigenen Mess-Server zu sehen. Jetzt stehen im
Merkposten des Zuges (``TurnContext.usage``, der als ``token_usage`` im
Debug-Block landet):

* ``zeiten_ms[<knoten>]`` — je Graph-Knoten, in der Reihenfolge der Kette
  (``messe_knoten``, in ``graph/build`` um jeden Knoten gelegt);
* ``zeiten_ms[<knoten>.<schritt>]`` — Teilschritte ohne eigenen LLM-Aufruf, etwa
  ``assess.safety`` und ``respond.rag`` (``schritt``);
* ``per_phase[<phase>].ms`` — je LLM-Phase (``obs/usage.add_usage``).

Gemessen wird die Wanduhr in Millisekunden — einschließlich Warteschlange, denn
so lange wartet der Zug.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from typing import Any

from boerdi.obs.usage import current_turn_usage

ZEITEN_KEY = "zeiten_ms"


def seit_ms(t0: float) -> int:
    """Millisekunden seit ``t0`` (einem ``time.perf_counter()``-Wert)."""
    return round((time.perf_counter() - t0) * 1000)


def _buche(acc: dict[str, Any] | None, name: str, ms: int) -> None:
    if acc is None:
        return
    zeiten = acc.setdefault(ZEITEN_KEY, {})
    zeiten[name] = zeiten.get(name, 0) + ms


@contextmanager
def schritt(name: str, acc: dict[str, Any] | None = None) -> Iterator[None]:
    """Einen Teilschritt messen; ohne ``acc`` bucht er in den gebundenen Zug.

    Kein gebundener Zug (Start-Vorwärmung, Werkzeug-Aufrufe ohne Zug) heißt:
    keine Buchung, kein Fehler — wie bei ``add_usage``. Ein wiederholter Schritt
    summiert.
    """
    ziel = acc if acc is not None else current_turn_usage()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _buche(ziel, name, seit_ms(t0))


def spur_zeilen(acc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Die Zeiten als Zeilen für ``debug.trace`` (``TraceEntry``-Felder).

    Das Debug-Panel zeigt Trace-Zeilen schon als „· [step] label – N ms“ — so
    werden die Zeiten sichtbar, ohne neue Oberfläche. Zuerst ``gesamt`` (die
    Summe der Knoten; sie laufen nacheinander), dann je Knoten in der Reihenfolge
    der Kette seine Teilschritte darunter, zuletzt je LLM-Phase mit Aufrufzahl.
    """
    acc = acc or {}
    zeiten: dict[str, int] = acc.get(ZEITEN_KEY) or {}
    per_phase: dict[str, dict[str, Any]] = acc.get("per_phase") or {}
    if not zeiten and not any("ms" in werte for werte in per_phase.values()):
        return []

    def zeile(step: str, label: str, ms: int) -> dict[str, Any]:
        return {"step": step, "label": label, "duration_ms": ms}

    knoten = [name for name in zeiten if "." not in name]
    zeilen = [zeile("zeit", "gesamt", sum(zeiten[k] for k in knoten))]
    for k in knoten:
        zeilen.append(zeile("zeit", k, zeiten[k]))
        zeilen += [zeile("zeit", s, ms) for s, ms in zeiten.items() if s.startswith(k + ".")]
    gezeigt = {z["label"] for z in zeilen}
    zeilen += [zeile("zeit", s, ms) for s, ms in zeiten.items() if s not in gezeigt]
    zeilen += [zeile("llm", f"{phase} · {werte.get('calls', 0)}×", werte["ms"])
               for phase, werte in per_phase.items() if "ms" in werte]
    return zeilen


def messe_knoten(
    name: str, action: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Einen Graph-Knoten umhüllen: seine Dauer landet in ``ctx.usage``.

    ``functools.wraps`` hält die Signatur des Knotens sichtbar (``__wrapped__``):
    LangGraph liest sie, und eine Hülle mit ``**kwargs`` bekäme sonst ``config``
    eingeschoben, das kein Knoten annimmt. Eine Ausnahme wird gemessen und
    unverändert weitergereicht.
    """

    @functools.wraps(action)
    async def huelle(ctx: Any, *args: Any, **kwargs: Any) -> Any:
        with schritt(name, getattr(ctx, "usage", None)):
            return await action(ctx, *args, **kwargs)

    return huelle
