# Paket TB-T2: Zwei Themenbaum-Abläufe als Seed (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md`, Gruppe T, Auftrag N15: Die beiden Abläufe
anlegen, an den Kernfragen des Gestaltungsleitfadens orientiert, und eindeutig benennen. Sie
reichen bis zur Anzeige des Entwurfs im Chat. Sammlungen daraus anzulegen, kommt später.

## Benennung

Im Studio heißen alle drei Themenbaum-Abläufe „Themenbaum · aus …“:

| Kennung | Titel | Neu? |
|---|---|---|
| `sammlungsstruktur` | Themenbaum · aus Ordnern | nur der Titel (vorher „Themenbaum aus Ordnern“) |
| `themenbaum_aus_thema` | Themenbaum · aus einem Thema | neu |
| `themenbaum_aus_inhalten` | Themenbaum · aus eigenen Inhalten | neu |

Die Kennung von `sammlungsstruktur` bleibt, weil Verweise und Vorgänge an ihr hängen.

## `themenbaum_aus_thema`

- **Kernfragen** als Nachrichten mit Schnellantworten (TB-T1, `schreibt`):
  - `wofuer` → Teil `zweck`: Unterricht planen, Materialpool aufbauen oder Redaktionelle
    Sammlung;
  - `stufe` → Teil `stufe`: fünf Stufen, eine andere Zielgruppe als Freitext in denselben Teil;
  - `thema` → Teil `thema`: Freitext „Fach: Thema“;
  - `tiefe` → Teil `tiefe`: Überblick (2 Ebenen) oder Ausführlich (3 Ebenen).
- **`entwurf`** (`agent` mit `ui_strukturentwurf`, `ausgabe: draft`, 3 Züge): Der Hinweis
  verlangt Thema, Fach, Stufe und Tiefe aus den Antworten. Klassenstufen, Formate und Jahre sind
  keine Punkte (Leitfaden).
- **Ende:** „Weiter“ führt zu `ende`. Ohne Entwurf geht es zu `ohne_entwurf`.
- **Auslöser:** Knopf, Vorschlag der KI und zwei Wendungen. Keine Voraussetzung.

## `themenbaum_aus_inhalten`

- Voraussetzung `anmeldung`. Kernfragen `wofuer`, `stufe` und `thema` wie oben.
- **`hochladen`** (`ui_upload`): Die Person überträgt Dateien in ihren Bereich in WLO, daraus wird
  der Teil `ablage`. Die Verzweigung `uebertragen` (`wenn_teil: ablage`) führt ohne Übertragung zu
  `ohne_ablage`.
- **`metadaten_frage`:** Die Rückfrage vor dem schreibenden Flow, mit der Grenze „ersetzt Titel,
  Beschreibung und Schlagworte (neue Version)“. Bei „Nein“ geht es direkt zum Lesen.
- **`metadaten`:**
  - Ein `auftrag` `edusharing.chatbot/node-metadata-write` mit `repo_schreibt: true`.
  - Die nodeIds kommen nur aus der Ablage desselben Vorgangs
    (`{$teil: ablage, liste: inhalte, wo: {stand: stored}, feld: node_id}`), dazu
    `language: de`.
  - Scheitert der Flow, sagt `metadaten_fehlt` das, und es geht mit den vorhandenen Angaben
    weiter.
- **`lesen`** (`metadaten_lesen` → Teil `metadaten`): Ohne Ergebnis endet der Ablauf in
  `ohne_metadaten`, mit der Frage nach der Anmeldung.
- **`entwurf`** (`agent`): Die KI ruft `ui_strukturentwurf` mit `aus_inhalten: true`. Ordner,
  Klassen, Formate und Jahre sind keine Punkte.
- **Ende:** wie oben, mit dem Satz, dass Sammlungen später kommen.

## Prüfung

- Beide Seeds sind aus (`aktiv: false`), und `pruefe()` gibt keinen Befund.
- **Testfälle in der Simulation**, alle grün:
  - aus einem Thema: drei Fälle (alles beantwortet, Zielgruppe getippt, ohne Entwurf);
  - aus eigenen Inhalten: vier Fälle (mit Metadaten bis zum Ende, Flow scheitert, ohne Flow
    und Lesen leer, nur erfasst).
- Die Upload-Antworten der Testfälle haben die volle Form des Manifests. Mit verkürzten Antworten
  verwirft die Simulation sie, wie der Betrieb.
- **Wächter:** `test_ablauf_beispiele`, `test_seed_waechter` und `test_config_textarea_hints`
  sind grün. Der Fragetext ist auf 114 Zeichen gekürzt, damit er unter der Grenze von 120 für
  einzeilige Felder bleibt. Breiter Satz mit Werksabgleich und Import: grün.
- Doku: `ablaeufe.md`, Abschnitt „Beispiele: Themenbaum mit Kernfragen“.

## Chat-Smoke (lokal, gpt-6-luna, Wegwerf-DB, danach gelöscht)

`themenbaum_aus_thema` lief, nur in der Wegwerf-DB eingeschaltet:

1. **Start** per Wendung.
2. **Kernfragen:** Die vier Fragen kommen als Chips, ohne LLM, je unter 2 s.
3. **Entwurf:** Nach einer getippten Antwort am KI-Schritt ruft die KI `ui_strukturentwurf`
   (28,8 s, 1 Werkzeug). Der Entwurf hatte Fach Physik, Stufe Sekundarstufe I, Thema „Optik
   mit Schwerpunkt Linsen und Brechung“ und 10 Punkte ohne Klassen oder Formate.

**Zwei Erkenntnisse daraus:**

- **Ein KI-Schritt antwortet erst auf den nächsten getippten Zug** (Paket A2b, so gebaut). Der
  Text des Schritts fragt darum nach Schwerpunkten, „oder einfach ‚Los‘“. Das ist zugleich die
  präzisierende Frage. Beide Seeds sind so angepasst, und die Wünsche gehen als `hinweise` an
  den Entwurf.
- **Die KI bekommt nur UI-Module, die das Widget meldet** (`environment.ui_module`). Das echte
  Widget meldet sie; ein eigener API-Client muss sie mitschicken, sonst antwortet die KI nur in
  Prosa.

## Damit erste Tests möglich werden (Betrieb)

- Im Studio die Abläufe einschalten. Für „aus einem Thema“ genügt „Ablauf ausprobieren“ in der
  Vorschau. „Aus eigenen Inhalten“ endet in der Probe in `ohne_ablage`, weil der Upload dort ein
  Trockenlauf ist; er braucht einen echten Lauf.
- **Aus eigenen Inhalten:**
  - Unter „Datei-Upload“ muss die Ablage in WLO an sein.
  - Der Flow muss in `B_API_JOBS_FLOWS` stehen.
  - Der B-API-Schlüssel muss ihn starten dürfen (F9).
  - Fehlt eines davon, scheitert der Auftrag sauber zu `metadaten_fehlt`. „Nein, so lassen“
    testet den Weg ohne Flow.

## Grenzen

- Kein Start aus der Sammlungsseite mit Startdaten `sammlung` (Klick-Prototyp). Kommt mit dem
  Schritt „Sammlungen anlegen“.
- Kein Limit je Job (N14). Ein Stapel hat bis zu 200 Dateien. `metadaten_lesen` liest 50, der
  Rest steht in `fehlend` (Querschnitts-Review F/T).
- Keine Struktur-Warnungen nach dem Leitfaden im Code (TB-4).
