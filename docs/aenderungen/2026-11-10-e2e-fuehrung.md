# E2E für den Kernweg einer Führung (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5m (AS-7). Das war bisher offen in
`offene-befunde-und-todo.md` §1.

Neue Datei `frontend/e2e/fuehrung.spec.ts`. Zwei Fälle im echten Browser, das Backend ist eine
Attrappe:

1. **Wiederkehrer mit wartender Führung auf `/start`:**
   - Die Ablauf-Leiste zeigt „wartet auf den Seitenwechsel“ und den Weg-Knopf.
   - Der Seiten-Ping fragt auf `/start` nach und bekommt eine leere Antwort.
   - Es kommt kein Kontext-Gruß (Browser-Abnahme AS-7, L-3).
2. **Weg-Knopf → `/ziel`:**
   - Die Seite wechselt wirklich (gleiche Herkunft), und das Widget startet dort neu, mit derselben
     Sitzung.
   - Der Seiten-Ping meldet die Ankunft, der Schlusssatz erscheint, und die Leiste ist weg.

**Prüfung:**
- 2 grün, mit `--repeat-each 3` 6 grün. ESLint ist sauber.
- **Gegenprobe:** Ohne die Behebung L-3 (`lifecycle._afterResume` grüßt trotz wartender Führung)
  wird Fall 1 rot. Mit der Behebung sind beide grün.
