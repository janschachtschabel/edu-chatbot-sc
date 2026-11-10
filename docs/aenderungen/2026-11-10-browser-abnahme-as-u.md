# Browser-Abnahme AS-U (Ablauf-Leiste) und Behebungen (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5h (U-1 … U-8), §5k, §5l.

## Aufbau

- **Wegwerf-DB** `boerdi_asu_browser`: migriert, Seeds importiert, danach gelöscht.
- **Backend** aus dem Staging auf `127.0.0.1:8100`; **Widget** aus dem frisch gebauten Bündel,
  Seite `/widget/inline`; Engine `agent`, ohne Anmeldung.
- **Probe-Ablauf** `asu_probe`, angelegt über das Studio-API:
  - Auslöser „leiste testen“;
  - Schritt 1: Freitext → Teil `thema`;
  - Schritt 2: Wahl „Primarstufe/Sekundarstufe“ oder Freitext;
  - Schritt 3: Chip „Ja, weiter“, danach Ende.

## Fälle

| Fall | Ergebnis |
|---|---|
| Start | Die Leiste zeigt „Probe Leiste – Schritt 1 von 3, wartet auf dich“, „Einklappen“ und „Ablauf abbrechen“. Der feste Text trägt kein KI-Etikett (U-7). |
| Freitext, Wahl | Schritt 2 von 3, dann 3 von 3; „Gesammelte Daten (1)“ ist aufklappbar. **Befund L-1.** |
| Einklappen / Aufklappen | Eine Zeile: „„Probe Leiste“ wartet — hier geht es weiter, wenn du so weit bist.“ Der Fokus springt auf „Aufklappen“ und nach Enter zurück auf „Einklappen“. |
| Tastatur | Tab führt „Aufklappen“ → „Einklappen“ → „Ablauf abbrechen“, der Fokusring ist sichtbar. |
| Neuladen | Die Leiste steht wieder da, mit Schritt 3 von 3. |
| Abbrechen | Es kommt eine Rückfrage. **Befund L-2.** Nach der Bestätigung erscheint „Der Ablauf ist abgebrochen.“, die Leiste ist weg, darunter „Neues Vorhaben“ und „Arbeitsstand löschen“. |
| Weg zurück aus der Rückfrage | Die Wahl „Primarstufe“ unter der Rückfrage führt den Lauf weiter (Schritt 3 von 3), „Ja, weiter“ beendet ihn mit „Fertig.“, und die Leiste ist weg. |
| 320 px breit (entspricht 200 % Zoom) | Die Leiste bricht sauber um, die Knöpfe bleiben erreichbar. |
| „Meine Vorgänge“ | Ohne Anmeldung gibt es keinen Knopf, wie vorgesehen. Die Liste selbst braucht eine Anmeldung und war hier nicht prüfbar; die E2E-Tests decken sie mit nachgestellten Antworten ab. |
| Logs | Weder Server noch Browser-Konsole zeigen Fehler. |

## Befunde und Behebung

- **L-1 — „Gesammelte Daten“ sagte nichts.**
  - Ein Freitext-Teil zeigte nur „Text“.
  - Der Inhalt bleibt draußen (Review AS-3a, Befund 11), weil die Zusammenfassung in jedem Zug als
    Kennzeile an die KI geht.
  - **Behebung:** Die Zusammenfassung lautet „Text: <Name des Teils>“ (`ablauf/treiber.py`). Der
    Name stammt von der Redaktion. Die Leiste zeigt jetzt „Text: thema“.
- **L-2 — Rückfrage „Ablauf abbrechen?“.**
  - Neben „Ja, abbrechen“ stand der Chip des Schritts („Ja, weiter“). Das las sich wie eine zweite
    Zusage.
  - Schwerer wog: Bei zwei Schritt-Chips fehlte der Bestätigungs-Knopf ganz. Ursache war die
    Studio-Höchstzahl `display-rules.quick_replies.max_count: 2` im Widget-Nachlauf
    (`widget_postprocess`). Er kürzte auf zwei Chips und setzte danach die Wahl-Chips auf Kosten
    der übrigen wieder ein.
  - **Behebung:**
    - `wahl_knopf.ist_wahl_knopf` zählt den Knopf mit `bestaetigt` jetzt zu den Rückfrage-Knöpfen,
      die jede Höchstzahl überstehen, wie schon „Neu starten?“ (Querschnitt AS-4, Befund 3).
    - Der Knopf heißt „Ablauf abbrechen“ / „Cancel workflow“.
    - Gibt es einen Weg zurück, sagt die Frage dazu: „Willst du lieber weitermachen, wähle eine
      der anderen Antworten.“ (`action.ablauf.abbrechenFrageZurueck`).
  - Gleiche Wurzel wie der offene Punkt „Wahl mit ≥ 4 Chips schneidet den Ablauf-Knopf ab“
    (`offene-befunde` §1). Der dort beschriebene Weg über `turn_assembly.anhaengen` ist ein anderer
    und bleibt offen.
- **Beobachtung, kein Fehler:** Während ein Zug läuft, ist das Eingabefeld gesperrt („Boerdi
  denkt nach …“), und Getipptes geht verloren. Das ist so gewollt.

## Tests

- `test_ablauf_leiste.py`: Rückfrage mit und ohne Weg zurück.
- `test_ablauf_wahl_deckel.py`: Der Bestätigungs-Knopf zählt wie ein Wahl-Chip, der Leisten-Knopf
  nicht; im Widget-Nachlauf bleiben bei `max_count` 0 und 2 alle drei Knöpfe stehen.
- `test_ablauf_wahl.py`: Die Zusammenfassung lautet „Text: wunsch“, ohne den Inhalt.
- Alle vorher rot, danach grün.
- Teilmenge Ablauf/Wahl/Chips/Postprocess: 848 bestanden; ruff sauber.
- Nachprobe über die API und im Browser: drei Knöpfe, der Weg zurück funktioniert.

## Deploy

Backend neu bauen. Keine Migration, keine neue Variable.
