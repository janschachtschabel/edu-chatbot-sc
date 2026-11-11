# Paket TW-2: Vorgaben der Redaktion je Ablauf-Schritt (2026-11-11)

Plan `plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`, Entscheid E1. Der Nutzer wünscht
Wissen „am besten in den Abläufen“.

## Umsetzung

- **Feld `agent.vorgaben`** am KI-Schritt:
  - je Sprache, als Textfläche, höchstens 2000 Zeichen, Vorgabe `None`;
  - im Studio „Vorgaben für die Module“, de und en;
  - es ist Text der Redaktion, nie Eingabe der Person.
- **`ki_schritt.vorgaben(schritt, lang)`** liefert die Vorgaben in der Sprache, sonst Deutsch,
  sonst leer.
- **Weitergabe:** Wartet ein Lauf an diesem Schritt, bekommt die Umgebung der Module
  (`aufruf.Umgebung.vorgaben`) die Vorgaben.
  - **Agent-Weg:** `respond_agent` → `run_agent_loop(modul_vorgaben=…)` → `ModulUmgebung`.
  - **Muster-Weg:** `respond` legt sie für den Zug unter `tool_loop_module.VORGABEN_KEY` ab und
    räumt sie danach weg.
- **`ui_strukturentwurf`:** `Auftrag.vorgaben` geht in jede Aufforderung (obere Ebene, aus
  Dokument, aus Inhalten, Unterthemen). Sie steht im **Systemteil** unter „Vorgaben der Redaktion
  für diesen Ablauf“ und gilt vor den allgemeinen Regeln, nicht vor dem Antwortformat. Thema und
  Hinweise der Person bleiben im Nutzerteil, als Daten.

## Prüfung

- `test_tw2_ablauf_vorgaben.py`: 5 Fälle, zuerst rot; nach dem Review 7.
  - das Feld, die Grenze und der Rückfall auf Deutsch;
  - der Systemteil statt der Daten;
  - die Vorgaben bei Unterthemen, Dokument und Inhalten;
  - der Dienst übernimmt die Umgebung;
  - der Muster-Weg über `_ergebnis`.
- ruff sauber.

## Review (unabhängig) und Behebung

3 MINOR, 2 NIT. Geprüft und in Ordnung:

- Die Vorgaben kommen nur aus dem Studio, die KI kann sie nicht setzen.
- Log, Trace und Debug-Block tragen sie nicht.
- Der Schlüssel wird aufgeräumt und nie gespeichert.
- Die Fassung bleibt bei `None` gleich.

Behoben:

- **MINOR 1:** Ein im Studio geleertes Feld (`{"de": ""}`) änderte die Fassung und hätte
  wartende Läufe beendet. Jetzt gilt `_ohne_leere_saetze` wie bei `freigabe`: leer heißt nicht
  gesetzt. Dasselbe gilt für `startknopf` (TW-3).
- **MINOR 2:** Ein neuer Test prüft, dass jeder Aufruf des Generators die Vorgaben trägt: Ebene 1
  und Ebene 2, ohne und mit Dokument. Ein vergessenes `vorgaben=` fällt so auf.
- **MINOR 3:** Bereichsschema und OpenAPI werden nach TW-4 neu exportiert, siehe Querschnitt.
- **NIT 4:** Im Muster-Weg gehen die Vorgaben nur an Module, die der KI-Schritt nennt, wie im
  Agent-Weg. Der Schlüssel trägt dafür ein Paar aus Vorgaben und Werkzeugen.
- **NIT 5:** Der Modul-Docstring des Prompts nennt die Vorgaben im Systemteil.
- **Beobachtung:** Ändert die Redaktion die Vorgaben, ändert sich die Fassung, und wartende Läufe
  enden, wie bei jedem Schritttext.

## Grenzen

- **Nur am KI-Schritt:** Die Vorgaben gelten, solange der Lauf am KI-Schritt wartet. Ein späteres
  „vertiefe“ oder „ergänze“ nach dem Ende des Ablaufs läuft ohne sie, mit den allgemeinen Regeln
  des Generators (Querschnitts-Review TW, Befund 7).

- **Kein Test für den Agent-Weg.** Er ist eine Zeile in `respond_agent`, ein Test über den ganzen
  Zug fehlt. Den Weg zeigt der Chat-Smoke nach TW-4.
- **Cache:** Mit Vorgaben ändert sich der Systemteil je Ablauf. Der Cache des Anbieters trifft
  dann je Ablauf, nicht über alle Entwürfe hinweg.
