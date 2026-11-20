"""Den Text der Texterkennung glätten (Plan 2026-11-19, Paket C) — rein, ohne I/O.

- Ein Codezaun um die Antwort des Modells wird entfernt.
- **Seitenkopf** (C4): das Modell sieht jede Seite allein und schreibt den Kopf jedes Mal als
  Überschrift — in der Gliederung stand „# Aufbereitungsmechaniker“ dann 13-mal. Als Kopf gilt eine
  kurze erste Zeile ohne Tabellensyntax, die auf mindestens drei und mehr als der Hälfte der Seiten
  gleich ist; sie bleibt nur auf der ersten. Review Paket C, Befund 6: eine Tabellenkopfzeile
  (``| Lernziele | Lerninhalte |``) steht auch auf jeder Seite — sie zu entfernen zerbrach die
  Tabellen ab Seite 2.
"""

from __future__ import annotations

import re
from typing import Final

_ZAUN: Final = re.compile(r"^```[A-Za-z]*\n(.*?)\n?```$", re.S)
#: Länger ist kein Seitenkopf mehr, sondern Inhalt.
KOPF_ZEICHEN: Final = 120


def ohne_zaun(text: str) -> str:
    text = text.strip()
    treffer = _ZAUN.match(text)
    return treffer.group(1).strip() if treffer else text


def _zeilen(text: str) -> list[str]:
    """``[erste Zeile, Rest]`` einer Seite (ohne Rand)."""
    return text.strip().split("\n", 1)


def _kopf(text: str) -> str:
    """Die erste Zeile, verglichen ohne ``#``, Leerraum und Groß-/Kleinschreibung — leer, wenn sie
    kein Seitenkopf sein kann (Tabellenzeile, zu lang)."""
    erste = _zeilen(text)[0]
    if "|" in erste or len(erste) > KOPF_ZEICHEN:
        return ""
    return " ".join(erste.lstrip("#").split()).casefold()


def ohne_seitenkopf(texte: list[str | None]) -> list[str | None]:
    """Die Texte je Seite (``None`` = nicht gelesen); ein wiederkehrender Kopf nur auf der
    ersten."""
    koepfe = [_kopf(t) if t else "" for t in texte]
    gelesen = sum(1 for t in texte if t)
    zaehler: dict[str, int] = {}
    for k in koepfe:
        if k:
            zaehler[k] = zaehler.get(k, 0) + 1
    kopf = next((k for k, n in zaehler.items() if n >= 3 and n * 2 > gelesen), None)
    if kopf is None:
        return texte
    aus: list[str | None] = []
    erster = True
    for t, k in zip(texte, koepfe, strict=True):
        if t and k == kopf and not erster:
            t = _zeilen(t)[1].strip() if len(_zeilen(t)) > 1 else ""
        elif t and k == kopf:
            erster = False
        aus.append(t)
    return aus
