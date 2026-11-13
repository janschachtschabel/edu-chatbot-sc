# Fix: Kippler im Widget-E2E „320 px, Zeile bricht um“ (2026-11-13)

Der CI-Lauf auf `main` nach dem Merge von PR #63 war rot: `e2e/meine-vorgaenge.spec.ts:47`,
„btn-mic unter dem Feld“ (erwartet > 550, gemessen 550). Der PR-Lauf mit demselben Stand war grün,
und PR #63 hat das Frontend nicht berührt.

- **Ursache:** Das Widget startet mit Mikrofon-Knopf und blendet ihn erst aus, wenn
  `/speech/status` „aus“ meldet. Der Test maß die Eingabezeile, ohne darauf zu warten. Kam die
  Antwort später als die Messung, stand das Mikrofon noch in der Zeile des Feldes.
- **Nachgestellt:** mit einem um 400 ms verzögerten Sprachstatus stand `btn-mic` in der
  gemessenen Zeile. Lokal lag er 2 px unter der Oberkante des Feldes, der Test lief dort also auch
  im falschen Zustand durch; in der CI lagen beide gleich.
- **Behoben im Test, nicht im Widget:** Der Harness hat `ohneMikrofon()` und wartet damit, bis der
  Knopf weg ist. Vier Tests, die die Eingabezeile ohne Mikrofon messen, rufen es vor der Messung
  auf (`meine-vorgaenge.spec.ts` zweimal, `auth-button.spec.ts` zweimal).
- **Geprüft:** Gegenprobe mit verzögertem Status (vorher ein Mikrofon, nach dem Warten keines);
  beide Dateien fünfmal hintereinander, 45 von 45 grün; `eslint` sauber.
- **Nicht geändert:** Das Widget zeigt das Mikrofon weiter kurz an, bis der Status da ist. Das ist
  so gebaut (übernommen aus dem alten Chatbot) und eine eigene Frage.
- Deploy: nichts, nur Tests.
