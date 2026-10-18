"""Feld-Unterschiede zwischen zwei Fassungen eines Bereichs (Paket 16, C6) — rein, ohne I/O.

Die Sicherung zeigt neben dem YAML-Diff eine Tabelle *Feld · Werk · Eigen*. Hier entstehen ihre
Zeilen: nur abweichende Blätter, Werte als gekürzter JSON-Text, ``None`` = das Feld fehlt auf
dieser Seite (ein gesetztes ``null`` erscheint als Text ``"null"``).

Listen von Objekten werden je Eintrag verglichen (``steps[1].text``), Listen von Werten als
Ganzes — sonst zerfiele ein eingefügtes Stichwort in lauter verschobene Zeilen.
"""

from __future__ import annotations

import json
from typing import Any

_FEHLT = object()


def feld_unterschiede(
    werk: Any, eigen: Any, *, grenze: int = 100, laenge: int = 160,
) -> tuple[list[dict[str, str | None]], int]:
    """Die abweichenden Blätter (höchstens ``grenze``) und ihre Gesamtzahl."""
    zeilen: list[dict[str, str | None]] = []
    _vergleiche(werk, eigen, "", zeilen)
    return [
        {"pfad": z["pfad"], "werk": _text(z["werk"], laenge), "eigen": _text(z["eigen"], laenge)}
        for z in zeilen[:grenze]
    ], len(zeilen)


def _vergleiche(a: Any, b: Any, pfad: str, zeilen: list[dict[str, Any]]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in [*a, *(k for k in b if k not in a)]:
            _vergleiche(a.get(k, _FEHLT), b.get(k, _FEHLT), f"{pfad}.{k}" if pfad else str(k),
                        zeilen)
        return
    if isinstance(a, list) and isinstance(b, list) and _mit_objekten(a, b):
        for i in range(max(len(a), len(b))):
            _vergleiche(a[i] if i < len(a) else _FEHLT, b[i] if i < len(b) else _FEHLT,
                        f"{pfad}[{i}]", zeilen)
        return
    if a != b:
        zeilen.append({"pfad": pfad, "werk": a, "eigen": b})


def _mit_objekten(a: list[Any], b: list[Any]) -> bool:
    return any(isinstance(x, dict | list) for x in (*a, *b))


def _text(wert: Any, laenge: int) -> str | None:
    if wert is _FEHLT:
        return None
    text = json.dumps(wert, ensure_ascii=False)
    return text if len(text) <= laenge else text[:laenge] + "…"
