# Restpakete: Abläufe, Kestra-Aufträge, UI-Module (2026-11-12)

Auftrag (Nutzer, 12.11.): selbstständig weiterarbeiten, bis alle offenen Pakete rund um die Abläufe,
die Ansteuerung von Kestra-Flows und die UI-Widgets abgeschlossen sind. Vorgehen wie bisher:
Umsetzung mit den Coding-Skills, Review mit Befundbehebung, zweites Review bei vielen Befunden oder
nach mehreren zusammenhängenden Paketen, Durchtest zur Verifikation.

Quelle der Liste: `offene-befunde-und-todo.md` und die Pläne vom 02.11. bis 12.11. (Sichtung 12.11.,
jeder Punkt im Code gegengeprüft).

## 1 Was hier nicht gebaut wird, und warum

- **Externe Stellen** (B-API/Kestra-Team F3–F10, AS-6, AS-T `umwandeln`, `ablage_zuordnen`, T4
  Benachrichtigung, MCP-Byte-Werkzeug, `WLO_BATCH_UPLOAD_ENABLED`/MA-0): ohne Antwort bzw.
  Gegenstelle nicht baubar. Bleiben in `offene-befunde` §3/§6.
- **Läufe des Nutzers** (Golden GV-UI-8…16, Eval mit/ohne UI-Module, `includeContentCounts`,
  Staging-Probe „aus eigenen Inhalten“ mit Anmeldung): startet der Nutzer.
- **TB-3 Schritt 6 „Sammlungen aus dem Entwurf anlegen“** und die daran hängenden Fragen L1–L4,
  L6–L10: Nutzer-Entscheid N15 („noch nicht“). Bleibt zurückgestellt.

## 2 Entscheide (selbst getroffen, Auftrag „offene Entscheide selbst treffen“)

| Nr. | Frage | Entscheid | Grund |
|---|---|---|---|
| R-E1 | Löschen aus einem Ablauf erlauben? | Nein, bleibt gesperrt. | Unumkehrbar; kein Seed braucht es; die KI im Chat kann es mit Rückfrage. |
| R-E2 | „Arbeitsstand löschen“ außerhalb eines Ablaufs? | Kein weiterer Einstieg. | „Meine Vorgänge“ (AS-Ud) und die Ablauf-Leiste decken es ab. |
| R-E3 | Moderation `closed` sperrt Steuer-Aktionen? | Steuer-Aktionen ohne Text der Person laufen durch (Liste im Code). | „Stand prüfen“/„Abbrechen“ tragen nichts, was zu moderieren wäre; sonst sitzt die Person fest. |
| R-E4 | `/api/ui/*` kennt die Moderations-Sperre nicht | Gewollt, so lassen. | Keine Chat-Züge; Text dort geht nicht an das Modell. |
| R-E5 | `browse_collection_tree` in Vorlagen auf `ui_themenbaum` umstellen? | Ja, in den Vorlagen `vorgehen.md`/`vorgehen-kompakt.md`, mit Rückfall „ohne UI-Module“. | Einheitlich mit der live genutzten Kurzfassung. |
| R-E6 | Textfassung für später abgeschaltete Module im Verlauf? | Nein. | Der Verlauf zeigt, was die Person sah. |
| R-E7 | Nachgeladene Themenbaum-Zweige speichern (H-8)? | Nein. | Schreibweg ohne Zug; Neuladen zeigt den Ursprung, Aufklappen geht erneut. |
| R-E8 | Beispiel-Abläufe der UI-Module im Studio? | Nein, Kommandozeile reicht. | Sonst bräche die Vergleichbarkeit der Gold-Läufe. |
| R-E9 | `ui_befund`, `ui_themenbaum_auswahl` | Nicht freigeben. | Kein Bedarf aus einem Ablauf heraus. |
| R-E10 | `ui_upload`-Konzept (U1, §13) | Gilt als umgesetzt durch U2–U5, TB-E1, TW. Virenprüfung/OCR: nein. | Kein Speichern roher Dateien außer der Ablage in WLO. |
| R-E11 | TB-4 Raster (L5) | Nur als Warnung im Entwurf, nie als Sperre. | Ein Baum darf vom Raster abweichen. |
| R-E12 | `X-Edu-User-Id` bei Abfrage, Abbruch, Datei | Mitsenden, wenn die Person angemeldet ist. | Gleiche Identität für denselben Job; eine fehlende Kennung wäre das größere Risiko (400 → „Stand prüfen“ ohne Ende). |
| R-E13 | Limit je Job (N14) | Feld `hoechstens_je_auftrag` am Schritt `auftrag` (Vorgabe leer = alles in einem Job); mehr IDs → Teilaufträge nacheinander. | Grenze der B-API (20 Jobs je Schlüssel) schonen; nacheinander ist einfacher als parallel. |
| R-E14 | `language: de` im Seed | Platzhalter für die Sprache der Person. | Englischsprachige Personen bekämen sonst deutsche Metadaten. |

## 3 Pakete

Je Paket: Schritt 0 `/better-coding-workflow` (bei UI dazu `/better-coding-frontend`), Tests zuerst,
Review mit Befundbehebung, Änderungsnotiz unter `docs/aenderungen/`.

### R1 Kestra-Aufträge
- R1-a Limit je Job (R-E13).
- R1-b Sprache der Person als Flow-Eingabe (R-E14).
- R1-c `X-Edu-User-Id` bei Abfrage, Abbruch und Datei (R-E12).
- R1-d `ui_auftrag._wartender_auftrag` frischt den Verweis auf.
- R1-e `ui_fortschritt`: 403 `abgewiesen` eigener Text, nicht „nicht angemeldet“.

### R2 Abläufe
- R2-a Studio-Liste zeigt `direkt` am Auslöser `agent`.
- R2-b Voraussetzung `dokument_lesen` (Dokument im Chat für die Person erlaubt).
- R2-c Kennzeichen `ablauf_unbestimmt`, das Widget pingt einmal nach.
- R2-d Anonym begonnener Vorgang geht nach der Anmeldung auf die Person über (wie TB-E1).
- R2-e Deckel der Schnellantworten schützt alle System-Knöpfe (`__action__`).
- R2-f Ein „ja“ zur Freigabe speichert eine Assistenten-Nachricht.
- R2-g Moderation `closed`: Steuer-Aktionen laufen durch (R-E3).
- R2-h Verklemmung Verdrängen/Sperre und `Teil` doppelt.

### R3 UI-Module und Widget
- R3-a „Inhalte anzeigen“ prüft das Angebot (`angebotene_mcp_werkzeuge`).
- R3-b `ui_upload` nennt die Anmeldung gleich unter dem Hinweis, wenn Lesen nur für Angemeldete gilt.
- R3-c `ui_strukturabgleich`: Lücken der Ebene 2 nennen den Elternpunkt.
- R3-d `ui_themenbaum`: lange Titel, kein „Erneut laden“ bei 404/422.
- R3-e `ui_upload`: „Vorgang herunterladen“; keine doppelte Ablage nach abgelaufener Freigabe.
- R3-f Widget `runCardAction`: `setLoading(false)` bei gewechselter Sitzung.
- R3-g Studio-Reste U1 (Fokus nach Speichern, Probelauf meldet Module, `eval-compare`).
- R3-h Vorlagen auf `ui_themenbaum` (R-E5).

### R4 Strukturprüfung (TB-4, R-E11)
- Warnungen im Strukturentwurf: Tiefe, Breite, Einzelkinder, doppelte Titel.

### R5 Doku
- In `offene-befunde` veraltete Punkte streichen (V-4 Frist, Job-IDs vor der Kaskade, `freigabe` an
  `auftrag`, AS-5c).

Nach R1+R2 und nach R3+R4 je ein Querschnitts-Review; am Ende Durchtest im Chat (Wegwerf-DB).
