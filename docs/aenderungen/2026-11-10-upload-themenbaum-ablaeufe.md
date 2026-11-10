# Upload 2026-11-10: Themenbaum-Abläufe (Gruppen E, F, T)

Plan [`plans/2026-11-10-themenbaum-aus-inhalten.md`](../plans/2026-11-10-themenbaum-aus-inhalten.md).
Der Upload baut auf PR #51 (Abläufe im Studio, AS-0 … AS-8) auf. Er ist ein gestapelter PR: Erst
#51 mergen, dann diesen PR auf `main` umstellen und mergen.

## Was

| Commit (Paket) | Inhalt | Notiz |
|---|---|---|
| TB-E1 | Dokument-Besitz: Ein anonym gelesenes Dokument gehört nach Anmeldung und Ablage der Person (`ablage.fuer_aufrufer`). | `2026-11-10-paket-tb-e1-dokument-besitz.md` |
| TB-E2 | Proben der Studio-Vorschau zählen nicht im Betrieb: Spalte `sessions.vorschau` (Migration 0022), Scope `probe`, Widget-Attribut `vorschau`. | `…-tb-e2-vorschau-nicht-betrieb.md` |
| TB-E3 | Abläufe direkt starten (`modus: direkt` am Auslöser `agent`, `ui.direkt_start`). | `…-tb-e3-ablauf-direkt.md` |
| TB-E4 | Formeln im Widget: LaTeX → MathML (`ui/src/markdown/formel.ts`), Druck und Vorlesen; Budget +10 kB. | `…-tb-e4-formeln.md` |
| Querschnitt E | Review über E1–E4 (Klammern im Treiber als Entitäten, Formel-Regel im Master-Skill). | `2026-11-10-querschnitt-gruppe-e.md` |
| TB-F1 | Schreibende Flows: `X-Edu-User-Id` beim Start, Vermerk `repo_schreibt`, Rückfrage direkt davor. | `…-tb-f1-flow-identitaet.md` |
| TB-F2 | Ablauf-Werkzeug `metadaten_lesen` → Teil `metadaten`. | `…-tb-f2-metadaten-lesen.md` |
| TB-T1 | Wahl als Teil (`schreibt` an `nachricht`), `ui_strukturentwurf` mit `aus_inhalten`. | `…-tb-t1-antworten-und-inhalte.md` |
| TB-T2 | Seeds „Themenbaum · aus einem Thema“ und „Themenbaum · aus eigenen Inhalten“; „Themenbaum · aus Ordnern“ umbenannt. | `…-tb-t2-themenbaum-ablaeufe.md` |
| Querschnitt F/T | Frischer Vorgang für schreibende Abläufe, leere Auswahl startet keinen Auftrag, Textfläche für Schritttexte. | `2026-11-10-querschnitt-gruppe-ft.md` |
| Doku | Plan, offene Befunde, diese Notiz. | — |

Dateien, an denen mehrere Pakete arbeiteten, stehen im Commit ihres letzten Paketes.

## Prüfung vor dem Upload

- **Tests:**
  - Backend: breiter Satz 2768 grün.
  - Frontend: Studio 2144, ui 1415, widget 98, ui-module 348 grün.
- **Wächter:** ruff (ganzes `backend`), OpenAPI-Vertrag unverändert, `pip-audit --strict` ohne
  Befund, `npm run lint` und `check:*` samt `check:audit` sauber.
- **Chat-Smoke** (lokal, gpt-6-luna, Wegwerf-DB): „Themenbaum · aus einem Thema“ von der Wendung
  bis zum Entwurf.
- Die volle Suite läuft in der CI.

## Deploy

1. Migration **0022** (`alembic upgrade head`) einspielen.
2. Image neu bauen: Widget, Studio und Backend haben sich geändert. Danach im Browser hart neu
   laden.
3. `boerdi import-config --werksabgleich` ausführen. Das bringt die zwei neuen Seeds (aus) und
   den neuen Titel von `sammlungsstruktur`.
4. Für „Themenbaum · aus eigenen Inhalten“:
   - `B_API_JOBS_FLOWS` enthält `edusharing.chatbot/node-metadata-write`;
   - die b-api ist für Aufträge eingerichtet;
   - im Studio unter „Datei-Upload“ ist die Ablage in WLO an;
   - die Person ist bei WLO angemeldet.
5. Im Studio unter „Abläufe“ die gewünschten Abläufe einschalten.

## Offen

Siehe `offene-befunde-und-todo.md`, Abschnitt „Themenbaum aus Inhalten, Gruppen F/T“:

- das Limit je Job;
- `X-Edu-User-Id` bei der Abfrage;
- F7;
- die Staging-Probe;
- Sammlungen anlegen;
- der Start aus der Sammlungsseite;
- die Raster-Warnungen.
