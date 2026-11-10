"""Sicherungen von vor AS-0 lesen: der Ablauf-Katalog wird ein Dokument je Ablauf.

Bis AS-0 (Plan 2026-11-09) lagen alle Abläufe in ``06-ablaeufe/katalog``. Schnappschüsse, der
Werkszustand in der Datenbank und heruntergeladene Sicherungen tragen ihn noch. Ein Wiederherstellen
übersprang ihn (gestrichen) und hätte im Modus „exakt“ die Abläufe gelöscht (Review AS-0,
Befund 2). :func:`katalog_aufteilen` macht daraus vorher, was Migration 0021 aus einer Datenbank
macht: je gültigem Eintrag ``06-ablaeufe/<id>``; ein Dokument, das die Sicherung selbst trägt, hat
Vorrang. Rein, ohne I/O.
"""

from __future__ import annotations

import re
from typing import Any, Final

KATALOG: Final = "06-ablaeufe/katalog"
_ORDNER: Final = "06-ablaeufe/"
_ID: Final = re.compile(r"[a-z][a-z0-9_]{0,39}")


def katalog_aufteilen(bereiche: dict[str, Any]) -> dict[str, Any]:
    """``bereiche`` ohne ``06-ablaeufe/katalog``, dafür seine Einträge als Dokumente."""
    if KATALOG not in bereiche:
        return bereiche
    ergebnis = {k: v for k, v in bereiche.items() if k != KATALOG}
    katalog = bereiche[KATALOG]
    liste = katalog.get("ablaeufe") if isinstance(katalog, dict) else None
    for eintrag in liste if isinstance(liste, list) else []:
        kennung = eintrag.get("id") if isinstance(eintrag, dict) else None
        if isinstance(kennung, str) and _ID.fullmatch(kennung) and kennung != "katalog":
            ergebnis.setdefault(_ORDNER + kennung, eintrag)
    return ergebnis
