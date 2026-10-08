# Paket 4b: Folgebefunde aus Paket 4

Stand 2026-10-08. Paket 4 ist gemergt (PR #11, main `9d17060`); die Bild-Veröffentlichung nach grünem `ci` (L3) ist nach dem Merge geprüft: `image` startete per `workflow_run` zwei Sekunden nach `ci` und schob `sha-9d17060` und `latest` mit demselben Digest.

Dieses Paket nimmt die Folgebefunde aus Paket 4, die keinen Entscheid brauchen. Für jeden steht ein Vorschlag in der Befundliste (§1.5, §5).

**Nicht drin, weil ein Entscheid fehlt:**
- ReDoS in Lotsen-Regeln: Die Härtung bräuchte `regex` (mit Zeitgrenze) als neue direkte Abhängigkeit.
- URL-Import über `httpx` gegen tröpfelnde Kopfzeilen: nur über das Studio erreichbar, ein Umbau des Abrufs.
- Alles aus Paket 5 (Paket-4-Plan §5).

## Aufgaben

### Phase A · Backend
Schritt 0: `/better-coding-workflow` neu laden.

- **A1 · Studio-Auslieferung** (Befundliste §1.5). Nach einem Deploy zeigte der Browser den alten Stand oder eine Seite ohne Stil.
  - `SpaFiles.file_response` setzt `Cache-Control: no-cache` für `index.html`, auch beim SPA-Rückfall.
  - Für die gehashten Angular-Dateien (`main|chunk|styles|polyfills|worker-<8 Zeichen>.js|css`) setzt es `public, max-age=31536000, immutable`, wie beim Widget.
  - Ein Pfad mit Datei-Endung fällt nicht mehr auf die `index.html` zurück, er ergibt 404.
  - Test zuerst in `tests/test_studio_bff.py`, drei Fälle.
- **A2 · `PUT /config/data` liefert `type`** wie GET. Sonst holte der Bereichs-Editor den Rohtext eines Markdown-Bereichs nach dem Speichern als `.yaml`. Test: Ein Markdown-Bereich antwortet `type: md`.
- **A3 · Umwandlungsfehler als Typ.** Die Umwandler bleiben ALT-treu und liefern Fehler als Text. Die Texte werden aber `Umwandlungsfehler(str)`, und `_pruefe_umwandlung` prüft den Typ statt des Präfixes.
  - Test: Ein Dokument, das mit „Fehler“ beginnt, wird eingelesen.
  - Fehlertexte bleiben 400, nicht lesbare Formate 415.
- **A4 · Datenbankfehler beim Wiederherstellen und Seed-Anwenden.**
  - `put_many` meldet einen `DataError` (ein Wert, den Postgres nicht speichern kann, etwa `\u0000`) als `BereichNichtSpeicherbar(area)`.
  - Die Endpunkte antworten 400 mit dem Bereich (de/en). Andere Datenbankfehler bleiben 500.
  - Test mit `\u0000`.

### Phase B · Studio: Live-Regionen mit `role="status"`
Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` neu laden.

Dieselbe Schwäche wie F-M6: Eine Live-Region, die mit ihrem Text entsteht, sagen Screenreader oft nicht an. Das Muster ist das aus Paket 4 S1 (`views/_live-region.scss`): Die Region steht dauerhaft im DOM, nur ihr Inhalt ist bedingt.

- **B1 · Drei Statuszeilen:** `eval-runs` (`.er-status`), `quality-logs` (`.ql-status`), `eval-compare` (`.cmp-computing`).
- **B2 · `mcp-registry`:** Die Zusammenfassung des Abgleichs (fehlt etwas, passt alles, nicht eingetragen) steht in einer dauerhaften Status-Region. Die Listen darunter bleiben bedingt.
- **B3 · Sechs Rückmeldungen `action.message()`** (`shell/backup-tools`, `backup`, `factory-panel`, `privacy-purge`, `seed-panel`, `snapshots-panel`): Ein Erfolg steht in einer dauerhaften Status-Region. Ein Fehler bleibt ein bedingtes `role="alert"`, das beim Einfügen zuverlässig angesagt wird.
- **Test zuerst** je Stelle: Die Region ist vor der Meldung da und ganz leer, danach steht der Text in derselben Region.

### Abschluss
- Volle Suiten (Backend, Frontend zweimal, E2E), lint, `check:*`.
- Ein frischer Prüfer liest den Diff.
- Befundliste: Erledigtes streichen.
- Upload: Branch `paket-4b-folgebefunde`, ein PR. Den Merge macht der Nutzer.

## Log

### Vorab (2026-10-08)
- Nach dem Merge von PR #11: Klon auf main `9d17060`, lokaler Branch gelöscht. Staging und main sind gleich (Abgleich: 0 Abweichungen). Den Remote-Branch `paket-4-audit-extern` löscht der Nutzer.
- Docker Desktop lief nicht (nach einem Neustart); die Datenbank-Tests wären still übersprungen worden („Compose-PG nicht erreichbar“). Docker gestartet, nur die Entwicklungs-Datenbank per `docker compose -f deploy/compose.dev.yml up -d --wait postgres`.

### A1 · erledigt
- `SpaFiles.file_response`: `index.html` ist `no-cache` (auch beim Rückfall und bei 304), die gehashten Angular-Dateien sind `immutable`.
- Ein fehlender Pfad mit Datei-Endung (`.js`, `.css`, Schriften, Bilder …) ist 404 statt Startseite.
  - Nur echte Endungen: Eine Studio-Route mit Punkt (etwa eine Versionsnummer) fiele sonst künftig auf 404.
- Tests: drei neue in `test_studio_bff.py`, vorher rot; alle 34 grün.

### A2 · erledigt
- `PUT /config/data` liefert `type` wie GET. Test vorher rot (`KeyError: 'type'`).
- `config.py` hat 299 Zeilen. Der OpenAPI-Vertrag ist unverändert, weil der Handler ein ungetyptes Dict liefert.

### A3 · erledigt, mit einer Abweichung vom Plan-Wortlaut
- **Abweichung:** keine Ausnahmen. Die Umwandler sind laut Modulkopf ALT-treu („never raises“). Die Fehlertexte werden `Umwandlungsfehler(str)`, Wortlaut unverändert, und der Router prüft den Typ.
- **Tests:**
  - Ein Dokument „Fehlerkultur …“ wird eingelesen; vorher 400.
  - Jeder Fehlerweg der Umwandler liefert den Typ. Das ist an allen bestehenden Fehlertests ergänzt, denn die Router-Tests täuschen ihn nur vor.
  - Gegenprobe: eine Verpackung entfernt, ergibt rot.

### A4 · erledigt, weiter gefasst als geplant
- **Befund am Code:** Der asyncpg-Adapter reicht den `\u0000`-Fehler als allgemeinen `DBAPIError` durch, nicht als `DataError`. Erkennbar ist er nur am SQLSTATE (`22P05`, Klasse 22).
- **Umsetzung:** `als_bereichsfehler(area)` in `services/config_conflict.py` macht aus Klasse-22-Fehlern `BereichNichtSpeicherbar(area)`. Das gilt in `put_many` und im bedingten `put`.
- **Weiter gefasst:** ein App-weiter Handler (`config_guards.nicht_speicherbar_antwort`, registriert in `main.py`) antwortet 400 mit dem Bereich (de/en). So gilt es für alle Konfig-Schreibwege, nicht nur für Wiederherstellen und Seed.
- **Tests:**
  - Die drei D4-Tests sagen jetzt 400 bzw. die neue Ausnahme mit Bereich zu; „nichts geschrieben“ bleibt.
  - Neu: der bedingte `put` und der Formularweg.
  - Gegenprobe ohne Handler-Registrierung ergibt rot.
- `config_store.py` hat 311 Zeilen (+2).

### B1 · erledigt
- `eval-runs`, `quality-logs`, `eval-compare`: Die Statuszeile steht dauerhaft (`.live`), nur der Text ist bedingt. Die Specs sagen die leere Region vorab und dieselbe Region danach zu, vorher rot (4).
- `eval-compare` entsteht mit dem Klick und rechnet sofort; die erste Zeile bleibt deshalb stumm, wie bei `costs` dokumentiert. Angesagt wird jedes weitere Rechnen im offenen Panel (Auswahlwechsel, Neu laden).

### B2 · erledigt, mit einer Abweichung vom Plan-Wortlaut
- **Abweichung:** Der sichtbare Satz „Eingetragen, aber vom Server nicht angeboten:“ ist der Vorspann seiner Liste und bleibt dort. Angesagt wird das Ergebnis als ein Satz in einer dauerhaften, nur für Screenreader sichtbaren Region (`.mr-ansage`), bei fehlenden Werkzeugen samt Namen. Die sichtbaren Absätze tragen keine Rolle mehr, damit nichts doppelt angesagt wird.
- **Tests:** zwei neue. Test und Umsetzung entstanden hier in einem Zug; als Gegenprobe ohne die Region werden beide rot.

### B3 · erledigt
- Sechs Rückmeldungen: Ein Erfolg steht in der dauerhaften Status-Region, ein Fehler bleibt ein bedingtes `role="alert"`. Bei `backup-tools` steht der Link „Zu den Snapshots“ im Erfolgszweig.
- **Tests:** Die Erfolgstests der sechs Panels sagen die leere Region vorab und dieselbe Region danach zu, bei `backup-tools` auch den Fehlerfall und das Aufräumen. Die Vorlagen entstanden vor den Tests; Gegenprobe mit den alten Vorlagen aus main: 8 rot.

### npm-Audit-Gate · neu im Abschluss, erledigt
- **Befund:** `check:audit` war rot, am 2026-10-04 noch grün. Neu war `GHSA-68fv-2mgg-jv7q` (high) in `source-map-js` < 1.2.2: Ein Source-Map-Abschnitt mit ungünstigen Versätzen blockiert die Ereignisschleife. Das Paket kommt nur zur Bauzeit über `postcss`, `sass` (`@angular/build`) und `css-tree` (`jsdom`). Weil das Gate in der CI läuft, wäre der PR rot gewesen.
- **Dabei gefunden:**
  - Für die Ausnahme `GHSA-ch52-4w7c-c8xp` (`http-cache-semantics` ≤ 4.2.0) gibt es seit dem 2026-10-04 die behobene Version 4.3.0. Die Ausnahme beruhte darauf, dass es keine gab.
  - Dazu `GHSA-rj75-hqrm-r3gf` (moderat, unter der Schwelle) in `postcss-selector-parser` < 7.1.6.
- **Umsetzung:**
  - `npm audit fix` ohne `--force`. Nur das Lockfile ändert sich, alle drei Pakete innerhalb ihrer Versionsbereiche: `source-map-js` 1.2.2, `http-cache-semantics` 4.3.0, `postcss-selector-parser` 7.1.6. Die Lizenzen bleiben gleich.
  - Die Ausnahme ist gestrichen, `audit-ausnahmen.json` ist leer. Eine ungenutzte Ausnahme hätte das Gate am 2027-01-01 mit „abgelaufen“ rot gemacht, obwohl der Fund längst weg wäre.
- **Nachweis:** `npm audit` meldet 0 Funde. `check:audit` ist grün ohne Ausnahme; `check-audit.test.mjs` 10/10; das Lizenz-Gate ist grün.

### pip-audit · neu in der CI des PR, erledigt
- **Befund:** Im PR war `licenses-backend` rot; die Lizenzliste selbst war grün. `pip-audit` meldete zwei neue CVEs im gesperrten Laufzeit-Baum, beide transitiv:
  - `langgraph-sdk` 0.4.2 (`CVE-2026-104873`, behoben ab 0.4.4), über `langgraph`;
  - `multidict` 6.7.1 (`CVE-2026-104874`, behoben ab 6.9.1), über `aiohttp`/`yarl` (litellm, instructor).
  - Mit 4b hat das nichts zu tun; main ist genauso betroffen.
- **Umsetzung:** `uv lock --upgrade-package langgraph-sdk --upgrade-package multidict`. Nur diese zwei Pakete ändern sich: `langgraph-sdk` 0.4.6 (die neueste Patch-Version derselben Linie), `multidict` 6.9.1. `pyproject.toml` bleibt unverändert, die Lizenzen auch (MIT, Apache 2.0).
- **Nachweis:** `pip-audit` meldet wie in der CI „No known vulnerabilities found“, das Lizenz-Gate ist grün. Die volle Backend-Suite läuft auf den neuen Versionen grün: 5180 passed, 4 skipped. `ruff` ist sauber, der OpenAPI-Vertrag unverändert.
- **Nebenbefund, nicht in diesem Paket:** In einem von drei vollen Läufen standen nach der Zusammenfassung OTel-Exportfehler im Log.
  - Ursache: `test_otel.py` setzt den OTLP-Endpunkt und ruft `create_app()`. Das richtet einen prozessweiten Exporter auf `localhost:4318` ein, wo nichts lauscht, und er bleibt für den Rest des Laufs aktiv.
  - Älter als 4b, das Ergebnis bleibt grün. Als eigene Aufgabe vorgeschlagen.

### Review mit frischem Blick (2026-10-08)
Ein frischer Prüfer las den ganzen Diff gegen main. Er fand keinen Blocker und nichts Schweres, aber vier kleine Befunde. Alle vier sind am Code bestätigt und behoben, jeweils Test zuerst.

- **R4b-1 · A4: „Geschrieben wurde nichts“ stimmte nicht überall.**
  - Der Handler gilt für jeden Konfig-Schreibweg. Drei ALT-Sammelrouten schreiben aber je Bereich eine eigene Transaktion: `PUT /personas`, `PUT /patterns` und `PUT /tone-modifiers`. Bei der letzten steht „partial writes stay“ ausdrücklich im Code.
  - Scheiterte dort der zweite Bereich, stand der erste schon, und die Antwort sagte trotzdem „nichts geschrieben“. Das Studio nutzt diese Routen nicht.
  - **Behoben:** Die Ausnahme trägt `ganzer_vorgang`. `put_many` setzt es, wenn die Transaktion mehr als einen Bereich trug (Wiederherstellen, Seed). Dann heißt es weiter „Der ganze Vorgang wurde verworfen“, sonst „Dieser Bereich wurde nicht gespeichert“ (de/en).
  - Die Sammelrouten atomar zu machen hätte die dokumentierte ALT-Semantik geändert. Die zweite Fassung braucht es trotzdem: Das Studio zeigt nach einem gescheiterten Wiederherstellen nur diesen Text.
  - **Tests:** Wiederherstellen und Seed sagen den ganzen Vorgang zu, der Formularweg nur den Bereich. Neu ist der Fall des Prüfers auf `PUT /personas`: Die erste Zielgruppe ist gespeichert, die zweite nicht, und die Meldung sagt das. Dazu die Store-Tests für das Merkmal (drei Bereiche, bedingter `put`, einzelner `put`).
  - Vorher rot: 7. Danach grün.
- **R4b-2 · B2: Die Ansage-Region stand im Lade-Zweig.**
  - `load()` läuft nach dem Speichern, nach „Neu laden“ und beim Wiederholen. Die Region entstand danach neu, schon mit dem geänderten Satz, und gerade die Änderung des Abgleichs wurde nicht zuverlässig angesagt.
  - **Behoben:** Die Region steht jetzt außerhalb des Lade-Zweigs, neben der Statuszeile.
  - **Test:** Dieselbe Region während des Ladens und danach, mit dem neuen Satz. Vorher rot (`null` während des Ladens).
- **R4b-3 · B3: Eine Prüfung in `backup-tools` war immer wahr.** „Region vorhanden“ galt nach B3 auch ohne Meldung. Jetzt prüft der Test den Text und den Link vor dem Aufräumen, danach die leere, selbe Region ohne Link. Gegenprobe ohne Erfolgstext: rot.
- **R4b-4 · A3: Zwei Fehlerwege ohne Test.** Gemeint sind der `ImportError` (markitdown fehlt im Image) und ein sonstiger Abruffehler beim URL-Import. Zwei neue Tests prüfen Typ und Text. Gegenprobe je Weg ohne die Verpackung: rot.
- **Ohne Befund geprüft:**
  - A1: Cache-Kopf auch bei Rückfall und 304; die Hash-Regel trifft nur esbuild-Ausgaben; keine Studio-Route hat einen Punkt.
  - A2.
  - A3: alle Fehlerwege verpackt; kein anderer Aufrufer prüft das Präfix.
  - A4: SQLSTATE-Erkennung für 22P05/22P02 und clientseitige Kodierfehler; Rückrollen und Cache erst nach dem Commit; Handler app-weit samt CORS.
  - B1–B3: Leere trotz Kontrollfluss-Ankern; `.live` und `.sr` in jeder Komponente gestylt; keine doppelte Ansage.

### Abschluss (2026-10-08)
- **Backend:**
  - 5180 passed, 4 skipped (22 min). `ruff` ist sauber, der OpenAPI-Vertrag unverändert.
  - Der erste Lauf im Hintergrund brach bei 80 % am 20-Minuten-Zeitlimit ab, ohne Fehler. Parallel lief die Testsuite einer anderen Sitzung. Der zweite Lauf lief durch.
- **Frontend:**
  - lint und alle `check:*` grün, `check:audit` ohne Ausnahme.
  - Unit ui 867, widget 71, studio 1381, je zweimal.
  - E2E 50: zweimal vor dem Review, einmal danach.
  - Der Studio-Build hat keine Warnung. Die `.live`-Regeln stehen in jedem Chunk mit einer neuen Statuszeile.
- **Upload:** Branch `paket-4b-folgebefunde`, PR #12, Commits nach Bereichen (Backend, Studio, Frontend-Werkzeuge, Doku). Dazu kamen die Backend-Abhängigkeiten aus der PR-CI (pip-audit, siehe oben) und dieser Nachtrag. Der Abgleich zeigt 0 Abweichungen. Den Merge macht der Nutzer.
- **Testcontainer:** aus dem Branch gebaut (`edu-chatbot-sc:paket4b-lokal`), die Datenbank steht auf `0006` (Kopf).
  - Live geprüft: `/studio/` ist `no-cache`, auch beim Rückfall und bei 304. Die gehashte Stildatei ist `immutable`, eine fehlende `.js` ergibt 404.
