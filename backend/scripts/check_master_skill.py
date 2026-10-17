#!/usr/bin/env python
"""Prüft den Master-Skill im Repositorium gegen die Wächter der Vorlage (nur lesen).

Gedacht für nach jedem Übertragen im md-editor. Das Skript holt den Knoten so,
wie ihn der Chat bekommt (``master_skill.neu_laden`` → MCP ``get_skill``, an
beiden Zwischenspeichern vorbei, Konfiguration aus ``backend/.env``), trennt den
Vorspann des MCP-Servers ab und wendet die Wächter aus
``tests/test_master_skill_vorlage.py`` an — dieselben Regeln, die die Vorlage im
Repo hält, an einer Stelle gepflegt. Die Umformatierung des Editors (Absätze
einzeilig, ``**M09**`` statt ``(M09)``, fette Überschriften) tragen die Wächter.

    uv run python scripts/check_master_skill.py

Rückgabe: 0 = alle Regeln erfüllt · 1 = mindestens eine verletzt · 2 = Knoten
nicht abrufbar oder keine Regel gefunden.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from boerdi.services import master_skill

_WAECHTER = Path(__file__).resolve().parents[1] / "tests" / "test_master_skill_vorlage.py"

#: Die Linie, mit der der MCP-Server seinen Vorspann (Titel, „Aktivierung“,
#: Hinweis) vom Dokument trennt. Die Vorlage selbst enthält keine.
_TRENNLINIE = "---"


def dokumentteil(roh: str) -> str:
    """Der Text unter der Trennlinie des Servers — ohne Trennlinie der ganze Text."""
    zeilen = roh.splitlines(keepends=True)
    for i, zeile in enumerate(zeilen):
        if zeile.strip() == _TRENNLINIE:
            return "".join(zeilen[i + 1:]).lstrip("\n")
    return roh


def waechter() -> dict[str, Callable[[str], None]]:
    """Die Wächter der Vorlage: jede Prüffunktion, die nur den Text nimmt."""
    spec = importlib.util.spec_from_file_location("waechter_master_skill", _WAECHTER)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return {
        name: funktion for name, funktion in inspect.getmembers(modul, inspect.isfunction)
        if name.startswith("test_") and list(inspect.signature(funktion).parameters) == ["text"]
    }


def pruefe(text: str) -> dict[str, str | None]:
    """Je Wächter ``None`` (erfüllt) oder der Grund, warum nicht.

    Jede Ausnahme zählt als Befund: ein Wächter, der seinen Abschnitt nicht
    findet, scheitert oft schon beim Zerlegen (``IndexError``) — auch das ist
    eine Meldung, die die Redaktion braucht, kein Absturz des Skripts.
    """
    befunde: dict[str, str | None] = {}
    for name, pruefung in waechter().items():
        try:
            pruefung(text)
            befunde[name] = None
        except Exception as fehler:
            befunde[name] = _meldung(fehler)
    return befunde


def _meldung(fehler: Exception) -> str:
    """``Typ: Meldung`` — bei einem nackten ``assert`` mit der Prüfzeile selbst.

    Ohne pytest schreibt niemand die Asserts um, und die meisten Wächter prüfen
    einen Satz mit ``assert "…" in abschnitt`` ohne eigene Meldung: gemeldet
    wurde nur „AssertionError: “. Die Quellzeile nennt den fehlenden Satz.
    """
    text = str(fehler)
    if not text and fehler.__traceback__ is not None:
        text = traceback.extract_tb(fehler.__traceback__)[-1].line or ""
    return f"{type(fehler).__name__}: {text}"


def main() -> int:
    try:
        stand = asyncio.run(master_skill.neu_laden())
        roh = stand.get("text")
        befunde = pruefe(dokumentteil(roh)) if roh else {}
    except Exception as fehler:
        # Skript-Grenze: fehlt die Testdatei, pytest oder der Server, ist das
        # „nicht prüfbar“ (2) — kein Regelbruch (1), den die Redaktion im Text sucht.
        print(f"NICHT PRÜFBAR: {type(fehler).__name__}: {fehler}")
        return 2
    if not roh:
        kennung = stand.get("node_id") or "(MASTER_SKILL_NODE_ID leer)"
        print(f"NICHT ABRUFBAR: Knoten {kennung} — {stand.get('last_error')}")
        return 2
    if not befunde:
        print(f"KEINE REGEL GEFUNDEN in {_WAECHTER}")
        return 2
    print(f"Knoten {stand['node_id']} · {stand['length']} Zeichen · "
          f"sha256 {(stand.get('sha256') or '')[:12]}")
    for name, befund in befunde.items():
        print(f"{'VERLETZT' if befund else 'erfüllt '}  {name}"
              + (f" — {befund}" if befund else ""))
    verletzt = sum(1 for befund in befunde.values() if befund)
    print(f"{len(befunde) - verletzt} von {len(befunde)} Regeln erfüllt")
    return 1 if verletzt else 0


if __name__ == "__main__":
    # Nur die Befunde: das Abruf-Protokoll des MCP-Clients steht auf INFO.
    logging.disable(logging.INFO)
    sys.exit(main())
