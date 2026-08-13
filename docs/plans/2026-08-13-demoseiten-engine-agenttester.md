# Demoseiten, Engine-Umschalter, Agent-Tester (2026-08-13)

Fünf Befunde des Nutzers, drei Pakete. Log-Dokument: Schnitt, Entscheidungen,
je Scheibe die Belege.

## 1. Die Befunde, und was der Code dazu sagt

| # | Befund | Nachgeprüft |
|---|---|---|
| 1 | „Die Demoseiten sehen alle gleich aus" | **Stimmt.** `/widget/`, `/inline`, `/classic` setzen alle `position="bottom-right"` ohne `embed-mode` → dreimal derselbe schwebende Knopf. Sie trennen nur `show-debug-button`, `show-language-buttons`, `inline-result-grouping` — und alle drei stehen ohnehin im Bedienpult jeder Seite. Wirklich anders ist nur `/frameless`. |
| 2 | „inline sollte eingebettet starten" | Der Modus dafür existiert: `embed-mode="frameless"` + Host-Container (heute `/frameless`). |
| 3 | „klassisch = geschlossene Blase, öffnet bei Klick" | Das ist der Vorgabe-Modus (`panel` + `initial-state="collapsed"`) — heute auf `/widget/`. |
| 4 | „Agent-Loop testen, im Studio keine Einstelloption" | Der Bereich `01-base/engine` existiert (Vorgabe `pattern`), aber `curated-views.ts` listet ihn **nicht** → nur über „Alle Bereiche" erreichbar. Und das Widget schickt `X-Boerdi-Engine` **nicht** — im Chat ist die Agent-Schleife heute nur global umstellbar. |
| 5 | „Seite zum Testen des Endpunkts" | `/api/agent` hängt an `require_agent_caller`. Das Studio schiebt `/studio/api/*` → `/api/*` und spritzt den Schlüssel serverseitig ein — von dort erreichbar, ohne neue Anmeldung. |
| 6 | „Trigger übergeben, um eine Sammlung/Themenseite/… zu simulieren" | Das Widget hat einen URL-Wechsel-Melder (`host-bridges._checkUrlChange` → `onUrlChange` → `refreshPageContext(true)` → `shell.onSpaContextChange`). Ein Simulator kann also den **echten** Pfad benutzen. |

## 2. Entscheidungen des Nutzers (2026-08-13)

1. **Demoseiten:** Übersicht + drei echte Modi. Alle vier Pfade bleiben (eingefrorener
   OpenAPI-Vertrag — Umwidmen ist billig, Löschen wäre Drift).
2. **Engine:** Studio sichtbar machen **und** Host-Attribut am Widget.
3. **Agent-Tester:** Studio-Ansicht.

## 3. Zuschnitt

### Paket D — Demoseiten

| Pfad | Vorher | Nachher |
|---|---|---|
| `/widget/` | schwebender Knopf | **Übersicht** — kein Widget, sondern was die drei Varianten zeigen, das Einbau-Schnipsel, der Verweis auf die Attributliste im Studio |
| `/widget/classic` | `inline-result-grouping="false"` | **Schwebende Blase**, geschlossen, öffnet bei Klick (der Vorgabe-Einbau) |
| `/widget/inline` | Knopf ohne Mikro/Debug | **Eingebettet** — `embed-mode="frameless"` im Seiten-Container, offen |
| `/widget/frameless` | rahmenlos im Container | bleibt: **rahmenlos pur**, die Lektion „der Gastgeber muss Höhe geben" |

Der A/B `inline-result-grouping` geht **nicht** verloren: er ist ein Schalter im
Bedienpult jeder Seite. Genau deshalb kostet das Umwidmen von `/classic` nichts.

**D2 — Kontext-Simulator.** Neues Feld im Bedienpult: Seitentyp + Wert →
`page-context` als JSON am Element plus `auto-context="false"`.

Zwei Entscheidungen dazu:

* **Serverseitig aus dem Query-String**, nicht per JavaScript nach dem Boot.
  Damit ist die Simulation neuladefest, teilbar, und der Kontext steht schon
  beim Aufbau — also greift der Pfad `context_open_initial`, der dem „ich lande
  auf einer Sammlungsseite" am nächsten kommt. Es ist zugleich das Prinzip, das
  `widget_demo_controls` schon trägt („serverseitig gebaut, nicht per JS").
* **`auto-context="false"`**, wie in der Studio-Vorschau und aus demselben Grund:
  sonst trüge der Detektor `page_url`/`page_host` der Demoseite bei, und das
  Backend entschiede „eigene Seite oder fremde" gegen eine Adresse, die mit dem
  simulierten Typ nichts zu tun hat.

Der Wert wird **validiert**, nicht nur maskiert: UUID für Sammlung/Inhalt, Slug
für Themenseite, Längendeckel für Suche, `http(s)` für „andere URL". Ein
öffentlicher Endpunkt, der einen Query-Parameter in HTML spiegelt, braucht die
Prüfung am Rand — Maskierung allein ist die zweite Verteidigungslinie, nicht die
erste.

**Dateischnitt** (beide Bestandsdateien liefen sonst über die 300):
`widget_demo_layout.py` (Hülle: Stile, Ereignis-Spiegel, Seitenschablone) ·
`widget_demo_html.py` (welche Seite was zeigt) · `widget_demo_controls.py`
(Attribut-Schalter, unverändert) · `widget_demo_context.py` (Kontext-Simulator).

### Paket E — Engine

* **E1 Studio:** `01-base/engine` in eine kuratierte Ansicht + Katalog-Schlüssel.
* **E2 Widget:** Host-Attribut `engine` → Kopfzeile `X-Boerdi-Engine`. Vertrag
  +1 Attribut (Element, Pinning-Test, `widget-contract-data.ts`,
  `reference-widget.ts`). CORS braucht nichts: `allow_headers=["*"]`.
* **E3 Bedienpult:** Schalter `engine` auf den Demoseiten.

### Paket A — Agent-Tester

Studio-Ansicht „Agent testen": Formular über `AgentRequest` (instruction,
collection_id, node_ids, result_schema, write_mode, locale) → `/studio/api/agent`
→ Text, Ergebnis-JSON, `stop_reason`, Iterationen, gerufene Werkzeuge.

## 4. Belege je Scheibe

### D — Demoseiten (Backend, Python)

**Rot zuerst.** 6 Zusicherungen für den neuen Zuschnitt geschrieben, Lauf: `6 failed,
41 passed` — jede aus dem richtigen Grund.

**Ein falscher Grün-Fall dabei gefunden und behoben.** Der Helfer `_element_tag`
teilte den Seitentext an `<boerdi-chat` — und traf einen **JS-Kommentar** im
Bedienpult (dort steht der Text ``` `<boerdi-chat>` ```, die Erklärung, warum das
Pult über dem Element sitzt). Er lieferte einen leeren Tag, und jede Zusicherung
„Attribut X steht NICHT im Tag" war damit geschenkt. Jetzt ein Ausdruck auf das
mehrzeilige Start-Tag; danach `6 failed` (statt 5) — die siebte Zusicherung biss.

**Störungsprobe** (Implementierung absichtlich zurückgedreht, Test muss fallen):

| Störung | Ergebnis |
|---|---|
| Prüfung im Kontext-Simulator abgeschaltet | 10 failed |
| `auto-context` nicht auf `false` | 1 failed |
| `/inline` wieder als schwebender Knopf | 2 failed |

**Vertrag.** `test_route_inventory_matches_spec_5_1` blieb still (kein Pfad kam
hinzu oder fiel weg); das eingefrorene Dokument driftete durch die drei
`?kontext=&wert=`-Parameter und wurde neu erzeugt. Beim Vergleich mit dem
git-Index fiel auf: der **Index** kennt `/api/agent` noch gar nicht — der
Arbeitsbaum war schon voraus (Paket A3 vom 2026-08-12, nie nachgestellt). Der
Diff gegen den Index trägt deshalb beides; meine Änderung sind exakt die drei
`kontext`- und drei `wert`-Parameter.

**Dateischnitt** (alle unter 300): `widget_demo_context.py` 248 ·
`widget_demo_controls.py` 246 · `widget_demo_html.py` 220 ·
`widget_demo_layout.py` 199 · `widget.py` 176.

### E — Engine

* **E1** `01-base/engine` sitzt in der neuen kuratierten Ansicht `agent`.
* **E2** Host-Attribut `engine` → Kopfzeile `X-Boerdi-Engine`, durchgereicht über
  `StreamChatOptions.extraHeaders` (Strom **und** Rückfall-POST — sonst wechselte
  ein Zug bei einem Stream-Abbruch still die Maschine). CORS brauchte nichts:
  `allow_headers=["*"]`.
* **E3** Schalter „Maschine" im Bedienpult jeder Demo-Seite.

Fünf neue Zusicherungen in `chat-api-engine.spec.ts` pinnen, was auf dem **Draht**
landet, nicht welche Methode gerufen wurde — dieselbe Linie wie
`stream-client-auth.spec.ts`: Strom, Rückfall, „ohne Wahl gar keine Kopfzeile",
Normalisierung, Zurückstellen.

Vertrag +1 Attribut, an allen drei Stellen nachgezogen: Pinning-Test (24 → 25),
`widget-contract-data.ts`, `reference-widget.ts` (de + en).

### A — Agent-Tester

Studio-Ansicht `agent` mit zwei Abschnitten: Bereich `01-base/engine` + Panel
`agent-tester`. Formular-Logik pur in `agent-request.ts` (10 Zusicherungen,
prüfbar ohne DOM — Muster `preview-embed.ts`); Transport in
`core/agent-api.service.ts` über `/studio/api/agent`, der Schlüssel bleibt
serverseitig.

**Sechs Registry-Wächter schlugen an** — genau ihre Aufgabe, wenn eine Ansicht
dazukommt. Alle sechs faithful nachgezogen statt weichgeklopft: `OHNE_ALT_VORBILD`
(mit Begründung), Paket-Erlaubnisliste (`+D2`), Katalog-Zähler (20 → 21),
gerenderte Panel-Liste, und die Zusicherung „kuratierte Ansicht ⇒ Paket 9-4"
wurde zur Erlaubnisliste `['9-4','D2']` — der Kern (jeder Schnitt MUSS in der
Registry stehen) blieb.

### Abnahme

| Prüfung | Ergebnis |
|---|---|
| `ruff check src tests` | All checks passed |
| `pytest -q` | **3263 passed**, 4 skipped (2:29) |
| `eslint .` | 0 |
| `check:tokens` · `check:a11y` · `check:radii` | grün |
| `ng test ui` / `widget` / `studio` | **762 / 56 / 971** |
| `ng build studio` · `widget:build-widget` | sauber |
| Widget-Budget | roh 89,6 % · gzip 89,5 % von §5.5 |

**5052 Tests grün** (+41 gegenüber dem Stand von heute Mittag).

## 4b. Review-Durchlauf (2026-08-13 abends)

Ein Review über dasselbe Paket fand sieben Punkte; alle behoben.

| # | Befund | Behebung |
|---|---|---|
| 1 | **MAJOR** `architecture-reference.component.spec.ts:90` zählte `HOST_ATTRIBUTES` auf 24 — mit `engine` sind es 25. **Die Studio-Suite war rot.** | Zähler auf 25, Kommentar ergänzt, `toContain('engine')` dazu. |
| 2 | `_ERWARTUNG[kind_id]` war ein Direktzugriff: ein sechster `ContextKind` ohne Eintrag → `KeyError` → HTTP 500, und nur bei ungültiger Eingabe. | Ein Test je Typ (`test_every_kind_can_say_what_it_expected`), über das **Verhalten**, nicht über die private Tabelle. |
| 3 | `widget-contract-data.ts` sagte „16 der 19 Vorgabewerte … nur drei"; tatsächlich 20 von 25, fünf. | Zahlen berichtigt. |
| 4 | Das Agent-Formular deckte 5 der 6 Felder ab; `allow_curation` fehlte. | Haken dazu (Vorgabe an). Nur die **Abweichung** reist mit — `allow_curation: false`, nie `true`. |
| 5 | `aria-live` sass auf der `<section>`, die das `@if` erst mit ihrem Inhalt einfügt — so wird sie unzuverlässig angesagt. | Dauerhafte Region `.at-live` mit **einem Satz** (Muster `.egs-live`); der Ergebnisblock verlor sein `aria-live`. |
| 6 | „acht der 23 Host-Attribute" im Pult-Docstring. | **Zurückgenommen in korrigierter Form.** Der Satz steht im Präteritum: 23 war die Vertragsgrösse zur Zeit von U8. Auf 25 zu heben wäre falsch gewesen — jetzt „der damals 23". |
| 7 | `_element` interpolierte roh; maskiert wurde in einem **anderen** Modul (`_as_json_attr`). Korrekt, aber die Pflicht lag über einer Modulgrenze. | Maskierung wandert nach `_element`, für **jeden** Wert; `element_attributes` liefert rohes JSON. Die Zusicherung wanderte mit — sie prüft jetzt die gerenderte Seite. |

**Störungsproben** (Implementierung zurückgedreht, Test muss fallen):

| Störung | Ergebnis |
|---|---|
| Ein `_ERWARTUNG`-Eintrag entfernt | 1 failed |
| `escape()` aus `_element` entfernt | 3 failed (alle Live-Seiten) |

**Ein eigener Fehlgriff dabei.** Die erste Fassung der Ausbruch-Zusicherung
verbot die Zeichenkette `onerror=` im ganzen Tag — sie war rot bei richtigem
Code: der Text steht sehr wohl dort, als Teil des Suchbegriffs zwischen zwei
`&quot;`, und dort ist er Text. Die Zusicherung prüft jetzt, dass der Angriff
**vollständig im einen Attribut** steckt: bleibt draussen etwas übrig, hat sein
Anführungszeichen das Attribut vorzeitig beendet.

Dazu ein Satz im Kontext-Hinweis: „Anwenden" lädt neu, die Pult-Schalter
beginnen danach wieder bei den Vorgaben der Seite.

**Abnahme nach dem Durchlauf:** ruff pass · **pytest 3270 passed**, 4 skipped ·
eslint 0 · tokens/a11y/radii grün · **ui 762 / widget 56 / studio 973** ·
`ng build studio` sauber. Zusammen **5061 Tests** (+9). Am Widget-Bundle hat
dieser Durchlauf nichts geändert — nur Studio, Backend und Tests.

## 5. Nutzer-Domäne (nicht durch Tests ersetzbar)

* Commit, Docker-Build (3 Images), Deploy.
* **Seed-Import**, damit `01-base/engine.yaml` in der DB steht — ohne ihn zeigt
  die neue Studio-Ansicht einen leeren Bereich.
* Der frisch gebaute Widget-Bundle muss mit ins Backend-Image (sonst kennt das
  ausgelieferte Widget das Attribut `engine` nicht).
* Live-Probe: Agent-Schleife im Chat gegen die Muster-Engine, und der
  Kontext-Simulator gegen echte Sammlungs-/Themenseiten-IDs.
