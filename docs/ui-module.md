# UI-Module: Prinzip, Aufbau, neues Modul ergänzen

Entwicklerdoku für die UI-Module des Widgets (Paket U1). Sie erklärt, wie ein Modul gebaut ist,
wie ein Block in eine Antwort kommt, was beim Ergänzen von selbst geschieht und was Handarbeit
bleibt. Stand 2026-11-04 (U1-a … U1-h, U2 Themenbaum: Bestand und KI-Entwurf); alle Aussagen
sind am Quelltext geprüft.

| Vertiefung | Dokument |
|---|---|
| Plan mit allen Entscheiden und offenen Punkten | [`plans/2026-11-02-paket-u1-ui-module.md`](plans/2026-11-02-paket-u1-ui-module.md) |
| Paket U2: Bestand und Entwurf, Dienst, Brücke | [`plans/2026-11-04-paket-u2-themenbaum-entwurf.md`](plans/2026-11-04-paket-u2-themenbaum-entwurf.md) |
| Abläufe, die Module zeigen (Studio-Seite „Abläufe“, Querverweise Modul ↔ Ablauf) | [`plans/2026-11-09-ablaeufe-im-studio.md`](plans/2026-11-09-ablaeufe-im-studio.md) |
| Regeln für Modul-Autoren (kurz) | [`frontend/projects/ui-module/README.md`](../frontend/projects/ui-module/README.md) |
| Grafik: Einbindung und Nutzung | [interaktiv](architektur-grafiken/ui-module-einbindung.html) · [Bild (PNG)](architektur-grafiken/png/ui-module-einbindung.png) · [Quelle](architektur-grafiken/quellen/ui-module-einbindung.json) |
| Gesamtbild | [`architektur.md`](architektur.md) |
| Agent-Schleife | [`agent-modus.md`](agent-modus.md) |
| Evaluation mit UI-Modulen | [`../evals/README.md`](../evals/README.md#ui-module-paket-u1-g) |

---

## 1. Prinzip

Ein UI-Modul ist eine kleine Angular-Komponente, die das Widget in einer Bot-Antwort zeigt:
ein Dokument, eine Trefferliste, eine Auswahlfrage, einen Themenbaum. Die Antwort trägt dafür
**Blöcke** (`UiBlock`) im Feld `ui.ui_bloecke`; ein Block nennt Modul, Version, Daten und eine
Textfassung. Jedes Modul beschreibt sich in **einem Manifest** (`manifest.json`). Daraus
entstehen das Register im Widget, die Werkzeugbeschreibung für die KI, die Prüfung im Backend
und die Studio-Seite. Ein Modul **zeigt an** (`art: anzeigen`) oder **fragt ab** (`abfragen`,
die Antwort der Person geht in den nächsten Zug). Module greifen nie selbst nach außen: Drucken,
Links, Antworten und Nachladen laufen über einen **Host** je Block, der nur die Fähigkeiten aus
dem Manifest zulässt. Große Daten (Baum, Trefferliste) laufen nicht durch das Modell: Die KI
nennt nur Kennungen, das Backend holt die Daten über eine **Datenquelle**. Die meisten Module liegen
im einen Widget-Bündel; große oder seltene laden nach (§2.5: `ui_upload`, `ui_strukturabgleich`,
`ui_fortschritt`, `ui_strukturentwurf`, dazu das Debug-Panel als Widget-Teil). Die Grenze ist
**200 kB gzip** (Warnung ab 190 kB; Stand 2026-11-10 nach AS-8: 189,3 kB, gemessen mit
`node scripts/check-widget-budget.mjs`).

---

## 2. Aufbau

### 2.1 Ordner eines Moduls

`frontend/projects/ui-module/src/ui-<name>/` — Ordner mit Bindestrich, Modulname mit
Unterstrich (`ui-themenbaum` → `ui_themenbaum`, Klasse `UiThemenbaum`).

| Datei | Zweck |
|---|---|
| `manifest.json` | Vertrag des Moduls: Beschreibung für die KI, `eingabe`/`antwort` als JSON Schema, Fähigkeiten, Textfassung, Platz, Beispiele |
| `ui-<name>.component.ts` | Standalone-Komponente mit den Eingaben `daten` und `kontext`; Texte de/en im Modul |
| `ui-<name>.component.scss` | Stil nur über Widget-Tokens (`--mat-sys-*`, M3-Radien); die Gates `check:tokens`/`check:radii` scannen mit |
| `ui-<name>.component.spec.ts` | rendert **jedes Beispiel** des Manifests (Angular hat keine Fehlergrenze je Komponente) |
| `README.md` | wofür, Grenzen, Beispiel |
| weitere `*.ts` | eigene Hilfen ohne Angular, z. B. `themenbaum-zweige.ts`, `inhaltsrahmen.ts` |

Ordner ohne `ui-`-Präfix sind keine Module; das Register übergeht sie. Neben `_vertrag/` ist das
seit U2 **`_baum/`**, der gemeinsame Baum-Kern von Bestand und Entwurf (Tastenregel
`baum-tasten.ts`, Ansage `baum-ansage.ts`, SCSS-Mixin `_baum.scss`). Module importieren einander
nicht (ESLint); Gemeinsames gehört nach `_baum/` oder `_vertrag/`.

Daneben der gemeinsame Vertrag `src/_vertrag/` (nur mit Plan ändern):

| Datei | Inhalt |
|---|---|
| `manifest.schema.json` | JSON Schema jedes Manifests — die eine Quelle |
| `manifest.ts` | Lesetyp `UiModulManifest`, `ModulFaehigkeit` |
| `ui-block.ts` | `UiBlock`, `ModulKontext` (spiegelt `backend/src/boerdi/api/schemas_ui.py`) |
| `modul-host.ts` | Token `MODUL_HOST`, Schnittstelle `ModulHost` |
| `register.ts` | Token `UI_MODUL_REGISTER`, Laufzeit-Felder des Manifests |
| `modul-namen.ts` | Namen, die Shell und Studio brauchen (`INHALTSRAHMEN`, `LINKBOX`, `TREFFERLISTE`) |

`src/register.generated.ts` ist erzeugt (siehe §4).

### 2.2 Manifest

| Feld | Bedeutung |
|---|---|
| `name` | `^ui_[a-z0-9_]{2,40}$`; zugleich Werkzeugname für die KI und Schlüssel im Register |
| `version` | Hauptversion 1–99; nur erhöhen, wenn alte Daten nicht mehr passen (altes Widget zeigt dann die Textfassung) |
| `art` | `anzeigen` oder `abfragen` (dann ist `antwort` Pflicht) |
| `titel` | `{de, en?}`, je 2–60 Zeichen; Studio und Register |
| `beschreibung`, `wann`, `nicht_wann` | werden die Werkzeugbeschreibung (`WANN:`/`NICHT:`-Liste) |
| `agent` | `true` = darf als Werkzeug angeboten werden |
| `eingabe` | JSON Schema der Block-Daten; ohne Datenquelle zugleich die Werkzeug-Parameter. **Jedes Feld braucht eine `description`** — die KI liest sie |
| `antwort` | JSON Schema der Antwort (nur `abfragen`) |
| `datenquelle` | `{werkzeug, argumente[], vorgaben?}` oder `null`: die KI nennt nur `argumente`, `vorgaben` setzt das Backend fest und überschreibt Werte der KI |
| `dienst` (U2) | `{name, parameter}` oder `null`: das Backend **erzeugt** die Daten (`ui_module/dienst.py`); die KI sieht nur `parameter` (den Auftrag). Schließt `datenquelle` aus |
| `faehigkeiten` | `antworten`, `auftrag` (K1b), `drucken`, `herunterladen`, `hochladen` (U3-2c), `nachladen`, `oeffnen` — nur diese schaltet der Host frei |
| `vorgang` (V2) | `schreibt: [Teil…]` — was eine geprüfte Antwort im Vorgang hinterlässt; `liest: [Teil…]` — was der Dienst des Moduls serverseitig liest. Teile reisen nie durch das Modell; Werkzeuge bekommen sie per `{"$teil": "<name>"}` (Plan `docs/plans/2026-11-05-vorgang-und-ablaeufe.md`) |
| `textfassung` | `{vorlage, feld?}`: Rückfall, wo das Widget das Modul nicht kennt (`markdown`, `nummerierte_liste`, `link_liste`, `zusammenfassung`) |
| `darstellung` | `platz`: `oben` (Vorgabe, vor den Trefferboxen) oder `unten` (danach); `breit` siehe §7 |
| `laden` (U3-0) | `sofort` (Vorgabe: Angular-Komponente im Haupt-Bündel) oder `bei_bedarf`: rahmenloses Custom Element in einem eigenen Bündel, das das Widget erst beim ersten Block lädt (§2.5) |
| `beispiele` | 1–10 `{titel, daten, antwort?}` für Spec, Studio-Vorschau und Backend-Prüfung |
| `x-nur-system` (an einem Feld) | Werte, die nur das System setzt; gehen nicht an die KI (z. B. `ui_inhaltsrahmen.art`: `volltext`, `schreib_vorschau`) |

Das Backend prüft beim Laden jedes Manifest gegen das Schema, `eingabe`/`antwort` als gültiges
JSON Schema, `textfassung.feld` als Feld der Eingabe und jedes Beispiel gegen `eingabe` und
`antwort` (`backend/src/boerdi/ui_module/katalog.py`).

### 2.3 Komponente und Host

```ts
export class UiBeispiel {
  readonly daten = input.required<BeispielDaten>();   // laut manifest.eingabe
  readonly kontext = input.required<ModulKontext>();  // blockId, sprache, nurLesen, antwort, schriftSkala, anzeigeRegeln
  private readonly host = inject(MODUL_HOST);         // nur über den Host nach außen
}
```

`kontext().nurLesen` ist `true` bei `beantwortet` oder `veraltet`: nur zeigen, nichts auslösen.

| Host-Methode | Fähigkeit | Wirkung |
|---|---|---|
| `herunterladen(datei, mime, inhalt)` | `herunterladen` | Datei im Browser speichern |
| `drucken(titel, markdown)` | `drucken` | Druckansicht des Widgets (auch „Als PDF speichern“) |
| `link(url)` | `oeffnen` | `{href, hinweis}` mit Sitzungs-Kennung bzw. Warnung; nur `http(s)`, sonst wie ohne Fähigkeit leer |
| `aktion(name, …)` | `oeffnen` | `volltext`, `sammlung`, `lernpfad`, `alsEntwurf` (U2), `mehrLaden` der Shell |
| `antworten(daten, text)` | `antworten` | nächster Zug mit `ui_antwort` |
| `vormerken(daten \| null)` (U2) | `antworten` | die nächste **getippte** Nachricht nimmt `daten` als `ui_antwort` mit, solange der Block offen ist (Block wird `beantwortet` statt `veraltet`) |
| `zweig(nodeId)` | `nachladen` | Daten ohne Zug nachladen (heute nur Themenbaum); ohne Fähigkeit Ablehnung mit `status: 403` |
| `hochladen(datei, onFortschritt?)` | `hochladen` | Ein Dokument ohne Zug lesen lassen (U3-2c, `POST /api/ui/dokumente`); löst mit dem Befund auf, lehnt mit `status` und `code` ab |
| `ablegen(schritt)` | `hochladen` | Ein Schritt der Ablage im persönlichen Bereich (U3-3b, `POST /api/ui/ablage/*`), ohne Zug; `vorbereiten` bringt seit M6 die eigenen letzten Ablagen mit (`letzte`) |
| `auftrag(schritt)` | `auftrag` | K1b: `stand` fragt den Stand eines Ablauf-Auftrags ohne Zug (`POST /api/ui/auftrag/stand`, `{stand}`; 409 = kein wartender Auftrag); `abholen` lässt die Shell das Ergebnis im Zug holen (Direktaktion `ablauf_auftrag_pruefen`, ohne Nutzerblase) → `{gesendet}` |
| `markdown(text)`, `treffer()`, `beschaeftigt()` | immer | Darstellung; ohne `oeffnen` baut der Kontext von `treffer()` keine Adressen (`withBsid`/`externalLinkWarning` leer) |

Fehlt eine Fähigkeit, passiert nichts außer einer Warnung in der Konsole
(`frontend/projects/ui/src/ui-bloecke/block-modul-host.ts`).

`markdown()` hängt am Render-Cache der Shell: wechselt die Sprache oder kommen neue vertraute
Seiten dazu, rechnet ein `computed` darüber neu (`shell-render.ts`, Review U1 gesamt). Ob ein
Block sein Modul zeigt (Register, gleiche Hauptversion, Daten da), entscheidet eine Stelle
(`ui-bloecke/modul-darstellbar.ts`) — für den Platzhalter und für die Tore, die bisherige Boxen
(Trefferboxen, Webseiten-Box, Druckleiste) schweigen lassen; bei einer fremden Hauptversion
bleiben sie stehen.

### 2.4 Regeln je Antwort

- Höchstens **5 Blöcke**; Überzählige fallen mit Warnung weg (`domain/ui_bloecke.py`).
- Höchstens **ein offener abfragender** Block; ein zweiter Aufruf bekommt „Je Antwort nur eine
  Frage mit Auswahlfeld“.
- Je Block höchstens **256 000 Zeichen** Daten als JSON; nicht darstellbare Daten fallen weg.
- Fehlt das Modul im Register, passt die Hauptversion nicht oder fehlen die Daten, zeigt das
  Widget die **Textfassung** (`block.text`).
- Importe nur aus `_vertrag/` und Einzeldateien von `@boerdi/ui`, nie aus der Shell oder dem
  Sammel-Export (ESLint prüft das).
- Barrierefrei nach WCAG 2.2 AA, bedienbar ab 320 px, Texte de und en.

---

### 2.5 Nachgeladene Module (`laden: "bei_bedarf"`, Paket U3-0)

Das Widget ist eine Datei mit festem Budget (`check-widget-budget.mjs`, Warnung ab 190 kB gzip).
Selten gebrauchte oder große Module kommen deshalb **nicht** ins Haupt-Bündel, sondern in ein eigenes:

- **Quelltext:** `ui-<name>/ui-<name>.element.ts` statt der Komponente — ein rahmenloses Custom Element
  `boerdi-ui-<name>` (kein `@angular`-Import; das Bündel-Skript weist ihn ab). **Pflicht:** nur
  definieren, wenn der Name frei ist (`if (!customElements.get(name)) customElements.define(…)`) — ein
  Bündel kann zweimal laufen (zwei Widgets mit verschiedener API-Basis, Skript nach Fristablauf). CSS-Dateien werden als
  Text importiert und in den Shadow Root gesetzt. Styles nur über die M3-Tokens (`--mat-sys-*`, erben in
  den Shadow Root). **SCSS (seit Paket BU-2):** eine `ui-<name>.element.scss` übersetzt
  `npm run module:register` mit dem dart-sass des Projekts nach `ui-<name>.stil.generated.ts` (`STIL`,
  eingecheckt; `--pruefen` in CI meldet einen veralteten Stand). So nutzt ein Element dieselben
  SCSS-Bausteine wie die Komponenten (etwa `_baum/_baum.scss`) statt eines Nachbaus als Zeichenkette.
- **Widget-Teile ohne Manifest (seit Paket BU-3):** Selten gebrauchte Teile des Widgets, die kein
  UI-Modul sind (kein KI-Werkzeug, nicht im Register), liegen unter
  `frontend/projects/ui/src/nachgeladen/ui-<name>/ui-<name>.element.ts`. Bau, Index, SRI, Pfad und
  Stil-Erzeugung sind dieselben wie bei den Modulen. Ein Name darf nur einmal vorkommen. Das erste
  ist das Debug-Panel (`ui-debug-panel`, Hülle `ui/src/debug/debug-panel-huelle.component.ts`).
  **Begriffe im Widget (Querschnitts-Review Q-12):** „Vorgang“ ist die gespeicherte Arbeit einer
  Person (Liste „Meine Vorgänge“); „Ablauf“ ist, was darin läuft (Leiste); „Auftrag“ ist ein Job bei
  der b-api. „Fortsetzen“ heißt immer: in das Gespräch eines Vorgangs wechseln — die Leiste klappt
  dagegen nur „Ein“/„Auf“. Die Bot-Texte „Neues Vorhaben“ (beginnt einen neuen Vorgang) und
  „Arbeitsstand löschen“ (alle Vorgänge **und** das hochgeladene Dokument) bleiben bewusst.
  **Dev-Server:** `ng serve widget` bindet den leeren `nachlade-index.ts` ein, dort lädt kein
  nachgeladener Teil (Module zeigen ihre Textfassung, das Debug-Panel seinen Ladefehler). Zum
  Ausprobieren `npm run build:widget` (tauscht den Index per `fileReplacements`).
- **Vertrag** (`ui-module/_nachladen/element-vertrag.ts`): Der Platzhalter setzt am Element die
  Eigenschaften `daten`, `kontext`, `host` und `beschaeftigt` — bei jeder Änderung neu, am **selben**
  Element (eigener Zustand bleibt). `host` ist eine eingefrorene Brücke mit den Methoden des Block-Hosts
  **ohne** `markdown` und `treffer` (beide hängen an Angular); die Fähigkeiten aus dem Manifest gelten wie
  bei Komponenten. Das Element zeichnet sich bei jeder Zuweisung neu.
- **Register:** `npm run module:register` trägt den gemeinsamen Platzhalter
  (`_nachladen/nachlade-platzhalter.component.ts`) und den Element-Namen ein; nichts vom Modul landet im
  Haupt-Bündel.
- **Build:** `npm run build:widget` ruft zuerst `scripts/build-nachlade-module.mjs`: esbuild (`iife`,
  klassisches Skript wie das Widget) → `dist/widget-module/ui-<name>.<sha256-8>.js` und der Index
  `ui/ui-bloecke/nachlade-index.build.ts` (Datei + SRI `sha384`, **nicht eingecheckt**), den der Build per
  `fileReplacements` statt des leeren `nachlade-index.ts` einbindet. Budget: je Modul ≤ 20 kB gzip (seit U3-3b, vorher 15),
  zusammen ≤ 60 kB (`scripts/check-module-budget.mjs`, auch in CI).
- **Laden:** `ui/ui-bloecke/nachladen.ts` hängt beim ersten Block ein `<script>` mit `integrity` und
  `crossorigin="anonymous"` an; Adresse = API-Basis ohne `/api` + `/widget/module/<datei>`, jede Adresse
  **je Seite** einmal (auch bei zwei Widgets), Frist 10 s, nach einem Fehler darf ein späterer Block neu
  versuchen. Verlangt die Gastseite Trusted Types, geht die Adresse durch die Richtlinie
  `boerdi-ui-module` (eine je Seite), die nur gehashte Bündel unter `/widget/module/` zulässt. Scheitert etwas (Netz, SRI, CSP, kein Index-Eintrag), zeigt der Platzhalter
  die **Textfassung** des Blocks — wie bei einem unbekannten Modul.
- **Auslieferung:** `GET /widget/module/{datei}` (Backend `api/widget.py`): nur gehashte Namen aus
  dem Modul-Ordner, unveränderlich gecacht, CORS `*` (sonst prüft der Browser das SRI nicht),
  `nosniff`. Im Image ist das `widget_dist/module/` (das Dockerfile kopiert `dist/widget-module`
  dorthin); lokal zeigt `WIDGET_MODULE_DIR` direkt auf `frontend/dist/widget-module` — ein Ordner
  unter `dist/widget/browser` bräche die Einzeldatei-Schranke des Widget-Budgets. Die E2E-Harness muss
  die Bündel von dort mit CORS ausliefern (kommt mit dem ersten Modul, U3-1).
- **Einbettung mit strenger CSP:** `script-src` muss den Ursprung des Widgets erlauben (wie für das
  Widget selbst); Seiten, die nur Nonces oder Hashes zulassen, sehen die Textfassung.
- **Dev-Build, Tests, Studio:** der Index ist leer → Textfassung, solange niemand einen eigenen Lader
  setzt (Eingabe `nachladen` von `<boerdi-ui-bloecke>`).

## 3. Wie ein Block entsteht und ankommt

Drei Wege führen zu einem Block. Alle enden in `ui.ui_bloecke` der Antwort und im Verlauf.

**a) Die KI ruft ein Modul-Werkzeug** (`agent: true`, `ui_module/werkzeuge.py`)

- **Agent-Modus:** automatisch angeboten, wenn das Widget das Modul meldet
  (`environment.ui_module`) und das Studio es für den Agenten nicht abgeschaltet hat
  (`services/agent_tools.py`). Ein Widget von vor U1 meldet nichts und bekommt kein Modul.
- **Muster-Modus:** nur, wenn das Muster es unter `tools:` nennt, das Widget es meldet und es
  aktiv ist (`services/response_tool_selection.py`, U-F4). `phase3_modulate` trennt die Module
  als `ui_werkzeuge` von den MCP-Werkzeugen.
- Der Aufruf wird gegen `eingabe` geprüft; ein Fehler geht samt Pfad an die KI zurück.
- Anzeigend: Ergebnis „OK“, die Schleife läuft weiter. Abfragend: die Runde endet wie
  `respond_to_user`, ohne Schnellantworten (`services/agent_loop.py`,
  `services/tool_loop_module.py`).

**b) Abgeleitet an der API-Grenze** (`ui_module/abgeleitet.py`, `api/publikum.py`)

- `ui_trefferliste` aus `cards`, `query_metas` und `pagination`; `ui_linkbox` aus `web_links`.
  Live aus der fertigen Antwort, im Verlauf aus den gespeicherten Feldern.
- Das Muster wählt mit `ui_module: [ui_trefferliste, ui_linkbox]`; fehlt der Schlüssel, gelten
  alle, `[]` heißt keine. Im Agent-Modus gelten alle. Studio-Schalter wirken auch hier.
- Kennung = Hash aus Modul und Daten (siehe §7).

**c) Das System setzt den Block**

- `ui_inhaltsrahmen` entsteht im Trichter `services/turn_persist.py` aus jedem Dokument: dem
  Dokument-Werkzeug `ui_inhaltsrahmen` (Alias `zeige_dokument`), Volltext (M17),
  Lernpfad-Direktaktion und Schreib-Vorschau. Dokumente stehen vor allen anderen Blöcken.
- Die Direktaktion `show_collection_tree` baut einen Themenbaum ohne KI (für ältere Widgets).

**Antwortweg abfragender Module**

1. Das Modul ruft `host.antworten(daten, text)`; die Shell sendet einen Zug mit
   `ui_antwort {block_id, daten}` und `text` als Nutzerblase.
2. `services/ui_antwort.py` schließt im ersten Knoten die offene Frage der Sitzung und prüft
   die Antwort gegen Frage und `antwort`-Schema (`ui_module/antwort.py`). Ungültig → still
   verworfen, der Text zählt wie getippt. Bei offener Schreib-Abnahme zählt sie als NEIN.
3. Die geprüfte Antwort steht gerahmt vor der Nachricht an die KI; ohne Antwort die
   übergangene Frage selbst. Gespeichert als `_ui_antwort` an der Nutzernachricht.
4. Im Verlauf wird der Block `beantwortet` (mit Antwort) oder `veraltet`. Jeder andere Zug der
   Person macht offene Fragen im Widget sofort `veraltet` — auch Karten-Aktionen, „Weitere laden“
   und der Tour-Start; nicht Kontext-Ping, Tour-Tick und das Nachladen im Themenbaum (kein Zug).

**Datenquelle** (`ui_module/datenquelle.py`)

- Die KI sieht nur die `argumente` mit der Beschreibung aus dem MCP-Werkzeug-Katalog.
- Angeboten wird das Modul nur, wenn sein Werkzeug im Zug verfügbar ist (Studio, Sperren,
  Modus der Einbettung).
- Das Backend ruft das MCP-Werkzeug selbst (`call_mcp_tool_status`, mit Cache und Zugang),
  formt die Daten und prüft sie gegen `eingabe`. Die KI bekommt nur eine Quittung ohne Knoten.
- Nachladen ohne Zug: `POST /api/ui/themenbaum/zweig` (`api/ui_themenbaum.py`) — öffentlich,
  gedrosselt, ohne KI, nichts gespeichert. **Betrieb:** Ein Proxy vor dem Backend (etwa die B-API)
  muss `/api/ui/*` durchreichen; sonst scheitert das Aufklappen („nicht geladen“), während
  `/api/chat` geht. Die Konsole des Widgets nennt dann den Status
  (`boerdi: Unterthemen nicht geladen — StreamHttpError status=404`).

**Dienst** (U2, `ui_module/dienst.py`, `ui_module/aufruf.py`)

- Die KI sieht nur den Auftrag (`dienst.parameter`); der Aufruf wird dagegen geprüft, der Dienst
  erzeugt die Block-Daten, das Backend prüft sie gegen `eingabe` und die Deckel des Moduls.
- Asynchron wie die Datenquelle: die Schleifen fragen `werkzeuge.ist_asynchron` und rufen
  `aufruf.asynchron(name, args, Umgebung)`. Die `Umgebung` trägt den Token-Zähler des Zugs, das
  Fristende des Laufs und den mitgeschickten Entwurf der Person (`vorlage`).
- Heute ein Dienst: `strukturentwurf` (`services/strukturentwurf_dienst.py`) — top-down, Ebene 1 in
  einem Aufruf, Ebene 2 je Punkt parallel (höchstens 5 zugleich und höchstens die Hälfte des
  Anbieter-Deckels `LLM_MAX_CONCURRENCY`, eigene Platz-Frist bis zum Fristende), Ebene 3 nur bei
  `tiefe: 3`; was die Frist nicht schafft, wird `ausstehend`. Eine reine Funktion Auftrag → Struktur mit ersetzbarer LLM-Naht — später als Job
  hinter der B-API denkbar.
- Den letzten Entwurf merkt sich die Sitzung (`ui_module/strukturentwurf_merken.py`, nach der
  Sicherheitsprüfung, die 5 Züge nach dem Antwort-Zug): als `vorlage` späterer Züge und als Rahmen
  `[DEIN LETZTER ENTWURF]`. Die Brücke „Als Entwurf bearbeiten“ vergisst ihn; über 60 000 Zeichen
  ohne Beschreibungen/Schlagworte gemerkt, dann lehnt `erneut_zeigen` ab (Vertiefen geht).

---

## 4. Neues Modul ergänzen — Schritt für Schritt

1. **Gerüst anlegen** (in `frontend/`):
   ```bash
   npm run module:neu -- merkliste              # anzeigend
   npm run module:neu -- bewertung --abfragen   # abfragend, mit antwort-Schema
   ```
   Legt `ui-<name>/` mit Manifest, Komponente, SCSS, Spec (rendert jedes Beispiel) und README
   an und erzeugt danach das Register. Vorgaben im Manifest: `agent: false`,
   `datenquelle: null`, Textfassung `markdown` aus Feld `text`, ein Beispiel.
2. **Manifest ausfüllen:** Beschreibung, `wann`/`nicht_wann`, `eingabe` mit `description` je
   Feld, `faehigkeiten`, `darstellung.platz`, mehrere Beispiele. `agent: true`, wenn die KI es
   rufen soll.
3. **Komponente bauen:** Texte de/en im Modul (nach `kontext().sprache`), alles nach außen über
   den Host, `nurLesen` beachten.
4. **Register erneuern:** `npm run module:register` schreibt
   - `frontend/projects/ui-module/src/register.generated.ts` (statischer Import, Laufzeit-Felder),
   - `backend/src/boerdi/ui_module/manifeste.json` (alle Manifeste vollständig),
   - `backend/src/boerdi/ui_module/manifest.schema.json` (Kopie des Schemas).
5. **Studio-Spec ergänzen:** das Manifest in
   `frontend/projects/studio/src/app/views/ui-modul-vorschau.component.spec.ts` importieren und
   in `MANIFESTE` aufnehmen (der Test verlangt es).
6. **Prüfen:** in `frontend/` `npx ng test ui-module`, `npx ng test studio`,
   `npm run module:register -- --pruefen`, `npm run budget`, `npm run check:tokens` und
   `npm run check:radii`; in `backend/` `uv run pytest tests/test_ui_modul_katalog.py` und bei
   neuem Werkzeug die Tests, die die Modul-Menge festschreiben (§4.2).
7. **README** des Moduls schreiben, Änderungsnotiz unter `docs/aenderungen/`.

### 4.1 Automatisch erkannt und eingebunden

| Was | Wo | Bedingung |
|---|---|---|
| Komponente im Widget-Bündel, Register-Eintrag | `register.generated.ts` | nach `module:register` |
| Widget meldet das Modul (`environment.ui_module`) | `chat-shell.component.ts` (`Object.keys` des Registers) | — |
| Backend-Katalog samt Schema- und Beispiel-Prüfung | `ui_module/katalog.py` liest `manifeste.json` | — |
| Darstellung im Platzhalter, Host mit den Fähigkeiten, Textfassung als Rückfall | `ui-bloecke.component.ts` | Fähigkeit im Vertrag vorhanden |
| Werkzeug für den Agenten aus dem Manifest, Prüfung gegen `eingabe`, Block, Quittung | `werkzeuge.py`, `agent_loop.py` | `agent: true`, ohne Datenquelle |
| Werkzeug im Muster-Modus, Auswahl im Studio-Katalog `tools` | `response_tool_selection.py`, `config_choices.py` | Muster nennt es unter `tools:` |
| Abfragend: Ende der Runde, offene Frage, Status im Verlauf, Veralten im Widget | `agent_loop.py`, `antwort.py`, `fragen-status.ts` | Antwortform wie `ui_entscheidung` (§7) |
| Studio-Seite „UI-Module“: Liste, Angaben, Vorschau mit echter Komponente, Schalter | `GET /api/config/ui-module`, `ui-module.component.ts` | — |
| Werkzeug-Übersicht und Prompt-Vorschau des Agenten | `agent_tool_overview.py`, `agent_prompt_preview.py` | `agent: true` |
| Evaluation: gemeldet in jedem Lauf, `ui_any`/`ui_none`, Modul-Nutzung | `evals/run_golden.py`, `services/eval/modul_nutzung.py` | — |
| CI-Wächter: Register aktuell | `.github/workflows/ci.yml` | schlägt fehl, wenn `module:register` fehlt |

### 4.2 Handarbeit nötig

| Fall | Was zu tun ist |
|---|---|
| Jedes Modul | Studio-Spec-Import (Schritt 5); Texte de/en im Modul; README |
| Abgeleitetes Modul (ohne Werkzeug aus der Antwort) | Bauregel in `ui_module/abgeleitet.py`, Name in `namen.ABGELEITETE`; Shell-Weiche, damit die alte Darstellung schweigt |
| Modul mit Datenquelle | Umformer in `datenquelle._UMFORMER` (Ergebnis → Block-Daten, Textfassung, Quittung) wie `ui_module/themenbaum.py`; das Werkzeug muss in `services/mcp/tool_defs.py` stehen. Ohne Umformer wird das Modul nicht angeboten |
| Nachladen ohne Zug für ein anderes Modul | eigener Endpunkt wie `api/ui_themenbaum.py` und eigene Host-Kette; `zweig` ist auf den Themenbaum zugeschnitten |
| Neue Fähigkeit oder Host-Aktion | Schema-Enum, `ModulFaehigkeit`, `ModulHost`, `BlockModulHost` (Freigabe), `WidgetModulHost` und Shell-Naht, `VorschauModulHost` im Studio, Studio-Text `uiModule.faehigkeit.<name>` |
| Abfragendes Modul mit anderer Antwortform | eine Datei wie `ui_module/strukturentwurf_antwort.py` und die Weichen in `antwort.merke_frage`, `_grund`, `antwort_block`, `frage_block`, `sicherheits_text`, `frage_satz` (U2); Gold-Zug `ui_antwort` in `evals/run_golden.py` kennt `ui_entscheidung` (`waehle`) und `ui_strukturentwurf` (`uebernehmen`) |
| Modul mit Dienst (U2) | Dienst in `ui_module/dienst._DIENSTE` eintragen (Auftrag prüfen, erzeugen, Block, Quittung); ohne Eintrag wird das Modul nicht angeboten. Ruft der Dienst MCP-Werkzeuge, nennt das Manifest sie unter `dienst.braucht` (U4) — sonst umginge das Modul deren Sperre. Ein Werkzeug, das der Dienst nur nebenbei nutzt, prüft er selbst gegen `Umgebung.verfuegbar` (die im Zug angebotenen Werkzeuge; U5). Im Muster-Weg sind das nur die `tools:` des Musters |
| Vom System gesetztes Modul | Code an der Stelle, die den Block baut (wie `turn_persist` oder `themenbaum_aktion`) |
| Textfassung `link_liste` oder `zusammenfassung` | eigene Textfassung bauen; der allgemeine Weg kennt nur `markdown` (Text-Feld) und `nummerierte_liste` |
| Muster soll das Modul nutzen | `tools:` (Werkzeug) oder `ui_module:` (abgeleitet) im Muster-Seed bzw. im Studio; heute nennt kein Seed ein Modul |
| KI soll das Modul gezielt wählen | Werkzeugbeschreibung schärfen **und** eine Regel in den Master-Skill (`docs/skills/vorgehen-knapp.md`, live im Knoten) oder die Rollen-Vorgabe, dann Golden-Lauf. Die Beschreibung allein reichte für `ui_entscheidung` nicht (Golden-Lauf 2026-11-03: der Agent wählte das Auswahlfeld erst mit der Master-Skill-Regel) |
| Tests, die die Modul-Menge festschreiben | z. B. `test_config_choices.py`, `test_agent_prompt_preview.py`, Golden-/Eval-Tests mit Modullisten |
| Gold-Abläufe | `ui_any`/`ui_none` in `evals/ui-module-flows.yaml` von Hand |

---

## 5. Wo eingliedern

| Ebene | Datei/Ort | Wann anfassen |
|---|---|---|
| Modul | `frontend/projects/ui-module/src/ui-<name>/` | immer |
| Vertrag | `frontend/projects/ui-module/src/_vertrag/` | neue Fähigkeit, neues Manifest-Feld, neue Host-Methode |
| Register (erzeugt) | `register.generated.ts`, `backend/src/boerdi/ui_module/manifeste.json` | nie von Hand; `npm run module:register` |
| Widget-Platzhalter und Host | `frontend/projects/ui/src/ui-bloecke/` | neue Fähigkeit oder Aktion |
| Shell | `frontend/projects/ui/src/shell/chat-shell.component.{ts,html}` | Host-Naht, alte Darstellung abschalten |
| Backend-Katalog, Werkzeuge, Schalter | `backend/src/boerdi/ui_module/` | Datenquelle, Ableitung, Antwortform |
| Schleifen | `services/agent_loop.py`, `services/tool_loop_module.py` | nur bei neuem Aufrufmuster |
| Muster | `backend/seeds/03-patterns/*` (`tools:`, `ui_module:`) | Modul im Muster-Modus nutzen |
| Schalter | Studio „UI-Module“ → `display_rules.ui_module {aus, agent_aus}` | Betrieb |
| Öffentliche API | `api/schemas_ui.py`, `docs/api/*` | nur bei Vertragsänderung (OpenAPI neu erzeugen) |
| Studio-Vorschau | `views/ui-modul-vorschau*.ts`, `i18n/catalogue/ui-module.ts` | Spec-Import; neue Fähigkeit |
| Evaluation | `evals/ui-module-flows.yaml`, `evals/run_golden.py` | Abläufe; neue Antwortform |

---

## 6. Aktuelle Module

| Modul | Art | Entsteht durch | Datenquelle | Fähigkeiten | Platz | seit |
|---|---|---|---|---|---|---|
| [`ui_inhaltsrahmen`](../frontend/projects/ui-module/src/ui-inhaltsrahmen/README.md) | anzeigen | System (Trichter): Dokument-Werkzeug, Volltext, Lernpfad, Schreib-Vorschau | — | drucken, herunterladen | oben | U1-b |
| [`ui_linkbox`](../frontend/projects/ui-module/src/ui-linkbox/README.md) | anzeigen | abgeleitet aus `web_links` | — | oeffnen | unten | U1-c1 |
| [`ui_trefferliste`](../frontend/projects/ui-module/src/ui-trefferliste/README.md) | anzeigen | abgeleitet aus `cards`, `query_metas`, `pagination` | — | oeffnen | unten | U1-c2 |
| [`ui_entscheidung`](../frontend/projects/ui-module/src/ui-entscheidung/README.md) | abfragen | Modul-Werkzeug (`agent: true`) | — | antworten | oben | U1-d |
| [`ui_themenbaum`](../frontend/projects/ui-module/src/ui-themenbaum/README.md) | anzeigen | Modul-Werkzeug; Direktaktion `show_collection_tree` | `browse_collection_tree` (`depth: 2`, `maxResults: 31`) | oeffnen, nachladen | oben | U1-e, U1-h |
| [`ui_strukturentwurf`](../frontend/projects/ui-module/src/ui-strukturentwurf/README.md) | abfragen, **nachgeladen** (seit BU-2) | Modul-Werkzeug mit **Dienst** `strukturentwurf`; Direktaktion `edit_collection_as_draft` (Brücke aus dem Themenbaum); „Als Themenbaum-Entwurf übernehmen“ in `ui_upload` (`quelle: ordner`) | — | antworten, herunterladen | oben | U2 |
| [`ui_upload`](../frontend/projects/ui-module/src/ui-upload/README.md) | abfragen, **nachgeladen** (`laden: bei_bedarf`) | Modul-Werkzeug mit **Dienst** `upload_angebot` | — | antworten, hochladen, oeffnen | oben | U3-1, U3-2, U3-3 |
| [`ui_strukturabgleich`](../frontend/projects/ui-module/src/ui-strukturabgleich/README.md) | anzeigen, **nachgeladen** | Modul-Werkzeug mit **Dienst** `strukturabgleich` (ohne LLM; liest den Teil `draft`); mit `abdeckung: true` Lücken in ganz WLO | `browse_collection_tree` im Dienst (`depth: 2`, mit Inhaltszahlen; `dienst.braucht`); `count_wlo_content_matches` nur, wenn im Zug angeboten | oeffnen | oben | U4, U5 |
| [`ui_fortschritt`](../frontend/projects/ui-module/src/ui-fortschritt/README.md) | anzeigen, **nachgeladen** | nur der Ablauf-Treiber, wenn ein `auftrag`-Schritt startet (`agent: false`) | — | auftrag | oben | K1b, K2b (Abbrechen) |

**Zwei Anwendungsfälle, zwei Module (U2):** `ui_themenbaum` zeigt **nur Bestand** („Aus WLO“) —
die Knoten laufen nie durchs Modell. `ui_strukturentwurf` ist eine **neue** Gliederung („Entwurf
(KI)“ bzw. „Entwurf (aus WLO)“), bearbeitbar, herunterladbar, übernehmbar; ihr Stand geht kompakt
an die KI. Erkennung: Werkzeugbeschreibungen schließen sich aus, der Master-Skill regelt den
mehrdeutigen Fall („Themenbaum für <Fachportal>“ → Bestand + Schnellantwort „Neue Gliederung dazu
entwerfen“; „entwirf / gliedere / neue Struktur / Unterrichtsreihe“ → Entwurf).

**Ordner erfassen (U3-1):** `ui_upload` liest einen Ordner im Browser (Knopf oder Ablegen) und zeigt
ihn als Baum mit Dateizahlen; die Person setzt Rollen (Inhalt, Strukturdokument, ignorieren). Zurück
gehen nur Ordnernamen und Zahlen, nie Dateinamen; hochgeladen wird nichts. „Als Themenbaum-Entwurf
übernehmen“ formt die Ordner im Backend ohne LLM zu einem Strukturentwurf
(`ui_module/strukturentwurf_ordner.py`, `services/ordner_aktion.py`, Haken in `graph/nodes/preflight`
hinter derselben Sicherheitsprüfung wie Direktaktionen). Die Antwortformen abfragender Module stehen
seit U3-1 in einem Verzeichnis (`ui_module/antwort_formen.py`).

**Strukturdokument lesen (U3-2):** Ist in `ui_upload` ein Strukturdokument markiert und erlaubt es
das System (Studio „UI-Module → Hochladen“, Bereich `01-base/upload-config`; ohne WLO-Anmeldung nur
mit `dokument_ohne_anmeldung`), lädt das Modul genau diese Datei über die Host-Fähigkeit `hochladen`
an `POST /api/ui/dokumente`. Das Backend wandelt sie um (Kindprozess, Frist), gliedert sie, lässt
Übersicht und Anfang moderieren und legt Markdown + Gliederung an der Sitzung ab
(`dokument_uploads`, Frist nach letzter Nutzung, Aufbewahrungslauf); die Rohdatei bleibt nicht
liegen. Das Modul antwortet mit dem Befund und einem **Ziel** (heute `themenbaum`); der Rahmen
`[DOKUMENT DER PERSON …]` sagt der KI, `ui_strukturentwurf` mit `aus_dokument: true` zu rufen. Der
Dienst liest das Dokument serverseitig über einen Lader in der Umgebung (`services/dokumente/stand`):
Ebene 1 sieht Gliederung (≤ 8000) und Anfang (≤ 1500), Ebene 2 den Text der zugeordneten Abschnitte
(≤ 6000) — jeder solche Auszug geht vorher einmal durch die Moderation (beanstandet oder ohne Urteil
bei `MODERATION_FAILURE_MODE=closed` → kein Auszug; `services/strukturentwurf_auszug`); jeder Punkt trägt `abschnitte` und `fundstelle`, der Entwurf `quelle: dokument`.

`ui_inhaltsrahmen` ist im Studio fest (nicht abschaltbar); seine Anzeige steuert
`display_rules.inline_documents.enabled`.

---

## 7. Generisch und Kompromisse

**Voll generisch nach dem neuen Schema:** ein Feld `ui_bloecke` statt eines Felds je Fläche;
ein Platzhalter mit zwei Plätzen; Register und Backend-Katalog aus den Manifesten; Werkzeug
samt Prüfung aus dem Manifest für beide Maschinen; Host je Block mit Fähigkeiten aus dem
Manifest; Regeln je Antwort; Textfassung als Rückfall; Studio-Liste, -Vorschau und -Schalter;
Evaluation (`ui_any`/`ui_none`, Modul-Nutzung); CI-Wächter.

| Kompromiss | Warum | Ausweg / Plan |
|---|---|---|
| Alte Felder `cards`, `web_links`, `inline_documents`, `ui.dokumente` werden weiter gesendet bzw. bleiben im Vertrag (veraltet markiert) | Host-Ereignisse, `page_action`, Folgezug, Evals, ältere Widgets lesen sie (U-F5) | Wegfall je Feld nach Gleichwertigkeits-Liste; eigener Entscheid |
| Trefferliste ist ein Adapter um `result-groups`/`card-list` | gleiche Darstellung ohne Kopie; die Komponenten liegen in `@boerdi/ui` | später eigenständiges Modul |
| Abgeleitete Blöcke haben Hash-Kennungen, eindeutig nur je Nachricht | live und Verlauf sollen dieselbe Kennung haben | Aktionen nutzen die Nachrichten-ID (`nachrichtId`), nicht die Block-Kennung |
| Ableitung ist Code je Modul (`abgeleitet.py`) | jede Quelle (Karten, Links) hat eigene Regeln | bei neuen abgeleiteten Modulen bewusst ergänzen |
| Inhaltsrahmen fest, eigener Werkzeugweg | trägt Systemarten; Schreib-Vorschau muss vor einer Freigabe sichtbar sein | bleibt so (F-4) |
| Datenquelle kennt nur `browse_collection_tree`; Fehlertexte und Zählung sind auf den Baum zugeschnitten | erste und einzige Datenquelle | beim zweiten Fall verallgemeinern |
| Dienst-Verzeichnis kennt nur `strukturentwurf` (Auftrag, Fehlertexte, Frist im Dienst selbst) | erster Dienst | bei Kestra/B-API-Jobs eine zweite Umsetzung derselben Schnittstelle |
| Nachladen (`zweig`) und Endpunkt `/api/ui/themenbaum/zweig` nur für den Themenbaum | kleinste öffentliche Fläche ohne LLM (H-1) | allgemeiner Endpunkt erst bei Bedarf |
| Nachgeladene Unterthemen gelten nur bis zum Neuladen | Speichern hieße die Nachricht ohne Zug ändern (H-8) | Entscheid Nutzer offen |
| Antwortweg abfragender Module: eine Weiche je Modul in `ui_module/antwort.py` (U2: Entscheidung, Strukturentwurf) | zwei Antwortformen | beim dritten abfragenden Modul ein Verzeichnis der Formen |
| Allgemeine Textfassung nur für `markdown` und `nummerierte_liste` | Themenbaum und abgeleitete bauen ihre eigene | bei Bedarf weitere Vorlagen umsetzen |
| `darstellung.breit` wird nirgends ausgewertet | Vertrag vorbereitet, Größer-Knopf nicht angebunden | anbinden, sobald ein Modul es braucht |
| ~~Alle Module statisch im Haupt-Bündel~~ | erledigt: Nachladen seit U3-0 (§2.5), Widget-Teile ohne Manifest seit BU-3 | — |
| Studio-Vorschau-Spec importiert Manifeste von Hand | JSON-Import im Test; `module:neu` legt ihn nicht an | Gerüst-Skript erweitern |
| `tool_mode` am Zweig-Endpunkt kommt vom Aufrufer | Modus der Einbettung, keine Berechtigung; heute sperrt kein Modus `browse_*` | Sperren gegen Missbrauch sind Drosselung, Sitzungsprüfung, Studio-Schalter |
| Evaluation kann nicht klicken (Aktionen, Aufklappen) | Gold-Züge kennen nur Text und `ui_antwort` | Zug-Schlüssel `aktion` (U1-g, offen) |
| Kein Seed-Muster nennt Module in `tools:` oder `ui_module:` | Entscheid Nutzer je Muster (z. B. M03) | im Studio je Muster wählen |
| Gespeicherte Blöcke abgeschalteter Module bleiben im Verlauf | Verlauf ist Protokoll (F-2) | Widget-Regel „leere Daten → Textfassung“ bei Bedarf |
| Studio-Probelauf meldet keine Module | Probe zeigt keine Blöcke | Studio-Widget-Vorschau nutzt das echte Bündel |

---

## 8. Häufige Fallen

- **Register vergessen:** Ohne `npm run module:register` fehlt das Modul im Widget und im
  Backend; die CI bricht mit `--pruefen` ab. `register.generated.ts` und `manifeste.json` nie
  von Hand ändern.
- **Fehler beim Rendern** reißt das Widget mit (kein Error-Boundary je Modul). Deshalb rendert
  die Spec jedes Beispiel — gute Beispiele sind Pflicht.
- **Injector je Block** bleibt stabil (Kennung + Modul). Ein neuer Injector erzeugt das Modul
  neu und löscht dessen Zustand (etwa „mehr anzeigen“).
- **Abgeleitete Kennung** ist über Nachrichten nicht eindeutig: Aktionen über die
  Nachrichten-ID führen, nie über `block_id` suchen.
- **Modul-Aufrufe nach `respond_to_user`:** Die Schleifen behandeln Module in einer Vorrunde.
  Scheitert eine Datenquelle, wird die Antwort derselben Runde verworfen — sonst stünde „hier
  ist der Baum“ ohne Baum da.
- **Server meldet keine Kürzung oben:** Der Themenbaum holt `maxResults: 31` für 30 gezeigte
  Knoten; der 31. zeigt „es gibt mehr“.
- **Muster ohne `mcp` in `sources`** bekommt die Regel „Rufe KEINE Tools auf“; die KI ruft das
  Modul dann kaum.
- **`ui_module:` im Muster** nimmt nur abgeleitete Module; `tools:` weist Inhaltsrahmen und
  abgeleitete ab.
- **Studio-Vorschau:** Links fängt sie in der Capture-Phase ab, weil Kacheln ihren Klick
  anhalten. Neue klickbare Elemente in der Vorschau prüfen.
- **DB-Tests ohne Postgres** werden übersprungen; Katalog- und Muster-Tests mit Postgres laufen
  lassen, bevor man „alles grün“ meldet.
- **Altes Widget-Bündel im Cache:** neues Modul erst nach Neubau des Bündels und hartem
  Neuladen sichtbar.

---

## 9. Weiterlesen

- Plan: [§3 Aufbau](plans/2026-11-02-paket-u1-ui-module.md#3-aufbau),
  [§6 Entscheide](plans/2026-11-02-paket-u1-ui-module.md#6-entscheide-nutzer-2026-11-02),
  [§14 Entscheidung](plans/2026-11-02-paket-u1-ui-module.md#14-u1-d-entscheidung-im-einzelnen-tests-zuerst-je-teil-ein-review),
  [§15 Themenbaum](plans/2026-11-02-paket-u1-ui-module.md#15-u1-e-themenbaum-im-einzelnen-tests-zuerst-review-danach),
  [§16 Studio](plans/2026-11-02-paket-u1-ui-module.md#16-u1-f-studio-seite-im-einzelnen-tests-zuerst),
  [§17 Evaluation](plans/2026-11-02-paket-u1-ui-module.md#17-u1-g-ui-module-in-der-evaluation-tests-zuerst),
  [§18 Aufklappen](plans/2026-11-02-paket-u1-ui-module.md#18-u1-h-unterthemen-im-baum-aufklappen-tests-zuerst).
- Änderungsnotizen: [`aenderungen/2026-11-02-paket-u1a.md`](aenderungen/2026-11-02-paket-u1a.md)
  bis [`aenderungen/2026-11-03-paket-u1h.md`](aenderungen/2026-11-03-paket-u1h.md).
- Offene Punkte: [`offene-befunde-und-todo.md`](offene-befunde-und-todo.md) (Abschnitte „Paket U1“).
