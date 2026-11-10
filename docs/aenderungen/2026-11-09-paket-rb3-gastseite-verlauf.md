# Paket RB-3: Aufträge der Gastseite und der wiederhergestellte Verlauf (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5f.
Befunde: Review AS-4b, Befunde 4 und 5 (Vorbefunde aus `startTask`).

Keine Migration, keine neue Variable. Das Image muss neu gebaut werden (Widget, Backend). Danach
im Browser einmal hart neu laden.

## Reihenfolge: erst der Verlauf, dann der Auftrag (Befund 4)

- **Vorher:** In einer fortgesetzten Sitzung ging ein Auftrag der Gastseite (`startTask`,
  `startAblauf`, Attribut `ablauf-start`) ab, bevor der alte Verlauf geladen war. Seine Blase stand
  deshalb vor dem alten Gespräch.
- **Jetzt:** Die Shell hat ein eigenes Signal `_verlaufBereit`. Der Lebenszyklus setzt es vor dem
  Laden auf `false` und danach wieder auf `true`, auch wenn das Laden scheitert oder ein Neustart
  den Verlauf verwirft. Solange es `false` ist, warten Aufträge in derselben Warteschlange wie
  während eines Zugs (`_mussWarten`).
- **Entscheid:** Ein eigenes Signal statt `isLoading` zu halten. Der erste Versuch, `isLoading` zu
  halten, brach 25 Specs, weil es auch Eingabe, Knöpfe und Begrüßung sperrt.
- `vorgangFortsetzen` wartet nicht auf den Verlauf. Es wechselt das Gespräch ohnehin, und der
  alte Verlauf wird dann verworfen (`sitzungsWache`).
- Die Warteschlange beim Gesprächswechsel (Teil des Vorbefunds) ist schon seit dem
  Querschnitts-Review AS-4 gelöst: Ein Eintrag mit einer fremden Sitzung verfällt mit einer
  Warnung.

## Merker „Auftrag der Seite“ nach dem Neuladen (Befund 5)

- **Widget:** Ein Zug der Gastseite schickt `from_host: true` mit. Gelesen wird der Merker
  synchron mit der Blase (`SendMessageContext.vomGastgeber`). Er reist auch im POST-Rückfall mit.
  Ein gewöhnlicher Zug bleibt unverändert, ohne das Feld.
- **Backend:**
  - `ChatRequest.from_host` (Vorgabe `false`).
  - Die Nutzernachricht trägt dann im Debug-Block `_vom_gastgeber: true`
    (`db_sessions.nutzer_debug`, auch auf dem Weg der Tour).
  - Der öffentliche Verlauf gibt das als `ui.from_host` zurück, nur wenn es gesetzt ist und
    `true` ist.
- **Widget nach dem Neuladen:** `restoreHistory` legt eine solche Blase wieder als Auftrags-Blase
  an (`fromHost`).
- **Sicherheit:** Das Feld ist nur Anzeige, kein Recht. Wer es selbst setzt, färbt nur die eigene
  Blase. Bremse, Safety und Rechte laufen wie ohne das Feld.

## Tests

- **Backend:** `test_restbefunde_rb3.py` (Speichern mit und ohne Modul-Antwort, Vorgabe, öffentlicher
  Verlauf mit falscher Form). `test_publikum.py` hält den neuen öffentlichen Schlüssel `from_host`
  fest.
- **Widget:** `chat-shell-verlauf-bereit.spec.ts`. Geprüft wird: der Auftrag wartet auf den
  Verlauf und steht dahinter; eine frische Sitzung sendet gleich; ein gescheitertes Laden hält
  nicht auf; `from_host` steht nur am Zug der Gastseite; die Blase kommt nach dem Neuladen wieder.
- `chat-shell-strukturentwurf.spec.ts` startet jetzt ohne Persistenz. Eine dort fortgesetzte
  Sitzung ließe den Auftrag auf einen echten Verlauf-Abruf warten.

## Review RB-2/RB-3 (unabhängig, 2026-11-09)

Ergebnis: 0 kritisch, 0 schwer, 5 klein, 3 Kleinigkeiten. Bestätigt wurde: Das Effect-Tracking
verliert keinen Wechsel. `from_host` läuft auf keinen anderen Zug über (es wird synchron gelesen
und im `finally` zurückgesetzt). Beide Orte, die Nutzernachrichten speichern, tragen den Merker.
Der Client darf ihn setzen, weil er nur Anzeige ist. Alle Befunde sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Der Abruf des Verlaufs hat keine Frist. Hängt er, warteten Aufträge der Gastseite für immer. `restart`/`resetSession`/`wechseln` gaben das Signal nicht frei. | klein | Frist `VERLAUF_FRIST_MS` (15 s) in `lifecycle.init`; alle drei geben `_verlaufBereit` frei. Specs: „Verlauf hängt“ (Fake-Timer) und „Neustart während des Ladens“. |
| 2 | Ob nach dem Verlauf der Kontext-Gruß oder der wartende Auftrag zuerst kommt, entschied der Zeitplaner. | klein | **Entscheid:** Wartet ein Auftrag der Gastseite, entfällt der Kontext-Gruß der Wiederaufnahme (`gastAuftragWartet`, `_afterResume(ohneGruss)`). Der Auftrag ist der Zweck der Seite, ein Gruß davor wäre Rauschen. Vorher fiel der Gruß ohnehin am `isLoading`-Tor still weg. Ein Spec hält das fest. |
| 3 | Der POST-Rückfall, `startAblauf`, `buildBody`, der Tour-Weg und ein Neustart während des Ladens waren ungetestet; die Prüfung „getippt ohne Merker“ zählte nur Argumente. | klein | Specs für Rückfall und `startAblauf`, ein `buildBody`-Test, ein echter Start der Tour mit und ohne `from_host` (`test_restbefunde_rb3.py`); der Merker-Test prüft das letzte Argument. |
| 4 | Die Kennungen standen nur im `title` (mit Tastatur und Touch nicht erreichbar). | klein | Zusätzlich als Text nur für Screenreader (`.sr`). |
| 5 | Der Drift-Wächter zählte die Typen von Hand auf und suchte die ganze Datei ab. | klein | Er sammelt alle Typkennungen aus den Konstanten von `typen.py` (auch verschachtelt) und vergleicht nur mit dem Block `TYP_NAMEN`. |
| 6 | Bei den Marken `?`/`…` stand die Marke im `title`. | Kleinigkeit | Marken fallen weg; ohne echte Kennung kein `title`. |
| 7 | Auch der Wechsel auf „Verlauf lädt“ löst den Effect aus. | Kleinigkeit | Kommentar: harmlos, Gruß und Fokus warten nur, solange ein Zug lief. |
| 8 | Werkzeugnamen mit `-` ergaben keinen Namen „Ergebnis von …“. | Kleinigkeit | Regex `[a-z0-9_-]+`; Punkte bleiben ausgeschlossen. |

## Browser-Abnahme AS-4 und RB-3 (2026-11-09)

**Aufbau:**
- Wegwerf-DB `boerdi_as4_browser` (migriert, Seeds importiert, danach wieder gelöscht).
- Backend aus dem Staging auf `127.0.0.1:8100`, Widget aus dem frisch gebauten Bundle
  (`frontend/dist/widget/browser`, enthält `from_host`), Demo-Seite `/widget/edu-sharing-demo.html`.
- Ein eigener Probe-Ablauf `as4_probe`: Auslöser „Gastseite“; Startschema `sammlung` (nodeid,
  Pflicht) und `thema` (Text); ein wartender Schritt mit dem Chip „Ja, weiter“.

| Fall | Ergebnis |
|---|---|
| A: `startAblauf('as4_probe', {sammlung, thema})` | Blase „Auftrag der Seite“. Der Ablauftext enthält die eingesetzten Startdaten. Der Chip „Ja, weiter“ ist da. |
| B: derselbe Start noch einmal | „Dieser Ablauf läuft hier schon — es geht weiter, wo er steht.“ Kein Neustart; der Chip der vorigen Antwort bleibt anklickbar. |
| C: andere Daten | Rückfrage: „…läuft noch einer. Ein Neustart beendet den laufenden…“ mit „Neu starten“. Nach dem Klick startet der Lauf neu, mit den neuen Daten. |
| D (RB-3): eigenes Element mit `persist-session="true"`, Start, Neuladen, sofort derselbe Start | Die Sitzung wird fortgesetzt. Die alte Blase ist nach dem Neuladen wieder eine Auftrags-Blase (`host-bubble`). Der sofort gesendete Start wartete auf den Verlauf und steht **hinter** ihm. Die Bremse antwortet „läuft hier schon“. |

Im Server-Log stand kein Fehler.

**Beobachtung (nicht Teil dieses Pakets):** Auch feste Texte eines Ablaufs tragen das Etikett
„KI-generierte Antwort“. Eingetragen in den offenen Befunden.
