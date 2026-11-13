# Paket R1: Kestra-Aufträge in Teilen, Sprache, Identität, Stand (2026-11-13)

Plan [`2026-11-12-restpakete-ablaeufe-kestra-ui.md`](../plans/2026-11-12-restpakete-ablaeufe-kestra-ui.md),
Entscheide R-E12 bis R-E14.

## Was

- **R1-a Limit je Job (N14):** Neues Feld `aufteilen: {argument, hoechstens}` am Schritt `auftrag`.
  - Eine längere Liste im Argument geht in Teilaufträgen an die B-API, und zwar nacheinander: Jedes
    „Stand prüfen“ holt einen Teil ab und startet den nächsten. Die Antwort sagt „Teil 1 von 3 ist
    erledigt, Teil 2 läuft“.
  - Höchstens 20 Teile (Grenze der B-API je Schlüssel). Bei mehr werden die Teile größer, nichts
    fällt weg.
  - Die Argumente (Liste und Sprache) werden beim ersten Teil eingefroren. Ändert sich die Ablage
    während des Wartens, bleibt der Schnitt derselbe.
  - Am Ende steht EIN Ergebnis im Teil `schreibt`:
    - `outputs` zusammengeführt: Listen gleicher Schlüssel hängen aneinander (etwa `report`), sonst
      gilt der Wert des letzten Teils;
    - `teile` (Anzahl) und die Dateien zusammen in `dateien`.
  - Im Lauf liegen höchstens 128 KB Teilergebnisse. Darüber zählt ein Teil nur noch (`gekuerzt`,
    Teilerfolg).
  - Ein gescheiterter oder nicht gestarteter Teil hält die anderen nicht auf (`gescheitert`,
    `warnungen`). Erst wenn alle scheitern, geht es zu `bei_fehler`.
  - Die Prüfung meldet ein `argument`, das es unter `argumente` nicht gibt. Sie meldet auch
    `aufteilen` zusammen mit `dateien_holen`: Gleiche Kennungen der Teile überschrieben einander.
  - Ohne `aufteilen` bleibt alles wie bisher, auch die Fassung (Vorgabe `None`).
- **R1-b Sprache der Person:** `{"$sprache": true}` als Wert eines Arguments wird `de` oder `en`.
  Der Seed „aus eigenen Inhalten“ nutzt es für `language` und teilt zu je 50 Dateien auf. 50 Dateien
  liest `metadaten_lesen` auf einmal.
- **R1-c `X-Edu-User-Id`** geht jetzt auch bei Abfrage, Abbruch und Datei mit, nicht nur beim
  Start: derselbe Job, dieselbe Identität. Ohne bestätigte Anmeldung fehlt der Kopf weiter.
- **R1-d `/api/ui/auftrag/stand`:** Fehlt der Verweis der Sitzung oder ist sein Vorgang weg, etwa
  weil ein anderer Tab ihn ersetzt hat, gilt der jüngste offene Vorgang der Person. Den nimmt
  auch der Preflight des nächsten Zuges.
  - Der Endpunkt liest dabei nur.
  - Das Kürzel des Auftrags muss passen. Sonst bleibt es bei 409 `kein_auftrag`.
- **R1-e `ui_fortschritt`:** 403 `abgewiesen` (die B-API weist den Schlüssel ab) zeigt einen eigenen
  Satz: neu anmelden und den Ablauf neu starten. „Nur angemeldet“ wäre hier falsch.
  - Dazu trägt ein HTTP-Fehler des Widgets jetzt `code` aus `detail`.
  - Nur ein kurzes Wort wird übernommen, nie freier Text des Servers.

## Review R1 und Behebung

Unabhängiges Review: 3 MAJOR, 4 MINOR, 3 NIT, alle behoben.

- **MAJOR 1:** Die Teile wurden bei jedem Abholen neu aus der Ablage geschnitten. Änderte sie
  sich, fielen IDs weg oder gingen doppelt an den schreibenden Flow. Jetzt sind die Argumente
  eingefroren (höchstens 64 KB, sonst kein Aufteilen und `bei_fehler`).
- **MAJOR 2:** Der Rückfall in `/stand` fand jeden wartenden Vorgang. Das Abholen im Zug liest aber
  den Verweis und hätte woanders abgeholt. Jetzt gilt nur der jüngste offene Vorgang, und nur wenn
  der Verweis fehlt oder ins Leere zeigt. Genau den nimmt auch der Preflight des nächsten Zuges.
- **MAJOR 3:** Die Teilergebnisse lagen ungedeckelt im Lauf, der je Zug gelesen wird. Jetzt
  höchstens 128 KB, darüber `gekuerzt`.
- **MINOR 4:** `outputs` nur des letzten Teils sah wie der ganze Lauf aus. Jetzt hängen Listen
  aneinander.
- **MINOR 5:** Die Prüfung meldet `$sprache` außerhalb der obersten Ebene eines Auftrags. Der
  Studio-Hinweis sagt es.
- **MINOR 6:** Tests über den Zug: drei Teile bis zum Ende, Abbruch in Teil 2, Konflikt beim
  Festhalten.
- **MINOR 7:** Der Rumpf eines Fehlers darf höchstens 2 s dauern. Ein Fehler mit Status bleibt
  dieser Fehler, auch wenn die Frist dabei abläuft.
- **NIT 8:** Eigener Satz für einen gescheiterten Teil. Schon der Start sagt, dass es mehrere Teile
  werden.
- **NIT 9:** Plan und TB-Plan nachgezogen.
- **NIT 10:** Ein fester Wert unter `aufteilen.argument` ist ein Befund.

## Grenzen

- Die Teile laufen nacheinander, nicht parallel. Das schont die Grenze von 20 Jobs, braucht aber je
  Teil ein „Stand prüfen“ (das `ui_fortschritt` fragt selbst nach).
- Ob die B-API `X-Edu-User-Id` bei Abfrage und Abbruch auswertet, zeigt erst die Staging-Probe.
  Schaden kann der Kopf nicht: Es ist derselbe Wert wie beim Start.

## Tests

- `test_r1_auftrag_teile.py` (17): Teilen, Grenze, Prüfung, Treiber nacheinander, Teilerfolg, alle
  gescheitert, Start des nächsten scheitert, ohne `aufteilen` unverändert, Sprache, Seed.
- `test_tb_f1_flow_identitaet.py`: Kopf bei Abfrage, Abbruch und Datei.
- `test_ui_auftrag_api.py`: veralteter Verweis, ohne Verweis, fremdes Kürzel.
- Widget: `chat-api-auftrag.spec.ts` (`code`), `fortschritt-ablauf.spec.ts`,
  `ui-fortschritt.element.spec.ts`.

## Deploy

- Keine Migration. Image neu bauen.
- `boerdi import-config --werksabgleich` bringt den geänderten Seed „aus eigenen Inhalten“. Er ist
  ab Werk aus.
