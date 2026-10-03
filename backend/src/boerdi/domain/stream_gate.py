"""Streamt dieser Zug? (Plan ``docs/plans/2026-10-01-token-streaming.md``, T8)

Entschieden wird vor der Antwortrunde. Gesperrt wird, was die Endverarbeitung
sicher umschreibt oder verschiebt — dort spränge die Blase, wenn ``result`` sie
am Ende ersetzt:

- Suchmuster M05/M06: Typ-Fokus ersetzt den ganzen Text, die
  Anti-Halluzinations-Wache schreibt Sätze um (``services/turn_links``);
- Dokument-Muster M09–M11: der Text wandert in den Kasten (``turn_persist``, E-S6);
- M16: der Themenseiten-Auflöser kann den Text neu binden;
- erhöhtes Risiko: der fertige Text trägt Hinweise und kommt besser auf einmal.

Rein (CLAUDE.md, Regel 4): nur stdlib.
"""

from __future__ import annotations

_SUCHMUSTER = frozenset({"M05", "M06"})
_DOKUMENTMUSTER = frozenset({"M09", "M10", "M11"})
_AUFLOESER = frozenset({"M16"})


def sperrgrund(*, eingeschaltet: bool, antwort_werkzeug: bool, muster_id: str,
               risiko: str) -> str | None:
    """``None`` = der Zug streamt. Sonst der Grund für die Logzeile.

    ``antwort_werkzeug``: ob ``respond_to_user`` angeboten wird — gestreamt
    wird nur dessen Text (E-S1). ``risiko`` ist ``SafetyDecision.risk_level``.
    """
    if not eingeschaltet:
        return "aus"
    if not antwort_werkzeug:
        return "ohne_antwort_werkzeug"
    if risiko != "low":
        return "risiko"
    if muster_id in _SUCHMUSTER:
        return "suchmuster"
    if muster_id in _DOKUMENTMUSTER:
        return "dokumentmuster"
    if muster_id in _AUFLOESER:
        return "aufloeser"
    return None
