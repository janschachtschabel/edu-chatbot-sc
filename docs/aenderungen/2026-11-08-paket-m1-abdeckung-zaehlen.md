# Paket M1 — Trefferzahlen je Gliederungspunkt (2026-11-08)

Plan: [`plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`](../plans/2026-11-08-pakete-m1-u4-u5-u3-5.md), E-1/E-2.

## Was sich ändert

Der Chatbot kann jetzt ohne Sprachmodell zählen, wie viele WLO-Inhalte es zu den Punkten einer Gliederung gibt.
Er nutzt dafür `count_wlo_content_matches` (MCP, lesend, seit Paket M4). Grundlage für U5 (Lücken im Abgleich).

- **Punkte:** die Ebenen 1 und 2 eines Strukturentwurfs (`wlo.sammlungsstruktur@1`), höchstens 60.
  - Nur mit Kennung und Titel; eine doppelte Kennung zählt einmal.
  - Gesucht wird nach dem Titel und bis zu zwei Schlagwörtern.
- **Filter je Punkt:** Fach und Bildungsstufe vom Punkt, sonst vom Elternpunkt, sonst vom Entwurf.
  - Die Bildungsstufe nur als WLO-Label; das Fach ist ein kurzes Label, ob WLO es kennt, sagt erst der Server.
  - Ein nicht auflösbarer Filter steht als `unresolved_filter` beim Punkt, ein geratener (`fuzzyFilters`) als
    `geraten`.
  - Kennt WLO das Fach des ganzen Entwurfs nicht, sagt das `filter_unaufgeloest`.
- **Zählen:**
  - in Bündeln zu 30 Anfragen, ohne Cache, denn nur so trägt die Antwort ihren strukturierten Teil;
  - ein Bündel ohne Antwort setzt seine Punkte auf `keine_antwort`; nach keiner Antwort, „ausgelastet“ oder
    einer Abweisung bleibt auch der Rest ungezählt, ohne zweiten Aufruf;
  - was der Server meldet (`missing`), wird zum Code aus seiner festen Liste, nie zu seinem Text;
  - die besten zwei Treffer je Punkt mit Kennung, Titel und, nur wenn sicher, Adresse (http(s), höchstens
    300 Zeichen, ohne Leer- oder Steuerzeichen). Zu lange Kennungen und Adressen fallen weg.
- **Lücke:** höchstens 2 Treffer (`LUECKE_BIS`).
- **Ablauf-Dienst `abdeckung_zaehlen`:** `argumente: {entwurf: {$teil: draft}}` liefert
  `{punkte: [{id, titel, ebene, total, top, luecke} | {…, fehlt}], gezaehlt, luecken}`.
- Die Zahlen gelten für **ganz WLO**, nicht für eine Sammlung.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 3 hoch, 5 klein, 3 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Logzeile mit `antwort.code` (Log-Wächter rot, Servertext ungekürzt). | Grund vorher gekürzt; dasselbe im Abgleich (U4). |
| Ein kaputter Entwurf (Knoten kein Objekt, `kinder` kein Array, sehr tief) warf eine Ausnahme; der Lauf brach ab statt `bei_fehler`. | Eigene, tiefenbegrenzte Iteration über nur gültige Knoten. |
| Es galten nur Fach und Bildungsstufe der Wurzel; ein Physik-Punkt unter einer Mathematik-Wurzel wurde falsch gezählt. | Filter je Punkt, geerbt. |
| „Nur gültige Labels“ stimmte fürs Fach nicht; ein unbekanntes Fach sah aus wie eine sichere Zählung. | Doku korrigiert; `geraten` je Punkt, `filter_unaufgeloest` für den Entwurf. |
| Nach einem Ausfall lief das zweite Bündel trotzdem (bis 120 s). | Abbruch nach keiner Antwort, „ausgelastet“, Abweisung. |
| Die Sperre bei persönlichen Daten griff über den Ablauf-Dienst nicht. | `werkzeuge.DIENST_MCP`; der Treiber prüft auch die MCP-Werkzeuge eines Dienstes. |
| `code` ungeprüft; `total` als `true` zählte. | Feste Liste der Codes; nur echte Ganzzahlen. |
| Kennung, Titel, Schlagwörter ungeprüft; Kennungen und Adressen gekürzt. | Kennung nach dem Muster des Entwurfs, nur Text; zu lange fallen weg, Adressen höchstens 300 Zeichen. |
| `LUECKE_AB`/`LUECKE_BIS` uneinheitlich. | `LUECKE_BIS` = 2 überall. |
| Testlücken | Tests für alle Punkte oben, über das echte Argument-Modell und im Treiber. |

## Geändert

- neu `backend/src/boerdi/services/abdeckung.py`.
- `services/ablauf/werkzeuge.py`: Dienst `abdeckung_zaehlen`, `DIENST_MCP`.
- `services/ablauf/treiber.py`: ein Dienst ist gesperrt, wenn eines seiner MCP-Werkzeuge gesperrt ist.

## Tests

- neu `backend/tests/test_abdeckung_m1.py`: Punkte (Ebenen, Deckel, ohne Titel, doppelt), Filter, Bündel zu 30
  ohne Cache, Bündel ohne Antwort, `missing` als Code, ohne strukturierten Teil, Ablauf-Dienst.

## Betrieb

Keine Migration, kein Seed geändert.
