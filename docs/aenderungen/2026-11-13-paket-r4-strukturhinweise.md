# Paket R4: Hinweise zur Struktur im Entwurf (2026-11-13)

Plan [`2026-11-12-restpakete-ablaeufe-kestra-ui.md`](../plans/2026-11-12-restpakete-ablaeufe-kestra-ui.md),
Abschnitt R4. Grundlage sind TB-4 im Plan 2026-11-10 und Entscheid R-E11 (L5): nur Warnungen, nie
eine Sperre.

## Was

Der Strukturentwurf zeigt unter dem Baum einen zugeklappten Abschnitt „Hinweise zur Struktur (n)“,
wenn der Baum von den Richtwerten des Leitfadens abweicht. Dieselben Richtwerte nennt der Generator
(`services/strukturentwurf_prompt.py`).

| Hinweis | Richtwert |
|---|---|
| oben | 5 bis 15 Punkte auf der obersten Ebene |
| tief | höchstens 3 Ebenen |
| einzelkind | nie genau ein Unterpunkt |
| breit | höchstens 12 Unterpunkte |
| name | kein Schuljahr („2024/25“), keine Jahreszahl allein, keine Klasse, kein Format, kein Sammelbegriff („Sonstiges“) |
| doppelt | kein Titel zweimal auf derselben Ebene (ohne Groß/Klein) |

- Gerechnet wird im Modul über den bearbeiteten Baum (`entwurf-pruefung.ts`), also nach jeder
  Änderung neu. Backend und Manifest bleiben unverändert.
- Es sind höchstens 10 Hinweise, der Rest steht als Zahl da.
- Ob der Abschnitt offen ist, merkt sich der Zustand, denn das Element zeichnet bei jeder Änderung
  neu.
- Was Auslegung ist, prüft der Code nicht: Begriffsart der Geschwister, Facette oder Thema. Das
  steht im Master-Skill und im Hinweis des KI-Schritts.
- Die Befüllung (Materialien je Punkt) fehlt. Der Entwurf kennt keine Zahlen, erst der
  Strukturabgleich.

## Grenzen

- Gibt die Quelle eine Ordnung vor (ein Lehrplan mit 3 Lernfeldern, ein Schuljahr als Ordnung),
  erscheinen Hinweise trotzdem. Sie sind bewusst nur Warnungen.
- TB-3 Schritt 6 (Sammlungen anlegen) bleibt zurückgestellt (N15).

## Tests

- `entwurf-pruefung.spec.ts` (7 Fälle).
- `ui-strukturentwurf.element.spec.ts`: Abschnitt zugeklappt mit Zahl und Sätzen; ohne Abweichung
  kein Abschnitt.
- Budget: `ui-strukturentwurf` 11,7 kB gzip (Grenze je Modul 20 kB).

## Deploy

Widget-Bündel neu bauen, damit das nachgeladene Modul neu entsteht.
