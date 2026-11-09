# Paket U3-5 — Abschluss der Upload- und Abgleich-Strecke (2026-11-08)

Plan: [`plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md)
§9 „U3-5 Abschluss“ und [`plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`](../plans/2026-11-08-pakete-m1-u4-u5-u3-5.md) E-9.

## Was sich ändert

- **Master-Skill** (`docs/skills/vorgehen-knapp.md`, Abschnitt „Oberfläche ansteuern“):
  - **Ordner oder Lehrplan** als Grundlage führt zu `ui_upload` (`zweck: sammlungsstruktur`). Danach arbeitet die
    KI nur mit dem Befund. Übertragen geht nur per Klick im Modul; ohne Anmeldung sagt sie, dass Übertragen eine
    braucht. Ohne eigene Dateien bleibt es `ui_strukturentwurf`.
  - **Abgleich** führt zu `ui_strukturabgleich` mit der `nodeId` der Sammlung. Wird nach fehlendem Material
    gefragt, setzt die KI `abdeckung: true`. Sie nennt nur Zahlen, Lücken als „in ganz WLO“. Ohne Entwurf kommt
    erst `ui_strukturentwurf`.
  - „Nicht angeboten“: Fehlt der Abgleich, belegt die KI Lücken mit M19 (`count_wlo_content_matches`).
  - M08 verweist bei eigenen Dateien auf `ui_upload`, M19 bei Lücken eines Entwurfs auf `ui_strukturabgleich`.
  - **Den Master-Skill überträgt der Nutzer in den WLO-Knoten.**
- **Gold-Abläufe** (`evals/ui-module-flows.yaml`):
  - GV-UI-13 Ordner mit Materialien → `ui_upload`;
  - GV-UI-14 Lehrplan → `ui_upload`;
  - GV-UI-15 Gegenprobe ohne Dateien → `ui_strukturentwurf`, kein `ui_upload`;
  - GV-UI-16 Entwurf, übernehmen, Abgleich mit Lücken → `ui_strukturabgleich`.
- **Werkzeugbeschreibungen:**
  - `ui_upload` „Wann“ nennt jetzt auch den Lehrplan;
  - `ui_strukturentwurf` „nicht wann“: eigene Dateien zuerst `ui_upload`;
  - `ui_themenbaum` „nicht wann“: Abgleich und Lücken eines Entwurfs über `ui_strukturabgleich`.
- **Quittung von `ui_upload`:** sagt der KI, was im Auswahlfeld nicht geht (Dokument lesen, Übertragen),
  samt fehlender Anmeldung.
- **Doku:**
  - `architektur.md`: der Weg der Bytes (Erfassen im Browser, Strukturdokument, Übertragen, Abgleich ohne LLM);
  - `edu-sharing-einbindung.md` §2: Nachladen vom selben Ursprung mit SRI, CSP-Hinweis. Dort stand noch „kein
    Nachladen“;
  - `ui-module.md`: Tabelle (`ui_strukturabgleich`), §4.2 `dienst.braucht`.
- **Bündel gemessen** (`npm run budget`): `ui-strukturabgleich` 3,6 kB gzip, `ui-upload` 18,0 kB,
  `ui-fortschritt` 4,0 kB; zusammen 25,9 kB von 60 kB (nach dem Gesamt-Review).

## Gesamt-Review U3 · M1 · U4 · U5 · U3-5 (2026-11-08)

Ein frischer Reviewer über die ganze Strecke: 0 kritisch, 0 hoch, 7 klein, 3 Kleinigkeiten. Die Datenformen
an den Nahtstellen passen zusammen. Behoben:

| Befund | Behebung |
|---|---|
| Brach der Zug während des Lesens der Sammlung ab, lief die Zählung verwaist weiter. | `try/finally` bricht sie ab. |
| Eine kaputte Antwort der Zählung (Kennung als Liste, Filter als Objekt) kippte den ganzen Zug. | Jeder Eintrag erst geprüft; eine Ausnahme der Zählung lässt den Abgleich stehen (`fehler`). |
| Regeln zu Abgleich und Lücken widersprachen sich (M19, `ui_themenbaum`, „nicht angeboten“). | M19 verweist auf `ui_strukturabgleich`; `ui_themenbaum` nennt ihn unter NICHT; ohne Modul belegt die KI mit M19. |
| Upload oder Entwurf war nur an einer Stelle geregelt. | M08 und die Manifeste (`ui_upload` Wann: Lehrplan; `ui_strukturentwurf` NICHT: eigene Dateien). |
| Die KI wusste nicht, was im Auswahlfeld geht. | Die Quittung nennt, was nicht geht (Dokument lesen, Übertragen) und ob die Anmeldung fehlt. |
| Ordnernamen konnten persönliche Daten als Suche an WLO tragen. | Punkte mit E-Mail, Telefon, IBAN oder dem PII-Muster der Sicherheitsprüfung (`regex_gate.enthaelt_persoenliches`) gehen nicht in die Suche (`persoenlich`). Namen erkennt das nicht (Rest-Risiko). |
| Im Muster-Weg hieß eine Zählung ohne das Werkzeug in `tools:` „gesperrt“. | Neutraler Satz „nicht angeboten“; die Regel steht in `ui-module.md` §4.2. |
| `architektur.md`: ein Satz war beim Einfügen verrutscht; die Frist des Dokuments stimmte nicht. | Zurückgestellt; „bis 24 Stunden nach der letzten Nutzung“. |
| Doku hinter dem Code (Tabelle, §4.2, README, Trusted Types). | Nachgezogen. |
| Veralteter Docstring in `tool_loop_module.py`. | Korrigiert. |

## Tests

- `backend/tests/test_master_skill_vorlage.py`: Wächter für beide Regeln und den Satz unter „Nicht angeboten“.
- `backend/tests/test_golden_ui_module_flows.py`: GV-UI-1 bis 16.
- aus dem Gesamt-Review: `test_strukturabgleich_u4.py` (verwaiste Zählung, kaputte Antwort, persönliche Daten), `test_kleine_punkte_k2d.py` (Quittung von `ui_upload`), `test_master_skill_vorlage.py` (M08, M19).
- Gesamtlauf nach dem Gesamt-Review: Backend 9097 grün (5 übersprungen), ruff sauber; Frontend ui-module 322, studio 2045, ui 1215, widget 76; Register aktuell, Tokens, Radien und eslint sauber.

## Betrieb

- Master-Skill in den WLO-Knoten übertragen (Nutzer), dann Golden-Lauf
  `run_golden.py --flows ../evals/ui-module-flows.yaml --engine agent --only GV-UI-13,GV-UI-14,GV-UI-15,GV-UI-16`
  (startet der Nutzer).
