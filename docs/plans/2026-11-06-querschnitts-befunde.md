# Plan: Befunde des Querschnitts-Reviews beheben (2026-11-06)

Grundlage: [`../audits/2026-11-06-querschnitts-review.md`](../audits/2026-11-06-querschnitts-review.md).
Nutzer 2026-11-06: „wie empfohlen vorgehen und alle Befunde beheben“ — damit gelten die Vorschläge zu
M1 (Abholen schließt keine fremden Fragen) und M6 (Vorgang endet mit seinem Ablauf, neues Vorhaben).
Je Paket: Tests zuerst, Review mit Befundbehebung, Änderungsnotiz; Commits macht der Nutzer.

## Q1 — Upload und automatisches Abholen (M1, M2, M3 + Upload-/Frontend-MINOR/NIT)

Backend
1. M2: `datei`/`abschluss` ohne offene Frage; gebunden an Sitzung, Anmeldung, Schalter und den Teil
   `ablage` (Prüf-Kürzel **und** `block_id` im Teil). `vorbereiten` verlangt die Frage weiter.
2. M3: selbst gesetztes „ohne Antwort“ (`ohne_antwort: true`) ist nicht endgültig — ein neuer Versuch lädt
   hoch und löst beim MCP erneut ein (dort je Index idempotent); nur ein vom MCP gemeldetes `unverified` ist
   endgültig.
3. Verlorene Stände: `teile_speichern` rechnet nach `VorgangKonflikt` neu (Rückruf), `_stand_festhalten` und
   `abschluss` nutzen das.
4. `vorbereiten` überschreibt keinen offenen Stapel mit abgelegten Einträgen (409 `stapel_offen`, solange er
   jünger als die Freigabe ist); danach bleiben dessen abgelegte Einträge als `frueher` im Teil.
5. `vorbereiten` prüft `max_mb` je Eintrag (413 `zu_gross`) und drosselt vor der Anmeldungs-Bestätigung.
6. Ein Wortschatz für das Layout im Teil (`ordner`/`flach`); totes `timeout` in `mcp_ablage` weg;
   `umwandlung.py` schreibt und löscht über `asyncio.to_thread`.
7. M1 Backend: `ablauf_auftrag_pruefen` mit `automatisch: true` schließt keine offene Frage (und lässt eine
   Schreib-Abnahme stehen) — wie ein Hintergrund-Zug, aber mit gespeicherter Antwort.

Frontend
8. M1: das Abholen sendet `automatisch: true` und schließt im Widget keine fremden Fragen.
9. `ui_upload` zeigt eine laufende oder beendete Übertragung auch „nur lesen“ weiter (ohne Antwortknopf).
10. `modulAntworten` sendet nur für offene Blöcke; ein Befund für einen geschlossenen Block wird verworfen.
11. Datenschutz-Satz, wenn das Übertragen angeboten ist; Datei-Eingaben einmal bauen; Ansagen nur an
    Meilensteinen, `role="alert"` nur beim Wechsel; ruhiger Balken bei reduzierter Bewegung (beide Module).
12. `nachladen.ts` prüft gegen die aufgelöste Modul-Basis; Ladetext und Rückfallname über Texte; Text-Typen
    erzwingen DE/EN-Gleichheit; Doku der Host-Brücke ohne „Sicherheitsgrenze“.
13. E2E: `ui_upload` und `ui_fortschritt` zugleich (Abholen während einer Übertragung).

## Q2 — Abläufe (M4, M5, M7 + Ablauf-MINOR/NIT)

1. M4: Wendung → volle Sicherheitsprüfung (`sicherheits_text`), Test mit langer Nachricht.
2. M5: frühe Antworten (`nur_text`) schreiben die Entities fest; Verweis in „unbekannt“-Zweigen auffrischen.
3. M7: `verbindung_freigeben` vor jedem Netzaufruf in `fortsetzen`, `weiter_nach_ki`, `pruefen`, `wartet_auf`.
4. `pruefen`: endgültige Gründe (`unbekannt`, `aus`) wie ein Fehlschlag, `abgewiesen` Hinweis ohne Knopf.
5. Ein neuer Lauf schließt den Auftrag des alten; Wendung nur mit erfüllten Voraussetzungen.
6. `fassung` ohne `None`-Vorgaben (einmaliger Wechsel, Deploy-Notiz); Längengrenzen für `titel`/`wann`/
   `nicht_wann`; geparster Katalog je Speicherstand; `wartet_auf` schreibt erst hinter dem Tor;
   `MAX_AUSGABE_BYTES` zählt Bytes.
7. Tests: `ablauf_auftrag_pruefen` durch den Preflight, zwei Sitzungen, Wendung ohne Voraussetzung.

## Q3 — Vorgang (M6 + Vorgang-/Datenschutz-MINOR/NIT)

1. M6: Start auf einem Vorgang mit beendetem oder fremdem Lauf → alter Vorgang `fertig`, neuer Vorgang;
   Direktaktion „neues Vorhaben“ (schließt den aktiven Vorgang). Nach Review Q3 geändert: ein Lauf, der
   `fertig` endet, schließt seinen Vorgang **nicht** mehr selbst (der Entwurf bliebe sonst unerreichbar).
2. Verweis einmal je Zug aus der DB auffrischen (Frist, Teile, Lauf); `uebernehmen` meldet Erfolg.
3. `$teil`-Werte höchstens 64 KB; Historie nur für `draft`; Löschweg „Arbeitsstand löschen“; Teil `document`
   geht mit dem Dokument (Löschen und 24-h-Verfall).
4. Migration 0020: Index `vorgaenge.session_id`, Präfix-Suche für anonyme Vorgänge, Indexname angleichen.
5. Plan §2 an den Bau angleichen.

## Q4 — Rest

1. Moderation der Abschnittstexte vor Ebene 2 (je Abschnitt gemerkt).
2. Ordner-Brücke merkt ihren Entwurf (kein Rückgriff auf einen alten `draft`).
3. Dateien über 300 Zeilen teilen (`pruefung`, `treiber`, `arbeitsstand`, `strukturentwurf_dienst`,
   `preflight`, `ui-upload.element.ts`) — verhaltensgleich.
4. Postgres-Integrationstests für Ablauf, Auftrag und Ablage (echter Vorgang, Konflikt, Zug mitten im Stapel).
5. Schon vorher da: `widget.py` liefert nur das Bündel mit passendem Digest (sonst 404); `rag/umwandeln.py`
   loggt keinen Ausnahmetext. Nicht in diesem Plan (eigene Entscheide): markitdown-Update/`pip-audit`,
   Multipart vor den Prüfungen (Starlette), Text in 429-`detail`, `_`-Entities des Klassifikators.

## Stand

- **Q1** (Upload und Abholen: M1, M2, M3, Upload-MINOR) — fertig, reviewt, Befunde behoben
  (`aenderungen/2026-11-06-paket-q1-upload-und-abholen.md`).
- **Q2** (Abläufe: M4, M5, M7, Ablauf-MINOR) — fertig, reviewt, Befunde behoben
  (`aenderungen/2026-11-06-paket-q2-ablaeufe.md`).
- **Q3** (Vorgang: M6, Datenschutz) — fertig, zwei Review-Runden (4 MAJOR, dann 1 MAJOR: Savepoint-Freigabe),
  Befunde behoben; M6 umgestellt auf „der nächste Start schließt“ (`aenderungen/2026-11-06-paket-q3-vorgang.md`).
- **Q4** (Rest) — fertig, reviewt, Befunde behoben bis auf einen begründeten (Bestands-Brücke)
  (`aenderungen/2026-11-06-paket-q4-rest.md`).
- Backend-Suite voll grün nach jedem Paket; Frontend ui-module 300, E2E Upload/Fortschritt/Entwurf 21, Budget.
