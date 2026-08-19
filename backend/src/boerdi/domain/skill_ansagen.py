"""Die Sitzungs-Ansage der Gesamtanleitung — „diese Anlage arbeitet nach X".

Eine Zeile, einmal je Sitzung, vom SERVER gesetzt. Nutzer-Vorgabe 2026-08-19:
„diese Nachricht sollte immer am Start jeder neuen Sitzung kommen, wenn der
User ein Gespraech beginnt und die Skill geladen wird."

**Warum der Server und nicht das Modell.** Der Master-Skill bittet unter
„## Aktivierung" selbst darum, die Zeile woertlich auszugeben. Gemessen ueber
drei Zuege einer Sitzung: Zug 1 ja, Zug 2 nein, Zug 3 wieder ja. Eine Ansage,
die das Modell vergisst oder umformuliert, ist eine Behauptung; diese hier
entsteht, weil der Abruf lief — sie ist ein Beleg. Dieselbe Lehre wie bei
``skill_precedence.mit_ladehinweis``, nur eine Ebene hoeher.

**Warum ein eigenes Modul.** ``mit_ladehinweis`` liest die Gespraechs-Notiz, die
``skill_precedence`` selbst schreibt (``LAUF_KEY``) — Schreiber und Leser
gehoeren zusammen. Die Sitzungs-Ansage hier braucht davon nichts: Text, Zeile,
Zugzaehler, fertig. Sie lag dort nur zufaellig, weil die verwandte Funktion
dort steht (Durchsicht 2026-08-19).
"""

from __future__ import annotations


def _ohne_zeile(text: str, zeile: str) -> str:
    """Alle Vorkommen der Ansage als eigene Zeile entfernen."""
    behalten = [z for z in text.splitlines() if z.strip() != zeile]
    return "\n".join(behalten).lstrip("\n")


def mit_master_ansage(text: str, zeile: str, turn_count: object) -> str:
    """Die Ansage voranstellen — im ersten Zug einer Sitzung, sonst nicht.

    **Zwei Halbschritte, beide noetig.** Gesetzt wird nur im ersten Zug
    (``turn_count == 0``: der Zaehler steht beim Antworten auf dem Stand VOR
    diesem Zug). Entfernt wird die Modell-Kopie **immer** — sonst stuende sie im
    ersten Zug doppelt und tauchte spaeter zufaellig wieder auf.

    ``zeile`` leer heisst „keine Anleitung geladen" ⇒ nichts behaupten.
    An eine leere Antwort kommt nichts (Regel aus ``append_answer_notes``).

    Steht die Zug-Ansage („… wird geladen") schon voran, schliesst diese Zeile
    ohne Leerzeile daran an: zwei Angaben ueber denselben Zug sind EIN Block und
    keine Doppelung (Durchsicht 2026-08-19).
    """
    if not isinstance(text, str) or not text.strip():
        return text
    if not zeile:
        return text
    sauber = _ohne_zeile(text, zeile)
    erster = (isinstance(turn_count, int) and not isinstance(turn_count, bool)
              and turn_count == 0)
    if not erster or not sauber.strip():
        return sauber
    trenner = "\n" if sauber.lstrip().startswith("[ edu-sharing Skill ]") else "\n\n"
    return f"{zeile}{trenner}{sauber}"
