"""Modul-Nutzung eines Eval-Laufs (Paket U1-g, G-6) — rein, ohne E/A.

Welche UI-Module in wie vielen Zügen erschienen, je Muster und je Anwendungsfall. Quelle ist das
Zug-Feld ``ui_module`` (die gezeigten Blöcke, ``evals/ui_module_golden.gezeigte_module`` bzw.
``runner._gezeigte_module``) — nicht ``tools_called``: abgeleitete Module entstehen ohne Aufruf.

Beim Lesen gerechnet wie das Profil (``run_profile``). Züge vor U1-g tragen das Feld nicht; sie
zählen nicht als „ohne Modul“, sondern gar nicht (``erfasst`` sagt, wie viele zählten).
Fehlzüge und Ersatzblasen (Fehler/„ausgelastet“, ``golden.fallback``) zählen nie — sie haben
nichts gezeigt (Review U1-g #11).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

#: Zeile für Züge ohne Muster-Angabe (fehlender Debug-Block).
OHNE_MUSTER = "—"


def _muster(turn: dict[str, Any]) -> str:
    """``"AGENT (Werkzeug-Agent)"`` → ``"AGENT"``, ``"M04 (…)"`` → ``"M04"``."""
    wert = str((turn.get("debug") or {}).get("pattern") or "").strip()
    return wert.split(" ", 1)[0] if wert else OHNE_MUSTER


def _ersatz(turn: dict[str, Any]) -> bool:
    """Eine Ersatzblase statt Antwort — der Gold-Lauf vermerkt sie in ``golden.fallback``."""
    golden = turn.get("golden")
    return isinstance(golden, dict) and bool(golden.get("fallback"))


def _leer() -> dict[str, Any]:
    return {"zuege": 0, "module": defaultdict(int)}


def _fertig(gruppen: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {k: {"zuege": g["zuege"], "module": dict(g["module"])}
            for k, g in sorted(gruppen.items())}


def modul_nutzung(conversations: list[dict[str, Any]]) -> dict[str, Any]:
    """``{zuege, erfasst, module, je_muster, je_anwendungsfall}``.

    ``zuege``: beantwortete Züge (ohne Fehlzüge und Ersatzblasen); ``erfasst``: davon mit
    ``ui_module``; ``module``: alle
    gesehenen Module, sortiert. Je Zeile ``{zuege, module: {name: Züge}}`` — ``zuege`` ist
    der Nenner. ``je_anwendungsfall`` nur aus Zügen mit ``anwendungsfall`` (Gold-Läufe).
    """
    je_muster: dict[str, dict[str, Any]] = defaultdict(_leer)
    je_fall: dict[str, dict[str, Any]] = defaultdict(_leer)
    gesehen: set[str] = set()
    zuege = erfasst = 0
    for conv in conversations:
        for turn in conv.get("turns") or [] if isinstance(conv, dict) else []:
            if not isinstance(turn, dict) or turn.get("error") or _ersatz(turn):
                continue
            zuege += 1
            module = turn.get("ui_module")
            if not isinstance(module, list):
                continue
            erfasst += 1
            namen = [str(m) for m in dict.fromkeys(module) if m]
            gesehen.update(namen)
            zeilen = [je_muster[_muster(turn)]]
            if fall := str(turn.get("anwendungsfall") or ""):
                zeilen.append(je_fall[fall])
            for zeile in zeilen:
                zeile["zuege"] += 1
                for name in namen:
                    zeile["module"][name] += 1
    return {"zuege": zuege, "erfasst": erfasst, "module": sorted(gesehen),
            "je_muster": _fertig(je_muster), "je_anwendungsfall": _fertig(je_fall)}
