"""Text aus einer Zeile des Qualitätsprotokolls nehmen (Paket 16, D1) — rein, ohne I/O.

Das Qualitätsprotokoll hat eine eigene, längere Frist (``01-base/quality-log-config``), weil
seine Kennzahlen die Auswertung tragen. Mit ihnen stand aber auch die Nachricht und was aus ihr
folgte in der Zeile — länger, als die Gesprächsverläufe selbst bleiben. Nach deren Frist nimmt
der Aufbewahrungslauf (``services/aufbewahrung``) mit :func:`text_entfernen` heraus:

* ``message`` — die Nachricht (bis 500 Zeichen) → ``None``;
* die Entities, dreimal (``entities``, ``debug.entities``, ``debug.context.entities``): Thema,
  Fach, Suchbegriff und Dokumenttitel der Seite → ``{}``;
* die Begründungen des Modells (``debug.pattern_reasoning``,
  ``debug.phase3_modulations.selected_card_reasoning``);
* Fehlertexte der Werkzeuge (``debug.outcomes[*].error`` und die flache Kopie
  ``tool_outcomes[*].error`` — können den Suchbegriff nennen);
* der Freitext der Rechtsprüfung in ``debug.safety.reasons`` (``legal:… (Freitext)``).

Kennzahlen, Kennungen und Konfigurationstext (``core_rule``) bleiben. :data:`MARKE` hält den Lauf
idempotent: eine geleerte Zeile wird nicht noch einmal gelesen.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Final

MARKE: Final = "text_geleert"

_FREITEXT_IN_KLAMMERN = re.compile(r"\s*\(.*\)\s*$", re.S)


def text_entfernen(data: dict[str, Any]) -> dict[str, Any]:
    """Eine Kopie von ``data`` ohne Nutzer- und Modelltext, mit :data:`MARKE`."""
    neu = copy.deepcopy(data)
    neu["message"] = None
    _entities_leeren(neu)
    _fehler_leeren(neu.get("tool_outcomes"))
    debug = neu.get("debug")
    if isinstance(debug, dict):
        _entities_leeren(debug)
        _entities_leeren(debug.get("context"))
        debug.pop("pattern_reasoning", None)
        if isinstance(modulation := debug.get("phase3_modulations"), dict):
            modulation.pop("selected_card_reasoning", None)
        _fehler_leeren(debug.get("outcomes"))
        if isinstance(safety := debug.get("safety"), dict) and isinstance(
                gruende := safety.get("reasons"), list):
            safety["reasons"] = [_ohne_freitext(g) for g in gruende]
    neu[MARKE] = True
    return neu


def _entities_leeren(teil: Any) -> None:
    if isinstance(teil, dict) and "entities" in teil:
        teil["entities"] = {}


def _fehler_leeren(ergebnisse: Any) -> None:
    for ergebnis in ergebnisse if isinstance(ergebnisse, list) else []:
        if isinstance(ergebnis, dict):
            ergebnis.pop("error", None)


def _ohne_freitext(grund: Any) -> Any:
    if isinstance(grund, str) and grund.startswith("legal:"):
        return _FREITEXT_IN_KLAMMERN.sub("", grund)
    return grund
