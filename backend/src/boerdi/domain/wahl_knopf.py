"""Die Chips einer Ablauf-Wahl erkennen (Paket AS-3a, Querschnitts-Review AS-3, Befund 1).

Ein Schritt mit Schnellantworten wartet auf die Wahl; seine Chips (Direktaktion ``ablauf_wahl``)
sind der einzige Weg weiter im Ablauf, wenn der Schritt keinen Freitext nimmt. Kein Deckel der
Schnellantworten darf sie deshalb streichen — weder die Zielzahl der Anzeige-Regeln
(``display-rules.quick_replies.max_count``, im Werk 2) noch das Muster, der Gastgeber oder die
Anmelde-Chips. Andere Vorschläge rücken nach hinten oder fallen weg.

Hier in ``domain`` (rein, ohne Abhängigkeiten), weil auch ``domain/auth_qr`` sie braucht.
"""

from __future__ import annotations

import json
from typing import Any, Final

#: Die Direktaktion eines Wahl-Chips (``services/ablauf/wahl_zug.AKTION``).
AKTION: Final = "ablauf_wahl"


#: Die Knöpfe einer Rückfrage „Neu starten?“ (``ablauf/zug._ersetzen_fragen``) tragen die Marke
#: ``ersetzt`` — auch sie sind der einzige Weg zur Antwort (Nachprüfung Querschnitt AS-4, Befund 3).
_RUECKFRAGE_AKTIONEN: Final = frozenset({"ablauf_starten", "ablauf_auftrag_pruefen"})
#: Der Knopf der Rückfrage „Ablauf abbrechen?“ (``ablauf/abbruch_zug``, mit ``bestaetigt``) — neben
#: den Chips des wartenden Schritts verdrängten diese ihn unter ``max_count: 2`` (Browser-Abnahme
#: AS-U, L-2). Der Leisten-Knopf ohne ``bestaetigt`` gehört nicht dazu.
_ABBRUCH_AKTION: Final = "ablauf_abbrechen"
#: AS-7a (F-2): der Navigations-Chip eines ``seite``-Schritts (``ablauf/seite_zug``) — der Weg zum
#: Ziel einer Führung; er übersteht jeden Deckel wie die Chips einer Wahl.
FUEHRUNG_PRAEFIX: Final = "__fuehrung__|"


def ist_wahl_knopf(qr: Any) -> bool:
    """Ist ``qr`` ein Chip ``__action__|<Label>|ablauf_wahl|{…}`` — oder ein Knopf der Rückfrage
    „Neu starten?“ (mit ``ersetzt``) bzw. „Ablauf abbrechen?“ (mit ``bestaetigt``)?"""
    if not isinstance(qr, str):
        return False
    if qr.startswith(FUEHRUNG_PRAEFIX):
        return True
    teile = qr.split("|", 3)
    if len(teile) != 4 or teile[0] != "__action__":
        return False
    if teile[2] == AKTION:
        return True
    if teile[2] not in _RUECKFRAGE_AKTIONEN and teile[2] != _ABBRUCH_AKTION:
        return False
    try:
        params = json.loads(teile[3])
    except ValueError:
        return False
    if not isinstance(params, dict):
        return False
    if teile[2] == _ABBRUCH_AKTION:
        return params.get("bestaetigt") is True
    return isinstance(params.get("ersetzt"), str)


def wahl_zuerst(qrs: list[Any]) -> list[Any]:
    """Die Wahl-Chips vorn, der Rest in seiner Reihenfolge dahinter."""
    return [q for q in qrs if ist_wahl_knopf(q)] + [q for q in qrs if not ist_wahl_knopf(q)]
