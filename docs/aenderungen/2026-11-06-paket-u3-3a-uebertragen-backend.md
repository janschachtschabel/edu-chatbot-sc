# Paket U3-3a: Übertragen in den persönlichen Bereich — Backend (2026-11-06)

Plan: [`../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md),
Abschnitt „U3-3 angepasst“. Gegenstück im MCP-Server: MA-1…MA-5 (`wlo-mcp-server-sc`, CHANGELOG
2026-11-06, zwei Review-Runden).

## Was entsteht

Das Backend kann einen erfassten Ordner im Auftrag der angemeldeten Person **in ihren persönlichen Bereich
in WLO** übertragen. Das Modul `ui_upload` bekommt die Oberfläche dafür mit U3-3b; bis dahin gibt es nur die
Endpunkte. Kein Zug und keine KI dazwischen: die Person hat die Vorschau gesehen und „Jetzt übertragen“
gewählt.

1. `POST /api/ui/ablage/vorbereiten` (JSON: Ordnername, je Datei Titel, sha256, Größe, Art) gibt die
   **Vorschau des MCP-Servers** zurück — normalisierte Namen, Ordner oder flach — und einen
   Freigabe-Schlüssel für genau diese Liste. Die Vorschau wird Teil **`ablage`** (`wlo.ablage@1`) im
   Vorgang. Gespeichert wird nur ein Prüf-Kürzel des Schlüssels; der Schlüssel selbst bleibt im Widget.
2. `POST /api/ui/ablage/datei` (multipart: Schlüssel, Index, Datei) schickt die Bytes **als Strom** an
   `POST {MCP}/api/uploads` (nie mehr als ein Stück im Speicher) und legt die Datei als Eintrag `index` ab —
   **nacheinander**, eine Datei zur Zeit. Der Stand geht in den Teil. Ein endgültiger Stand (auch
   `failed`) wird ohne MCP-Aufruf zurückgegeben; ein Grund des MCP ohne Anlegen (`erneut`, `passt_nicht`,
   `neu_vorbereiten`) lässt den Eintrag offen; bleibt die Antwort aus, wird er `unverified` (die Datei KANN
   abgelegt sein) und der Code `zu_langsam`.
3. `POST /api/ui/ablage/abschluss` legt `vorgang.json` ab (baut der MCP-Server) und markiert den Teil als
   abgeschlossen.

**Bremsen** (alle vor jedem MCP-Aufruf):
- Sitzung und offene Frage von `ui_upload` (404/409);
- **bestätigte Anmeldung** (403 `nur_angemeldet`), MCP-Aufrufe nur mit dem Zugangsblock des **Zuges**, nie
  dem der Anlage;
- Studio-Schalter `ablage_in_wlo` (403 `aus`);
- Größe je Datei = `max_mb` des Studios (413);
- Index außerhalb (400), fremder Schlüssel (409 `fremder_stapel`);
- `vorbereiten` über die Fenster der Redaktion, die anderen über die IP-Drossel;
- Rumpf-Grenzen: Datei wie Dokument, JSON 256 KiB.

Fehler des MCP werden zu Codes (`kein_recht`, `abgewiesen`, `nicht_erreichbar`, `zu_gross`, `art`, `voll`,
`zu_langsam`), nie zu Servertext.

**Die KI** sieht nur den Kurztext des Teils („Ablage in WLO: 35 von 36 abgelegt, 1 mit Problem“). Die
Stapel-Werkzeuge stehen in **keinem** Werkzeug-Angebot: der Chatbot nimmt seine Werkzeuge aus festen
Listen. Ein Test pinnt das.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Backend | `services/ablage/mcp_ablage.py` (vorbereiten, datei_hochladen, datei_ablegen, abschliessen; Codes) |
| Backend | `services/ablage/vorgang_teil.py` (Teil `ablage`: aus Plan, mit Ergebnis, Kurztext, lesen/speichern) |
| Backend | `api/ui_ablage.py` (drei Endpunkte), `main.py` (Router), `api/body_limit.py` (Grenzen) |
| Backend | `arbeitsstand.teile_speichern` (verhaltensgleich aus `uebernehmen` gelöst: Teile ohne Modul-Antwort) |
| Doku | `docs/api/openapi-*.json` neu erzeugt |

## Tests

Neu:
- `test_ablage_mcp`: Plan des Servers, Fehler-Codes, ohne Anmeldung kein Aufruf, Strom mit dem Block der
  Person, Upload-Codes, Ablegen/Abschluss, keine Stapel-Werkzeuge im KI-Angebot.
- `test_ui_ablage_api`: Vorschau und Teil (ohne Schlüssel), Abweisungen vor jedem MCP-Aufruf, MCP-Fehler als
  Code, Strom und Stand, Index zweimal, unpassende Dateien, Abschluss.

Läufe nach den Review-Fixes: Backend 8498 grün; MCP-Server 2363 grün; ruff sauber.

## Offen

- T5 (Rahmen `[ABLAGE DER PERSON …]` in der Antwort des Moduls) und T1b (Dienst „letzte Ablagen nach der
  Anmeldung“) kommen mit U3-3b; die KI sieht bis dahin den Kurztext des Teils in der Kennzeile.

- U3-3b: die Oberfläche in `ui_upload` (Hashen, Vorschau, Übertragen, Ergebnis). Danach schaltet
  `dienst_upload.schalter` `ablage_in_wlo` frei, und der Studio-Hinweis „Noch ohne Wirkung“ wird
  angepasst.
- Live erst nach MA-0 (Messung mit Testkonto) und nach der Verdrahtung `registerCurationBatchTools` in
  `wlo-mcp-server-sc/src/server.ts` (Nutzerdatei).

## Review U3-3a (2026-11-06, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 3 MAJOR, 7 MINOR, 2 NIT. Geprüft und in Ordnung: Reihenfolge der Anmeldeprüfung, nur der
Block des Zuges, `Authorization`/`X-Upload-Name` sauber, Prüf-Kürzel + Besitzprüfung des MCP gegen fremde
Schlüssel, Logs ohne Inhalt.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Ein `failed` wurde erneut hochgeladen, das MCP antwortete „schon behandelt“ und ließ den Platz liegen (30 min Speicher) | `failed` ist endgültig (kein zweiter Versand); im MCP nimmt der Stapel-Aufruf den Platz **zuerst** und verwirft ihn auf jedem Weg | `test_ein_endgueltiger_fehlschlag_wird_nicht_noch_einmal_geschickt` |
| 2 | MAJOR | `structuredContent` einer Ablehnung ging verloren (alles „abgewiesen“), Zeitüberschreitung ohne Stand | `transport.call_tool` reicht ihn bei `isError` mit; Gründe → Codes (`erneut`, `passt_nicht`, `neu_vorbereiten`, `nichts_abgelegt`); keine Antwort → `unverified` + `zu_langsam` | `test_eine_ablehnung_mit_grund_kommt_als_ergebnis`, `test_ein_grund_des_mcp_laesst_den_eintrag_offen`, `test_keine_antwort_beim_ablegen_ist_unklar`, `test_eine_zeitueberschreitung_beim_hochladen` |
| 3 | MAJOR | Entities der Sitzung wurden über Sekunden hinweg veraltet zurückgeschrieben | nur der Verweis, auf frisch gelesenem Stand (`_verweis_zurueckschreiben`) | (über alle Endpunkt-Tests) |
| 4 | MINOR | Rückgabe von `speichern` ignoriert | `vorbereiten` → 503 `nicht_gespeichert`; sonst Warnung | `test_ohne_gespeicherten_teil_kein_schluessel` |
| 5 | MINOR | Stand auf veraltetem Teil geschrieben | Stand auf frisch gelesenem Teil; Vertrag „nacheinander“ | — |
| 6 | MINOR | 429 `too_many_logins` als „voll“ gemeldet | eigener Code `anmeldungen` + Warnung (`AUTH_CREDENTIAL_LIMIT`) | `test_zu_viele_anmeldungen_ist_kein_voll` |
| 7 | MINOR | Wurzel des MCP an der Einstellung vorbei | `transport.resolve_mcp_url()` | `test_die_wurzel_folgt_dem_werkzeug_weg` |
| 8 | MINOR | Größe nicht gegen die Vorschau geprüft; Rumpf vor der Anmeldeprüfung auf Platte | 400 `groesse` vor dem Versand; Rumpf-Puffer wie beim Dokument (bewusst gelassen) | `test_eine_andere_groesse_geht_gar_nicht_erst_hin` |
| 9 | MINOR | Testlücken (Fehlschlag, Zeitüberschreitung, `speichern`, Abschluss ohne Datei, Logs, Rumpf-Grenzen) | ergänzt | `test_abschluss_ohne_abgelegte_datei`, `test_logs_ohne_dateinamen`, `test_die_grenzen_der_pfade` |
| 10 | MINOR | Notiz ungenau; T5/T1b nicht genannt | berichtigt, unter „Offen“ | — |
| 11 | NIT | `ordner_verweigert`/`bereits` ungenau | eigenes Feld im Teil; `already` des MCP durchgereicht | — |
| 12 | NIT | doppelte Prüfung, privater Import | doppelte Prüfung entfernt; privater Getter bleibt (wie `anmeldung.py`) | — |
| — | Wächter | i18n-Katalog, OpenAPI-Zusätze, Routen-Inventar, öffentliche Routen | Codes als einsprachig eingetragen, drei Zusätze dokumentiert, Inventar ergänzt | `test_i18n_messages`, `test_openapi_*` |
