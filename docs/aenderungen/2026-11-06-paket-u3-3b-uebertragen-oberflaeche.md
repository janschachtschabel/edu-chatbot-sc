# Paket U3-3b: Übertragen in den persönlichen Bereich — Oberfläche (2026-11-06)

Plan: [`../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md),
Abschnitte „U3-3 Übertragen“ (T5–T8) und „U3-3 angepasst“. Baut auf U3-3a
([Backend](2026-11-06-paket-u3-3a-uebertragen-backend.md)) auf.

## Was entsteht

Das Modul `ui_upload` kann die erfassten Dateien **per Klick** in den persönlichen Bereich der
angemeldeten Person in WLO übertragen. Kein Zug und keine KI dazwischen; die KI erfährt danach nur Zahlen.

1. **Angebot** unter dem Ordnerbaum — nur, wenn das System es im Block erlaubt
   (`schalter.ablage_in_wlo` = Studio-Schalter **und** bestätigte Anmeldung). Es nennt, wie viele
   Dateien gehen und was nicht (Art, die WLO nicht annimmt; größer als `grenzen.max_mb_ablage`), höchstens
   200 je Freigabe. Übertragen werden nicht ignorierte Dateien bekannter Art.
2. **Prüfen** im Browser: SHA-256 je Datei (k von n, Fortschrittsbalken), dann `vorbereiten`. Die
   Freigabe trägt je Datei nur Titel, Prüfsumme, Größe und Art — keine Pfade.
3. **Vorschau** mit dem Ziel (neuer Ordner „…“ oder flach), Umfang und den Namen des Servers;
   „Jetzt übertragen“ oder „Abbrechen“ (nichts wird gesendet; die Freigabe verfällt im MCP).
4. **Senden**, eine Datei zur Zeit, mit Fortschritt. „Nach dieser Datei anhalten“ wirkt nach der
   laufenden Datei (eine halb gesendete abzubrechen ließe offen, ob sie ankam). Ein Fehler einer Datei
   (`passt_nicht`, `zu_langsam` …) lässt die anderen weiterlaufen; ein Fehler des Stapels (Anmeldung,
   Schalter, abgelaufene Freigabe, Netz) hält an — der Rest steht als „nicht gesendet“ da.
5. **Ergebnisliste**: je Datei Stand als Text **und** Symbol (✓ abgelegt, ? unklar, ✗ nicht abgelegt
   samt Grund, – nicht gesendet), ein Link „… in WLO ansehen“ je Knoten. Den Link baut das Backend
   (`render_url`), das Modul reicht ihn durch `host.link` (Sitzungs-Kennung, Hinweis bei fremden
   Seiten). „Nicht übertragene noch einmal senden“ schickt nur, was ein neuer Versuch heilen kann.
6. **Abschluss**: `vorgang.json` wird abgelegt, sobald nichts mehr nachzusenden ist (sonst vor dem
   Weiter im Chat). Die Antwort `aktion: "uebertragen"` mit `ablage{layout, gesamt, abgelegt, unklar,
   fehler, abgebrochen, ordner_verweigert, vorgang_abgelegt}` wird **vorgemerkt** (geht mit einer
   getippten Nachricht mit) und mit „Im Chat weitermachen“ gesendet.

**Die KI** sieht den Rahmen `[ABLAGE DER PERSON …]` (T5): Ziel, Ordnername, Zahlen, ob der Ordner
verweigert und ob `vorgang.json` abgelegt wurde — keine Kennungen, keine Dateinamen (das Schema lässt
keine zu; `grund` prüft zusätzlich, dass die Zahlen aufgehen).

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Backend | `dienst_upload.schalter`: `ablage_in_wlo` = Studio **und** `has_personal_auth()`; `grenzen.max_mb_ablage` = `max_mb` |
| Backend | `upload_antwort`: Rahmen `[ABLAGE DER PERSON …]`, `grund` für `ablage` (nur mit `aktion: uebertragen`, Zahlen gehen auf) |
| Backend | `api/ui_ablage.datei`: Feld `link` (Render-Adresse des Knotens oder `null`) |
| Manifest | `ui_upload`: Fähigkeit `oeffnen` (Links), `grenzen.max_mb_ablage`, Antwort `aktion: uebertragen` + `ablage` |
| ui | `stream/xhr-senden.ts` (aus `dokument-transport.ts` gelöst, verhaltensgleich), `stream/ablage-transport.ts`, `ChatApiClient.ablageSchritt` |
| ui | Host-Kette `ablegen(schritt)`: `BlockModulHost` (Fähigkeit `hochladen`) → `WidgetModulHost` → Shell → `collection-actions.ablageSchritt` (Sitzungs-Wache, Logs ohne Namen; gemeinsam mit dem Dokument über `ohneZug`) |
| ui-module | Vertrag `ModulHost.ablegen`, `AblageSchritt`, `AblageEintrag`; Brücke des Custom Elements |
| ui-module | `ui-upload/upload-uebertragen.ts` (Regeln), `-ablauf.ts` (Zustand), `-ansicht.ts` (Darstellung), `-texte.ts` (DE/EN), Element verdrahtet, Stil |
| Studio | Vorschau-Host simuliert `ablegen`; Hinweis „Inhalte in WLO ablegen“ beschreibt die Wirkung statt „noch ohne Wirkung“; `max_mb` gilt auch je abgelegter Datei |
| Budget | je nachgeladenem Modul 20 kB gzip statt 15 (`ui-upload` 15,7 kB; zusammen weiter ≤ 60 kB) — **bewusste Anhebung**, siehe unten |

## Entscheide in diesem Paket

- **Fähigkeit:** `ablegen` hängt an `hochladen` (wie das Dokument), keine neue Fähigkeit. Für die Links
  bekommt `ui_upload` `oeffnen`.
- **Anhalten statt Abbrechen mitten in einer Datei**: ein abgebrochener Versand ließe den Stand offen.
- **Kein Neu-Vorbereiten** nach `neu_vorbereiten`/`fremder_stapel`: eine zweite Freigabe derselben
  Dateien legte schon abgelegte doppelt an (der MCP benennt um). Die Person sieht den Grund und kann neu
  auswählen.
- **Budget 15 → 20 kB gzip** je Modul: `ui_upload` trägt drei Aufgaben in zwei Sprachen; ein Bündel
  lässt sich wegen SRI nicht weiter nachladend teilen. Zurücknehmen = Texte kürzen oder Aufgaben in
  ein zweites Modul lösen.
- **Ohne https** (kein `crypto.subtle`) ein eigener Code `unsicher` mit eigenem Satz.

## Tests

Neu:
- Backend `test_ui_upload`: Schalter folgen Studio und Anmeldung, `max_mb_ablage`, Rahmen
  (Zahlen, Ordner, flach, verweigert, `vorgang.json`), `ablage` nur mit `aktion: uebertragen`, Zahlen
  gehen auf, keine fremden Felder. `test_ui_ablage_api`: `link` je Knoten, ohne Knoten `null`.
- ui: `ablage-transport.spec` (JSON/multipart, Zugangsblock, Fortschritt, Codes, Abbruch),
  `block-modul-host.spec` (Fähigkeit), `collection-actions.spec` (ohne Zug, Sitzungs-Wache, Logs ohne
  Namen); die Spec des Dokument-Transports bleibt unverändert grün.
- ui-module: `upload-uebertragen.spec` (Art, Titel, Auswahl, Prüfsumme, Plan, Stand, Codes, Zählung,
  Antwort ohne Kennungen, `unsicher`), `ui-upload-uebertragen.element.spec` (Angebot, Vorschau,
  Abbrechen, nacheinander mit Fortschritt, Link, Abschluss, Vormerkung, Fehler einer Datei / des
  Stapels, Anhalten und Nachsenden, Fehler beim Vorbereiten, nur lesen).
- E2E `upload-uebertragen.spec` (gemocktes Backend): ganzer Weg mit echter Prüfsumme und Link, Fehler
  in der Mitte, Abbrechen, nur Tastatur (Fokus auf der Vorschau), 320 px.

Läufe nach den Review-Fixes: Backend 8505 grün (5 übersprungen); ui 1166, ui-module 256, widget 76,
Studio 1967 grün; E2E gesamt 96 grün, Upload-Specs `--repeat-each 5` 50/50; Lint, ruff, Token-/Radien-/
A11y-/Kontrast-Wächter sauber; Budget: Haupt-Bündel 191,78 kB gzip (Warnschwelle 190, Grenze 200, vorher
191,7), `ui-upload` 16,2 kB gzip (Grenze jetzt 20).

## Offen

- Live erst nach MA-0 (Messung mit Testkonto) und der Verdrahtung `registerCurationBatchTools` in
  `wlo-mcp-server-sc/src/server.ts` (Nutzerdatei); bis dahin antwortet das MCP auf die Stapel-Werkzeuge
  nicht, und `vorbereiten` endet mit einem Code.
- T1b (Dienst „letzte Ablagen nach der Anmeldung“) und „Vorgang herunterladen“ — nicht in diesem Paket.
- Zweites Ziel (Inbox) bleibt im MCP vorbereitet, nicht freigeschaltet.

## Review U3-3b (2026-11-06, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 3 MAJOR, 8 MINOR, 1 NIT. Geprüft und in Ordnung: Schreibweg nur mit Anmeldung (Studio
**und** `has_personal_auth()`, Endpunkte prüfen erneut), keine Kennungen/Dateinamen an die KI, Zahlen gehen
auf, Links nur über `host.link` und `https:`, Logs ohne Namen, Doppelklick auf „prüfen“/„Jetzt übertragen“.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Das Backend reicht `layout` des MCP durch (`folder`/`flat`), das Modul erwartete `ordner` — jede Vorschau sagte „ohne eigenen Ordner“, die KI „flach“; alle Attrappen nutzten die falsche Form | `planAus` liest `folder`; Attrappen (Spec, E2E, Studio-Vorschau) auf die echte Form | `der Plan des Servers …`, `Befund 1: …` |
| 2 | MAJOR | Widget geschlossen mitten im Stapel: der `AbortError` wurde `fehler` (Dateifehler), der Stapel lief unsichtbar weiter | `codeAblage`: Abbruch → `abgebrochen` (hält an); `_mitAbbruch` startet nach dem Entfernen nichts; `disconnectedCallback` hält nach der laufenden Datei an, Prüfen bricht ab | `Befund 2: …` (zwei Tests) |
| 3 | MAJOR | Der Fortschrittsbalken trug `data-ablage` (Marke der Ablagefläche): ein Ablegen darauf setzte mitten im Senden zurück | Marke `data-ablage-balken`; Auswahl ruht während einer Übertragung; Lauf-Nummer — ein überholter Lauf schreibt nichts mehr | `Befund 3: …` |
| 4 | MINOR | „Im Chat weitermachen“ doppelt → zwei Abschlüsse | Sperre `weiterLaeuft`, Knopf gesperrt | `Befund 4: …` |
| 5 | MINOR | Nach „Anhalten“ lag der Fokus auf einem gesperrten Knopf → `body` | `zeichne` überspringt gesperrte Knöpfe, Ersatzziel | `Befund 5: …` |
| 6 | MINOR | Nachsenden auch nach einem Halt, den es nicht heilt (Anmeldung, Schalter …) | nur ohne Halt oder bei heilbarem Halt | `Befund 6: …` |
| 7 | MINOR | `nicht_erreichbar` als „nicht abgelegt“ (Backend: unklar); „unklar“ ohne Antwort nie nachfragbar; `voll` durch 429→gedrosselt verdeckt | `nicht_erreichbar` → unklar; „unklar“ mit Code lässt sich nachsenden (Backend sagt dann den Stand); eigener Code vor dem Status | `Befund 7: …`, `codeAblage` |
| 8 | MINOR | Ordnername ungekürzt (Backend 120) → 422 ohne Ausweg | `einZeiler` | `Befund 8: …` |
| 9 | MINOR | Rollbare Liste ohne Tastaturzugang | Bereich `role=region`, Name, `tabindex=0`, Fokusring | `Befund 9: …`, E2E Tastatur |
| 10 | MINOR | E2E fokussierte selbst und prüfte dann den Fokus | prüft, wohin der Fokus nach dem Senden geht, und den nächsten Tab-Halt; fehlende Tests ergänzt (1–9) | E2E `nur mit der Tastatur` |
| 11 | MINOR | `ui-upload.element.ts` 379 Zeilen | **bewusst gelassen** — nächster Eingriff löst `befund`/`ablageTeil` in eine Ansicht | — |
| 12 | NIT | „Datei k von n“ beim Nachsenden mit dem Index; doppelte Ansage; `%` ohne Intl | Stelle in der Sendung (`position`/`anzahl`); Ansage und `%` gelassen | (über Befund 7) |
