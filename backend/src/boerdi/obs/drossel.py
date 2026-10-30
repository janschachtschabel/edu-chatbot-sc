"""Gedrosselte Logzeilen (Paket 18E/18F).

Ein Fehler, der je Zug oder je Aufruf auftritt (ein kaputter Konfigurationswert, ein abgelehnter
LLM-Schlüssel), soll im Log stehen, ohne es zu fluten: höchstens eine Zeile je Schlüssel und
Abstand; die nächste nach der Pause nennt die Zahl der ausgelassenen. ``math.inf`` als Abstand
heißt „einmal je Prozess“.

Der Zustand liegt im Prozess — je Replik eine Zeile, das genügt für den Betrieb.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

_uhr = time.monotonic


@dataclass
class _Stand:
    zuletzt: float
    ausgelassen: int = 0


_staende: dict[str, _Stand] = {}


def gedrosselt(logger: logging.Logger, stufe: int, schluessel: str, abstand_s: float,
               text: str, *args: object, exc_info: bool = False) -> bool:
    """``text % args`` auf ``stufe`` loggen, höchstens einmal je ``abstand_s`` und
    ``schluessel``. Gibt zurück, ob die Zeile geschrieben wurde. ``exc_info`` hängt den
    Traceback der gerade behandelten Ausnahme an."""
    jetzt = _uhr()
    stand = _staende.get(schluessel)
    if stand is not None and jetzt - stand.zuletzt < abstand_s:
        stand.ausgelassen += 1
        return False
    ausgelassen = stand.ausgelassen if stand is not None else 0
    _staende[schluessel] = _Stand(zuletzt=jetzt)
    # Durchreiche: was ins Log geht, prüft der Wächter an jedem Aufruf von ``gedrosselt``
    # (``tests/test_log_ohne_inhalt.py``).
    if ausgelassen:
        logger.log(stufe, text + " (%d gleiche Meldungen ausgelassen)",  # log-ok: Durchreiche
                   *args, ausgelassen, exc_info=exc_info)
    else:
        logger.log(stufe, text, *args, exc_info=exc_info)  # log-ok: Durchreiche
    return True


def zuruecksetzen() -> None:
    """Für Tests: alle Schlüssel vergessen."""
    _staende.clear()
