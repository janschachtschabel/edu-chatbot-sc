"""Die Werkzeugpflicht eines Musters (A1-Reflexion im Tool-Loop).

Ein Muster mit ``force_tool_use`` verlangt Werkzeuge aus ``tools`` — eines davon
(Vorgabe) oder alle (``requires_all_tools``). Antwortet das Modell, ohne die
Pflicht erfüllt zu haben, verwirft ``services/tool_loop`` die Antwort einmal und
fragt neu. Seit dem Token-Streaming (Plan ``2026-10-01-token-streaming``, T9/T10)
fragt der Loop das auch VOR einer Runde: deren Text darf nur gestreamt werden,
wenn die Reflexion ihn nicht mehr verwerfen kann.

Rein (CLAUDE.md, Regel 4): nur stdlib. Herausgelöst ohne Verhaltensänderung.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def gerufene_werkzeuge(tools_called: Iterable[str | None]) -> set[str]:
    """Die blanken Namen — Vorabruf-Einträge tragen einen Zusatz hinter dem Namen."""
    return {(t or "").split(" ", 1)[0].strip() for t in tools_called}


def fehlende_pflichtwerkzeuge(pattern_output: dict[str, Any],
                              tools_called: Iterable[str | None]) -> list[str]:
    """Die Pflichtwerkzeuge, die in diesem Zug noch fehlen — leer, wenn das Muster
    keine verlangt oder die Pflicht erfüllt ist."""
    if not pattern_output.get("force_tool_use"):
        return []
    verlangt = list(pattern_output.get("tools") or [])
    if not verlangt:
        return []
    gerufen = gerufene_werkzeuge(tools_called)
    if pattern_output.get("requires_all_tools"):
        return [t for t in verlangt if t not in gerufen]
    return [] if set(verlangt) & gerufen else verlangt
