"""Was vom mitlaufenden Antworttext schon sichtbar werden darf (Token-Streaming, T4).

Der Text einer Antwort kommt stückweise. Die Endverarbeitung formt ihn danach
noch um — Links werden zu Labels, eine Ansage-Zeile steht voran. Was der Client
vorab sieht, soll dazu passen; sonst springt die Blase, wenn ``result`` sie
ersetzt (Plan ``docs/plans/2026-10-01-token-streaming.md``, Ansatz B).

- :func:`stabiler_teil` hält am Ende zurück, was ein späteres Zeichen noch
  umdeuten kann.
- :class:`VorschauStrom` formt den stabilen Teil mit derselben Funktion um wie
  später die Endverarbeitung (der Aufrufer gibt sie herein) und gibt nur heraus,
  was das schon Herausgegebene fortsetzt. Passt eine Umformung nicht mehr dazu,
  wartet der Strom; den Rest richtet ``result``.

Rein (CLAUDE.md, Regel 4): nur stdlib.
"""

from __future__ import annotations

import re
from collections.abc import Callable

#: Zeilenanfänge, deren Zeile die Endverarbeitung als Ganzes entfernen kann:
#: Aufzählungen, die nur aus einem Link bestehen (``url_helpers``), und
#: Modell-Ansagen „▸ … aktiv" (``skill_precedence``). Auch „1" allein zählt —
#: daraus kann noch „1. " werden.
_GANZE_ZEILE = re.compile(r"\s*(?:▸|(?:\d+[.)]?|[-*+•])(?:\s|$))")


def _klammer_offen(roh: str, p: int) -> bool:
    """Ist die eckige Klammer bei ``p`` noch ein unfertiger Link?"""
    zu = roh.find("]", p + 1)
    if zu < 0:
        return True  # Link-Text noch offen
    if zu + 1 >= len(roh):
        return True  # „]" am Ende: es kann noch „(" kommen
    if roh[zu + 1] != "(":
        return False  # eine Klammer, kein Link
    return roh.find(")", zu + 2) < 0  # Adresse noch offen


def stabiler_teil(roh: str) -> str:
    """``roh`` bis vor das erste noch offene Konstrukt.

    Offen sind: eine ``[`` ohne fertigen Link; eine Zeile ohne Zeilenende, die mit
    ``[``, ``▸`` oder einem Aufzählungszeichen beginnt (solche Zeilen entfernt die
    Endverarbeitung womöglich als Ganzes — gesendet wären sie ein Stau, Review
    M2); ein ungepaartes ``**`` im letzten Absatz; ein einzelnes ``*`` am Ende,
    das noch ``**`` werden kann.
    """
    schnitt = len(roh)
    p = roh.find("[")
    while p >= 0:
        if _klammer_offen(roh, p):
            schnitt = p
            break
        p = roh.find("[", p + 1)

    zeilenanfang = roh.rfind("\n") + 1
    letzte_zeile = roh[zeilenanfang:]
    if letzte_zeile.lstrip().startswith("[") or _GANZE_ZEILE.match(letzte_zeile):
        schnitt = min(schnitt, zeilenanfang)

    absatz = roh.rfind("\n\n", 0, schnitt)
    absatz = 0 if absatz < 0 else absatz + 2
    letzter = roh[absatz:schnitt]
    if letzter.count("**") % 2:
        schnitt = absatz + letzter.rfind("**")

    stabil = roh[:schnitt]
    if stabil.endswith("*") and not stabil.endswith("**"):
        stabil = stabil[:-1]
    return stabil


class VorschauStrom:
    """Rohtext stückweise hinein, anzuhängender Vorschautext heraus."""

    def __init__(self, umformen: Callable[[str], str]) -> None:
        self._umformen = umformen
        self._roh = ""
        self._gesendet = ""
        self._rueckschritte = 0

    def weiter(self, stueck: str) -> str:
        """Den neu anzuhängenden Vorschautext nach ``stueck`` — oder ``""``."""
        self._roh += stueck
        return self._neu(stabiler_teil(self._roh))

    def ende(self) -> str:
        """Am Ende ist nichts mehr offen: der ganze Rohtext zählt."""
        return self._neu(self._roh)

    def _neu(self, stabil: str) -> str:
        vorschau = self._umformen(stabil)
        if not vorschau.startswith(self._gesendet):
            self._rueckschritte += 1
            return ""
        neu = vorschau[len(self._gesendet):]
        self._gesendet = vorschau
        return neu

    @property
    def gesendet(self) -> str:
        """Alles bisher Herausgegebene."""
        return self._gesendet

    @property
    def rueckschritte(self) -> int:
        """Wie oft die Umformung schon Herausgegebenes geändert hätte."""
        return self._rueckschritte
