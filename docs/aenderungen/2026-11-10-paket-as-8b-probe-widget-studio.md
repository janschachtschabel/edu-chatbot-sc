# Paket AS-8b — „Im Widget ausprobieren“: Widget und Studio (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5n (P-9, P-10). Backend: AS-8a.

## Widget

- **Attribut `probe`** (Vorgabe `false`; `<boerdi-chat probe>` schaltet es ein). Die Hülle reicht
  es an die Shell (`setProbe`), der Client schickt `probe: true` in jedem Zug.
- **Etikett** „Probe · Trockenlauf — es wird nichts geschrieben“ (de/en) oben in der Shell, also in
  jeder Einbettungsart, auch rahmenlos. Text mit Farb-Tokens `on-surface-variant` auf
  `surface-variant` (rund 8:1 hell wie dunkel), `role="note"`.
- In der Probe gibt es kein „Meine Vorgänge“ und keine Frage nach offenen Vorgängen („Gespräch
  fortsetzen“). Das Backend antwortete dort ohnehin 409 `trockenlauf`.
- **Fehlertexte:**
  - ein 403 auf dem Chat-Weg heißt in der Probe „Die Probe braucht eine gültige Studio-Anmeldung …“
    (`probeHinweis`, nur mit Probe);
  - die Ablage nennt 409 `trockenlauf` („Probe der Studio-Vorschau: Dateien werden nicht in WLO
    abgelegt.“).
- `startAblauf()` und der Start aus den Attributen übernehmen den Probe-Stand jetzt synchron, bevor
  der Zug hinausgeht (siehe Befund B-3).

## Studio

- **Vorschau, Abschnitt „Ablauf ausprobieren“** (`views/ablauf-probe.component.ts`):
  - Ablauf wählen, ausgeschaltete mit „(aus)“; vorgewählt aus `?ablauf=`;
  - Startdaten als JSON (optional), geprüft in `views/probe-start.ts`; ein Fehler steht am Feld
    (`aria-invalid`, `aria-describedby`), der Text bleibt;
  - „Ablauf starten“, „Probe beenden“; eine Statuszeile sagt, welche Probe läuft;
  - die Liste hat die Zustände laden, leer (Hinweis auf „Abläufe“) und Fehler (mit „Erneut
    versuchen“).
- **Vorschau-Widget:** Eine Probe baut ein neues Element mit `probe` und startet den Ablauf über
  die Laufzeit-API `element.startAblauf(id, daten)`, genau einmal je Element.
- **Am Ablauf:** Link „Im Widget ausprobieren“ (`vorschau?ablauf=<id>`, im Studio ohne
  Neuladen), dazu der Hinweis „Es gilt die gespeicherte Fassung — erst speichern.“
- **Referenz:** Attribut `probe` in der Widget-Referenz (`widget-contract-data.ts`, 38 Attribute)
  und in `docs/browser-plugin-einbindung.md`. Dort steht jetzt auch, dass `ablauf-start` nicht
  wirkt, wenn es erst nach dem Verbinden gesetzt wird.

## Browser-Abnahme

**Aufbau:**
- Wegwerf-DB `boerdi_probe_browser` (migriert, Seeds), danach gelöscht.
- Backend aus dem Staging mit echtem Studio-Passwort und Schlüssel. Beides waren erzeugte
  Testwerte nur im Scratchpad, danach gelöscht. Ohne offenen Admin-Modus, damit das Cookie-Tor
  wirklich prüft.
- Studio über `ng serve` mit Proxy.

| Fall | Ergebnis |
|---|---|
| Probe ohne Cookie (direkt ans Backend) | 403 `probe_ohne_recht`, kein Zug. |
| Link am Ablauf | „Im Widget ausprobieren“ führt ohne Neuladen nach `vorschau?ablauf=fuehrung`; der Ablauf ist vorgewählt, alle drei Beispiele stehen mit „(aus)“ in der Liste. |
| Ungültige Startdaten (`[1,2]`) | Meldung am Feld, `aria-invalid`, kein Start. |
| Start „Kurze Führung“ (aus) | Etikett im Widget, Antwort des ersten Schritts, die Leiste „Schritt 2 von 4, wartet auf den Seitenwechsel“ mit Weg-Knopf, ohne WLO-Anmeldung. In der DB: Sitzung mit `_probe`, Vorgang gehört `probe:…`, Lauf trägt `probe`. |
| Zweiter Start | läuft wieder (neues Element, neue Sitzung). |
| „Probe beenden“ | gewöhnliche Vorschau ohne Etikett und ohne Statuszeile. |
| Logs | keine Serverfehler. |

Der Browser-Bereich war verdeckt, deshalb gibt es keine Bildschirmfotos. Die Fälle wurden über das
DOM geprüft.

**Befunde der Abnahme (alle behoben, je mit Spec zuerst):**
- **B-1:**
  - Das Studio setzte `ablauf-start` als Bindung erst nach dem Verbinden des Elements. Das Widget
    liest es aber nur in `ngOnInit`, also startete nichts.
  - Außerdem merkt sich der Attribut-Weg den Start je Tab, ein zweiter Start bliebe stumm.
  - Die Vorschau startet deshalb über `element.startAblauf()`.
- **B-2:** Direkt nach dem Neubau zeigte `viewChild` noch auf das alte Element; der Start wäre dort
  gelandet (die Spec fing es). Jetzt trägt das Element seinen Boot (`data-boot`), und nur das
  aktuelle Element bekommt den Start.
- **B-3:**
  - Der Start ging ohne `probe` hinaus: Die Vorschau ruft `startAblauf` sofort, bevor der Effect
    der Hülle das frisch gesetzte Attribut an die Shell gereicht hatte. Das Backend behandelte den
    Zug deshalb als gewöhnlichen („ausgeschaltet“).
  - `startAblauf` und der Start aus den Attributen übernehmen den Stand jetzt synchron.

## Review und Behebung

Das Review fand 0 kritische, 0 schwere, 6 mittlere und 5 kleine Befunde. Alle sind am Code bestätigt
und behoben.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | mittel | Das Etikett nutzte `--boerdi-*`-Token, die im ausgelieferten Widget nicht gesetzt sind (nur im Studio). Auf Gastseiten fehlten Hintergrund und Rahmen. | Dieselben `--mat-sys-*`-Token wie die Ablauf-Leiste. |
| 2 | mittel | Das Studio prüfte die Startdaten nur auf „JSON-Objekt“; die Grenzen des Widgets (16 000 Zeichen, 20 Felder) führten zu einer stummen Probe. | `START_JSON_MAX`/`START_SCHLUESSEL_MAX` aus `@boerdi/ui` (eine Quelle), eigene Meldungen `gross`/`schluessel` (de/en). Spec. |
| 3 | mittel | „Probe beenden“ verschwand mit dem Fokus; der Fokus fiel auf `body`. | Fokus auf „Ablauf starten“. Spec. |
| 4 | mittel | Die Meldung zu ungültigen Startdaten erreichte Screenreader nicht (Fokus blieb am Knopf). | Fokus ins Feld; `aria-describedby` liest die Meldung vor. Spec. |
| 5 | mittel | Kommentare und Plan P-9 nannten noch den Start über Attribute. | Auf `element.startAblauf()` angeglichen. |
| 6 | mittel | Die Reihenfolge „Probe vor der Frage nach offenen Vorgängen“ war nur über die Hülle getestet. | Widget-Spec: angemeldet, `probe`, neue Shell → keine Frage (war schon grün, bleibt als Wächter). Dazu eine zweite Sicherung im Template: kein Hinweis „Gespräch fortsetzen“ in der Probe. |
| N1 | klein | Doc-Block von `apply()` stand über `onProbe`. | Zurückgesetzt. |
| N2 | klein | Der Q-4-Kommentar stand vor dem Etikett statt vor `.ueber-eingabe`. | Etikett davor eingefügt. |
| N3 | klein | Der B10-Kommentar stand über dem neuen Schlüssel. | Schlüssel davor gesetzt. |
| N4 | klein | „Vorschau neu starten“ während einer Probe startet den Ablauf neu — gewollt, aber nicht festgehalten. | Entscheid im Kommentar, Spec. |
| N5 | klein | Fällt `probe` zur Laufzeit weg, bleibt die Sitzung im Backend Probe, das Etikett nicht. | In `browser-plugin-einbindung.md`: „Nur beim Erzeugen setzen“. |
| — | klein | Eine unbekannte Kennung aus `?ablauf=` (ungespeicherter Ablauf) wählte still den ersten. | Hinweis „gibt es noch nicht — erst speichern“. Spec. |

## Prüfung

- Tests:
  - `ng test ui`: 1384 grün (ein früherer Lauf zeigte einmal `anmelde-frist.spec` rot, allein
    grün, Kippler);
  - `ng test widget`: 97 grün;
  - `ng test ui-module`: 348 grün;
  - `ng test studio`: 2141 grün (nach dem Review).
- ESLint ist sauber für alle berührten Dateien.
- Widget-Bündel 189,34 kB gzip (vorher 188,93; Grenze 200).
