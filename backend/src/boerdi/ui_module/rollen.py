"""Rollen einer Datei aus ``ui_upload`` (Plan 2026-11-20, P1 / UO-4).

Je Datei wählt die Person **Gliederung** (``struktur``: liefert die Struktur, wird nicht
einsortiert), **Material** (``inhalt``: wird in den Baum einsortiert), **Gliederung und Material**
(``beides``) oder „Nicht verwenden“ (``ignorieren``). ``beides`` gilt überall als
Strukturdokument UND als Inhalt — darum fragen die Lesestellen nie nach einem Wert, sondern nach
:func:`ist_gliederung` bzw. :func:`ist_material`. Alte Einträge (nur ``struktur``/``inhalt``)
bleiben gültig.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

STRUKTUR: Final = "struktur"
INHALT: Final = "inhalt"
BEIDES: Final = "beides"
#: Die Rollen, die als Strukturdokument gelesen werden (Höchstzahl und lesbare Formate gelten).
GLIEDERUNG: Final = frozenset({STRUKTUR, BEIDES})
#: Die Rollen, die als Inhalt einsortiert werden (Kurzangaben, Metadaten, Entwurf aus Dateien).
MATERIAL: Final = frozenset({INHALT, BEIDES})


def ist_gliederung(rolle: Any) -> bool:
    """Liefert die Datei die Struktur (``struktur`` oder ``beides``)?"""
    return isinstance(rolle, str) and rolle in GLIEDERUNG


def ist_material(rolle: Any) -> bool:
    """Wird die Datei als Inhalt einsortiert (``inhalt`` oder ``beides``)?"""
    return isinstance(rolle, str) and rolle in MATERIAL


def als_material(rolle: Any) -> str:
    """Die Rolle eines Eintrags im Teil ``metadaten``: ``beides`` bleibt, sonst ``inhalt`` —
    auch bei einem Wert, den der Browser unterschob."""
    return BEIDES if rolle == BEIDES else INHALT


#: Plan 2026-11-20, P2: die Rollen-Vorgabe eines Upload-Schritts (``ui_upload``-Daten
#: ``rolle_vorgabe``) — mit welcher Rolle die nutzbaren Dateien beginnen. ``auto`` ist die Regel
#: des Moduls (ein Lehrplan-Name in der Wurzel wird Gliederung).
VORGABEN: Final = ("auto", "gliederung", "material", "beides")


def vorgabe(daten: Mapping[str, Any]) -> str:
    """Die Rollen-Vorgabe aus Schritt- oder Block-Daten. Ein ausdrücklicher Wert zählt; sonst
    heißt der alte Schlüssel ``einzeldatei_als_struktur: true`` ``gliederung`` (alte Fassungen
    bleiben gültig), alles andere ``auto``."""
    wert = daten.get("rolle_vorgabe")
    if wert in VORGABEN:
        return str(wert)
    return "gliederung" if daten.get("einzeldatei_als_struktur") is True else "auto"
