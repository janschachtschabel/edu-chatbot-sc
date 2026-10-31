# Paket 20 — Aufräumen aus §5 der Befundliste (2026-10-31)

Auftrag (Nutzer, 2026-10-31): „wie vorgeschlagen vorgehen — wichtigsten Dinge planen und umsetzen
und Rest als offene Todo vermerken“. Umgesetzt werden die Gruppen 1 (kleine echte Mängel) und 2
(technische Schwachstellen) aus `docs/offene-befunde-und-todo.md` §5; Gruppen 3 und 4 bleiben dort
stehen und laufen mit, wenn die Dateien ohnehin angefasst werden.

## Umfang

| Nr. | Befund (§5) | Änderung | Prüfung |
|---|---|---|---|
| A1 | `clear_quality_logs`: `scope=production` zählt als Filter und umgeht `confirm` — löscht fast die ganze Tabelle; die Rückfrage im Studio nennt den Umfang nicht | Nur echte Einschränkungen (Sitzung, Muster, Intent) befreien von `confirm`; Umfang und Maschine allein brauchen es. Studio schickt `confirm` genau dann; die Rückfrage nennt den Umfang | Backend-Test je Fall, Studio-Spezifikation |
| A2 | `data.page` und `data.debug.context.page` halten den Pfad der Gastseite 180 Tage, samt Query | `log_quality_event` speichert die Adresse ohne Query und Anker (beide Stellen), ohne den Debug-Block des Zugs zu verändern | Backend-Test |
| A3 | „Trotzdem speichern“ ohne Version schreibt bedingungslos | Einziger echter Fall: MCP-Server-Liste (`version === null` → kein Bedingungsfeld). Jetzt `create: true` (wie `saveCondition`), Backend nimmt `create` an | Backend- und Studio-Test |
| B1 | Blockierendes `getaddrinfo` in der Restore-Prüfung | Die Prüfungen mit Namensauflösung laufen in async-Endpunkten per `asyncio.to_thread` | Test: Prüfung läuft nicht im Loop-Thread |
| B2 | Master-Skill: Erstabruf nicht gebündelt | Ein laufender Erstabruf je Kennung wird geteilt (Single-Flight, `asyncio.shield`) | Test: N gleichzeitige Züge → 1 Abruf |
| B3 | Zeitabhängiger Test `test_aufbewahrung_takt` | Wartet auf die Bedingung (zweiter Lauf) statt fest 50 ms | Test selbst |

## Bewusst nicht in diesem Paket (bleibt in §5)

- Klassifikator liest im Fehlerpfad nur `choices[0]` — Restrisiko, nie beobachtet.
- E2E-Kippler `auth-button.spec.ts` (Tab-Reihenfolge) unter Parallellast — erst nachstellen (siehe
  Vorgehen in der Befundliste), dann ändern.
- Gruppe 3 (Dateien über 300 Zeilen, fest deutsche Reiter-Namen, Einstellungen ohne Leser) und
  Gruppe 4 (Kosmetik): beim nächsten Anfassen der Dateien.

## Log

- 2026-10-31: A1–A3, B1–B3 umgesetzt, je mit Test. Änderungsnotiz
  [`aenderungen/2026-10-31-paket-20.md`](../aenderungen/2026-10-31-paket-20.md).
- Prüfung:
  - Backend: `7376 passed, 2 skipped` (18:39 min), ruff sauber; `docs/api/openapi-v1.json` neu erzeugt — einziger Unterschied ist das Feld `create` in `McpServerUpdate`
  - Studio: 1850/1850 (im ersten vollen Lauf kippte einmal `agent-tools.component.spec.ts` „verweist bei Policy-Sperren …“ — einzeln 3× grün, zweiter voller Lauf grün; der Test berührt keine Änderung dieses Pakets, vermerkt in §5), Lint und `check:tokens|a11y|contrast|radii|docs|audit` sauber, `ng build studio` fehlerfrei
  - Neue Tests: A1 (Router + Studio-Dienst + Ansicht), A2 (`test_quality_events_pg`), A3 (Router + Registry-Ansicht), B1 (zwei Off-Loop-Tests), B2 (fünf gleichzeitige Erstzüge → ein Abruf, ein abgebrochener Zug), B3 (Test selbst)
  - Widget und ui unverändert, kein E2E-Lauf nötig
- Befundliste §5 nachgezogen (erledigte Punkte durchgestrichen mit Verweis, E2E-Kippler und der
  Studio-Kippler neu eingetragen).
- 2026-10-31: unabhängiger Review — 0 hoch, 0 mittel, 9 niedrig, alle behoben (Tabelle in der
  Änderungsnotiz). Nachprüfung: Backend-Gruppen 833 grün, Studio 1851/1851, Lint, Build.
