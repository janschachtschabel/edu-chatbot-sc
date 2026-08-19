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
gehoeren zusammen. Die Sitzungs-Ansage hier fuehrt ihre eigene Notiz und
braucht von jener nichts. Sie lag dort nur zufaellig, weil die verwandte
Funktion dort steht (Durchsicht 2026-08-19).

**Warum ein Merker und kein Zugzaehler.** Bis 2026-08-19 galt ``turn_count ==
0`` als „erste Antwort der Sitzung". Live gemessen: nach einem Tour-Zug stand
die Zeile ein zweites Mal im Chat. Der Zaehler waechst allein in
``turn_persist``; die Zuege, die frueher enden — Tour, Kontext-Begruessung,
Schreib-Abnahme — beantworten den Zug selbst und kommen dort nie an. „Erster
Zug" traf danach ein zweites Mal zu. Der Merker in ``entities`` kennt diesen
Fall nicht: angesagt ist angesagt. Er reist in derselben jsonb-Spalte wie
``LAUF_KEY`` und ``_last_pattern`` und wird von ``turn_persist`` mitgeschrieben.
"""

from __future__ import annotations

from typing import Final

#: Der Schluessel in ``session_state['entities']``: „in dieser Sitzung angesagt".
#: Unterstrich-Praefix wie die uebrigen internen Merker (``_last_pattern``) —
#: das Feld ist eine Ablage des Zuges und kein erkanntes Entity.
ANSAGE_KEY: Final = "_master_ansage"


def _ohne_zeile(text: str, zeile: str) -> str:
    """Alle Vorkommen der Ansage als eigene Zeile entfernen."""
    behalten = [z for z in text.splitlines() if z.strip() != zeile]
    return "\n".join(behalten).lstrip("\n")


def mit_master_ansage(text: str, zeile: str, entities: object) -> str:
    """Die Ansage voranstellen — einmal je Sitzung, sonst nicht.

    **Zwei Halbschritte, beide noetig.** Gesetzt wird nur, solange die Sitzung
    sie noch nicht hatte; entfernt wird die Modell-Kopie **immer** — sonst
    stuende sie beim ersten Mal doppelt und tauchte spaeter zufaellig wieder auf.

    ``entities`` ist der Sitzungs-Beutel (``session_state['entities']``), und
    diese Funktion schreibt hinein: sie merkt sich, dass angesagt wurde.
    Dieselbe Bauart wie ``skill_precedence.merke_laufende_anleitung`` — nur
    faellt hier der Schreib- mit dem Lesezeitpunkt zusammen, deshalb EINE
    Funktion und nicht zwei. Ist der Beutel nicht lesbar, gibt es keinen Ort
    zum Merken, und dann wird auch nichts angesagt: eine Ansage in JEDEM Zug
    waere schlimmer als keine.

    ``zeile`` leer heisst „keine Anleitung geladen" ⇒ nichts behaupten.
    An eine leere Antwort kommt nichts (Regel aus ``append_answer_notes``) —
    und der Merker bleibt dann unberuehrt, denn angesagt wurde ja nichts.

    Steht die Zug-Ansage („… wird geladen") schon voran, schliesst diese Zeile
    ohne Leerzeile daran an: zwei Angaben ueber denselben Zug sind EIN Block und
    keine Doppelung (Durchsicht 2026-08-19).
    """
    if not isinstance(text, str) or not text.strip():
        return text
    if not zeile:
        return text
    sauber = _ohne_zeile(text, zeile)
    offen = isinstance(entities, dict) and not entities.get(ANSAGE_KEY)
    if not offen or not sauber.strip():
        return sauber
    entities[ANSAGE_KEY] = True
    trenner = "\n" if sauber.lstrip().startswith("[ edu-sharing Skill ]") else "\n\n"
    return f"{zeile}{trenner}{sauber}"
