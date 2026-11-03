# Paket U1 — UI-Module als Werkzeuge (Vorschlag 2026-11-02)

Stand: **Entscheide U-F1…F5 am 2026-11-02 (§6); U1-a … U1-f umgesetzt und reviewt (§9–§16; Review-Befunde U1-f behoben 2026-11-03).** DB-Tests mit Postgres nachgeholt: [`aenderungen/2026-11-03-paket-u1-db-tests.md`](../aenderungen/2026-11-03-paket-u1-db-tests.md). Auftrag (Nutzer 2026-11-02): „Wir setzen erstmal die UI-Widgets um.“ Ziel: modular erweiterbar, von der KI wie Werkzeuge nutzbar (Agent über Werkzeugbeschreibungen, Muster-Modus über feste Einbindung im Pattern), Ein- und Ausgaben beschrieben, in Angular wie das Widget, verträglich mit Anmeldung und den übrigen Abläufen, getrennt entwickelbar in einem eigenen Ordner mit fester Struktur, für Menschen gut erweiterbar, optisch aus einem Guss mit dem Widget. Neben den Sammlungs-Modulen auch die bestehenden Flächen: Inhaltsrahmen mit Druck und Download, Treffer- und Linkbox. Prüffrage: mehr als ein Modul je Antwort?

Bezug: Konzept `2026-10-24-ablaeufe-und-ui-module.md` (§6.5 Manifest und Element-Vertrag, §16.12 Startpunkt). Dieser Plan ersetzt dort die Auslieferung „ohne Framework“ (§16.12): Module werden **Angular-Komponenten im selben Build** wie das Widget.

## 1 Ausgangslage (am Code geprüft)

| Baustein | Heute | Beleg |
|---|---|---|
| Inhaltsrahmen mit Drucken | feste Komponente `boerdi-inline-documents`, Feld `inline_documents` bzw. `ui.dokumente`, Drucken über `print/` | `frontend/projects/ui/src/inline-doc/`, `print/print-utils.ts` |
| „UI als Werkzeug“ | gibt es schon einmal: das virtuelle Agent-Werkzeug `zeige_dokument` liefert eine Box statt Text | `backend/src/boerdi/domain/inline_documents.py:103`, `services/agent_tools.py` (`include_dokument`) |
| Treffer, Linkbox, Themenseite | feste Komponenten `result-groups`, `card-list`, `web-links`, `swimlanes`, je ein `@if` in der Shell | `ui/src/grouping/`, `ui/src/cards/`, `shell/chat-shell.component.html:82-173` |
| Muster-Modus | Pattern-Frontmatter mit `output_mode` (`generate`, `clarify`, `rerender`), Ausgabe über feste Felder | `domain/config_models/patterns.py:45`, `services/response_tool_selection.py` |
| Öffentlicher Teil der Antwort | `UiInfo` (`query_metas`, `web_links`, `dokumente`, `topic_page_view`, `prepared_write`) | `api/schemas_ui.py` |
| Bündel | eine Datei, 167 von 175 kB gzip; Angular Material schon enthalten | `frontend/scripts/check-widget-budget.mjs` |
| Größer-Knopf | `sizeToggleVisible` / `sizeToggle` am Widget | `shell/chat-shell.component.ts:198-206` |

Folge: Jede neue Fläche kostet heute Code an fünf Stellen (Feld in `ChatResponse`, `UiInfo`, Nachrichtentyp, Shell-`@if`, Verlauf). U1 ersetzt das durch **ein** allgemeines Feld und **einen** Platzhalter.

## 2 Entscheidungen (Empfehlung)

| # | Frage | Empfehlung | Begründung |
|---|---|---|---|
| U-E1 | Technik der Module | **Angular-Standalone-Komponenten** in einer eigenen Bibliothek `frontend/projects/ui-module/`, gebaut **im selben Widget-Bündel** | keine zweite Laufzeit (die frühere Sorge galt einem getrennten Paket); Material, Tokens, i18n, Druck-Helfer werden mitbenutzt; dieselben Gates (`check:tokens`, `check:radii`, Kontrast) greifen |
| U-E2 | Auslieferung | erst **im Haupt-Bündel**, Größe messen; große oder seltene Module später als **nachgeladene Chunks** vom eigenen Ursprung (ändert die CI-Regel „eine Datei“ zu „eine Einbettungs-Datei“) | kleine Module kosten geschätzt 2–6 kB gzip; Messung in U1-a entscheidet K11 |
| U-E3 | Ein Feld für alle | `ui_bloecke: UiBlock[]` an Antwort, Strom-`result`, `UiInfo` und gespeicherter Nachricht; alte Felder bleiben befüllt, bis alle Widgets umgestellt sind | ältere Widgets und `/api/agent` funktionieren weiter |
| U-E4 | Mehrere Module je Antwort | **ja**: beliebig viele anzeigende (Deckel 5), **höchstens ein abfragendes** offenes Modul je Antwort | Suche = Trefferliste + Linkbox; Material = Inhaltsrahmen + „Passt das so?“; Befund + Entscheidung. Zwei offene Fragen zugleich wären mehrdeutig |
| U-E5 | Einbinden durch die KI | Agent: Module mit `agent: true` werden virtuelle Werkzeuge (Verallgemeinerung von `zeige_dokument`). Muster-Modus: feste Einbindung je Pattern (`ui_module:`) und Modul-Werkzeuge, wenn sie in `tools:` des Patterns stehen (U-F4) | deterministisch im Muster-Modus, frei im Agent-Modus |
| U-E6 | Große Daten | Manifest-Feld `datenquelle`: Die KI nennt nur Kennungen, das Backend holt die Daten (MCP `structuredContent`, das heute verworfen wird) und füllt das Modul | Bäume und Trefferlisten laufen nicht durch das Modell |
| U-E7 | Anmeldung | Module bekommen **keine** Zugangsdaten; alles, was nach außen geht, läuft über einen **Modul-Host-Dienst** der Shell (Angular-DI): antworten, Link öffnen, drucken, herunterladen. Antworten gehen als normaler Chat-Zug mit dem bestehenden Zugangsblock | dieselben Regeln wie heute; Schreiben bleibt an Freigabe und Anmeldung gebunden |

## 3 Aufbau

### 3.1 Ordner je Modul (feste Struktur)

```
frontend/projects/ui-module/src/
  _vertrag/                     # gemeinsamer Vertrag, nicht anfassen ohne Plan
    modul-host.ts               # Dienst MODUL_HOST: herunterladen() (U1-a); drucken() U1-b, antworten() U1-d
    ui-block.ts                 # Typen UiBlock, ModulKontext
    manifest.ts, register.ts    # Typen, Token UI_MODUL_REGISTER
    manifest.schema.json        # JSON Schema für jedes manifest.json
  register.generated.ts         # vom Skript erzeugt: Name → Laufzeit-Manifest + Komponente (statisch importiert)
  ui-inhaltsrahmen/
    manifest.json               # Beschreibung, Ein-/Ausgabe, KI-Nutzung (siehe 3.2)
    ui-inhaltsrahmen.component.ts
    ui-inhaltsrahmen.component.scss
    ui-inhaltsrahmen.component.spec.ts
    README.md                   # für Menschen: wofür, Grenzen, Beispiel
  # Beispieldaten stehen im Manifest (`beispiele`), eigene Texte de/en in der Komponente;
  # Ordner in Angular-Schreibweise (ui-inhaltsrahmen), Modulname mit Unterstrich (ui_inhaltsrahmen).
  ui-trefferliste/ …
  ui-linkbox/ …
  ui-entscheidung/ …
  ui-themenbaum/ …
```

Ein Skript `npm run module:neu -- <name>` legt das Gerüst an; `npm run module:register` erzeugt `register.generated.ts` (im Bündel nur Name, Version, Art, Titel, Fähigkeiten, Darstellung) und im Backend `boerdi/ui_module/manifeste.json` samt Kopie des Schemas. Beides ist versioniert; die CI prüft mit `--pruefen`, dass es aktuell ist, das Backend prüft Manifeste und Beispiele gegen das Schema — **eine Quelle** für Frontend, Werkzeugbeschreibung und Studio.

### 3.2 Manifest (Ein- und Ausgabe, KI-Nutzung)

```json
{
  "name": "ui_entscheidung", "version": 1, "art": "abfragen",
  "titel": { "de": "Entscheidung", "en": "Choice" },
  "beschreibung": "Lässt die Person zwischen festen Möglichkeiten wählen, einzeln oder mehrfach.",
  "wann": ["Antwortmöglichkeiten sind bekannt und überschaubar"],
  "nicht_wann": ["Freitext", "mehr als 8 Möglichkeiten", "Baumstrukturen (ui_themenbaum)"],
  "agent": true,
  "eingabe": { "type": "object", "required": ["frage", "optionen"], "properties": { … } },
  "antwort": { "type": "object", "required": ["gewaehlt"], "properties": { … } },
  "datenquelle": null,
  "faehigkeiten": [],
  "textfassung": { "vorlage": "nummerierte_liste", "antwort_aus_text": "nummer_oder_text" },
  "darstellung": { "breit": false }
}
```

- `eingabe` / `antwort`: JSON Schema (Draft 2020-12), geprüft im Backend (vor dem Senden, nach der Antwort) und in den Vertragstests.
- `datenquelle` (anzeigende Module mit großen Daten): `{ "werkzeug": "browse_collection_tree", "argumente": ["nodeId", "depth"] }` — dann zeigt das Werkzeug der KI nur diese Argumente.
- `faehigkeiten`: was das Modul vom Host braucht, z. B. `["drucken", "herunterladen", "oeffnen"]`; nur das wird freigeschaltet.
- `textfassung`: Rückfall, wenn das Widget das Modul nicht kennt (ältere Widgets, `/api/agent`).
- `darstellung.breit`: das Modul schlägt die breite Ansicht vor (vorhandener Größer-Knopf).

### 3.3 Komponenten-Vertrag

```ts
@Component({ selector: 'ui-entscheidung', standalone: true, … })
export class UiEntscheidung implements UiModul<Eingabe, Antwort> {
  readonly daten = input.required<Eingabe>();      // gegen manifest.eingabe geprüft
  readonly kontext = input.required<ModulKontext>(); // sprache, nur_lesen, beantwortet?, block_id
  private readonly host = inject(ModulHost);        // antworten(), drucken(), herunterladen(), oeffnen(), t()
}
```

Die Shell rendert alle Blöcke über **einen** Platzhalter `<boerdi-ui-bloecke>` mit `NgComponentOutlet` (Eingaben per `ngComponentOutletInputs`). Fehlt ein Modul im Register oder passt die Hauptversion nicht, erscheint die Textfassung. Eine Fehlergrenze je Komponente kennt Angular nicht: Wirft ein Modul beim Rendern, geht der Fehler an den `ErrorHandler` des Widgets. Darum prüft die Spec jedes Moduls alle Beispiele seines Manifests (Pflicht im Gerüst ab U1-b). Zustand `beantwortet` = nur lesend mit der gegebenen Antwort; Wiederherstellen aus dem Verlauf wie heute die Dokumente.

### 3.4 Backend

- `boerdi/ui_module/katalog.py` (U1-a): Manifeste laden und prüfen. U1-b: Werkzeugbeschreibung daraus bauen (Name, Beschreibung + wann/nicht_wann, Parameter = `eingabe` bzw. nur die `datenquelle`-Argumente).
- Agent: `build_agent_tools(include_module=…)` legt die Modul-Werkzeuge an, **nur** für Module, die das Widget meldet (`environment.ui_module`: Namen + Versionen) — ein altes Widget bekommt keine Werkzeuge, die es nicht zeigen kann. Anzeigende Module: Ergebnis `{status: ok, block_id}`, die Schleife läuft weiter. Abfragende: beenden die Schleife wie `respond_to_user`, die Antwort kommt im nächsten Zug als Werkzeug-Ergebnis zurück.
- Daten-Prüfung (U1-b): beim Werkzeugaufruf gegen `eingabe` (`katalog.daten_fehler`); ein Fehler geht als Werkzeug-Ergebnis an die KI zurück, damit sie korrigiert. Beim Speichern prüft `regeln_anwenden` nur Größe, Anzahl und offene Abfragen.
- `zeige_dokument` wird zu `ui_inhaltsrahmen` (alter Name als Alias, bis die Seeds umgestellt sind).
- Muster-Modus: Pattern-Frontmatter `ui_module: [{ modul: ui_trefferliste, quelle: suche }, { modul: ui_linkbox, quelle: web_links }]`; `domain/result_delivery` füllt die Blöcke aus den vorhandenen Ergebnissen. Studio-Formular bekommt die Auswahl aus dem Modul-Katalog.
- `ui_antwort { block_id, daten, text }` an der Anfrage; geprüft gegen `antwort`, `text` wird Nutzerblase. Freigaben bleiben beim bestehenden Schreibweg (Zustimmungsprüfung, gemerkte Argumente).
- MCP-Client: `structuredContent` von Lesewerkzeugen behalten, nur für Datenquellen, nie ins Modell.

### 3.5 Gestaltung

Module nutzen die Bausteine und Tokens der `ui`-Bibliothek (Material-Knöpfe, `--mat-sys-*`, Radien der M3-Skala) und laufen **im Shadow-DOM des Widgets** (kein eigenes). Gemeinsame Kleinteile (Kopfzeile mit Icon und Aktionen, Aktionsknopf, Leerzustand, Fehlerzustand) liegen in `_vertrag/bausteine/`, damit jedes Modul gleich aussieht. Pflicht: bei 320 px nutzbar, Tastatur, WCAG 2.2 AA, de und en.

## 4 Erste Module

| Modul | Art | Woher | Ein / Aus |
|---|---|---|---|
| `ui_inhaltsrahmen` | anzeigen | aus `inline-doc` + `print`; **neu: Download** als Markdown, PDF über den Druckdialog (U-F3) | ein: titel, art, markdown · aus: – |
| `ui_trefferliste` | anzeigen | aus `result-groups` / `card-list` | ein: treffer (Datenquelle Suche) · aus: – |
| `ui_linkbox` | anzeigen | aus `web-links` | ein: links[] · aus: – |
| `ui_entscheidung` | abfragen | neu | ein: frage, optionen · aus: gewaehlt[] |
| `ui_themenbaum` | anzeigen, später wählen | neu, Logik aus dem MCP-Widget `browse` nach Angular übertragen | ein: struktur (Datenquelle Baum) · aus (wählen): knoten_id |

Später: `ui_freigabe`, `ui_fortschritt`, `ui_befund`, `ui_profil`, `ui_aufgaben`; `ui_upload` als Fähigkeit der Seite.

## 5 Schritte (je eigene Änderungsnotiz, kleine Commits)

| Schritt | Inhalt | Nachweis |
|---|---|---|
| U1-a Vertrag + Gerüst | Bibliothek, `_vertrag`, Manifest-Schema, Skripte `module:neu` / `module:register`, Platzhalter mit Textfassung, `ui_bloecke` in Antwort/Verlauf | Vertragstests; Bündelgröße gemessen |
| U1-b Inhaltsrahmen | `ui_inhaltsrahmen` aus der heutigen Box, Download dazu; `zeige_dokument` → Modul-Werkzeug | gleiche Darstellung wie heute (Screenshot-Vergleich), Druck, Download |
| U1-c Treffer + Linkbox | `ui_trefferliste`, `ui_linkbox`; Muster-Modus über `ui_module:` im Pattern | Suche im Muster- und Agent-Modus zeigt beide Module in einer Antwort |
| U1-d Entscheidung | `ui_entscheidung`, `ui_antwort`, Freitext-Zuordnung | Agent ruft das Modul, nächster Zug bekommt die Antwort |
| U1-e Themenbaum | `ui_themenbaum` mit Datenquelle `browse_collection_tree`, `structuredContent` behalten | Baum ohne Modell-Tokens für die Knoten |
| U1-f Studio | Seite „UI-Module“: Liste, Vorschau mit Beispielen, Schalter aktiv / für den Agenten | Studio-Tests |

Jeder Schritt: Schritt 0 `/better-coding-workflow` und `/better-coding-frontend`, Tests zuerst, Review, Widget-Bündel neu bauen.

## 6 Entscheide (Nutzer 2026-11-02)

| # | Entscheid |
|---|---|
| U-F1 | **Eigene Bibliothek** `frontend/projects/ui-module/` (Übersicht, eigene Tests, klare Grenze). |
| U-F2 | Budget: Haupt-Bündel bis **200 kB gzip** (Warnung ab 190 kB, roh entsprechend ~690 kB); was darüber hinausgeht oder selten gebraucht wird, wird nachgeladen. Begründung in §7. |
| U-F3 | Inhaltsrahmen: **Markdown und PDF**; PDF über den Druckdialog des Browsers („Als PDF speichern“) mit eigener Druckvorlage, keine PDF-Bibliothek im Bündel. DOCX später. |
| U-F4 | Muster-Modus: Module **fest eingebunden** (`ui_module:` im Pattern) **und** als Werkzeuge nutzbar, aber **nur, wenn sie in der Werkzeugliste des Patterns stehen** (`tools:`); die Module erscheinen dafür im Werkzeug-Katalog des Studios. |
| U-F5 | Alte Felder (`inline_documents`, `web_links`, Trefferkarten, Themenseite …) fallen weg, **sobald die Module alle ihre Funktionen erfüllen**; dafür je Feld eine Gleichwertigkeits-Liste (Darstellung, Druck, Verlauf, Gastseiten-Ereignisse, ältere Widgets). |

## 7 Budget: warum 200 kB gzip

- Heute 167 kB gzip (572 kB roh). +33 kB gzip entsprechen rund +110 kB roh.
- Laden: +33 kB sind auf einer mobilen 4G-Verbindung etwa 0,1–0,2 s, beim zweiten Besuch nichts (Cache).
- Ausführen: der größere Teil der Kosten. Auf einem mittleren Handy rechnet man grob 1–1,5 ms Parse- und Startzeit je kB roher JavaScript-Datei, also +110–170 ms beim ersten Öffnen.
- Beides bleibt unter dem, was Menschen als Verzögerung wahrnehmen, solange das Widget wie heute erst nach dem Laden der Seite startet. Darüber wächst es spürbar, und jedes weitere Modul verteilt seine Kosten auf alle Besucher, auch die, die es nie sehen.
- Darum: kleine, häufige Module (Entscheidung, Linkbox, Inhaltsrahmen) ins Haupt-Bündel; große oder seltene (Themenbaum, Freigabe, Fortschritt) bei Bedarf nachladen. Gemessen wird in U1-a, mit Startzeit des Widgets vor und nach.

## 8 Offene Fragen (Nutzer)

Alle am 2026-11-02 beantwortet, siehe §6 (U-F1…F5).

## 9 U1-a im Einzelnen (Aufgaben, Tests zuerst)

Ziel: Vertrag und Transport stehen, noch ohne fertiges Modul. Ein Testmodul in den Specs beweist den Weg.

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| a1 | Backend: `UiBlock` (block_id, modul, version, art, daten, text, status, antwort) und `UiInfo.ui_bloecke` | `api/schemas_ui.py` | Modell weist falsche Modulnamen, Arten, Status ab |
| a2 | Backend: Regeln je Antwort — höchstens 5 Blöcke, höchstens ein offenes abfragendes; Überzählige fallen mit Warnung weg | `domain/ui_bloecke.py` | Deckel, ein Abfragendes, Reihenfolge bleibt |
| a3 | Backend: `TurnContext.ui_bloecke`; `turn_persist` speichert sie als `_ui_bloecke` im Debug-Block und setzt sie live an `ui`; `publikum` liest sie zurück (Verlauf) und behält sie in `antwort_fuer` | `graph/state.py`, `services/turn_persist.py`, `api/publikum.py` | Antwort trägt die Blöcke; Verlauf stellt sie her; kaputte Einträge fallen weg, der Verlauf lädt |
| a4 | Backend: Modul-Katalog liest `ui_module/manifeste.json`, prüft jedes Manifest gegen `manifest.schema.json` und jedes Beispiel gegen `eingabe` | `ui_module/katalog.py` | ungültiges Manifest → Fehler mit Pfad; Beispiele passen |
| a5 | Frontend: Bibliothek `projects/ui-module` (angular.json, Pfad-Alias `@boerdi/ui-module`, Test-Ziel, Gates `check:tokens`/`check:radii` scannen mit) | `angular.json`, `tsconfig.json`, `package.json`, Gate-Skripte | `ng test ui-module` läuft |
| a6 | Frontend: Vertrag `_vertrag/` — Typen `UiBlock`, `ModulKontext`, `UiModulManifest`; Token `UI_MODUL_REGISTER` (Vorgabe: erzeugtes Register); Token `MODUL_HOST` mit `herunterladen()`; `oeffnen()`, antworten und drucken folgen mit den Modulen, die sie brauchen (Texte wählt das Modul über `kontext().sprache`) | `projects/ui-module/src/_vertrag/` | Typprüfung, Register-Token |
| a7 | Skripte: `module:register` erzeugt `register.generated.ts` (statische Importe, kein Nachladen) und `manifeste.json` für Frontend und Backend; `module:neu -- <name>` legt das Gerüst an | `frontend/scripts/module-*.mjs` | Register-Skript gegen Beispielordner; Backend-Test: Kopie = Quelle |
| a8 | Shell: `<boerdi-ui-bloecke>` rendert je Block das registrierte Modul (`NgComponentOutlet`), sonst die Textfassung (`text`); beantwortet = nur lesend; Platz: nach dem Inhaltsrahmen, vor den Schnellantworten | `projects/ui/src/ui-bloecke/`, `shell/chat-shell.component.html` | Testmodul erscheint; unbekanntes Modul zeigt Text; Wiederherstellen aus dem Verlauf |
| a9 | Budget nach U-F2: 200 kB gzip / 690 kB roh, Warnung ab 190 kB; drei Stellen gemeinsam (angular.json, Budget-Skript, Spezifikation §5.5); Größe vorher/nachher (§10); Startzeit misst U1-b mit dem ersten echten Modul | `angular.json`, `scripts/check-widget-budget.mjs`, Spec | Budget-Skript mit Fixture |
| a10 | Vertrag OpenAPI neu erzeugen (Feld `ui.ui_bloecke`), Vertragszusätze | `docs/api/*` | Vertragstest |

## 10 Stand U1-a (2026-11-02)

Umgesetzt a1–a10. Bündel vorher 571,92 kB roh / 166,78 kB gzip, nachher 579,33 kB roh / 169,59 kB gzip (+2,8 kB gzip für Vertrag, Platzhalter und Host; noch kein Modul).

Unabhängiger Review: kein hoher Befund, sieben mittlere — alle behoben:

| Befund | Behebung |
|---|---|
| Daten, die sich nicht als JSON darstellen lassen, brachen den Zug | `regeln_anwenden` misst über `model_dump_json`; nicht darstellbare Blöcke fallen mit Warnung weg |
| Verlauf nahm Blöcken leere `daten`/`text` (`exclude_defaults` wirkt verschachtelt) | Blöcke im Verlauf vollständig; das Widget nimmt fehlende Felder als leer |
| Blob-Adresse beim Herunterladen sofort freigegeben | Freigabe nach 30 s |
| „Fehlergrenze“ im Plan versprochen, nicht gebaut | §3.3 ehrlich beschrieben; Absicherung über Specs mit allen Beispielen |
| README versprach Prüfung der Blockdaten | Prüfung kommt beim Werkzeugaufruf in U1-b (§3.4); README sagt das |
| Katalog prüfte `eingabe`/`antwort` nicht als JSON Schema | `check_schema`; dazu `textfassung.feld` muss in `eingabe` stehen |
| Reste der alten Budget-Zahlen (CI-Schritt, Kommentar) | angeglichen |

Dazu aus den niedrigen: Obergrenze vor der Abfrage-Regel geprüft (die Warnung nennt den richtigen Grund), Register sortiert nach Codepunkten und verträgt ein BOM, `Type<unknown>` statt `$any`, Lint-Regel gegen Importe aus Shell und Sammel-Export in `projects/ui-module`.

Offen (niedrig, bewusst später): `status` erscheint in OpenAPI als nullbar; Vorrang eines abfragenden Blocks, wenn mehr als fünf kommen; offene Abfragen im Verlauf werden erst mit U1-d „veraltet“; frühe Antworten (Krise, Ablehnung) laufen nicht über `turn_persist` und tragen keine Blöcke — für U1-b/c prüfen.

## 11 U1-b im Einzelnen (Entscheide Nutzer 2026-11-02, Tests zuerst)

**Entscheide:** (1) Dokumente reisen ab U1-b **als `ui_bloecke`** (Modul `ui_inhaltsrahmen`), die Funktionen des Ist-Stands ziehen mit um. (2) Das Werkzeug heißt **`ui_inhaltsrahmen`**; `zeige_dokument` wird als Alias weiter angenommen (gespeicherte Rollen-Vorgaben, live abgelegte Master-Skills). Geprüft 2026-11-02: außerhalb von boerdi-chat setzt kein Repo im Arbeitsbereich auf den Namen auf (MCP-Server, Quellenpanel, MD-Editor, ALT-badboerdi: 0 Treffer).

**Leitlinie:** Alle Dokument-Boxen laufen weiter in einen Trichter (`turn_persist`), egal woher sie kommen (Werkzeug, geratene M09–M11-Box, Volltext M17, Schreib-Vorschau, Direktaktionen). Der Trichter macht daraus `ui_inhaltsrahmen`-Blöcke, vor allen übrigen Blöcken (Dokumente gehen bei der Obergrenze nicht verloren). Ein eigener Weg „Modul-Werkzeug → Block“ für weitere Module kommt mit U1-c, wenn es ein zweites Modul gibt.

### U1-b1 Modul im Frontend (Review danach)

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| b1-1 | Manifest `ui_inhaltsrahmen`: `eingabe` = `titel` (≤160), `art` (die 10 Werkzeug-Arten + `volltext`, `schreib_vorschau`; letztere setzt nur das System), `markdown`; `textfassung` = `markdown`; Beschreibung aus `inline_documents._BESCHREIBUNG`; Fähigkeiten `drucken`, `herunterladen`; Beispiele je eine Art mit Liste, Tabelle, Link | `ui-module/src/ui-inhaltsrahmen/manifest.json` | Katalog-Test (Backend) lädt es; Drift-Wächter |
| b1-2 | `ModulHost` um `drucken(titel, markdown)` und `markdown(text): SafeHtml` erweitern; `WidgetModulHost` nutzt `printMarkdownDocument` und den Render-Seam der Shell; `<boerdi-ui-bloecke>` bekommt `translate` und `schriftProzent` (aus `displayRules.inline_documents`) | `_vertrag/modul-host.ts`, `ui/src/ui-bloecke/*` | Host druckt mit Titel/Markdown; Schriftgröße als CSS-Variable |
| b1-3 | Komponente `UiInhaltsrahmen`: Aussehen der heutigen Box (gleiche Klassen `.inline-document*`, Tokens, Schriftskala), Symbol und Bezeichnung je Art (alle 12, de/en im Modul), Knöpfe „Drucken / PDF“ und „Als Markdown herunterladen“ (Dateiname aus dem Titel, `text/markdown`), `nurLesen` ändert nichts (Box ist nur anzeigend) | `ui-module/src/ui-inhaltsrahmen/*` | Spec rendert **jedes Beispiel** des Manifests; Drucken/Herunterladen rufen den Host; Tastatur und Namen der Knöpfe |
| b1-4 | Shell: eine Weiche `hatDokumentBox` (alte Box oder `ui_inhaltsrahmen`-Block) hält beide Druckleisten fern | `ui/src/print/print-gates.ts`, `shell/chat-shell.component.html` | keine zweite Druckleiste unter einem Block |
| b1-5 | Register erzeugen, Bündel messen, Bildvergleich alte Box ↔ Modul (Playwright mit gemockter Antwort) | — | Budget-Gate; Bildvergleich |

**Stand U1-b1 (2026-11-02):** umgesetzt. Bündel 586,62 kB roh / 171,77 kB gzip (vorher 579,36 / 169,61). Bildvergleich (`e2e/inhaltsrahmen.spec.ts`): gleiche Rahmen-, Titel- und Textstile wie die alte Box; neu ist der Download-Knopf, die Kopfzeile ist durch die 24-px-Zielfläche der Knöpfe (WCAG 2.5.8) rund 2 px höher. Dazu: `ModulKontext.schriftSkala`, Host `drucken()`/`markdown()`, `hatDokumentBox` für die Druckleisten, Gerüst-Spec rendert jedes Manifest-Beispiel (`resolveJsonModule` in den Specs der Bibliothek).

**Review U1-b1 (2026-11-02):** kein kritischer, ein hoher Befund, sieben mittlere, drei kleine.
- **Behoben:**
  - Der gekürzte Titel hatte 161 statt höchstens 160 Zeichen; er wäre ab b2 an der Prüfung gescheitert. Der Kürzungs-Hinweis zählt jetzt zum Deckel.
  - Ein Drift-Wächter vergleicht Arten und Titel-Deckel zwischen Manifest und `inline_documents.py`.
  - Die Systemarten sind maschinenlesbar markiert (`x-nur-system`).
  - Unsichere Art-Namen wie `constructor` oder Nicht-Texte fallen sauber zurück.
  - Ein Block ohne `daten` zeigt die Textfassung.
  - Der Download-Anker hängt beim Klick im Dokument (Firefox).
  - Neu ist ein Tastatur-Test im E2E.
  - Unter den Blöcken stehen wieder 8 px Abstand wie früher.
  - Zwei Kleinigkeiten in Specs sind bereinigt.
- **Verschoben nach U1-d:** Der Host bietet heute jedem Modul alle Methoden an; die Fähigkeiten aus dem Manifest werden noch nicht durchgesetzt. Mit „antworten“ in U1-d kommt die erste Fähigkeit mit Wirkung nach außen; dann bekommt jeder Block einen eigenen Host, der nur die angegebenen Fähigkeiten zulässt.

### U1-b2 Backend und Leser (Review danach)

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| b2-1 | Werkzeug aus dem Manifest: `ui_module/werkzeuge.py` baut die Funktionsbeschreibung (Name, `beschreibung` + `wann`/`nicht_wann`, Parameter = `eingabe` ohne Systemarten) und prüft Argumente (`daten_fehler`) nach der Aufbereitung je Modul (Inhaltsrahmen: Art-Rückfall, Kürzen wie heute) — ein Fehler geht als Werkzeug-Ergebnis an die KI | `ui_module/werkzeuge.py`, `domain/inline_documents.py` | Schema = Manifest; falsche Argumente → Fehlertext mit Pfad; zu lang → gekürzt, nicht abgelehnt |
| b2-2 | Umbenennen `zeige_dokument` → `ui_inhaltsrahmen` in Agent-Schleife, Muster-Werkzeugschleife, Auswahl, Übersicht, Vorschau, Spur; Alias angenommen | `services/agent_loop.py`, `tool_loop.py`, `agent_tools.py`, `response_tool_selection.py`, `agent_tool_overview.py`, … | beide Namen werden angenommen, angeboten wird nur der neue |
| b2-3 | Trichter: `turn_persist` macht aus allen Dokumenten `ui_inhaltsrahmen`-Blöcke (vor den übrigen), `inline_documents` bleibt leer; Anzeige-Regel `inline_documents.enabled=false` hängt wie heute an den Text; `_dokumente` (Folgezug-Kontext) bleibt | `services/turn_persist.py` | je Herkunft ein Block; Reihenfolge; Schalter aus → Text; Verlauf stellt Blöcke her |
| b2-4 | Leser umstellen: Golden/Eval (`idoc` zählt Inhaltsrahmen-Blöcke, Inhalt aus `daten.markdown`), Studio-Probe, Widget-Wiederherstellung nach Abbruch (`ui.dokumente` nicht mehr doppelt) | `evals/*.py`, `services/eval/runner.py`, Studio `agent-probe`, `antwort-aus-verlauf.ts` | je Leser ein Test |
| b2-5 | Texte: Rollen-Vorgabe, Master-Skill-Vorlagen `docs/skills/*`, Studio-Referenztexte, Doku; OpenAPI neu (`inline_documents`, `ui.dokumente` als veraltet markiert, Felder bleiben) | `config_models/engine.py`, `docs/skills/*`, Studio i18n, `docs/api/*` | Vorlagen-Tests, Vertragstest |

**Stand U1-b2 (2026-11-02):** umgesetzt.
- **Werkzeug:** Es entsteht aus dem Manifest (`ui_module/werkzeuge.py`). Systemarten und `x-`-Schlüssel gehen nicht an die KI.
- **Prüfung:** Der Aufruf wird erst aufbereitet, dann gegen `eingabe` geprüft (`inline_documents.dokument_annehmen`); ein Fehler geht samt Feldern an die KI.
- **Name:** `ui_inhaltsrahmen` wird angeboten, `zeige_dokument` als Alias in beiden Schleifen angenommen.
- **Gemeinsame Texte:** Fehler- und Quittungstexte beider Schleifen stehen jetzt an einer Stelle.
- **Trichter:** `turn_persist` und die drei Selbstbauer (Volltext M17, Lernpfad-Direktaktion, Schreib-Vorschau bei unklarer Zustimmung) liefern Inhaltsrahmen-Blöcke. Dokumente stehen vor den übrigen Blöcken; im Verlauf und live gilt dieselbe `block_id`. Ein Wächter-Test verhindert neue `inline_documents=`.
- **Leser:** Golden-Lauf und Eval-Runner (`dokument_boxen`, liest auch das alte Feld für ältere Backends), Studio-Probe, Widget-Wiederherstellung (keine doppelte Box).
- **Texte:** Rollen-Vorgabe, Master-Skill-Vorlagen, Studio-Referenztexte, Agent- und Eval-Doku; die Studio-Schema-Attrappe ist neu erzeugt.
- **OpenAPI:** `inline_documents` und `ui.dokumente` sind als veraltet markiert, die Felder bleiben.
- **Bewusst offen:** `meta` der Volltext-Box (Knoten, Quelle, gekürzt) reist im Block nicht mit; das Widget zeigte es nie, die Kürzung steht im Begleitsatz. Die drei Selbstbauer speichern keine `_ui_bloecke` für den Verlauf — wie bisher bei ihren Boxen.

**Review U1-b2 (2026-11-02):** kein kritischer, ein hoher, zwei mittlere, drei kleine Befunde — behoben:
- **Hoch:** In der Agent-Schleife griff der Alias nicht. Die Prüfung „nur Angebotenes läuft“ wies `zeige_dokument` ab, bevor der Name erkannt wurde, und der Test verdeckte das, weil seine Hilfe den alten Namen mit anbot. Jetzt zählt ein früherer Name vor der Prüfung als `ui_inhaltsrahmen`. Die Test-Hilfe bietet wie der Betrieb nur den neuen Namen an, und ein Gegentest belegt: Ohne Angebot öffnet der Alias nichts.
- **Mittel:**
  - Der Fehlertext nennt jetzt das fehlende Feld.
  - Die Prüfung gegen das Manifest ist als Drift-Wächter beschrieben und hat einen eigenen Test.
  - Der Trichter deckelt den Titel auch für System-Boxen; unbekannte Arten fallen auf `dokument` zurück. Jeder Block besteht so die Prüfung gegen das Manifest (Test je Art).
- **Klein:**
  - Kommentare und Doku stehen auf dem neuen Namen.
  - Der Modulname liegt einmal im Vertrag (`INHALTSRAHMEN`).
  - Die Werkzeug-Aufbereitung lässt Feldnamen mit `x-` stehen und streicht leere Aufzählungen.
- **Bereits vorher vorhanden, offen:** Bei `inline_documents.enabled=false` wird der Inhalt erst nach dem Speichern an den Text gehängt. Nach dem Neuladen und im Folgezug fehlt er daher. Das ist ein eigener kleiner Folgepunkt.
  **Behoben (2026-11-02):** `turn_persist.persist_and_build_response` hängt die gelieferten Dokumente jetzt VOR `save_message` an. Das ist reine Textarbeit; die F-6-Begründung (Speichern vor der M16-Auflösung) bleibt unberührt. Der spätere Zweig verteilt nur noch auf Boxen. `_dokumente` bleibt in diesem Fall bewusst leer: Der Inhalt steht im gespeicherten Text, eine Box gab es nicht, und im Folgezug stünde er sonst doppelt. Test: `test_ohne_boxen_steht_der_inhalt_auch_im_gespeicherten_text`.

### U1-b3 Altes entfernen (Review danach)

`boerdi-inline-documents` und die `inlineDocuments`-Durchreichung im Widget entfallen (U-F5: das Modul trägt alle Funktionen); Playwright `write-preview` auf Blöcke; der Vergleichstest „sieht aus wie die bisherige Box“ in `e2e/inhaltsrahmen.spec.ts` entfällt mit; der dann tote Zweig `docs.length > 0` in `isPrintableCanvasMaterial` geht mit. Die Felder im öffentlichen Vertrag bleiben zunächst als veraltet stehen; ihr Wegfall ist ein eigener Entscheid.

**Stand U1-b3 (2026-11-02):** umgesetzt.
- **Entfernt:** `ui/src/inline-doc/` (Komponente, Hilfen, Specs), `printInlineDocument`, der tote Zweig in `isPrintableCanvasMaterial`, die `inlineDocuments`-Durchreichung (`addBotMessage` hat jetzt 10 statt 11 Positionen), der Typ `InlineDocument` und das Feld `inline_documents` im Frontend-Vertrag, der Rückfall auf `ui.dokumente` in der Wiederherstellung samt `chat.documentShortened`, die i18n-Schlüssel `inlineDoc.*` und der E2E-Vergleichstest.
- **Umgezogen:** Die Schriftskala liegt als `ui-bloecke/schrift-skala.ts` beim einzigen Nutzer, mit den übernommenen Tests.
- **Umgestellt:** `e2e/write-preview.spec.ts` liefert die Vorschau als Block (vor der Umstellung rot).
- **Bündel:** 579,33 kB roh / 170,31 kB gzip (nach U1-b1: 586,62 / 171,77).

**Review U1-b3 (2026-11-02):** kein kritischer, kein hoher, zwei mittlere und fünf kleine Befunde, fast alles Kommentare und Doku. Alle sind behoben:
- Vertragstext zu `ui.dokumente` korrigiert: Das Widget liest das Feld nicht mehr.
- Verweise auf den gelöschten Ordner umgestellt.
- Test- und Kopfkommentare auf 10 Positionen gebracht.
- Im Haupt-Sendepfad sind jetzt auch die letzten drei Positionen festgehalten.
- Bündelgröße im Plan ergänzt.

U1-b ist damit abgeschlossen.

**Deploy-Hinweise U1-b:** Widget-Bündel neu (auch die Kopie im Chrome-Plugin) — ein Widget von vor U1 zeigt keine Dokument-Box mehr. Live in WLO abgelegte Master-Skill-Fassung und eine im Studio gespeicherte eigene Rollen-Vorgabe auf `ui_inhaltsrahmen` umstellen (bis dahin greift der Alias).

## 12 U1-c im Einzelnen (Entscheide Nutzer 2026-11-02, Tests zuerst)

**Entscheide:**
1. **Blöcke zusätzlich:** Das Backend leitet `ui_trefferliste`/`ui_linkbox` aus den fertigen Karten und Links ab. `cards`/`web_links` bleiben, damit Host-Ereignisse, `page_action`, Folgezug, Evals, Studio-Probe und alte Widgets unverändert laufen. Das neue Widget zeigt Treffer nur noch über die Module, ohne Doppelanzeige; der Wegfall der alten Felder ist ein eigener Entscheid (U-F5).
2. **Reihenfolge:** zuerst die Linkbox mit dem Muster-Schlüssel (U1-c1), dann die Trefferliste (U1-c2). M16-Schwimmlinien bleiben vorerst unverändert.
3. **Agent-Modus:** Die Blöcke entstehen automatisch aus den Treffern; die KI ruft nichts extra auf.

**Leitlinie:** Abgeleitete Blöcke entstehen an der API-Grenze (`api/publikum`), live in `antwort_fuer` aus der fertigen Antwort (nach `widget_postprocess`, das Links noch ergänzt) und im Verlauf in `ui_aus_gespeichert` aus `_web_links`. Ihre `block_id` ist aus Modul und Daten berechnet. Live und Verlauf sind damit gleich, solange `widget_postprocess` keine Links ergänzt; die Kennung ist je Nachricht eindeutig, nicht über alle Nachrichten. Das Muster legt mit `ui_module:` fest, welche abgeleiteten Module es zeigt. Fehlt der Schlüssel, gelten alle (heutiges Verhalten), `[]` heißt keine. Im Agent-Modus gelten alle.

### U1-c1 Linkbox und Muster-Schlüssel (Review danach)

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| c1-1 | Vertrag: `darstellung.platz` (`oben` Vorgabe, `unten` = nach den Treffern) im Manifest-Schema und im Register; der Platzhalter rendert oben vor, unten nach den Trefferboxen | `_vertrag/manifest.schema.json`, `register.ts`, `module-register.mjs`, `shell/chat-shell.component.html` | Register trägt `platz`; Shell: Inhaltsrahmen oben, Linkbox unten |
| c1-2 | Host `link(url)` → `{ href, hinweis }` (Sitzungs-Kennung bei vertrauten Hosts, Hinweis bei fremden Seiten) über einen Seam der Shell | `_vertrag/modul-host.ts`, `ui-bloecke/*`, Shell | Host liefert `withBsid`-Adresse und Warnhinweis |
| c1-3 | Modul `ui_linkbox`: `eingabe.links[{titel,url}]` (1–30, nur http/https), anzeigend, `agent: false`, `platz: unten`; gleiches DOM und gleiche Klassen wie `boerdi-web-links` (eigener Rahmen) | `ui-module/src/ui-linkbox/*` | Spec rendert jedes Beispiel; Link geht über `host.link`; `target=_blank`, `rel` |
| c1-4 | Shell: die alte Web-Link-Box (in `result-groups` und unter den Kacheln) schweigt, wenn die Nachricht einen Linkbox-Block trägt | `grouping/result-groups.component.ts`, `web-links.component.ts` bzw. Shell-Gate | Nachricht mit Block: genau eine Box; ohne Block: wie bisher |
| c1-5 | Backend: `ui_module/abgeleitet.py` — `linkbox_block(web_links)` (stabile Kennung, gedeckelt), `abgeleitete_bloecke(web_links, erlaubt)`; `publikum` hängt sie live und im Verlauf an (nach den gelieferten Blöcken, Regeln je Antwort) | `ui_module/abgeleitet.py`, `api/publikum.py` | live und Verlauf gleiche Kennung; ohne Links kein Block; Muster mit `ui_module: []` → kein Block |
| c1-6 | Muster-Schlüssel `ui_module` (Liste von Modulnamen aus dem Katalog, nur abgeleitete Module): Frontmatter-Modell, `PatternDef`, Studio-Elementmodell, Katalog-Auswahl; Auflösung je Muster für `publikum` | `config_models/patterns.py`, `pattern_engine.py`, `api/config_element*.py`, `api/config_choices.py`, Studio-Fixture | unbekannter Name abgewiesen; fehlend = alle; Agent = alle |
| c1-7 | Bündel messen, E2E: eine Linkbox nach den Treffern, auch nach dem Neuladen | `e2e/*` | E2E |

**Stand U1-c1 (2026-11-02):** umgesetzt.
- **Vertrag und Platz:** Der Vertrag kennt `darstellung.platz`; der Platzhalter steht zweimal in der Shell (oben, unten), und ein leerer Platz nimmt keinen Raum ein.
- **Host:** Der Host hat `link(url)`.
- **Modul:** `ui_linkbox` mit gleichem DOM und Stil-Partial wie die bisherige Box.
- **Backend:** leitet den Block an der API-Grenze ab, nach den gelieferten Blöcken. Die Kennung kommt aus den Daten, die Grenze ist `webseiten_max`; Führungs-Nachrichten bekommen keinen Block.
- **Muster-Schlüssel:** `ui_module` in Frontmatter, Studio-Eintrag, Katalog, Feld-Reiter und Texten.
- **Alte Box:** schweigt mit Block; `displayContent` streicht Link-Aufzählungen weiter.
- **Bündel:** 584,01 kB roh / 170,91 kB gzip.
- **Muster-Schlüssel gelesen:** über die rohen Muster-Definitionen (`load_pattern_definitions`), nicht über `PatternDef`; die Muster-Engine braucht den Schlüssel nicht.
- **Bewusste Abweichung vom Aussehen:**
  - Im Textlink-Modus steht die Webseiten-Box jetzt nach dem Such-Absprung („Alle Treffer in der Suche …“), vorher davor.
  - Unter der Box liegen durch den Platzhalter 8 px mehr Abstand.
  - Mit der Trefferliste (U1-c2) wird die Reihenfolge neu bewertet.

**Review U1-c1 (2026-11-02):** kein kritischer, zwei hohe, acht mittlere, fünf kleine Befunde — behoben:
- **Hoch:**
  - `ui_module:` wirkte im Betrieb nie, weil das Muster im Debug-Block als „M05 (Suche)“ steht. Jetzt zählt die Kennung davor; die Tests nutzen das echte Format.
  - Typ-Fokus-Antworten hätten eine Linkbox bekommen, denn `widget_postprocess` ergänzt Links nach dem Leeren. Jetzt wird bei Typ-Fokus nichts abgeleitet.
- **Mittel:**
  - Ohne Links liest die Ableitung keine Einstellung mehr.
  - Der typisierte Studio-Eintrag weist unbekannte Namen ab.
  - Kaputter Bestand bricht keine Antwort.
  - Das Schema der Adressen wird klein geschrieben.
  - E2E nach dem Neuladen; Tests für Kachel-Modus und `hasGroupedResults`.
  - Rahmenabstand oben wie bisher.
  - Deploy-Hinweis ergänzt; Zusage zur Kennung präzisiert.
- **Klein:**
  - Ein Link ohne Titel heißt sichtbar „Webseite“.
  - Ein Wächter vergleicht die Texte mit dem Shell-Wörterbuch.
  - Kommentar-Reihenfolge korrigiert.


**Prüfung U1-c1:**
- **Backend:** 7011 bestanden, ein Fehlschlag, nur umgebungsbedingt (Health-Test ohne Postgres).
- **Frontend:** `ui` 1053, `ui-module` 22, `widget` 76, `studio` 1851 Tests bestanden; E2E 58.
- **Bündel:** 584,07 kB roh / 170,92 kB gzip.

### U1-c2 Trefferliste (Entwurf, vor der Umsetzung zu verfeinern)

Gleichwertig zur heutigen Darstellung (Bestandsaufnahme der Such-Agenten vom 2026-11-02):
- **Darstellungen:** zwei — Textlink-Boxen (Themenseiten, Sammlungen, Materialien, Such-Absprung) und Kacheln (Vorschaubild, Lizenz, Themenseiten-Knopf mit Varianten, Sammlungs-Aktionen); Wahl nach Fenstergröße, `show-cards` und `inline-result-grouping`.
- **Aktionen:** Sammlung öffnen, Lernpfad, Volltext (M17), „mehr anzeigen“, „mehr laden“ (Server, hängt an).
- **Regeln:** Typ-Fokus (nur Such-Absprung), Tour, Sitzungs-Kennung, Warnhinweise, Gruppen-Grenzen aus `display_rules.groups`.

Vorgehen:
- **Wiederverwendung:** Das Modul nutzt die vorhandenen Komponenten (`result-groups`, `card-list`, `search-cta`) über Einzeldatei-Importe und einen Adapter, der aus `daten` die erwartete Nachricht baut, statt sie zu kopieren.
- **Neue Host-Fähigkeiten:**
  - `aktion(name, parameter)` — die Shell führt die bestehenden Sammlungs-Aktionen aus.
  - `darstellung()` — Kacheln oder Boxen.
  - `beschaeftigt()`.
- **Ableitung:** Das Backend leitet `ui_trefferliste` aus den fertigen `cards` ab (live nach `widget_postprocess`, im Verlauf aus der Kartenspalte), dazu `query_metas` für den Such-Absprung und die Seitenangaben.
- **Abschalten:** Mit Block schweigen `result-groups` und `card-list`.
- **Unverändert:** M16-Schwimmlinien, `page_action`, Host-Ereignisse.

**Zuschnitt U1-c2 (2026-11-02):** „mehr anzeigen“ und „mehr laden“ ändern heute die Nachricht im Speicher der Shell. Ein Modul, das nur seine `daten` sieht, braucht dafür eigenen Zustand und eine Host-Aktion, die Daten zurückgibt. Deshalb zwei Teile, je mit Review:

| Teil | Inhalt | Test zuerst |
|---|---|---|
| c2a | **Backend:** `ui_trefferliste` aus `cards`, `query_metas` und `pagination` ableiten (live; im Verlauf aus der Kartenspalte und `_query_metas`). Vor der Linkbox; auch bei Typ-Fokus, dann ohne Karten nur mit Such-Absprung; nicht bei Tour. **Modul:** zeigt im Textlink-Modus die bisherigen Boxen über einen Adapter (`result-groups`) samt Such-Absprung und Volltext-Aktion (`host.aktion`). Im Kachel-Modus zeigt es vorerst nichts, dort bleibt `card-list`. **Shell:** `result-groups` schweigt mit Block. | Ableitung live und Verlauf; Grenzen; Typ-Fokus; Modul rendert die Beispiele; Shell ohne Doppelanzeige |
| c2b | **Kacheln im Modul** (`card-list` über Adapter): Sammlung öffnen, Lernpfad, Volltext, „mehr anzeigen“ (Zustand im Modul), „mehr laden“ (Host lädt und schreibt die Karten in den Block; das Modul bekommt sie als neue `daten`). Dann schweigt auch `card-list` mit Block. | Aktionen, Seitenwechsel, Shell |

**Stand U1-c2a (2026-11-02):** umgesetzt.
- **Backend:** leitet `ui_trefferliste` ab, vor der Linkbox, im Verlauf aus Kartenspalte und `_query_metas`. Bei Typ-Fokus nur Such-Angaben, dann keine Linkbox; bei Tour nichts. `ui_module` kennt jetzt beide Module.
- **Modul:** Adapter auf `boerdi-result-groups` mit `aktion('volltext')`. Im Kachel-Modus leer.
- **Host und Kontext:** Der Host hat `treffer()` und `aktion()`, der Kontext trägt `anzeigeRegeln`.
- **Shell:** Mit Block schweigen die bisherigen Boxen. Unten bringen die Module ihren Abstand selbst mit (wie die bisherigen Boxen).
- **Bündel:** 586,09 kB roh / 171,75 kB gzip.

**Review U1-c2a (2026-11-02):** kein kritischer, zwei hohe, sechs mittlere, ein kleiner Befund — behoben:
- **Hoch:**
  - Bei Typ-Fokus fielen die Materialien samt „Inhalt anzeigen“ weg; die Bestandsaufnahme war falsch, die bisherigen Boxen zeigen sie. Die Liste übernimmt jetzt, was ankommt.
  - Trefferliste ohne Linkbox ließ im Textlink-Modus die Web-Links verschwinden. Jetzt steht dann die bisherige Web-Link-Box nach den Treffern.
- **Mittel:**
  - Unten kein zusätzlicher Rand.
  - Modulnamen kommen aus der Einzeldatei `_vertrag/modul-namen` (kein Import-Ring über das Register).
  - Die Zusage zur Kennung ist ehrlich eingeschränkt: Seitenangabe nur live, mit Test.
  - Die Muster werden einmal je Verlaufsabruf gelesen.
  - Deploy-Hinweis und `ui_module`-Bedeutung vollständig.
  - Neue Tests: Laufzeitwechsel Boxen↔Kacheln, Sperre während eines Zugs, Gruppen-Grenzen, Web-Links ohne Linkbox, Typ-Fokus mit Karte.
- **Klein:** Kommentar-Reihenfolge in der Shell.


**Prüfung U1-c2a:**
- **Backend:** 7022 bestanden; ein Fehlschlag, umgebungsbedingt (Health-Test ohne Postgres).
- **Frontend:** `ui` 1058, `ui-module` 30, `widget` 76, `studio` 1851 Tests bestanden; E2E 59.
- **Bündel:** 586,36 kB roh / 172,08 kB gzip.
- **Gegenprobe:** Der Shell-Test „Web-Links ohne Linkbox“ scheitert ohne die Korrektur.

**Stand U1-c2b (2026-11-02):** umgesetzt.
- **Modul:** Im Kachel-Modus zeigt es `card-list` über den Adapter. Sichtbare Kacheln per `linkedSignal`: anfangs eine Seite, +5 je Klick, alle nach dem Nachladen.
- **Host-Aktionen:** `sammlung`, `lernpfad`, `volltext`, `mehrLaden`.
- **Shell:** Der Platzhalter kennt seine Nachricht (`nachrichtId`) und reicht sie bei „mehr laden“ durch — nicht über die Block-Kennung, die nicht eindeutig ist. `loadMore` zieht die Trefferliste im Block mit nach.
- **Ohne Doppelanzeige:** Mit Block schweigen `card-list` und die Web-Link-Box unter den Kacheln. Die Web-Links stehen in beiden Modi nach den Treffern.
- **Bündel:** 589,12 kB roh / 172,77 kB gzip.

**Review U1-c2b (2026-11-02):** kein kritischer, ein hoher, zwei mittlere, drei kleine Befunde — behoben:
- **Hoch:** „mehr laden“ suchte die Nachricht über die abgeleitete Block-Kennung. Gleiche Sammlung zweimal im Gespräch ergibt dieselbe Kennung, dann blätterte die falsche Liste. Jetzt reicht der Platzhalter die Nachrichten-ID durch; ein Shell-Test mit zwei gleichen Blöcken belegt es.
- **Mittel:**
  - Unbekannte Aktionsnamen scheitern mit Warnung statt Ausnahme.
  - Testlücken geschlossen: Host-Kette, Startwert aus `page_size`, andere Blöcke unberührt.
- **Klein:** Kommentare, README, E2E-Kopf, Plan-Wortlaut und Lage des Stands.

## 13 Fahrplan für alle Module (Auftrag Nutzer 2026-11-02)

Auftrag: „alle UI-Module abarbeiten — je Modul mit den Coding-Skills umsetzen, danach Review, Befunde beheben; überlegen, ob für unsere Anwendungsfälle weitere gebraucht werden (z. B. Datei-Upload mit Ordnern, Umwandlung über MarkItDown im Backend); Unklares darf offen bleiben.“

| Reihenfolge | Schritt | Kern |
|---|---|---|
| 1 | U1-c2b Kacheln | `card-list` im Modul über den Adapter; Sammlung öffnen, Lernpfad, Volltext über `host.aktion`; „mehr anzeigen“ als Zustand im Modul; „mehr laden“: Host lädt und schreibt die Karten in den Block; dann schweigt auch `card-list` mit Block |
| 2 | U1-d Entscheidung | erstes **abfragendes** Modul `ui_entscheidung` (Frage, Optionen, ein-/mehrfach, Freitext); Antwort `ui_antwort {block_id, daten, text}` an der Anfrage, gegen `antwort` geprüft, wird Werkzeug-Ergebnis im nächsten Zug; Status `offen` → `beantwortet` / `veraltet`; Fähigkeiten-Durchsetzung im Host (aus U1-b1 verschoben) |
| 3 | U1-e Themenbaum | `ui_themenbaum` mit Datenquelle (`browse_collection_tree` o. ä. am MCP), `structuredContent` behalten statt durchs Modell; erst anzeigen, Auswahl später |
| 4 | U1-f Studio | Seite „UI-Module“: Liste aus dem Katalog, Vorschau mit den Manifest-Beispielen, Schalter aktiv / für den Agenten |
| 5 | Prüfung weiterer Module | siehe unten; nur umsetzen, was entschieden ist |

### Weitere Module für die Anwendungsfälle (Vorschläge, nicht freigegeben)

Bezug: die drei Abläufe aus dem Konzept (Struktur aus Dokument/Lehrplan, Bildung aus Dateien/Ordnern, Struktur aus Thema) und die Kestra-Teilläufe.

| Modul | Art | Wofür | Stand |
|---|---|---|---|
| `ui_upload` | abfragend | Dateien **und Ordner** hineinziehen (Drag & Drop, `webkitdirectory`), Liste mit Größe/Typ, Entfernen, Senden; Ergebnis: hochgeladene Dateien als Kontext für den Zug bzw. Eingang für den Ablauf „Bildung aus Dateien“ | Konzept unten, Fragen offen |
| `ui_freigabe` | abfragend | Schreibvorgang bestätigen/ändern/abbrechen (heute Text + Chip „Ja, so ausführen“) — strukturiert statt Freitext | später, an U1-d anschließen |
| `ui_fortschritt` | anzeigend | Stand eines lang laufenden Kestra-Laufs (Teilschritte, Prozent, Ergebnis-Links), per Vorgangs-Kennung aktualisiert | wartet auf Kestra-Anbindung |
| `ui_befund` | anzeigend | Prüfergebnis (z. B. Sammlungs-Gatekeeper): Punkte mit Ampel, Begründung | später |
| `ui_themenbaum_auswahl` | abfragend | Knoten im Baum wählen/umbenennen/verschieben (Zwischenschritt im Ablauf „Struktur aus …“) | nach U1-e |

### Konzept `ui_upload` (offen zu entscheiden)

- **Machbar mit vorhandener Technik:** MarkItDown ist schon im Backend (`services/rag/umwandeln.py`, `convert_to_markdown`). Es läuft im eigenen Prozess mit Frist, Speichergrenze, Zip-Bomben-Vorprüfung (`umwandeln_kind`) und `BOERDI_MAX_INGEST_MB` (Vorgabe 25 MB) und kann PDF, DOCX, PPTX und XLSX.
- **Ablauf:**
  1. Das Modul sammelt Dateien und Ordner im Browser, mit Pfad relativ zum gezogenen Ordner.
  2. Ein Host-Aufruf lädt sie an einen neuen Endpunkt.
  3. Das Backend wandelt jede Datei um und legt den Text an der Sitzung ab, gedeckelt und mit Ablaufzeit.
  4. Die Antwort des Moduls nennt die Dateien. Der nächste Zug bekommt den Text als Kontext bzw. als Eingang für einen Ablauf.
- **Offene Fragen:**
  - Wer darf hochladen: nur Angemeldete oder auch anonyme Nutzer, und mit welchen Grenzen (Anzahl, Gesamtgröße)?
  - Wie lange wird aufbewahrt (Aufbewahrung wie Gesprächsverläufe?), mit Datenschutz-Hinweis?
  - Wohin geht es: nur Kontext im Chat, oder Weitergabe an edu-sharing (Inbox/Arbeitsbereich) bzw. an Kestra (großer Ablauf, dann am besten direkt aus dem Browser an den Dienst hinter der B-API)?
  - Virenprüfung?
  - Welche Formate über MarkItDown hinaus (Bilder mit OCR)?

## 14 U1-d Entscheidung im Einzelnen (Tests zuerst, je Teil ein Review)

Befunde der Bestandsaufnahme (2026-11-03):
- Werkzeugaufrufe werden nicht gespeichert; der nächste Zug sieht nur Text (`verlaufs_fenster`). Die Antwort muss als gerahmter Block in den Zug.
- Offene Blöcke bleiben im Verlauf `offen`. Ihr Zustand wird beim Lesen abgeleitet und im Widget sofort gesetzt.
- Eine `action` zählt bei offener Schreib-Abnahme als NEIN. Für `ui_antwort` gilt dasselbe, sonst würde ein „Ja“ zur Zustimmung.
- Im Muster-Modus fällt ein `ui_*` in `tools:` heute still heraus.

### U1-d1 Agent-Modus, Antwortweg, Modul

| # | Aufgabe | Test zuerst |
|---|---|---|
| d1-1 | **Manifest `ui_entscheidung`** (abfragend, `agent: true`). `eingabe`: `frage` (≤300), `optionen[{id, label, hinweis?}]` (2–8, `id` `^[a-z0-9_-]{1,40}$`), `mehrfach`, `freitext`. `antwort`: `gewaehlt[]`, `freitext?` (≤1000). Fähigkeit `antworten` | Katalog lädt; Beispiele passen |
| d1-2 | **Backend, Modul-Werkzeuge allgemein** (`ui_module/werkzeuge.py`): Werkzeuge für Katalog-Module mit `agent: true` (ohne `ui_inhaltsrahmen` mit eigenem Weg, ohne abgeleitete); `modul_aufruf_annehmen(name, args)` gibt Block oder Fehlertext; Prüfung gegen `eingabe`, Options-`id` eindeutig; Textfassung aus der Vorlage | Werkzeug = Manifest; Fehler mit Pfad; Block mit Status `offen` |
| d1-3 | **Agent-Schleife:** `build_agent_tools(include_module=True)`; Dispatch vor MCP. Ein abfragendes Modul beendet die Runde wie `respond_to_user` (`stop_reason` „frage“). `AgentRun.ui_bloecke`, dann `ctx.ui_bloecke`. Die offene Frage steht in `entities["_offene_frage"]` = `{block_id, modul, optionen, frage}`. Bubble-Text: die Prosa des Modells, sonst ein fester Satz (de/en) | Lauf endet mit Block; Fehlerweg; nur angeboten |
| d1-4 | **Anfrage:** `ChatRequest.ui_antwort {block_id, daten}`, `message` = lesbare Antwort. Die Prüfung in `setup` (vor Schreib-Abnahme und Sicherheitsprüfung) verlangt: passt zur offenen Frage, Antwort gegen `antwort` gültig, gewählte Kennungen existieren. Sonst wird `ui_antwort` verworfen und der Text zählt wie getippt. Jeder Vordergrund-Zug schließt die offene Frage. `ui_antwort` zählt bei offener Schreib-Abnahme als NEIN | gültig, fremde Kennung, gefälschte Option, alte Frage, Hintergrund-Zug |
| d1-5 | **Folgezug:** Die geprüfte Antwort geht als gerahmter Block an die KI, vor der Nutzernachricht: „Antwort auf die Frage …: gewählt …“. Gespeichert wird sie in `debug._ui_antwort` der Nutzernachricht | Block im Prompt; gespeichert |
| d1-6 | **Verlauf:** `verlauf_fuer` leitet den Status ab. Antwort in einer späteren Nutzernachricht ergibt `beantwortet` samt `antwort`; eine spätere Nachricht ohne Antwort ergibt `veraltet`; sonst `offen` | drei Fälle |
| d1-7 | **Modul `ui_entscheidung`:** `fieldset`/`legend`, Radio oder Checkbox, optional Freitext, Knopf „Antworten“ (gesperrt ohne Wahl und während eines Zugs), nur lesend mit gesetzter Antwort; de/en | Beispiele; Tastatur; Antwort an den Host |
| d1-8 | **Host je Block** (aus U1-b1 verschoben): Der Platzhalter gibt jedem Block einen eigenen `MODUL_HOST` (Injector über `NgComponentOutlet`) mit Block-Kennung. Er lässt nur die Fähigkeiten aus dem Manifest zu: `herunterladen`, `drucken`, `oeffnen` (Link/Aktionen), `antworten`; sonst Warnung. `antworten(daten, text)` geht über die Shell als nächster Zug mit `ui_antwort`. Lokal wird der Block danach `beantwortet`, andere offene Blöcke werden `veraltet` | Fähigkeit fehlt → nichts passiert; Antwort sendet; Status lokal |
| d1-9 | **Vertrag** (OpenAPI `ui_antwort`), Doku, E2E (Frage erscheint, Antwort geht mit, Block danach nur lesend) | Vertragstest, E2E |

**Stand U1-d1 (2026-11-03):** umgesetzt (d1-1 … d1-9).
- **Modul:** `ui_entscheidung` (Manifest, Komponente, Spec mit allen Beispielen, README). Native Radio/Checkbox in `fieldset`/`legend`, Freitext mit Label, „Antworten“ gesperrt ohne Wahl und während eines Zugs; nur lesend mit „Deine Antwort: …“ bzw. „Diese Frage ist nicht mehr offen.“
- **Backend:** `ui_module/werkzeuge.py` (`modul_werkzeuge`, `ist_modul_werkzeug`, `modul_aufruf_annehmen`, `textfassung`); `INHALTSRAHMEN` liegt jetzt in `ui_module/namen.py`. Agent-Schleife: Dispatch vor dem MCP, `AgentRun.ui_bloecke`, Ende „frage“; `respond_agent` merkt die Frage (`entities._offene_frage`), fester Satz `agent.frage` (de/en). `ui_module/antwort.py` (Prüfung, Block für die KI, Status im Verlauf), `services/ui_antwort.py` (Schließen im `setup`), `ChatRequest.ui_antwort` (`UiAntwort`), `_ui_antwort` an der Nutzernachricht, `discard_stale_approval` wertet eine geprüfte Antwort als NEIN.
- **Widget:** `BlockModulHost` je Block (Injector des Outlets, je Kennung und Modul einmal angelegt, damit Module ihren Zustand behalten), `ModulHost.antworten()`/`beschaeftigt()`, `fragen-status.ts`, Sendeweg mit `ui_antwort` in `chat-api`/`send-message`/Shell.
- **Bündel:** 597,26 kB roh / 174,75 kB gzip (nach U1-c2b: 589,12 / 172,77).
- **Vertrag:** OpenAPI neu (`UiAntwort`), Zeile in `docs/api/bewusste-vertragszusaetze.md`; Studio-Schema-Attrappe neu erzeugt (unverändert, keine Bereichsmodelle betroffen).
- **Abweichungen vom Plan:**
  - Unter einer Frage stehen keine Schnellantworten (`qr_mode` „none“; `respond_to_user` derselben Runde liefert nur den Text) — ein Klick auf einen Chip hätte die Frage sofort veraltet.
  - Nicht nur die Modul-Antwort, **jeder** Zug der Person macht offene Blöcke im Widget sofort `veraltet` — gleich der Regel im Backend.
  - Die offene Frage speichert zusätzlich `mehrfach` und `freitext`, sonst ließen sich Einzelwahl und Freitext nicht prüfen.
  - Eine ungültige `ui_antwort` ergibt kein 422, sondern fällt still weg (der Text zählt wie getippt) — ein veralteter Block soll keinen Fehler erzeugen.
- **Offen:** Freitext-Zuordnung (getippte Antwort „2“ auf die offene Frage, §5) und die Meldung der bekannten Module durch das Widget (`environment.ui_module`, §3.4) — ein Widget von vor U1 bekommt das Werkzeug trotzdem und zeigt dann nur den festen Satz.

**Prüfung U1-d1:**
- **Backend:** 7077 bestanden; ein Fehlschlag, umgebungsbedingt (Health-Test ohne Postgres).
- **Frontend:** `ui` 1080, `ui-module` 46, `widget` 76, `studio` 1851 Tests bestanden; E2E 63 (neu `e2e/entscheidung.spec.ts`).
- **Gegenproben:** Ohne Fähigkeiten-Prüfung scheitern drei Tests, ohne festen Injector je Block der Test „Modul-Instanz bleibt“.

**Review U1-d1 (2026-11-03):** acht Befunde, je Test zuerst (rot gesehen, dann grün).
1. **Sicherheit (MAJOR):** Die Ergänzung einer geprüften Antwort lief an Regex-Tor und `assess_safety` vorbei → `assess` prüft `ui_module/antwort.sicherheits_text` (Nachricht, Umbruch, Ergänzung; ohne Ergänzung unverändert die Nachricht), auch im Rückfall (`tests/test_ui_antwort_review.py`).
2. **Sicherheit (MAJOR):** Eine verworfene Modul-Antwort mit „Ja“ zählte als Zustimmung zur offenen Schreib-Abnahme → `setup` merkt sich vor dem Prüfen, dass eine kam, `discard_stale_approval(modul_antwort=True)` wertet sie als NEIN; Test umgedreht (`test_eine_verworfene_modul_antwort_zaehlt_bei_offener_schreib_abnahme_als_nein`).
3. **Folgezug (MAJOR):** Ohne Klick kannte der nächste Zug weder Frage noch Möglichkeiten → `offene_frage_schliessen` liefert `FrageSchluss(antwort, frage)`, `ctx.geschlossene_frage`; ohne geprüfte Antwort setzt `respond_agent` den Block `[DEINE LETZTE FRAGE …]` mit nummerierten Möglichkeiten (`antwort.frage_block`) vor die Nachricht, mit geprüfter Antwort nur den Antwort-Block.
4. **Vertrag:** `stop_reason`/`result_stop_reason` „frage“ in `docs/browser-plugin-einbindung.md` (acht Werte, Beispiel behandelt es wie `text`) und `docs/agent-modus.md`; Zeile U1-d1 in `docs/api/bewusste-vertragszusaetze.md` ergänzt.
5. **Härtung:** `ANTWORT` und `FRAGE` stehen in `domain/endmarken._MARKEN`; beide Blöcke laufen ganz durch `entschaerfe_endmarken` (Schreibweisen klein, Unterstrich, kyrillisch getestet), das wörtliche Ersetzen ist weg.
6. **Barrierefreiheit:** Getrennte id-Namensräume im Modul (`…-opt-<id>`, `…-eingabe-freitext`) — eine Möglichkeit `freitext` kollidiert nicht mehr mit dem Freitextfeld (Spec: ids eindeutig, Feld behält sein Label).
7. **Widget:** `runSendMessage` meldet, ob der Server den Zug annahm (`connected` oder Antwort); sonst macht die Shell den lokal beantworteten Block wieder `offen` (`fragen-status.wiederOffen`). Andere offene Blöcke bleiben `veraltet`. `sendMessage` behält seine Signatur.
8. **Verträglichkeit:** `Environment.ui_module` (≤ 50 Namen nach `^ui_[a-z0-9_]{2,40}$`, `null` = keine Meldung); das Widget meldet die Namen seines Registers (`ChatApiClient.setUiModule`, gesetzt in `ngOnInit`), das Backend bietet nur diese Modul-Werkzeuge an. Der Studio-Probelauf (`ChatProbeApi`) meldet keine und bekommt keine — er zeigt keine Blöcke; die Studio-Widget-Vorschau lädt das echte Bündel. OpenAPI neu, Studio-Schema-Attrappe neu erzeugt. Damit ist der offene Punkt `environment.ui_module` oben erledigt.
- **Prüfung danach:** Backend 7098 bestanden (ein umgebungsbedingter Fehlschlag wie oben), ruff sauber; Frontend `ui` 1089, `ui-module` 47, `widget` 76, `studio` 1851, eslint und Gates sauber, `module:register --pruefen` aktuell, E2E 63; Bündel 597,86 kB roh / 174,96 kB gzip.

### U1-d2 Muster-Modus und Studio

| # | Aufgabe |
|---|---|
| d2-1 | `tools:` eines Musters darf Modul-Werkzeuge (`agent: true`) nennen (U-F4); `_select_active_tools` bietet sie an. In der Muster-Schleife: Dispatch, abfragend beendet die Runde, Ausnahme in der Pflicht-Prüfung (`tool_pflicht`). Der Folgezug-Block auch im Muster-Weg |
| d2-2 | Studio: Werkzeug-Übersicht und Prompt-Vorschau nennen die Modul-Werkzeuge; Katalog `tools` bietet sie an |

**Stand U1-d2 (2026-11-03):** umgesetzt (d2-1, d2-2).
- **Trennung:** `phase3_modulate` legt UI-Module aus `tools:` (jedes Katalog-Modul) unter `ui_werkzeuge` ab (`ui_module/namen.UI_WERKZEUGE_KEY`), `tools` bleibt die MCP-Liste. Damit lesen Pflicht-Prüfung (A1, `tool_pflicht`), Kuratier-Absicht, Medientyp-Strip, Vorabruf-Sperre, Skill-Brücke und Prompt-Werkzeugschicht unverändert nur MCP-Namen — ein Modul löst keine „KORREKTUR“-Runde aus.
- **Angebot:** `_select_active_tools(…, ui_module=environment.ui_module)` bietet `modul_werkzeuge(ui_werkzeuge ∩ gemeldet)` an — nur genannt UND vom Widget gemeldet (Regel wie im Agent-Modus); Inhaltsrahmen und abgeleitete Module bleiben auf ihrem Weg. Auch im Rückfrage-Muster (`clarify`), vor dem Degradations-Wipe.
- **Muster-Schleife:** neue Vorrunde `services/tool_loop_module.nimm_module_an` (wie die der Dokumente, damit eine Frage nach `respond_to_user` nicht verloren geht): nur Angebotenes, Prüfung über `modul_aufruf_annehmen` (Fehler an die KI), höchstens eine Frage (`ZWEITE_FRAGE`); Blöcke im `session_state["_modul_bloecke_zug"]` (bis zum Review `_ui_bloecke`). Nach einer Frage läuft in derselben Runde kein echtes Werkzeug (`NACH_DER_FRAGE`); die Runde endet vor der A1-Reflexion, Text = `respond_to_user` derselben Runde, sonst Prosa. Modul-Aufrufe stehen nicht in `tools_called`.
- **Antwort-Knoten:** `respond` holt die Blöcke mit `pop` nach `ctx.ui_bloecke`, merkt die Frage (`merke_frage`), setzt `qr_mode` „none“ und ohne Text den festen Satz `agent.frage`. Im Fehlerweg fallen die Blöcke weg.
- **Folgezug:** `ui_module/antwort.vorsatz(ui_antwort, geschlossene_frage)` (von `respond_agent` und `respond` genutzt) geht über `generate_response(vorsatz=…)` an `_assemble_messages`; er steht vor der Nachricht, die Wissenssuche nimmt weiter nur die Nachricht.
- **Katalog:** `GET /api/config/choices` → `tools` nennt die Modul-Werkzeuge mit Titel (`ui_entscheidung: Entscheidung`); die Prüfung unbekannter Namen bleibt offen wie bisher.
- **Studio (d2-2):** Werkzeug-Übersicht mit Zeile `ui_entscheidung` (Art „virtual“, angeboten für das heutige Widget, Sperre `widget_module`); Prompt-Vorschau mit `tools.ui_module {names, chars}` (nicht mitgezählt) und eigener Zeile; Spur-Ende „frage“ mit Beschriftung (de/en).
- **Abweichungen vom Plan:**
  - Die Trennung sitzt in `phase3_modulate`, nicht in `tool_pflicht`: ein Ort statt sechs Leser, die `tools` als MCP-Liste nehmen (Präzedenz `skill_werkzeuge`).
  - Die Degradation (fehlender Pflicht-Slot) nimmt auch die Modul-Werkzeuge — der Prompt verlangt dort reinen Text.
  - Vertrag unverändert (OpenAPI und Schema-Attrappe geprüft, `--check`); `tools.ui_module` der Prompt-Vorschau ist Studio-intern (Antwort ohne Modell).
- **Offen:** Ein Muster ohne `mcp` in `sources`, das nur Module nennt, bekommt weiter die Regel „Rufe KEINE Tools auf“ (Prompt-Werkzeugschicht) — dort ruft die KI das Modul kaum; die Seeds nennen noch kein Modul in `tools:` (z. B. M03 wäre der natürliche Ort, Entscheid Nutzer).

**Prüfung U1-d2:**
- **Backend:** 7129 bestanden, 490 übersprungen; zwei Fehlschläge umgebungsbedingt: der Health-Test ohne Postgres und `test_url_safety::test_ein_tropfender_rumpf_wird_zur_frist_abgeschnitten` (Zeitgrenze, lief parallel zu den Frontend-Suiten; einzeln 32/32 grün). Neu `tests/test_ui_entscheidung_muster.py` (29, alle vorher rot), dazu Fälle in `test_agent_tool_overview`, `test_agent_prompt_preview`, `test_generate`; angepasst `test_config_choices` (pg). ruff sauber; OpenAPI und Schema-Attrappe `--check` unverändert.
- **Frontend:** `ui` 1089, `ui-module` 47, `widget` 76, `studio` 1853 Tests bestanden; eslint und Gates sauber, `module:register --pruefen` aktuell, E2E 63; Bündel unverändert 597,86 kB roh / 174,96 kB gzip.

**Review U1-d2 (2026-11-03):** zwölf Befunde, je Test zuerst (rot gesehen, dann grün; neu `tests/test_ui_entscheidung_muster_review.py`).
1. **`tool_choice` (MAJOR):** Ein Modul-Werkzeug allein zählte als echtes Werkzeug für „erste Runde ⇒ required“ — ein Rückfrage-Muster ohne `respond_to_user` zwang die KI in die Auswahl-Frage → `tool_loop` erzwingt nur, wenn ein Werkzeug außer den Modulen angeboten ist (beide Zweige, auch `force_tool_use`). Abweichung: `respond_to_user`, `select_top_cards` und `ui_inhaltsrahmen` zählen weiter als erzwingbar — sonst verlöre ein Muster mit `tools: []` den bisherigen Zwang zum Antwort-Werkzeug (Verhalten vor U1-d2, nicht Teil des Befunds).
2. **Klassifikator:** Er sah nach einer Auswahl-Frage nur „Klasse 5“ → `assess._classify` setzt denselben gerahmten Block wie die KI (`antwort.vorsatz`: geprüfte Antwort, sonst die übergangene Frage) vor die Nachricht; die Nachricht bleibt die letzte, Systemteil/Seite/Verlauf bleiben das Cache-Präfix.
3. **Werkzeug-Treue (Auswertung):** `_pattern_tools_map` zählt nur MCP-Namen (`t not in katalog()`, wie `phase3_modulate`); ein Muster nur mit Modulen zählt nicht.
4. **Seed-Wächter:** `test_jeder_im_pattern_genannte_tool_name_existiert` kennt Modul-Werkzeuge und weist Module ohne Wirkung in `tools:` (Inhaltsrahmen, abgeleitete; `namen.OHNE_WIRKUNG_IN_TOOLS`) eigens ab. Dazu der Validator `PatternFrontmatter.tools` (`namen.pruefe_werkzeug_namen`, wie `ui_module`): das Studio weist `tools: [ui_linkbox]` ab; unbekannte Namen bleiben erlaubt wie bisher.
5. **Fehlerweg `respond`:** Test — wirft `generate_response`, nachdem ein Block lag: keine Blöcke, keine offene Frage, `qr_mode` unverändert (Gegenprobe ohne `pop`: rot).
6. **Studio-Hinweis `tools`:** ein Satz de/en — UI-Module wie `ui_entscheidung` wirken nur, wenn das Widget sie meldet und `mcp` in den Quellen steht; bei fehlender Pflichtangabe fallen sie weg (`fields-patterns.spec.ts`).
7. **README `ui-entscheidung`:** die U-F4-Regel statt „kommt mit U1-d2“.
8. **Krisen-Sperrliste:** eigener Katalog `mcp_tools` (nur MCP, `_mcp_tools`) für `crisis_blocked_tools`; `tools` bleibt der Katalog der Muster. Schema-Attrappe neu erzeugt, OpenAPI unverändert (`--check`).
9. **Phase der Runde:** Eine Runde mit abfragendem Modul (`werkzeuge.ist_abfragendes_modul`) bucht als `response` wie `respond_to_user`.
10. **Kommentar** in `config_models/patterns.py`: `tools` = Werkzeuge der eingeschalteten Server und UI-Module mit `agent: true`.
11. **Schlüssel:** `MODUL_BLOECKE_KEY` heißt jetzt `_modul_bloecke_zug` (nicht mehr gleich `ui_bloecke.DEBUG_KEY`).
12. **Test:** `test_ein_modul_ist_kein_pflichtwerkzeug` nimmt die gerufenen Werkzeuge nicht mehr aus der Ausgabe selbst (Suche samt Helfern, ohne Modul).
- **Beobachtung (kein Befund):** Im Muster-Modus sperrt die Modul-Vorrunde alle MCP-Aufrufe derselben Runde, sobald eine Frage steht (`NACH_DER_FRAGE`, auch für Aufrufe VOR der Frage in der Antwort des Modells) — strenger als im Agent-Modus, wo nur Aufrufe nach der Frage abgewiesen werden. Bewusst so gelassen: die Runde endet ohnehin mit der Frage, ein Suchergebnis davor bliebe ungesehen.
- **Prüfung danach:** Backend 7146 bestanden, 490 übersprungen, ein umgebungsbedingter Fehlschlag (Health-Test ohne Postgres); ruff sauber; OpenAPI `--check` unverändert, Schema-Attrappe neu (`mcp_tools`). Frontend `studio` 1855, `ui-module` 47 bestanden; eslint, Gates und `module:register --pruefen` sauber. Widget-Code unberührt — kein neuer Bündel- oder E2E-Lauf.

## 15 U1-e Themenbaum im Einzelnen (Tests zuerst, Review danach)

### Befunde (2026-11-03, am Code geprüft)

**MCP-Server** (`wlo-mcp-server-sc`, der Server mit Apps-Widgets; `wlo-mcp-server` hat dasselbe Werkzeug ohne Widget):
- Werkzeug `browse_collection_tree` (`src/tools/browse.ts:179-314`): Argumente `nodeId` **oder** `subject` (Fachportal-Name, serverseitig aufgelöst, `:210-233`), `depth` 1–2 (Vorgabe 1), `includeContentCounts`, `includeContentPreview` 1–5, `maxResults` 1–100 (Vorgabe 50), `outputFormat`. Ergebnis `{ parent, depth, total, results, truncated }` (`:270`) — im JSON-Zweig **wörtlich gleich** als Text und als `structuredContent` (`:272-276`), im Markdown-Zweig als Text-Liste plus `structuredContent` (`:306-309`).
- Knoten: `FormattedNode` (rund 25 Felder: `nodeId`, `title`, `description`, `keywords`, `url`, `topicPageUrl`, `nodeType`, `contentsCount?` …) plus `fileCount?`, `contentPreview?`, `children?`, `hasMoreChildren?` (`src/apps/outputSchemas.ts:200-228`).
- Grenzen des Laufs (`src/services/collection-traversal.ts:203-222`, `239-314`): höchstens zwei Ebenen, je Elternknoten 3–10 Kinder aus einem Gesamtbudget von 150 Knoten, Zyklen-Schutz; `hasMoreChildren`, wenn ein Zweig gekürzt ist (ein Kind mehr geholt als gezeigt).
- Widget `browse` (`src/apps/widgets/browse/`): **statischer Baum** aus den mitgelieferten `children` (`state.ts:161-172`), Auf-/Zuklappen nur lokal über Knöpfe mit `aria-expanded`/`aria-controls` (`render.ts:265-287`), Hinweis „weitere Unterthemen“ bei `hasMoreChildren` (`render.ts:250-252`), je Sammlung „Inhalte anzeigen“ (Folgenachricht mit `nodeId`, `render.ts:225-232`, `main.ts:91-99`) und ein Öffnen-Link nur über `safeHref` (`render.ts:218-223`), Fokus nach dem Neuzeichnen zurück (`main.ts:51-62`). **Kein Nachladen im Widget** (`main.ts:4-11`, `state.ts:10-18`): tiefere Ebenen laufen über eine Folgenachricht und eine **neue** Karte. Es ist eine verschachtelte Liste mit Aufklapp-Knöpfen, kein `role="tree"`.

**Chatbot:**
- Werkzeugbeschreibung statisch in `services/mcp/tool_defs.py:415-457`, Argumente `api/schemas_mcp.py:154-170` (`depth` ≤ 2, `maxResults` ≤ 100), JSON wird angefordert (`services/mcp/tool_args.py:238`), Fach-Namen und falsche Kennungen löst `arg_resolvers._resolve_browse_node_id` (`:120-195`, `:649`), Cache 1800 s (`tool_cache.py:62`).
- Heute: das Ergebnis geht **ganz** an die KI (`domain/tool_result_redaction.py:443`: Sammlungen „bleiben unangetastet“), und die Unter-Sammlungen werden Karten (`services/card_collect.py:48`) — also Trefferliste, kein Baum.
- `structuredContent`: der Transport behält es (`services/mcp/transport.py:330-331`), der Client liest es nur für vorbereitete Schreibzugriffe und verwirft es sonst (`services/mcp/client.py:532-548`); `call_mcp_tool` gibt nur Text zurück.
- Modul-Werkzeuge laufen heute synchron und ohne MCP (`services/agent_loop.py:577-596`, `services/tool_loop_module.py:39-69`). Die Direktaktionen (`graph/nodes/preflight.py:75-80`, `:196-208`) laufen durch Drosselung und Sicherheitsprüfung wie ein Zug.

### Entscheide (U1-e)

| # | Frage | Entscheid | Warum |
|---|---|---|---|
| E-1 | Wie kommen die Knoten in den Block? | **Modul-Werkzeug mit Datenquelle.** `ui_themenbaum` (`agent: true`, anzeigend) mit `datenquelle {werkzeug: browse_collection_tree, argumente: [subject, nodeId], vorgaben: {depth: 2, maxResults: 30}}` (seit dem Review U1-e `maxResults: 31`, Befund 2). Die KI nennt nur Fach oder Sammlung; das Backend ruft das Werkzeug selbst (`ui_module/datenquelle.py`), formt schlanke Knoten und legt den Block in die Antwort. An die KI geht nur eine Quittung (Anzahl, Ebenen, gekürzt ja/nein), **kein Knoten**. | Plan §3.2/U-E6. Verworfen: (B) Block aus einem Aufruf von `browse_collection_tree` durch die KI ableiten — die Knoten liefen dann doch durchs Modell und stünden doppelt als Karten; (C) eigener Endpunkt zum Nachladen — neue öffentliche Fläche mit eigener Drosselung und Sitzungsprüfung, und Nachgeladenes stünde nicht im Verlauf |
| E-2 | `structuredContent` oder Text? | Die Datenquelle liest den **JSON-Text** (`outputFormat: json`, vom Client ohnehin gesetzt) — er ist wörtlich das `structuredContent` (`browse.ts:272-276`). Kein Seitenkanal im Client. | Der Werkzeug-Cache speichert nur Text (ein Cache-Treffer hätte sonst keine Daten); ein ContextVar-Kanal überlebt die Task-Grenzen der Frist (`innerhalb`) nicht. Der Text geht in diesem Weg nie ans Modell |
| E-3 | Parameter für die KI | Aus der Werkzeugbeschreibung (`TOOL_DEFINITIONS`), nur die `argumente`; `vorgaben` setzt das Backend fest und überschreibt Werte der KI. Angeboten wird das Modul nur, wenn sein Werkzeug im Lauf **verfügbar** ist (`angebotene_mcp_werkzeuge`: Studio-Schalter, Sperren der Sicherheit, Modus der Einbettung) und das Widget das Modul meldet | eine Sperre auf `browse_collection_tree` darf das Modul nicht umgehen |
| E-4 | Manifest-Vertrag | `datenquelle.vorgaben` (Objekt, optional) neu im Schema. `eingabe` beschreibt die **Block-Daten** (`titel?`, `wurzel_id?`, `knoten[]` mit `id`, `titel`, `url?`, `anzahl?`, `mehr?`, `kinder[]` eine Ebene tief, `gekuerzt?`). Grenzen: 30 Knoten oben, 10 Kinder je Knoten, Titel ≤ 200, URL nur http/https | gleicher Prüfweg wie bei den anderen Modulen (Beispiele gegen `eingabe`) |
| E-5 | Tiefe | **Feste Tiefe 2** aus der Datenquelle, Auf-/Zuklappen lokal; Start **zugeklappt** (nur erste Ebene sichtbar) | Abweichung vom MCP-Widget (dort alles offen): 30 × 10 offene Zeilen sprengten die Chat-Blase |
| E-6 | Tiefer gehen | Knopf **„Unterthemen öffnen“** für Knoten mit `mehr` und für Knoten der zweiten Ebene → neue Direktaktion **`show_collection_tree`** `{collection_id, title}` → neuer Zug **ohne KI** mit einem neuen Baum ab diesem Knoten (wie das MCP-Widget: neue Karte statt Nachladen im Block). Läuft durch Drosselung und Sicherheitsprüfung wie `browse_collection`, speichert den Block für den Verlauf | sicher (vorhandener Weg, kein neuer Endpunkt), kein Modell, Verlauf vollständig |
| E-7 | Aktionen je Knoten | „Inhalte anzeigen“ über die vorhandene Host-Aktion `sammlung` (Direktaktion `browse_collection`), „In WLO öffnen“ über `host.link`. Fähigkeit `oeffnen` | gleiche Wege wie die Trefferliste |
| E-8 | Barrierefreiheit | WAI-ARIA-Muster **Tree View**: `role="tree"`/`treeitem`/`group`, `aria-expanded`, `aria-level`, `aria-setsize`, `aria-posinset`, wandernder `tabindex`; Tasten ↑ ↓ → ← Pos1 Ende, Enter/Leertaste klappen. Keine Knöpfe **im** Baumeintrag (APG): die Aktionen stehen in einer Zeile unter dem Baum für den aktiven Knoten („Algebra: Inhalte anzeigen · Unterthemen öffnen · In WLO öffnen“) | Tastatur und Vorleser ohne verschachtelte Bedienelemente |
| E-9 | Textfassung | eingerückte Markdown-Liste mit Links (für ältere Widgets und `/api/agent`) | |
| E-10 | Bündel | statisch im Haupt-Bündel, solange unter 190 kB gzip; sonst nachladen (U-F2) | Messung entscheidet |
| E-11 | Muster-Modus | wie `ui_entscheidung` über `tools:` (U-F4); die Vorrunde der Muster-Schleife wird dafür `async`. Kein Seed nennt das Modul (Entscheid Nutzer) | |

### Aufgaben

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| e-1 | Vertrag: `datenquelle.vorgaben` im Manifest-Schema und Typ | `_vertrag/manifest.schema.json`, `manifest.ts` | Katalog-Test: Manifest mit `vorgaben` gültig, mit falschem Typ abgewiesen |
| e-2 | Manifest `ui_themenbaum` (+ Register) | `ui-module/src/ui-themenbaum/manifest.json` | Katalog lädt es; Beispiele passen; zu tiefe Kinder abgewiesen |
| e-3 | Backend Datenquelle: `themenbaum_daten(payload, titel)` formt schlanke Knoten (gedeckelt, nur http/https, ohne Beschreibung) und die Textfassung; `hole(manifest, args)` ruft das Werkzeug mit `argumente` + `vorgaben`, liest den JSON-Text, Fehler → Text für die KI | `ui_module/datenquelle.py` | Formen, Deckel, Fehler, gesendete Argumente (MCP gemockt) |
| e-4 | Werkzeug aus dem Manifest: Parameter = `argumente` aus der Werkzeugbeschreibung; Angebot nur bei verfügbarem Werkzeug; `modul_aufruf_annehmen_async` (Datenquelle) neben dem bisherigen Weg; Quittung ohne Knoten | `ui_module/werkzeuge.py` | Schema; Angebot; **Quittung enthält keinen Knotentitel** |
| e-5 | Agent-Schleife und Muster-Vorrunde rufen die Datenquelle (`await`, mit Frist) | `services/agent_loop.py`, `services/agent_tools.py`, `services/tool_loop_module.py`, `services/tool_loop.py`, `services/response_tool_selection.py` | Lauf: Block da, Modell-Nachrichten ohne Knoten (Nachweis U1-e) |
| e-6 | Direktaktion `show_collection_tree` | `services/direct_actions_baum.py`, `graph/nodes/preflight.py`, `domain/config_models/base_widget.py` | Block in der Antwort und im gespeicherten Debug-Block; ungültige Kennung; Fehler des Werkzeugs |
| e-7 | Modul `UiThemenbaum` (Tree View, Aktionszeile, leer, gekürzt, de/en) | `ui-module/src/ui-themenbaum/*` | Spec rendert jedes Beispiel; Tasten; Aktionen an den Host |
| e-8 | Host-Aktion `themenbaum` | `_vertrag/modul-host.ts`, `ui/src/ui-bloecke/*`, `controllers/collection-actions.ts`, Shell | Host reicht weiter; Fähigkeit fehlt → nichts |
| e-9 | E2E (Baum sichtbar, Tastatur, Unterthemen öffnen), Bündel messen, Doku, Vertrag | `e2e/themenbaum.spec.ts`, Docs | E2E |

**Stand U1-e (2026-11-03):** umgesetzt (e-1 … e-9).
- **Vertrag:** `datenquelle.vorgaben` im Manifest-Schema und -Typ.
- **Modul:** `ui_themenbaum` (Manifest mit drei Beispielen, Komponente, Spec mit allen Beispielen, README). Tree View wie in E-8; zusätzlich folgt die Auswahl dem Fokus (`aria-selected` = der Knoten der Aktionsleiste) und die Tasten liegen am Baumeintrag selbst — beides verlangte der Lint (`role-has-required-aria`, `interactive-supports-focus`), und beides ist im APG-Muster vorgesehen.
- **Backend:** `ui_module/datenquelle.py` (Parameter aus dem Werkzeug-Katalog, Ruf über `call_mcp_tool_status`, JSON-Text lesen, Fehler ohne Servertext), `ui_module/themenbaum.py` (schlanke Knoten, Textfassung, Quittung), `werkzeuge.modul_werkzeuge(…, verfuegbar=…)` und `hat_datenquelle`. Agent-Schleife ruft die Datenquelle mit Frist und nicht über `call_with_outcome` (keine Karten-Ernte); Muster-Vorrunde `nimm_module_an` ist asynchron; Muster-Angebot über `angebotene_mcp_werkzeuge`. Direktaktion `show_collection_tree` (`services/themenbaum_aktion.py`, `preflight`), Texte `action.tree.*` de/en. `abgeleitet.http_url` ist jetzt öffentlich (vom Themenbaum mitgenutzt).
- **Widget:** Host-Aktion `themenbaum` (Vertrag, `WidgetModulHost`, `ShellTreffer`), `showCollectionTree` in `controllers/collection-actions.ts`; die vier Karten-Aktionen laufen über `runCardAction` (Upgrade-Pfad des `simplify:`-Vermerks dort, ausgelöst durch die vierte Aktion), Text `error.collectionTree` de/en.
- **Studio:** ohne eigene Änderung (seit dem Review die Sperre `data_source`, Befund 8); die Prompt-Vorschau zählt Module mit Datenquelle nur bei angebotenem Werkzeug (wie im Zug).
- **Bündel:** 609,06 kB roh / 177,80 kB gzip (nach U1-d: 597,86 / 174,96) — unter 190 kB, darum statisch im Haupt-Bündel (E-10).
- **Vertrag:** OpenAPI und Bereichs-Schemas `--check` unverändert; Zeile in `docs/api/bewusste-vertragszusaetze.md`. Änderungsnotiz `docs/aenderungen/2026-11-03-paket-u1e.md`.
- **Abweichungen vom Plan:** Die Datenquelle nimmt bei `subject` und `nodeId` zugleich die Kennung (wie der Server) statt eines Fehlers; die Direktaktion speichert als Text nur den Begleitsatz, damit die Knoten auch über den Verlauf nicht an die KI gehen.

**Prüfung U1-e:**
- **Backend:** 7195 bestanden, 490 übersprungen; ein Fehlschlag umgebungsbedingt (`test_repo_config::test_health_nennt_das_repositorium`, ohne Postgres). Neu `tests/test_ui_themenbaum.py` (33), `test_ui_themenbaum_muster.py` (5), `test_ui_themenbaum_aktion.py` (11), alle vorher rot; angepasst drei Katalog-Tests, die die Modul-Menge festschrieben (`test_ui_entscheidung_muster`, `…_review`, `test_agent_prompt_preview`). ruff sauber.
- **Nachweis „Baum ohne Modell-Tokens für die Knoten“:** `test_die_quittung_an_die_ki_nennt_keinen_knoten`, `test_der_agent_bekommt_den_baum_ohne_dass_knoten_durchs_modell_laufen` und `test_die_vorrunde_holt_den_baum_und_quittiert_ohne_knoten` prüfen, dass kein Knotentitel und keine Knotenkennung in den Nachrichten an das Modell steht, während der Block alle trägt.
- **Frontend:** `ui` 1093, `ui-module` 64, `widget` 76, `studio` 1855 Tests bestanden; eslint und Gates sauber, `module:register --pruefen` aktuell, `module-register.test.mjs` 9/9; E2E 67 (neu `e2e/themenbaum.spec.ts`: zugeklappt + Klick, Tastatur, „Unterthemen öffnen“ als Direktaktion, 320 px).
- **Gegenprobe:** Ohne `themenbaum` in den Aktionen des Widget-Hosts scheitert der Platzhalter-Test „Unterthemen öffnen geht an die Shell“.

### Review-Befunde U1-e (2026-11-03, behoben)

Je Befund erst am Code geprüft, dann ein roter Test (`tests/test_ui_themenbaum_review.py`, Spec, Studio-Spec), dann die kleinste Änderung.

| # | Befund | Prüfung | Änderung |
|---|---|---|---|
| 1 | MAJOR: Modul-Werkzeuge sind von `_NACH_DER_ANTWORT` ausgenommen — scheitert die Datenquelle, galt die Antwort derselben Runde („hier ist der Baum …“ ohne Baum) | bestätigt (Agent: Antwort am Rundenende; Muster: `respond_to_user` nach der Vorrunde) | Agent: ein Aufruf mit Datenquelle ohne Block setzt `ohne_block`; am Rundenende gilt die Antwort nicht, ihre Werkzeug-Nachricht wird `datenquelle.ANTWORT_VERWORFEN`, die nächste Runde sieht die Fehlermeldung. Muster: `nimm_module_an` gibt `Vorrunde(erledigt, ohne_block)` zurück, `respond_to_user` wird dann nicht übernommen (`continue` statt `break`). Am Deckel bleibt es beim bestehenden ehrlichen Ende: Agent `max_iterations` → `respond_agent` holt den Abschluss nach oder setzt `agent.incomplete`; Muster `None` → `_max_iterations_fallback`. Eine gestreamte Antwortrunde ist schon über `strom_verbraucht` abgesichert (die nächste ersetzt den Text) |
| 2 | MAJOR: der Server liefert höchstens `maxResults` Knoten oben und meldet nicht, ob es mehr gibt | bestätigt: `getChildCollectionsResult(parentId, maxResults)` ohne Gesamtzahl, `truncated` nur für Zweige (`collection-traversal.ts:239-314`, `wlo-node.ts:110-133`) | Vorgabe `maxResults: 31` (= `HOECHSTENS_OBEN` + 1); `daten_aus` schneidet auf 30 und setzt `wurzel_mehr`, wenn der Server mehr als 30 Knoten schickte (gezählt roh — auch ein unbrauchbarer fehlt im Baum). Neu `wurzel_url` (die Sammlung in WLO, Form wie die Karten: `normalize._repo_collection_browse_url` mit `get_repo_base_url`). Manifest: beide Felder in `eingabe`, viertes Beispiel; Widget: Hinweis „Es gibt mehr Unterthemen, als hier stehen.“ mit Link „Alle in WLO ansehen“ (über `host.link`), de/en; ein leerer Baum bekommt „In WLO öffnen“ für die Wurzel. Quittung nennt die Kürzung ohne Knoten, Textfassung endet mit `- …`. **Wirkung auf `childSlice`:** der Server rechnet `floor(150 / Zahl oben)`, begrenzt auf 3–10. Bei ≤ 30 Knoten oben ändert sich nichts (die Zahl ist dieselbe); erst ab 31 sinkt der Anteil je Knoten von 5 auf 4 Kinder, und ein Kinder-Abruf mehr läuft (für den 31., der nicht gezeigt wird). Die 30 gezeigten sind die ersten 31 in Repositoriums-Reihenfolge, alphabetisch sortiert — nicht die alphabetisch ersten aller Themen; der Hinweis sagt deshalb nur „mehr“ |
| 3 | MINOR: Direktaktion ruft `browse_collection_tree` ohne Angebotsprüfung | bestätigt | `themenbaum_aktion` prüft `agent_tools.angebotene_mcp_werkzeuge(allow_curation=False, blocked_tools=…, tool_mode=…)`; `preflight` reicht `decision.blocked_tools` herein. Nicht angeboten → kein Aufruf, `action.tree.loadFailed`, ohne „Nochmal versuchen“-Chip (ein zweiter Versuch hülfe nicht) |
| 4 | MINOR: Anzahl und „weitere“ nicht am Eintrag | bestätigt | Kennungen an den Nebentexten, `aria-describedby` am `treeitem` (nur wenn vorhanden); der Name bleibt der Titel |
| 5 | MINOR: jeder Fehlschlag sagt „prüfe das Argument“ | bestätigt | eigener Text für `transport`/`timeout`/`auth`: „gerade nicht erreichbar. Rufe es nicht noch einmal auf; antworte ohne den Baum.“ Ablehnung des Servers (`tool`) und unbrauchbare Form behalten den bisherigen Text |
| 6 | MINOR: Aufruf fehlt in `tools_called`, `outcomes`, `respond.werkzeuge` | bestätigt (Agent und Muster-Vorrunde) | `datenquelle.aufruf` gibt `Ergebnis(block, text, outcome)` zurück (`ToolOutcome`: `success`/`empty` mit Zahl oben, sonst `error`/`timeout` mit der Art, nie Servertext). Beide Schleifen tragen den **Modulnamen** ein (so erfüllt er auch die Pflicht eines Musters, das `ui_themenbaum` verlangt) und messen unter `schritt("respond.werkzeuge")`; Frist des Agenten → `timeout` |
| 7 | NIT: Muster-Vorrunde „mit Frist“ (`asyncio.wait_for`) | **nicht umgesetzt — Widerspruch:** Die Agent-Schleife hat keine Konstante, sondern die Gesamtfrist des Laufs (`innerhalb(ende, …)`); die Muster-Schleife hat keine Laufrist. Jeder MCP-Aufruf — auch dieser, über `call_mcp_tool_status` — ist im Transport durch `MCP_CALL_TIMEOUT_S` gedeckelt (`transport._call_tool`, Art `timeout`), genau wie die übrigen Werkzeuge der Muster-Schleife (`call_with_outcome` ohne eigenes `wait_for`). Eine zweite, kürzere Frist nur für dieses Werkzeug wäre eine neue Konstante ohne Gegenstück. Der Zeitüberschreitungs-Weg ist über Befund 5 getestet (`timeout` → „nicht erreichbar“, kein Block, Antwort derselben Runde verworfen) |
| 8 | NIT: Übersicht nennt bei abgeschaltetem Werkzeug nur `widget_module` | bestätigt | Module mit Datenquelle tragen zusätzlich `{code: data_source, tool}`; Studio: `AgentToolLock.tool`, `lockText` → `agentTools.lock.dataSource` (de/en). Code im Stil der übrigen Sperren (`code` + Feld) statt `datenquelle:<werkzeug>` |
| 9 | NIT: Kommentar „vier Namen“ in `base_widget.py` | bestätigt (der Dispatch kennt fünf) | Kommentar nennt `show_collection_tree` als absichtlich fehlende fünfte Aktion (kein Kontext-Knopf) |
| 10 | NIT: Werkzeugname hart in `themenbaum_aktion` | bestätigt | `_werkzeug()` liest ihn aus dem Manifest (`datenquelle.werkzeug`) |
| 11 | NIT: Überschrift doppelt (Blase + Kopf des Blocks) | bestätigt | kleinere Änderung: Begleitsatz neutral („Hier sind die Unterthemen:“ / „Here are the subtopics:“); der Block behält seinen Kopf und `titel` (beschreibt sich im Verlauf selbst; die Nutzernachricht der Aktion nennt den Titel ohnehin) |
| 12 | NIT: Enter auf einem Blatt tut nichts | bestätigt | Enter auf einem Eintrag ohne Kinder = „Inhalte anzeigen“ (APG-Standardaktion), nicht während eines Zugs; Leertaste unverändert |

**Abweichungen vom Plan (Aufgabe e-6):** die Direktaktion steht in `services/themenbaum_aktion.py` statt `services/direct_actions_baum.py`; `domain/config_models/base_widget.py` bleibt ohne Änderung der Auswahl (`show_collection_tree` ist kein Kontext-Knopf), nur ihr Kommentar ist berichtigt.

**Prüfung Review U1-e:** siehe Änderungsnotiz (`docs/aenderungen/2026-11-03-paket-u1e.md`, Abschnitt „Review“).

### Offen (U1-e)

- **`_handle_browse_collection`** (Direktaktion „Inhalte anzeigen“, Bestand vor U1-e) ruft `get_collection_contents` ebenfalls ohne Angebotsprüfung (Studio-Schalter, Sperren, Modus der Einbettung). Nicht in diesem Paket geändert.
- **Auswahl („später wählen“)**: kommt mit `ui_themenbaum_auswahl` (abfragend, §13) — `aria-selected` und `antwort.knoten_id` sind dann der Weg.
- **`structuredContent` für Werkzeuge ohne JSON-Text**: Der Client verwirft es weiter; die Datenquelle braucht es heute nicht (E-2). Ein Seitenkanal im Client wäre ein eigener Schritt.
- **Muster, die heute `browse_collection_tree` nennen**, zeigen weiter Karten; ob sie auf `ui_themenbaum` umgestellt werden, entscheidet der Nutzer.
- **Master-Skill-Vorlagen** (`docs/skills/vorgehen*.md`) und die Werkzeug-Schicht des Muster-Prompts (`services/response_prompt_tools_text.py`) nennen für Themenbäume noch `browse_collection_tree`; ob dort `ui_themenbaum` beschrieben wird, entscheidet der Nutzer (die Werkzeugbeschreibung aus dem Manifest steht ohnehin im Angebot).
- **Review U1-e** umgesetzt (Abschnitt „Review-Befunde U1-e“); Befund 7 bewusst nicht.
- **Keine MCP-Änderung nötig.** `includeContentCounts` bleibt aus (ein Abruf mehr je Knoten); Anzahlen zeigt der Baum nur, wo der Server sie ohnehin mitschickt (`contentsCount`).

## 16 U1-f Studio-Seite im Einzelnen (Tests zuerst)

### Befunde (2026-11-03, am Code geprüft)

- **Studio-Seiten:** eine Liste `studio-views.ts` erzeugt Navigation und Routen; kuratierte Seiten stehen als Daten in `views/curated-pages-*.ts`, Sonder-Panels als `CuratedPanelSection` mit eigenem Zweig in `curated-view.component.html` (Vorbild `agent-tools`, `material-typen`). Texte je Bereich in `i18n/catalogue/*.ts` (de/en nebeneinander, Wächter `parts.spec.ts`, `views-i18n.spec.ts`). `studio-views.spec.ts` erlaubt nur bekannte Paket-Kürzel.
- **Eine Seite trägt jeden Bereich nur einmal** (sonst 409, Paket 15): gilt für Bereichs-Abschnitte einer Seite; zwei Seiten, die dasselbe Dokument schreiben, schützt die Version (`expected_version` → 409 → `studio-save-conflict`).
- **Bereiche:** Modelle in `domain/config_models` (`AREA_MODELS`), gelesen über kuratierende Lader (`services/config_loader/*`), geschrieben über `PUT /api/config/data/{area}` (ganzes Dokument, Prüfung gegen das Modell, Version). Werk- und eigene Fassung (Paket 12) hängen am Bereich, nicht am Feld; die Werks-Prüfsumme rechnet über die geparsten Daten (`werkfassung.py:46`) — ein reiner YAML-Kommentar im Seed ändert sie nicht.
- **`display_rules`** geht kuratiert in jede Antwort (`turn_persist`, `direct_actions`): ein neuer Schlüssel im Rückgabewert von `load_display_rules_config` wäre öffentlich.
- **Wo Module angeboten werden:** `werkzeuge.modul_werkzeuge` (Agent `agent_tools.build_agent_tools`, Muster `response_tool_selection`, Studio `agent_prompt_preview`), Übersicht `agent_tool_overview` (Sperren `widget_module`, `data_source`), abgeleitete Blöcke `abgeleitet.ergaenzt` (live `antwort_fuer`, Verlauf `ui_aus_gespeichert`), Direktaktion `themenbaum_aktion`. Die Schleifen führen nur Angebotenes aus (`nimm_module_an`, Agent-Prüfung). Eval-Läufe melden keine Module (`environment.ui_module` fehlt) — nicht betroffen; `eval/metrics` nimmt Module nur aus der Werkzeug-Treue.
- **`x-nur-system`** ist ein Feld-Vermerk in `eingabe` (`ui_inhaltsrahmen.art`: `volltext`, `schreib_vorschau` setzt nur das System), keine Modul-Eigenschaft.
- **Vorschau:** Das Studio darf `@boerdi/ui-module` importieren (Pfad-Alias; die Lint-Sperre gilt nur innerhalb der Modul-Bibliothek). Die Module brauchen `MODUL_HOST`, einen `ModulKontext` und die `--mat-sys-*`-Token, die nur das Widget an `:host` ausgibt (`widget.component.scss`, `mat.theme`); das Studio hat sie nicht. Die Trefferliste braucht einen `ResultGroupsContext` (Übersetzer aus `@boerdi/ui/i18n`, wie in ihrer Spec). Die Studio-Route ist lazy, das Widget-Bündel bleibt unberührt.
- **E2E:** Playwright prüft nur das Widget-Bündel (`playwright.config.ts`); für das Studio gibt es keinen Aufbau mit gemocktem Backend.

### Entscheide (U1-f)

| # | Frage | Entscheid | Warum |
|---|---|---|---|
| F-1 | Wo stehen die Schalter? | **`01-base/display-rules` → `display_rules.ui_module {aus: [], agent_aus: []}`** — Ausschalt-Listen wie `werkzeuge_aus`; fehlt ein Name, ist das Modul an. Eigener kuratierender Lader `load_ui_modul_schalter()` (eigene Datei `config_loader/ui_module.py`), **nicht** im Rückgabewert von `load_display_rules_config` (der ginge in jede Antwort). Seed: nur ein Kommentar. Seite „Anzeige“ blendet das Feld aus (`ohneFelder`), es gibt eine Pflegestelle | vorhandener Bereich „was der Chat zeigt“: Werk-/eigene Fassung, Sicherung, `import-config`, Werksabgleich gelten ohne Änderung; kein neuer Bereich (Modell, Seed, Wirkungstabelle, Heimatseite), keine Migration; ein Daten-Eintrag im Seed meldete angepassten Anlagen nur eine Schein-„neue Werksfassung“ |
| F-2 | Was heißt „aktiv = aus“? | Neue Antworten zeigen das Modul nicht mehr: kein Werkzeug (Agent und Muster-`tools:`), keine abgeleiteten Blöcke (`ui_module:` des Musters ∩ aktiv — dann stehen die bisherigen Trefferboxen), die Direktaktion `show_collection_tree` baut keinen Baum (eigener Satz `action.tree.inactive`, ohne „Nochmal“). **Verlauf:** gespeicherte Blöcke bleiben, wie sie gezeigt wurden; abgeleitete folgen der aktuellen Einstellung (wie `ui_module:` heute) | Der Verlauf ist ein Protokoll. Eine Textfassung im Verlauf bräuchte eine Widget-Änderung, und ältere Widgets zeigten das Modul mit leeren Daten; ein fehlerhaftes Modul behebt ein Widget-Update, nicht dieser Schalter. Eine offene Frage eines danach abgeschalteten Moduls bleibt beantwortbar (sie wurde gestellt) |
| F-3 | Was heißt „für den Agenten = aus“? | Nur der Agent-Modus bietet das Modul nicht an; ein Muster, das es unter `tools:` nennt, bietet es weiter (U-F4: eine redaktionelle Wahl je Muster). Schaltbar nur bei Modulen mit eigenem Werkzeug (`agent: true`, nicht Inhaltsrahmen, nicht abgeleitet); sonst steht „—“ mit Grund | kleinste Regel, die beiden Modi ihre eigene Steuerung lässt |
| F-4 | `ui_inhaltsrahmen` | **fest** (beide Schalter nicht verfügbar, das Modell weist den Namen in beiden Listen ab) | trägt Systemarten (`x-nur-system`: Volltext, Schreib-Vorschau — die Vorschau muss vor einer Freigabe sichtbar sein); das Dokument-Werkzeug ist bewusst nicht sperrbar (`agent_tools`); die Anzeige steuert `inline_documents.enabled` auf „Anzeige“ |
| F-5 | Übersicht und Vorschau des Agenten | `modul_werkzeuge(…, fuer="agent" \| "muster")` als Pflichtangabe; Übersicht: Sperre `{code: studio_off}` nur, wenn abgeschaltet, mit Link auf die Seite; Prompt-Vorschau nennt und zählt nur Module für den Agenten. Katalog `choices.tools` bleibt vollständig (ein Muster darf ein abgeschaltetes Modul nennen; es wirkt, sobald es an ist) | eine Stelle für das Angebot, keine stille Vorgabe |
| F-6 | Studio-Seite | gemeinsame Seite `ui-module` (Gruppe „gemeinsam“, Paket `U1`) mit Panel `ui-module`: Liste links (Titel, Name, Zustand — gebaut; geplant war „Art“ statt „Name“, die Art steht in den Angaben), rechts Angaben, Schalter, Vorschau. `GET /api/config/ui-module` liefert Katalog und Schaltbarkeit; die Schalter schreiben das Dokument über `/config/data` mit Version (Entwurf, Speichern/Verwerfen, Konflikt, Verlassen-Schutz wie „Werkzeuge“) | gleiche Bedienung wie die Werkzeug-Schalter |
| F-7 | Vorschau | **echte Komponenten** aus dem Register von `@boerdi/ui-module` in einem Rahmen mit dem M3-Theme des Widgets (Mixin aus `widget.component.scss` nach `ui/src/theme/_m3-theme.scss` gelöst, Widget-Ausgabe gleich). Host ohne Wirkung nach außen: Herunterladen, Drucken, Aktionen und Antworten werden angesagt statt ausgeführt; Links öffnen nicht (Klick abgefangen). Beispiel mit `antwort` → nur lesend. Fehlt das Modul im Register oder passt die Version nicht: Hinweis und Beispieldaten als JSON | zeigt, was das Widget zeigt, ohne dass etwas die Seite verlässt |

### Aufgaben

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| f-1 | Modell `UiModulSchalter` an `DisplayRulesBlock` (Namen `^ui_[a-z0-9_]{2,40}$`, eindeutig, kein festes Modul), Lader `load_ui_modul_schalter`, Seed-Kommentar | `config_models/base_widget.py`, `ui_module/namen.py`, `config_loader/ui_module.py`, `seeds/01-base/display-rules.yaml` | Modell weist `ui_inhaltsrahmen` und falsche Namen ab; Lader durch den echten Speicher; nicht in `load_display_rules_config` |
| f-2 | `ui_module/schalter.py` (`aktiv`, `fuer_agent`, `schaltbar`) und `modul_werkzeuge(…, fuer=…)` | `ui_module/schalter.py`, `ui_module/werkzeuge.py` + Aufrufer | Agent ohne `agent_aus`/`aus`, Muster nur ohne `aus` |
| f-3 | abgeleitete Blöcke, Direktaktion | `ui_module/abgeleitet.py`, `services/themenbaum_aktion.py`, `i18n/bot_text.py` | Trefferliste aus → kein Block (live und Verlauf); Aktion ohne Aufruf |
| f-4 | Übersicht, Prompt-Vorschau | `services/agent_tool_overview.py`, `services/agent_prompt_preview.py` | `studio_off`, Namen und Zeichen |
| f-5 | Endpunkt `GET /api/config/ui-module`; OpenAPI, Bereichs-Schemas neu | `api/config_ui_module.py`, `main.py`, `docs/api/*`, Studio-Fixture | Antwort je Modul mit Schaltbarkeit; Studio-Schlüssel nötig |
| f-6 | Studio: Seite, Panel, Logik, Vorschau-Host, Texte de/en, `ohneFelder` auf „Anzeige“, Sperrtext `studio_off` | `studio-views.ts`, `curated-pages-gemeinsam.ts`, `views/ui-module*.ts`, `i18n/catalogue/ui-module.ts`, … | Specs: Liste, Zustände, Schalter, Speichern/Konflikt, Vorschau rendert jedes Beispiel ohne Wirkung nach außen |
| f-7 | Prüfung, Doku | Plan, Änderungsnotiz, `bewusste-vertragszusaetze.md` | Suiten, Gates, Bündel |

**Stand U1-f (2026-11-03):** umgesetzt (f-1 … f-7).
- **Backend:** `UiModulSchalter` an `DisplayRulesBlock` (Validator `namen.pruefe_schalter_namen`, `namen.FEST`, neu `namen.ENTSCHEIDUNG`), Lader `config_loader/ui_module.py`, `ui_module/schalter.py` (`aktiv`, `fuer_agent`, `schaltbar`); `modul_werkzeuge(…, fuer=…)` in Agent-Werkzeugen, Muster-Auswahl und Prompt-Vorschau; `abgeleitet.ergaenzt` nur mit aktiven abgeleiteten Modulen; Direktaktion mit Satz `action.tree.inactive` (de/en); Übersicht mit Sperre `studio_off`; Route `GET /api/config/ui-module` (`api/config_ui_module.py`). Seed `display-rules.yaml` nur mit Kommentar.
- **Studio:** Seite `ui-module` (Gruppe „Gemeinsam“, Paket `U1`), Panel `studio-ui-module` (Liste, Schalter mit `role="switch"` und Beschreibung, Speichern/Verwerfen, Konflikt mit Zusammenführen auf den neuen Stand, Verlassen-Schutz über `curated-view`), Vorschau `studio-ui-modul-vorschau` (echte Komponenten, `VorschauModulHost`, eigener Chunk per `@defer`), Logik `views/ui-module.ts`, Dienst `core/ui-module-api.service.ts`, Texte `i18n/catalogue/ui-module.ts` und Feldtexte; Sperrtext und Link `studio_off` auf „Werkzeuge“; „Anzeige“ mit `ohneFelder: ['display_rules.ui_module']`.
- **Theme:** Mixin `ui/src/theme/_m3-theme.scss`; das Widget nutzt es — Bündel byte-gleich (`cmp` gegen den Stand vor U1-f).
- **Vertrag:** OpenAPI neu (ein Pfad, keine neuen Schemas), Bereichs-Schemas neu (Studio-Fixture); zwei Zeilen in `docs/api/bewusste-vertragszusaetze.md`; Routen-Inventar in `tests/test_openapi_contract.py`.
- **Abweichungen vom Plan:** Das Beispiel mit `antwort` startet in der Vorschau **offen** (zum Ausprobieren); „Beantwortet zeigen“ schaltet auf nur lesend — sonst wären beide Beispiele der Entscheidung nie bedienbar. Zusätzlich „Als Kacheln zeigen“ für die Trefferliste. Die Feldtabellen scrollen unter 30rem in ihrem Rahmen.

**Prüfung U1-f:**
- **Backend:** neu `tests/test_ui_modul_schalter.py` (31, vorher rot); angepasst Aufrufe von `modul_werkzeuge` in `test_ui_entscheidung`, `test_ui_themenbaum`, `test_agent_prompt_preview`, dazu `test_openapi_contract`. Zielgruppe (UI-, Übersicht-, Vorschau-, Lader-, Modell-, Router-Tests) 373 bestanden. Ganze Suite: 7253 bestanden, 490 übersprungen, 1 Fehlschlag umgebungsbedingt (`test_repo_config::test_health_nennt_das_repositorium`, ohne Postgres). ruff sauber; `export_openapi.py --check` und `export_area_schemas.py --check` unverändert nach dem Neuerzeugen.
- **Frontend (nacheinander):** `ui-module` 71, `ui` 1093, `widget` 76, `studio` 1903 (vorher 1855) bestanden; eslint (berührte Dateien) sauber; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs` sauber; `module-register --pruefen` aktuell. Bündel 610,74 kB roh / 178,22 kB gzip — unverändert. Studio-Build (Produktion, ohne Inline-Skript): Initial 888,33 kB; `curated-view` 245,46 kB, Vorschau-Chunk 19,30 kB.
- **Gegenprobe:** ohne `preventDefault` in der Vorschau scheitert „ein Link öffnet nichts“.
- **Sichtprüfung:** gebautes Studio mit gemocktem Backend (Playwright-Skript außerhalb des Repos): 1280 px hell und dunkel, 320 px ohne waagerechten Überlauf; Module im M3-Theme, Schalter, Feldtabellen, Themenbaum und Trefferliste in der Vorschau. Kein Studio-E2E im Repo (Playwright prüft nur das Widget).

### Review-Befunde U1-f (2026-11-03, behoben)

Je Befund erst am Code geprüft, dann ein roter Test (Studio-Specs, `tests/test_agent_prompt_preview.py`), dann die kleinste Änderung. Alle Befunde bestätigt.

| # | Befund | Prüfung | Änderung |
|---|---|---|---|
| 1 | MAJOR: Vorschau fängt Links nur in der Bubble-Phase ab; die Kachel hält ihren Klick an | bestätigt: `wlo-card-tile` ruft `(click)="$event.stopPropagation()"` am `<a target=_blank>` — in „Als Kacheln zeigen“ öffnete ein Klick (auch Enter) den Link | Die Vorschau hört am eigenen Host in der **Capture-Phase** auf `click`, `auxclick` (nur Taste 1) und `submit` (Listener im Konstruktor, `DestroyRef` räumt sie ab); nur Ziele in `.umv-buehne`. `wlo-card-tile` unverändert. Specs: Kachel-Link per Klick und per Enter (`click` mit `detail: 0`), Mittelklick, „In WLO öffnen“ im Themenbaum, Formular der Entscheidung. Die zwei Kachel-Klick-Specs waren vorher rot |
| 2 | MINOR: „Trotzdem speichern“ setzte die ganzen Listen `aus`/`agent_aus` des Entwurfs auf den neuen Stand | bestätigt (`erzwingen`) — ein inzwischen fremd umgelegter Schalter wurde zurückgedreht | `ui-module.ts` `mitUmschaltungen(neu, geladen, entwurf)`: je Liste nur, was der Entwurf gegenüber dem geladenen Stand hinzugefügt oder entfernt hat, auf die frischen Listen; übrige Schlüssel unter `ui_module` bleiben. Specs: fremder Schalter überlebt; hin- und zurückgelegter Schalter überträgt nichts |
| 3 | MINOR: Gegenrichtung auf „Anzeige“: `ohneFelder` blendet `display_rules.ui_module` aus, „Trotzdem speichern“ schickte das alte Dokument | bestätigt; dieselbe Lücke bei den Personas unter „Dimensionen“ (`ohneFelder: ['frontmatter.formality']`, Anrede auf „Zielgruppen“) | generisch in `AreaDocEditor.save(area, { force, vomServer })`: nur beim erzwungenen Speichern liest der Editor den Serverstand und übernimmt die verborgenen Pfade von dort (fehlt einer dort, fehlt er auch im Gesendeten); Bedingung bleibt die gemeldete Version. `area-section` und `group-section` reichen `section.ohneFelder` durch. Ohne Konflikt kein zusätzlicher Abruf (die Versionsbedingung schützt). Scheitert das Lesen, wird nichts geschrieben. Specs: Mechanismus (übernehmen, entfernen, kein Abruf ohne Konflikt, Lesefehler) und der Fall „Anzeige“ mit der echten Seiten-Definition |
| 4 | MINOR: `@defer` ohne `@error` | bestätigt | `@error` mit Hinweis (`role="alert"`) und Knopf „Seite neu laden“ (`location.reload()`), de/en. Spec rendert den Fehlerzustand (`DeferBlockBehavior.Manual`) |
| 5 | MINOR: WCAG 3.1.2 — Manifest-Texte nur deutsch | bestätigt | `lang="de"` an Beschreibung, „wann“/„nicht wann“, Feldbeschreibungen (eigener `span`, die Werte-Hinweise bleiben in Studio-Sprache), Beispieltiteln, Beispiel-JSON und der Bühne. **Entscheid Bühne:** immer `lang="de"` — die Beispieldaten sind deutsch und machen den Text der Bühne aus; die kurzen Bedienwörter der Module folgen weiter der Studio-Sprache und stehen im englischen Studio damit in einem deutsch ausgezeichneten Bereich (bewusst hingenommen, siehe Offen). Titel sind zweisprachig und bleiben ohne Auszeichnung |
| 6 | NIT: Ansage überlebt den Modulwechsel | bestätigt | `meldung` ist ein `linkedSignal` über Modul, Beispiel, „Beantwortet“ und „Kacheln“ |
| 7 | NIT: Sperrtext `studio_off` sagt „für den Agenten“, auch bei ganz abgeschaltetem Modul | bestätigt (`schalter.fuer_agent` ist auch bei `aus` falsch) | ein Code, neutraler Text: „Auf der Seite „UI-Module“ abgeschaltet.“ / „Switched off on the “UI modules” page.“; `lockText` nutzt ihn (Spec de und en); Docstring in `agent_tool_overview.py`. Zwei Codes brächten nur einen genaueren Satz — die Seite zeigt den Zustand ohnehin |
| 8 | NIT: rollende Feldtabelle nicht per Tastatur erreichbar | bestätigt | `tabindex="0"`, `role="region"`, `aria-labelledby` auf die Überschrift („Eingabe“/„Antwort der Person“) — Muster wie `backup`, `eval-vergleich-v2`; Fokusring global |
| 9 | NIT: Doku | bestätigt | `architektur.md` §7 nennt „UI-Module“; F-6 berichtigt (Titel, Name, Zustand); offene Punkte in `offene-befunde-und-todo.md` |
| 10 | NIT: „leer“-Text nennt einen internen Pfad | bestätigt | „Der Katalog enthält keine UI-Module.“ / „The catalogue holds no UI modules.“ |
| 11 | (seit U1-e) Prompt-Vorschau: `names` zählte Module mit Datenquelle auch ohne verfügbares Werkzeug, `chars` nicht | bestätigt (rot: `['ui_entscheidung', 'ui_themenbaum']` bei verborgenem `browse_collection_tree`) | Namen und Umfang aus derselben Liste `modul_werkzeuge(…, verfuegbar=…, fuer="agent")`; der doppelte Filter `schalter.fuer_agent` entfällt (macht `fuer="agent"`) |

**Stand Review U1-f (2026-11-03):** alle elf Befunde behoben (Tabelle oben).

**Prüfung Review U1-f:** Backend: Zielgruppe (`test_agent_prompt_preview`, `test_ui_modul_schalter`, `test_agent_center_router`, `test_agent_tool_overview*`) 77 bestanden; neu `test_namen_und_umfang_zaehlen_dieselben_module` (vorher rot). Ganze Suite 7254 bestanden, 490 übersprungen, 1 Fehlschlag umgebungsbedingt (`test_repo_config::test_health_nennt_das_repositorium`, Zeitüberschreitung ohne Postgres); `ruff check src tests` sauber. Frontend nacheinander: `studio` 1921 (vorher 1903, +18 Specs; vorher rot: Kachel-Klick und -Enter, Ansage bei Modul-/Kachel-/Beantwortet-Wechsel, `lang`, beide Konflikt-Specs, Region, leer-Text, `@error`, verborgene Pfade — Kompilierfehler —, „Anzeige“-Fall gegengeprüft ohne Durchreichen von `ohneFelder`), `ui-module` 71; `ui`, Widget und Bündel unberührt (kein `npm run budget`). eslint (berührte Dateien) sauber; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs` sauber. Studio-Build (Produktion, kein Dev-Server lief): `index.html` ohne Inline-Skript; Initial 888,66 kB, `curated-view` 246,35 kB, Vorschau-Chunk 19,78 kB. Keine Sichtprüfung im Browser nach dem Review. Einzelheiten in der Änderungsnotiz (`docs/aenderungen/2026-11-03-paket-u1f.md`, Abschnitt „Review“).

### Offen (U1-f)

- **Textfassung im Verlauf** für abgeschaltete Module: bewusst nicht (F-2); bräuchte eine Widget-Regel „leere Daten → Textfassung“. Entscheid Nutzer, falls ein Modul auch rückwirkend verschwinden soll.
- **Studio-E2E** mit gemocktem Backend gibt es nicht; die Sichtprüfung war einmalig (vor dem Review; die Review-Änderungen sind nur durch Specs geprüft).
- **Neue Module** müssen in `ui-modul-vorschau.component.spec.ts` ihr Manifest importieren (der Test verlangt es); `module:neu` legt das nicht an.
- Der Studio-Probelauf meldet weiter keine Module (U1-d1) — die Schalter wirken dort nicht sichtbar.
- **Sprache der Bühne** (Review #5): im englischen Studio stehen die englischen Bedienwörter der Module in einem `lang="de"`-Bereich. Sauber wäre `lang` je Beispieltext im Modul — das bräuchte eine Änderung der Module bzw. des Vertrags.
- **Gleiche Lücke wie Review #3, nicht in diesem Paket:** Abschnitte mit `felder` (nur ein Ausschnitt sichtbar, z. B. `01-base/engine` auf „Betrieb“ und im Agent-Bereich, `device-config` auf „Anzeige“) senden beim „Trotzdem speichern“ ebenfalls die verborgenen Teile im geladenen Stand; ebenso die Anrede-Tabelle (`anrede.component.ts`, ganzes Persona-Dokument). Der Mechanismus `vomServer` trägt dafür nur Pfade, die verborgen sind — bei `felder` wäre es die Umkehrung (Serverstand + sichtbare Pfade aus dem Entwurf).
- **Fokus nach dem Speichern** (studioweit, WCAG 2.4.3): siehe `offene-befunde-und-todo.md` §5.

## 17 U1-g UI-Module in der Evaluation (Tests zuerst)

Auftrag Nutzer (2026-11-03): „bei der evaluation kannst du ein paar beispiel abläufe entwerfen z.b. sammlungsbaum darstellen für fachgebiet physik oder für die entscheidungsboxen ein gespräch das auf eine entscheidung hinaus läuft usw - immer im bildungskontext“.

### Befunde am Code (2026-11-03)

- **Widget:** meldet `environment.ui_module` = alle Schlüssel seines Registers, sortiert (`ui/src/shell/chat-shell.component.ts:1006`, `stream/chat-api.ts:277`) — heute die fünf Katalog-Module. Ohne Meldung bietet der Server kein Modul-Werkzeug an (`api/schemas.py`, `Environment.ui_module`).
- **Studio-Evaluation:** `services/eval/runner._post_chat` schickt nur `session_id` und `message`; der Gold-Lauf (`evals/run_golden.post_chat`) nur das `environment` des Flows. In keiner Evaluation wird also `ui_themenbaum` oder `ui_entscheidung` angeboten.
- **Golden-Checks:** keiner prüft die gezeigten Blöcke (`ui.ui_bloecke[].modul`); `tools_any` sieht seit U1-e `ui_themenbaum` (an `tools_called` gehängt), `ui_entscheidung` gar nicht. Ein Zug kann nicht im Auswahlfeld antworten (`ChatRequest.ui_antwort`), die Kennungen der Möglichkeiten wählt das Modell erst im Lauf.
- **Simulierte Person** (generativer Lauf) liest nur Blase und Canvas (`_merge_canvas`) — eine Frage im Auswahlfeld sieht sie nicht; der Judge (`_augment_bot_text`, Zwilling `augment_bot_text`) auch nicht, ebenso keinen Themenbaum.
- **Werkzeug-Treue** (`metrics._aggregate_classification_metrics`) nimmt Module bewusst aus (Review U1-d2) — bleibt so.
- Kein Seed-Muster nennt `ui_entscheidung` oder `ui_themenbaum` in `tools:`; im Muster-Modus entsteht der Baum nur über die Direktaktion `show_collection_tree`. Die neuen Abläufe messen deshalb den **Agenten**.

### Entscheide

| # | Entscheid | Warum |
|---|---|---|
| G-1 | Studio-Läufe (Gold und generativ) und die Kommandozeile melden **alle Katalog-Module**, wie das Widget. Schalter „UI-Module melden“ (Vorgabe an) im Studio-Start, Feld `ui_module: bool = true` an beiden Start-Anfragen; CLI `--ohne-ui-module`. Gemeldete Liste in `config.ui_module` und den Messbedingungen (`ui_module`), auch im Vergleich der Bedingungen (`engine_metrics.conditions_of`) | Die Evaluation misst sonst eine Anlage, die keine Person sieht; der Schalter erlaubt den Vergleich mit/ohne |
| G-2 | Ein `ui_module` im `environment` eines Flows gewinnt über die Laufvorgabe (auch über „ohne“) | Der Flow beschreibt dann eine bestimmte Einbettung |
| G-3 | Neuer harter Check `ui` aus `ui_any` (mind. eines der Module erscheint als Block) und `ui_none` (keines). **Grundwahrheit ist der gezeigte Block** (`ui.ui_bloecke[].modul`), nicht `tools_called`; `tools_called` bleibt MCP plus Module mit Datenquelle (wie seit U1-e). Namen beim Laden gegen den Katalog geprüft (CLI: `manifeste.json`, Studio: `ui_module.katalog`), sonst nur die Namensform | Engine-fair (abgeleitete Module entstehen ohne Aufruf); ein vertippter Name fiele sonst still durch |
| G-4 | Zug-Schlüssel `ui_antwort: {waehle: [Wendung …], freitext?: str}`: der Runner sucht im **vorigen** Zug den offenen `ui_entscheidung`-Block, wählt die Möglichkeiten, deren Beschriftung eine Wendung enthält (ohne Groß-/Kleinschreibung; auch exakte Kennung), bei Einzelwahl nur die erste, Freitext nur, wenn der Block ihn anbietet; Nachricht = Beschriftungen mit „, “ (+ Zeilenumbruch + Freitext) wie das Widget. Ohne offene Frage oder ohne passende Möglichkeit geht `message` als getippte Nachricht (der Server rahmt die Frage, `frage_block`); `observed.ui_antwort.status` sagt `beantwortet` / `keine_frage` / `keine_passende_option`. **Seit Review U1-g:** Treffer in drei Stufen (genau, ganze Wörter, Wortteil), Status `gesendet` statt `beantwortet`, Freitext auf 1000 Zeichen gekürzt (Review #1, #3) | Kennungen sind erst im Lauf bekannt; getippt ist der reale Rückfall einer Person |
| G-5 | Simulierte Person und Judge sehen die **Textfassung** jedes Blocks außer Inhaltsrahmen und Trefferliste (die stehen schon als Dokument bzw. Karten da) — kein neuer LLM-Aufruf; die simulierte Person antwortet getippt | Minimal; der Server ordnet getippte Antworten zu |
| G-6 | Jeder Zug-Datensatz (Gold und generativ) trägt `ui_module` (gezeigte Module); `GET /eval/runs/{id}` liefert `modul_nutzung` (beim Lesen gerechnet, `services/eval/modul_nutzung.py`): je Muster (Agent-Züge = `AGENT`) und je Anwendungsfall die Zahl der Züge je Modul. Studio: Tabelle in der Lauf-Ansicht; Markdown-Bericht: Abschnitt | Alte Läufe: „nicht erfasst“ statt Nullen |
| G-7 | Die Beispiel-Abläufe stehen in **eigener Datei** `evals/ui-module-flows.yaml` (wie `skill-bruecke-flows.yaml`), nicht in der Seed-Suite | Die Maschinen-Matrix liest die Seed-Suite; „nur auf Abruf“ hieße im Studio „schreibt echt“. Für den Studio-Lauf bliebe ein Import — offen für den Nutzer |

### Aufgaben (Tests zuerst)

1. `evals/run_golden.py`: `katalog_module()`, `ui_any`/`ui_none` (Check `ui`, Validierung), `ui_antwort`-Züge, Textfassungen in `augment_bot_text`, Zug-Feld `ui_module`, `run_flows(…, ui_module=…)`, CLI `--ohne-ui-module`, Bericht `ui_module`. Tests in `tests/test_golden_ui_module.py`.
2. Backend: `GoldenRunRequest`/`StartRequest.ui_module`, `golden_run`/`generative_run`/`runner` reichen die Liste weiter, `run_conditions(ui_module=…)`, `conditions_of`, `modul_nutzung.py`, `run_profile.get_run_with_profile`, `bericht_md`. OpenAPI neu.
3. Studio (`/better-coding-frontend`): Schalter in beiden Start-Formularen, Kategorie `ui`, Messbedingung, Tabelle „Modul-Nutzung“, Hinweistext der Erwartungen; i18n de/en.
4. `evals/ui-module-flows.yaml` (sieben Abläufe), Format-Wächter; Doku (README, Änderungsnotiz, offene Befunde).

**Stand U1-g (2026-11-03):** umgesetzt wie entschieden (G-1 … G-7). Abweichung: Einzelwahl in `ui_antwort` nimmt die **erste Wendung**, die eine Möglichkeit trifft (Vorrang des Autors), nicht die erste Möglichkeit im Block. Neu `ui_module/katalog.widget_module()` (eine Quelle für „was das Widget meldet“). Die Werkzeug-Treue (`metrics.py`) bleibt ohne Module. Der I06-Vorlauf des generativen Laufs (`_prime_i06_session`) meldet keine Module — er bereitet nur Material vor.

**Beispiel-Abläufe** (`evals/ui-module-flows.yaml`):

| Flow | Zielgruppe | Verlauf | Tragende Erwartung |
|---|---|---|---|
| GV-UI-1 | Lehrkraft | Physik-Themen im Überblick → Optik eine Ebene tiefer | `ui_any [ui_themenbaum]` je Zug, Zug 1 ohne Auswahlfeld |
| GV-UI-2 | Lehrkraft | Themenstruktur Biologie → Ökologie-Arbeitsblätter Kl. 9 | Baum, dann `ui_trefferliste` + Karten |
| GV-UI-3 | Lehrkraft | „Material zum Thema Energie für Klasse 7“ (Fach offen) → Auswahl „Physik“ | `ui_entscheidung`, dann `ui_trefferliste` ohne zweite Frage |
| GV-UI-4 | Lehrkraft | Doppelstunde Photosynthese, Bausteine zur Auswahl → Mehrfachwahl + Freitext | `ui_entscheidung`, dann `ui_inhaltsrahmen` (Verlaufsplan) |
| GV-UI-5 | Lernende | „ich versteh brüche nicht“ → Klasse/Vorwissen | `ui_entscheidung` oder `ui_trefferliste`, geduzt |
| GV-UI-6 | Andere | Smalltalk, Frage nach Öffnungszeiten/Support | `ui_none [ui_entscheidung, ui_themenbaum]` |
| GV-UI-7 | Lehrkraft | Video Lichtbrechung Kl. 8 — beide Maschinen | `ui_any [ui_trefferliste]`, `ui_none [ui_entscheidung]` |

**Prüfung U1-g:**
- **Backend:** neu `tests/test_golden_ui_module.py` (24, vorher rot: alle), `tests/test_eval_ui_module.py` (16, vorher Sammelfehler), `tests/test_golden_ui_module_flows.py` (4, Format-Wächter). Angepasst: Attrappen auf die neuen Signaturen (`post_chat … ui_antwort`, `run_flows … ui_module`, `run_conditions … ui_module`, `validate_flows … module`) in `test_golden_runner`, `test_golden_umgebung`, `test_golden_ab`, `test_eval_runner`, `test_golden_messdaten`, `test_eval_router`, `test_eval_pg`; Kategorie `ui` in den Pins von `test_golden_runner`; Abschnitt „Modul-Nutzung“ in `test_eval_bericht_md`. Zielgruppe 162 bestanden. Ganze Suite (`uv run --frozen pytest -q -p no:cacheprovider`): 7781 bestanden, 4 übersprungen, **4 Fehlschläge außerhalb von U1-g** (siehe „Offen“). `ruff check src tests ../evals` sauber. OpenAPI neu erzeugt (zwei Felder), `--check` danach unverändert; Bereichs-Schemas unverändert.
- **Frontend:** `npx ng test studio` 1930 bestanden (158 Dateien; neu `eval-modul-nutzung.component.spec.ts`, Fälle in Gold-/Generativ-Start, Messbedingungen, `eval-api.service.spec`); eslint der berührten Dateien sauber; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs` sauber; Studio-Build (Produktion) ohne Inline-Skript, Initial 890,75 kB / 218,15 kB gzip. Widget und `ui`/`ui-module` nicht berührt.
- Kein Golden-, Eval- oder Lastlauf (startet der Nutzer).

### Review-Befunde U1-g (2026-11-03, behoben)

Je Befund erst am Code geprüft, dann ein roter Test, dann die kleinste Änderung. Alle Befunde bestätigt; die freiwillige Annahme-Erkennung (#3) nicht umgesetzt — siehe dort.

| # | Befund | Prüfung | Änderung |
|---|---|---|---|
| 1 | `baue_ui_antwort`: Teilwort-Treffer wählen falsch („Physik“ traf zuerst „Astrophysik“; Mehrfachwahl nahm jede Möglichkeit, die die Wendung nur enthält) | bestätigt (`w in label`, Block-Reihenfolge) | `_trefferstufe`: 0 = genaue Beschriftung oder Kennung, 1 = ganze Wörter (`(?<!\w)…(?!\w)` auf `_normalized`), 2 = Wortteil als letzter Rückfall. Je Wendung zählt nur ihre beste Stufe. Einzelwahl: beste Stufe, darunter die erste Wendung, deren erste Möglichkeit; Mehrfachwahl: je Wendung ihre besten Treffer, Block-Reihenfolge. Tests: Astrophysik vor Physik, ganzes Wort vor Wortteil, Stufe vor Wendungsfolge, Wortteil als Rückfall, Mehrfach-Fehltreffer |
| 2 | GV-UI-5 Zug 2: `waehle` mit „Grundlagen“ und „6.“ trifft fremde Möglichkeiten | bestätigt (Vorwissens-Frage „Grundlagen sitzen …“, „Klasse 6./7. gemischt“) | `waehle: [Klasse 6, gar nicht, von vorne, Anfang]`; Format-Wächter mit einer typischen Mehrfach-Frage |
| 3 | Status `beantwortet` heißt nur „gesendet“ — der Server verwirft eine unpassende Antwort mit einer Log-Zeile (`services/ui_antwort.py`); Freitext ungekürzt (Widget kürzt auf `FREITEXT_MAX`, Manifest `maxLength` 1000) | bestätigt | Status `gesendet` (Runner, README, Plan, Tests; das Studio zeigt ihn seit #9 übersetzt). `FREITEXT_MAX = 1000` im Runner wie im Widget (getrimmt, dann gekürzt), Test hält ihn am Manifest; gekürzt → `observed.ui_antwort.freitext_gekuerzt` (ursprüngliche Länge) und eine Warnzeile auf der Konsole. **Annahme erkennen: nicht umgesetzt** — die Chat-Antwort trägt sie nicht (die geprüfte Antwort steht nur im Debug-Block der *Nutzer*nachricht, `_ui_antwort`); dafür bräuchte es ein neues Debug-Feld (Vertragsänderung) |
| 4 | (dazu der ältere MAJOR) Dialog-Stufe des generativen Laufs baute den Text ohne Karten und ohne Inhaltsrahmen — simulierte Person und Judge sahen keine Treffer und keine Dokumente; die G-5-Ausnahme verbarg genau die | bestätigt (`_merge_canvas` + `_mit_textfassungen` statt `_augment_bot_text`) | Dialog-Stufe nimmt `_augment_bot_text(bot_resp)` (schließt `_merge_canvas` ein) wie die Szenario-Stufe. Die simulierte Person liest `_fuer_die_person`: die übrige Antwort bis `_PERSON_MAX` (1500) und die Textfassungen danach mit eigenem Deckel — eine lange Blase schneidet die Frage nicht mehr ab. Tests: Karten, Dokument, Leinwand für Judge und Person; Frage hinter 3000 Zeichen Blase |
| 5 | GV-UI-1 Zug 2 (Optik tiefer) kaum erreichbar: die Quittung des Themenbaums nennt keine Knoten | bestätigt (`themenbaum.quittung`) | `ui_any: [ui_themenbaum, ui_trefferliste]`, Erwartung und `must_offer` angepasst; Grenze im Kopf der Datei, im README und unten unter „Offen“ |
| 6 | GV-UI-6 Zug 1 (Smalltalk) verbot auch das Auswahlfeld | bestätigt — „Wobei kann ich helfen?“ als Auswahlfeld ist vertretbar | Zug 1 nur `ui_none: [ui_themenbaum]`; Zug 2 behält beide (die Gegenprobe der Datei bleibt erfüllt) |
| 7 | Gemeldet ≠ angeboten: im Studio abgeschaltete Module bietet der Server trotzdem nicht an; die Messbedingungen sagten das nicht | bestätigt (`ui_module/schalter`) | `run_conditions`: `ui_module_wirksam = {module, agent_aus}` (gemeldet ∩ aktiv; davon nur für den Agenten aus; `fest` gilt immer; Lesefehler → `{fehler}`), auch in `conditions_of`. `gold_flows.eigene_ui_module` (nur wenn ein Flow im `environment` eigene Module setzt, G-2). Hinweis `evalStart.uiModule.hint` de/en ergänzt |
| 8 | `compare_golden.py` verschwieg ungleiche UI-Module | bestätigt | Bericht trägt `ui_module_ref`/`ui_module_new` (`None` = Bericht von vor U1-g), Kopf „UI-Module: … → …“ und eine Warnzeile bei Ungleichheit (kein Blocker) |
| 9 | Studio: geöffneter Gold-Zug zeigte weder `ui_any`/`ui_none` noch gezeigte Module noch `ui_antwort.status` | bestätigt | `eval-gold-turns`: Zeilen „UI-Module — Soll: eines von … · keines von … · gezeigt: …“ und „Antwort im Auswahlfeld: {Status} · gewählt: …“ (Status übersetzt, unbekannter als Code); fehlen bei Zügen ohne UI-Erwartung bzw. ohne Antwort. Specs de/en |
| 10 | NIT: „Nicht erfasst (Lauf von vor U1-g)“ auch bei `zuege == 0` | bestätigt (`bericht_md`, `eval-modul-nutzung`) | eigener Satz „Noch keine beantworteten Züge.“ / „No answered turns yet.“ in Bericht und Studio |
| 11 | NIT: Ersatzblasen (Fehler/„ausgelastet“) zählten in der Modul-Nutzung als Zug ohne Modul | bestätigt | `modul_nutzung` überspringt Züge mit `golden.fallback` wie Fehlzüge |
| 12 | NIT: Format-Wächter wählte den Flow über die Stelle | bestätigt | `_flow(flow_id)` |
| 13 | NIT: Zwillinge `_SCHON_GEZEIGT`/`_TEXTFASSUNG_MAX` ohne Test | bestätigt | Test hält `runner` und `run_golden` gleich (wie `FALLBACK_TEXTS`) |
| 14 | 4 × `RuntimeWarning: coroutine … was never awaited` in `test_eval_ui_module.py` | bestätigt: die Start-Attrappe schließt nur die äußere Koroutine (`mit_herzschlag`), die innere `_execute_…_run` blieb offen | eigene Attrappe `_ohne_start` (ersetzt `mit_herzschlag`, schließt die innere); ältere Tests (`test_eval_router`) unverändert, siehe „Offen“ |

**Stand Review U1-g (2026-11-03):** alle vierzehn Befunde behoben (Tabelle oben); die Annahme der Auswahlfeld-Antwort bleibt unsichtbar (#3, siehe „Offen“).

**Prüfung Review U1-g:** Backend: neue Tests vorher rot — `test_golden_ui_module` (8 rot: Stufen, Mehrfachwahl, Freitext, Manifest-Grenze, Status), `test_golden_ui_module_flows` (3 rot: GV-UI-5, GV-UI-1, GV-UI-6), `test_eval_ui_module` (6 rot: Dialog-Text, Frage hinter langer Blase, Ersatzblasen, Bericht bei null Zügen, `ui_module_wirksam`, `eigene_ui_module`), `test_golden_compare` (2 rot); der Zwillings-Test (#13) ist ein Wächter und war von Anfang an grün. Zielgruppe danach grün (`test_golden_ui_module` 31, `test_golden_ui_module_flows` 7, `test_eval_ui_module` 23, `test_golden_compare` 25, dazu `test_eval_runner`, `test_eval_bericht_md`, `test_golden_messdaten`, `test_engine_matrix`, `test_eval_compare`, `test_eval_router`); `test_eval_ui_module.py` ohne „never awaited“ (`-W default`). Ganze Suite mit Postgres (`uv run --frozen pytest -q -p no:cacheprovider`): **7805 bestanden, 4 übersprungen, 0 Fehlschläge** (15:28 min; vorher 7786). `ruff check src tests ../evals` sauber; `export_openapi.py --check` und `export_area_schemas.py --check` unverändert. Studio nacheinander danach: neue Specs gegen den alten Stand rot (4: UI-Zeilen de/en, „Noch keine beantworteten Züge“, Hinweistext), dann `npx ng test studio` **1933 bestanden** (158 Dateien; vorher 1930); eslint der berührten Dateien sauber; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs` sauber; Studio-Build (Produktion, kein Dev-Server lief) ohne Inline-Skript, Initial 891,80 kB / 218,41 kB gzip (die Warnung NG8102 stammt aus `projects/ui`, unberührt). Keine Golden-/Eval-Läufe, keine LLM-Aufrufe, keine Sichtprüfung im Browser. Einzelheiten in der Änderungsnotiz (`docs/aenderungen/2026-11-03-paket-u1g.md`, Abschnitt „Review“).

### Offen (U1-g)

- **Läufe** der Beispiel-Abläufe (Befehle in `evals/README.md`, „UI-Module“): erst sie zeigen, ob die Wendungen in `ui_antwort` die Beschriftungen des Modells treffen (`observed.ui_antwort.status`).
- **Beispiel-Abläufe im Studio** (G-7): nur über den Bereich `eval/gold-flows` — Entscheid Nutzer (Seed-Suite und Matrix-Vergleichbarkeit, oder ein eigener Flow-Satz im Studio).
- ~~**Vier Fehlschläge der ganzen Suite, nicht aus U1-g**~~ erledigt 2026-11-03 (`docs/aenderungen/2026-11-03-paket-u1-db-tests.md`). War: sie sind Postgres-gebunden (`pytest.mark.pg`) und liefen bisher nicht (U1-f: 490 übersprungen, diesmal 4): `test_config_choices` (2: Werkzeug-Katalog enthält jetzt auch `ui_themenbaum`, der Test erwartet nur `ui_entscheidung` — seit U1-e), `test_kanarienvogel_logs::test_direktaktion_schreibt_keine_inhalte_ins_log` (liest `inline_documents`, seit U1-b2 stehen Boxen als `ui_inhaltsrahmen`), `test_zug_verbindung_pg::test_setup_gibt_frei_bevor_die_zustimmung_geprueft_wird` (Attrappe `_verwerfen` ohne `modul_antwort` — seit U1-d). Alle vier auch einzeln rot.
- `services/eval/runner.py` steht bei 703 Zeilen (vor U1-g 640, nach U1-g 687, Review +16; schon über der Schwelle; ALT-Abbild).
- Keine Sichtprüfung der neuen Studio-Teile im Browser (nur Specs und Build), auch nicht nach dem Review.
- **Knoten im Themenbaum öffnen** (Review #5): ein Zug kann es nur getippt; später ein Zug-Schlüssel `aktion` für Direktaktionen (wie das Widget `show_collection_tree`).
- **Annahme der Auswahlfeld-Antwort** (Review #3): `gesendet` sagt nicht, ob der Server sie übernahm; sichtbar machen hieße ein neues Debug-Feld der Chat-Antwort.
- **Studio-Vergleich** (`eval-compare`): die Bedingungs-Gruppen trennen Läufe mit verschiedenen `ui_module`/`ui_module_wirksam`, der Text der Gruppe nennt die Module aber nicht (nur Anbieter, Modelle, Skill, Deckel).
- Die Messbedingungen im Studio (`eval-messbedingungen`) und der Markdown-Bericht nennen `ui_module_wirksam` und `eigene_ui_module` nicht eigens (nur JSON und Bedingungsvergleich).
- Ältere Tests mit derselben Start-Attrappe (`tests/test_eval_router.py::_patch_guard_and_spawn`) melden weiter „never awaited“ (Review #14 nur in der U1-g-Datei).

## 18 U1-h Unterthemen im Baum aufklappen (Tests zuerst)

Rückmeldung Nutzer (2026-11-03): „themenbaum habe ich getestet - sieht gut aus - schade das wir nachgeladenes unten drunter anzeigen müssen“. Ziel: Aufklappen eines Knotens, dessen Unterthemen noch fehlen (zweite Ebene, „weitere“), lädt sie **ohne Zug und ohne KI** und zeigt sie **im selben Baum**. „Inhalte anzeigen“ (neue Antwort) und „In WLO öffnen“ bleiben.

### Befunde am Code (2026-11-03)

- **Heute** (U1-e, E-6): „Unterthemen öffnen“ → `host.aktion('themenbaum')` → `controllers/collection-actions.showCollectionTree` → `/api/chat/stream` mit `action: show_collection_tree` → `graph/nodes/preflight` (Drosselung `check_rate_limit`, Sicherheitsprüfung `assess_safety` über Nachricht und `action_params` — kann die Moderation rufen) → `services/themenbaum_aktion` (Schalter `schalter.aktiv`, Angebot `angebotene_mcp_werkzeuge(blocked_tools, tool_mode)`, `datenquelle.aufruf`) → neue Blase, gespeichert samt Block. E-1 hatte den eigenen Endpunkt (C) verworfen: „neue öffentliche Fläche mit eigener Drosselung und Sitzungsprüfung, Nachgeladenes stünde nicht im Verlauf“ — U1-h nimmt genau das bewusst in Kauf.
- **Öffentliche Widget-Routen** (`/api/sessions/{id}/messages`, `/api/speech/*`): `@public_rate_limit` (je IP-Netz, `RATE_LIMIT_CHAT`, 429 mit `Retry-After`), Form der Kennung (`_validate_session_id`, `pruefe_oeffentliche_kennung`: Präfixe, Mindestlänge), kein Studio-Schlüssel; Liste `PUBLIC_ROUTES` (`test_openapi_contract`), öffentliche Spec `OEFFENTLICH` (`api/openapi_public.py`). CORS gilt für alle Pfade gleich (`main.py`). Der Zugangsblock kommt per Kopfzeile `WLO-Access-Block` (`adopt_turn_auth_block` + `bestaetige_anmeldung`); `uebernimm_zugang` verlangt zusätzlich den LLM-Schlüssel (hier unnötig, kein LLM).
- **Sperren der Sicherheit** (`blocked_tools`) entstehen nur aus dem Text eines Zugs (`regex_gate`: Krise, Drohung, persönliche Daten; `service`: `crisis_blocked_tools`). Der Endpunkt nimmt keinen Text an.
- **Sitzungs-Wache im Widget:** `sitzungsWache(() => sessionId)` (`session/session-id.ts:175`) — ein Ladevorgang gehört der Sitzung, in der er begann (Paket 3). `postChat` (`stream/stream-client.ts:309`) schickt JSON mit `WLO-Access-Block` und Frist; `ChatApiClient.anmeldung` wartet auf einen Ticket-Tausch.
- **Modul:** feste zwei Ebenen, Pfade `"i"`/`"i-j"` als Element-Kennungen; Kinder der ersten Ebene sind bekannt (der Server holt `depth: 2`), Kinder der zweiten unbekannt — darum bot die Leiste dort „Unterthemen öffnen“. Mehr als 30/10 Knoten kürzt das Backend (`wurzel_mehr`, `mehr`).
- **Platzhalter:** der Injector je Block bleibt stabil (`ui-bloecke.component.ts`) — Zustand im Modul überlebt neue Eingaben derselben Nachricht.

### Entscheide (U1-h)

| # | Frage | Entscheid | Warum |
|---|---|---|---|
| H-1 | Transport | **Neuer öffentlicher Endpunkt `POST /api/ui/themenbaum/zweig`** `{session_id, node_id, tool_mode?}` → `{daten}` (Form wie `themenbaum.daten_aus`, über `datenquelle.aufruf`, also mit Deckeln, Prüfung gegen `eingabe`, nur http/https). Router `api/ui_themenbaum.py`, Ablauf `services/themenbaum_zweig.py`. Verworfen: Direktaktion mit „nur Daten“-Schalter — sie ist ein Zug (Sitzungssperre, Sicherheitsprüfung samt Moderation, Speichern, `ChatResponse`), ein Schalter bräche `/api/chat` und `preflight` für einen Sonderfall | kleinste Fläche ohne LLM; das Widget braucht Daten, keine Blase |
| H-2 | Eingaben | `session_id` wie `ChatRequest` (Muster + `pruefe_oeffentliche_kennung`), `node_id` `^[A-Za-z0-9-]{1,80}$` (wie die Direktaktion), `tool_mode` wie `Environment.tool_mode`. **Keine Tiefe, kein Titel:** Tiefe 2 und `maxResults: 31` setzt das Manifest (`datenquelle.vorgaben`) — der Aufrufer kann die Kosten nicht erhöhen; der Titel steht im Modul schon | dieselben Deckel wie U1-e |
| H-3 | Prüfungen | Sitzung muss existieren (Zeile in `chat_sessions`, sonst 404 — kein offener MCP-Durchgang ohne vorherigen Zug); Themenbaum im Studio an (`schalter.aktiv`, sonst 403 `aus`); `browse_collection_tree` angeboten (`angebotene_mcp_werkzeuge(allow_curation=False, blocked_tools=[], tool_mode)`, sonst 403 `nicht_angeboten`) — gemeinsame Funktion mit der Direktaktion. **Keine Sicherheitsprüfung:** es gibt keinen Text, also nichts zu prüfen und keine Sperre (`blocked_tools` entstehen nur aus Text); der Baum, aus dem geklappt wird, kam durch einen geprüften Zug | keine Moderations-Kosten je Klick |
| H-4 | Drosselung | außen `@public_rate_limit` (je IP-Netz, 429 von slowapi), innen `check_rate_limit(session_id, ip)` wie jeder Zug bisher (die Direktaktion zählte dort auch) → 429 mit dem Text der Redaktion, Sicherheitsereignis `rate_limited` wie in `preflight` | gleiche Bremsen wie der bisherige Weg |
| H-5 | Anmeldung, LLM | `adopt_turn_auth_block` + `bestaetige_anmeldung` (der Baum sieht, was der Zug sah); kein LLM-Schlüssel nötig, kein LLM-Aufruf, keine Buchung | |
| H-6 | Nichts gespeichert | kein `save_message`, keine Zug-Auswertung, keine Sitzungssperre (der Endpunkt liest und schreibt keinen Gesprächsstand) — Aufklappen geht auch während eines Zugs | „ohne Zug“ |
| H-7 | Fehler | Werkzeug nicht erreichbar oder unbrauchbares Ergebnis → **502** `nicht_geladen` (nochmal versuchen hilft vielleicht); `aus`/`nicht_angeboten` → 403 (nochmal hilft nicht); ohne Servertext | Widget unterscheidet „nochmal“ von „geht hier nicht“ |
| H-8 | Haltbarkeit | **Nur bis zum Neuladen**: das Modul hält Nachgeladenes als Ansichtszustand (wie auf/zu); der Verlauf zeigt den ursprünglichen Baum. Block-Daten und Manifest-Version bleiben unverändert | Speichern hieße die gespeicherte Nachricht ändern (Schreibweg ohne Zug, Größe, Prüfung) — eigener Schritt, siehe Offen |
| H-9 | Host-Vertrag | `ModulHost.zweig(nodeId): Promise<Record<string, unknown>>` (Daten wie `eingabe`); neue Fähigkeit **`nachladen`** im Schema und im Manifest des Themenbaums (`["oeffnen", "nachladen"]`); `BlockModulHost` lehnt ohne Fähigkeit ab (Warnung + abgelehntes Versprechen). Widget: `ShellTreffer.zweig` → `collection-actions.themenbaumZweig` → `ChatApiClient.themenbaumZweig` (wartet auf `anmeldung`, Frist, `WLO-Access-Block`); `sitzungsWache`: wechselt die Sitzung, wird abgelehnt | Module rufen nichts selbst im Netz auf (U-E7) |
| H-10 | Alter Weg | Knopf „Unterthemen öffnen“ entfällt (Aufklappen ersetzt ihn), ebenso im Widget `aktion('themenbaum')`, `ShellTreffer.themenbaum`, `showCollectionTree`, `error.collectionTree`. **Backend bleibt:** Direktaktion `show_collection_tree` für zwischengespeicherte ältere Widget-Bündel und Gold-Züge (U1-g, Offen „Zug-Schlüssel aktion“) | kein toter Code im Bündel |
| H-11 | Modul | rekursiver Baum; Kinder eines Knotens sind **bekannt**, wenn er als Knoten einer Antwort kam (erste Ebene des Blocks oder eines Zweigs), sonst **unbekannt**. Aufklappbar: bekannte Kinder vorhanden, oder unbekannt bzw. „weitere“ und noch nicht geladen (bis Ebene 8; tiefer bleibt „In WLO öffnen“). Aufklappen lädt dann: `aria-busy`, Nebentext „lädt …“ mit Kreisel (ohne Animation bei `prefers-reduced-motion`), bei „weitere“ stehen die bekannten Kinder bis dahin. Danach ersetzt die geladene Liste; ein aktives Kind behält über die Kennung seinen Fokus. Leer → Blatt mit „keine Unterthemen“. Fehler → Nebentext „nicht geladen“ (`aria-describedby`), Knopf „Erneut laden“ in der Aktionsleiste; erneutes Aufklappen versucht es ebenfalls. Eine `aria-live="polite"`-Zeile sagt „3 Unterthemen von Algebra geladen.“, „Algebra hat keine Unterthemen.“ oder den Fehler. Ebene, Position, Größe je Gruppe gerechnet; der Fokus bleibt am Knoten. Bleibt ein Zweig nach dem Laden gekürzt (`wurzel_mehr`), bleibt „weitere“, und „In WLO öffnen“ zeigt alles | APG Tree View; keine Bedienelemente im Eintrag |
| H-12 | Enter | Enter klappt jeden aufklappbaren Eintrag (also auch unbekannte); Inhalte eines Blatts wie bisher (Befund 12 U1-e gilt für Blätter) | APG: Enter = Standardaktion |
| H-13 | Studio-Vorschau | `VorschauModulHost.zweig` sagt „In der Vorschau wird nichts geladen“ an und gibt zwei Beispiel-Knoten zurück | zeigt das Verhalten ohne Netz |
| H-14 | Vertrag | ein neuer Pfad, zwei Schemas; Zeile in `bewusste-vertragszusaetze.md`; `PUBLIC_ROUTES`, `OEFFENTLICH` (öffentliche Spec), Routen-Inventar | |

### Aufgaben (Tests zuerst; je Paket zuerst `/better-coding-workflow`, bei UI `/better-coding-frontend`)

| # | Aufgabe | Dateien | Test zuerst |
|---|---|---|---|
| h-1 | Angebot als gemeinsame Funktion `themenbaum_aktion.angebot(blocked_tools, tool_mode) -> "aus" \| "gesperrt" \| "ja"` | `services/themenbaum_aktion.py` | bestehende `test_ui_themenbaum_aktion` grün |
| h-2 | Ablauf `zweig_laden(kennung, tool_mode) -> Zweig(status, daten)` | `services/themenbaum_zweig.py` | aus / gesperrt / nicht geladen / ok, kein LLM, gesendete Argumente |
| h-3 | Route `POST /api/ui/themenbaum/zweig` (Modelle in `api/schemas_ui.py`), `main.py` | `api/ui_themenbaum.py` | 422 Kennungen, 404 Sitzung, 403, 502, 200; Drosselung außen/innen; nichts gespeichert; Zugangsblock übernommen |
| h-4 | OpenAPI, öffentliche Spec, Inventare | `docs/api/*`, `api/openapi_public.py`, `tests/test_openapi_contract.py` | `--check`, `test_openapi_additions`, `test_openapi_public` |
| h-5 | Vertrag: `zweig`, Fähigkeit `nachladen`, Manifest, Register | `_vertrag/*`, `ui-themenbaum/manifest.json`, `npm run module:register` | Register-Prüfung, Katalog-Test |
| h-6 | Hosts: `WidgetModulHost`/`BlockModulHost`, Shell, `collection-actions`, `ChatApiClient`; alter Weg raus | `ui/src/ui-bloecke/*`, `shell/chat-shell.component.ts`, `controllers/collection-actions.ts`, `stream/chat-api.ts`, i18n | Host-Kette, Fähigkeit fehlt, Sitzungswechsel, Anfrage-Form |
| h-7 | Modul: rekursiver Baum, Laden, Fehler, Ansage, Fokus | `ui-themenbaum/*` | Spec: Laden/Fehler/Erneut/Tastatur/aria/„weitere“/Tiefe |
| h-8 | Studio-Vorschau | `views/ui-modul-vorschau-host.ts`, i18n | Spec |
| h-9 | E2E, Bündel, Doku | `e2e/themenbaum.spec.ts`, Plan, Notiz, README | E2E mit gemocktem Endpunkt |

**Stand U1-h (2026-11-03):** umgesetzt (h-1 … h-9) wie entschieden.
- **Backend:** `themenbaum_aktion.angebot` (gemeinsam mit der Direktaktion), `services/themenbaum_zweig.py` (`zweig_laden` → `Zweig(status, daten)`), Route `api/ui_themenbaum.py` mit `ThemenbaumZweigAnfrage`/`ThemenbaumZweigAntwort` (Modelle im Router statt in `schemas_ui.py`: `SITZUNGSKENNUNG` liegt in `api/schemas`, das `schemas_ui` importiert), `db_sessions.sitzung_vorhanden`, `themenbaum.KENNUNG` (Form der Knoten, auch für die Eingabe). Zusätzlich zum Plan: Rumpf-Grenze 16 KiB für den Pfad (`api/body_limit.py`) — öffentlich, drei kurze Felder; sonst galten 16 MiB.
- **Vertrag:** Fähigkeit `nachladen` (Schema, Typ, Manifest; Register neu erzeugt), `ModulHost.zweig`, `KartenAktion` ohne `themenbaum`. OpenAPI neu erzeugt (ein Pfad, zwei Schemas, auch öffentlich), Zeile in `bewusste-vertragszusaetze.md`, `PUBLIC_ROUTES`/Inventar in `test_openapi_contract.py`, `OEFFENTLICH`.
- **Widget:** Host-Kette `BlockModulHost.zweig` → `WidgetModulHost.zweig` → `ShellTreffer.zweig` → `collection-actions.themenbaumZweig` (Sitzungs-Wache) → `ChatApiClient.themenbaumZweig` (`postChat`, Frist 75 s über `MCP_CALL_TIMEOUT_S` = 60 s). Entfernt: `showCollectionTree`, `ShellTreffer.themenbaum`, `error.collectionTree` (de/en).
- **Modul:** Regeln in `themenbaum-zweige.ts` (ohne Angular), Texte in `themenbaum-texte.ts`, Komponente mit rekursivem `ng-template`; offene Einträge und Zweige je Knoten-Kennung (überstehen das Ersetzen gekürzter Listen), der aktive Eintrag je Pfad mit Umzug über die Kennung.
- **Studio:** `VorschauModulHost.zweig` (Ansage + zwei Beispiel-Unterthemen), Text `uiModule.faehigkeit.nachladen`, `uiModule.vorschau.zweig` (de/en). Der Spec-Helfer `status()` liest jetzt die Ansage der Vorschau (`.umv-meldung`) — der Themenbaum bringt eine eigene Statuszeile mit.
- **Abweichungen vom Plan:** keine in der Sache; die Modelle stehen im Router (siehe oben).

**Prüfung U1-h:**
- **Backend:** neu `tests/test_ui_themenbaum_zweig.py` (25; vorher rot: Sammelfehler, die Route fehlte), dazu `test_body_limit` (+1, vorher rot), Inventare in `test_openapi_contract`, Eintrag in `test_i18n_messages` (`sitzung_unbekannt` ist ein Code, kein Text). Zielgruppe (Zweig, Direktaktion, Body-Grenze, OpenAPI-Verträge, Drosselung, Auth, Publikum, Kennung, Themenbaum, Schalter, Preflight) grün. Ganze Suite mit Postgres (`uv run --frozen pytest -q -p no:cacheprovider`, 21:25 min): **7830 bestanden, 4 übersprungen, 1 Fehlschlag** — `test_i18n_messages::test_jede_meldung_geht_durch_den_katalog_oder_steht_hier` (der neue Code `sitzung_unbekannt`), danach eingetragen, die Datei allein grün (zusammen mit dem Zweig-Test 56 bestanden); die ganze Suite lief danach nicht noch einmal. `ruff check src tests` sauber; `export_openapi.py` neu erzeugt, `--check` unverändert; `export_area_schemas.py --check` unverändert.
- **Frontend (nacheinander):** `ui-module` 84 (vorher 71; die Komponente fehlte zuerst im Bau — rot), `ui` 1101 (vorher 1093), `widget` 76, `studio` 1934 (vorher 1933). Gegenproben: ohne Umzug des aktiven Eintrags scheitert „weitere … der Fokus bleibt beim selben Thema“; ohne Sitzungs-Wache scheitert „wechselt die Sitzung während des Ladens“. eslint (berührte Dateien) sauber; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs` sauber; `module-register --pruefen` aktuell, `module-register.test.mjs` 9/9. Bündel (`npm run budget`): **614,27 kB roh / 179,52 kB gzip** (vorher 610,74 / 178,22; Grenze 200 kB). E2E nur `e2e/themenbaum.spec.ts`: 6/6 (neu: Aufklappen im selben Baum mit Tastatur und gemocktem Endpunkt, Fehler + „Erneut laden“, 320 px bei Ebene 5).
- **Sichtprüfung:** ein Bildschirmfoto aus dem gebauten Widget (Playwright, gemockter Endpunkt): „lädt …“ mit Kreisel am Eintrag, „weitere“ daneben, Kinder darunter eingerückt.
- Keine LLM-Aufrufe, keine Golden-/Eval-Läufe; Docker nicht angefasst.

### Review-Befunde U1-h (2026-11-03, behoben)

Je Befund erst am Code geprüft, dann ein roter Test, dann die kleinste Änderung. Alle elf bestätigt; bei #8 trägt die Begründung des Reviews nicht (siehe dort), umgesetzt wurde trotzdem.

| # | Befund | Prüfung | Änderung |
|---|---|---|---|
| 1 | `api/ui_themenbaum.py`: `sitzung_vorhanden` (`session.get`) lässt eine Transaktion offen — die Verbindung steht „idle in transaction“ über `bestaetige_anmeldung` (bis 5 s MCP) und den Zweig (MCP bis 60 s), genau was Paket 19 H-5 für den Zug behob | bestätigt (Postgres: `in_transaction() is True`, `checkedout() == 1` in der Anmeldung) | `await verbindung_freigeben(session)` direkt nach der Sitzungsprüfung; der 429-Weg committet selbst (`log_safety_event`), bleibt. Test `test_zug_verbindung_pg::test_das_aufklappen_im_themenbaum_gibt_vor_anmeldung_und_mcp_frei` (echtes Postgres, Endpunkt über `httpx.ASGITransport`): in Anmeldung und MCP-Aufruf `(False, 0)` |
| 2 | Modul: nach einem Ladefehler bleibt der Knoten in `offen` — `aria-expanded="true"` ohne Gruppe, Enter/Klick klappen zu statt neu zu laden | bestätigt (Spec: `'true'`, erst ← dann → lud neu) | Fehlerweg in `laden`: ohne bekannte (sichtbare) Kinder `setzeOffen(id, false)` — →, Enter und Klick laden direkt neu; ein gekürzter Zweig mit mitgelieferten Kindern bleibt offen. Specs: Fehler → zu, Enter/Klick laden; „weitere“ bleibt offen; bestehender Fehler-Test ohne den Umweg über ← |
| 3 | `fokusImBaum` fragte die ganze Komponente — wer während des Ladens in die Aktionsleiste ging, wurde in den Baum zurückgeholt | bestätigt (Spec: Fokus landete am Eintrag) | nur noch das Element `[role="tree"]`. Spec „wer während des Ladens in die Aktionsleiste geht, bleibt dort“ |
| 4 | `ebenen` rekursiv ohne Grenze: ein Vorfahr in einem nachgeladenen Zweig (Kreis im Repositorium) → `RangeError`; dasselbe Thema an zwei Stellen teilt den Auf/Zu-Zustand | bestätigt (Spec: `Maximum call stack size exceeded`) | `ebenen` bekommt einen `Ort` (Ebene, Eltern-Pfad, bekannt, **Vorfahren**); ein Vorfahr steht im eigenen Zweig als Blatt (nicht aufklappbar, ohne Zustand, ohne „weitere“); dazu harte Grenze `HOECHSTE_EBENE` (#6). Spec mit Kreis Algebra → Terme → Algebra. Geteilter Zustand für dasselbe Thema an zwei **nicht** verwandten Stellen bleibt (siehe Offen) |
| 5 | SCSS: feste 20 px Einrückung je Ebene — bei 320 px blieben auf Ebene 8 rund 80–100 px | bestätigt und gemessen: der Baum ist bei 320 px Fensterbreite nur **196 px** breit (Blase 218 px); 20 px → Titel ≈ 48 px, ein erster Versuch mit `clamp(10px, 5%, 20px)` → 118 px (E2E rot) | `padding-inline-start: clamp(6px, 4%, 20px)` (Prozent der Elternzeile; 20 px ab rund 500 px Baum, bei 320 px etwa 8 px). Kein Container-Query: `container-type` am Modul hätte eine schrumpfende Elternbox auf 0 gezogen. E2E bis Ebene 8 bei 320 px: Zeile 147 px, Titel ≥ 120 px, keine Ebene 9, kein waagerechtes Scrollen in Box und Seite |
| 6 | Ebene 9 konnte sichtbar werden (ein „weitere“-Knoten auf Ebene 7 lädt Kinder mit eigenen Kindern) | bestätigt (Spec: Ebene-8-Knoten mit `aria-expanded`) | `aufklappbar` und Kinder nur bei `ebene < HOECHSTE_EBENE` — wie H-11 und README. Spec „höchstens Ebene 8 ist sichtbar …“ |
| 7 | `themenbaum_aktion.angebot` lief erst nach `adopt_turn_auth_block`/`bestaetige_anmeldung` | bestätigt; das Angebot hängt nicht an der Anmeldung (`allow_curation=False`, `agent_tools._mcp_werkzeuge`) | `themenbaum_zweig.zweig_angebot(tool_mode)` getrennt von `zweig_laden(kennung)`; der Endpunkt fragt das Angebot vor der Anmeldung. Tests: `aus` und `nicht_angeboten` ohne Anmeldungsprüfung (`auf.anmeldung == []`) |
| 8 | `KENNUNG` `^[A-Za-z0-9-]{1,80}$` lässt Nicht-UUIDs an den Server | bestätigt, **Begründung nur zum Teil:** `node_id="Mathematik"` löst kein Fachportal auf — `browse_collection_tree` nimmt eine `nodeId` wörtlich, nur `subject` wird aufgelöst (`wlo-mcp-server-sc/src/tools/browse.ts:210-232`). Durch gingen aber Sonderkennungen des Repositoriums (`-userhome-`, `-inbox-`, `-root-`) | eigene Form `themenbaum.KNOTEN_UUID` (UUID, Groß/klein) nur für `ThemenbaumZweigAnfrage.node_id`; `KENNUNG` (Block-Daten aus dem Server) und die Direktaktion bleiben unverändert. OpenAPI neu erzeugt (`openapi-v1.json`, `openapi-public.json`: neues `pattern`), Zeile in `bewusste-vertragszusaetze.md`. Tests: `bbbb-2222`, `Mathematik`, `-userhome-`, `-inbox-`, zu lang, ohne Bindestriche → 422 ohne Aufruf |
| 9 | `BlockModulHost.zweig` lehnte ohne Fähigkeit mit einem Fehler ohne `status` ab — das Modul bot „Erneut laden“ an | bestätigt | `Object.assign(new Error(…), { status: 403 })`. Spec `rejects.toMatchObject({ status: 403 })` |
| 10 | 429 ohne eigenen Text; eine gleiche Meldung zweimal wurde nicht neu angesagt | bestätigt | 429 → Zustand `gedrosselt`: am Eintrag „zu viele Anfragen – bitte kurz warten“, Ansage „Zu viele Anfragen – bitte kurz warten und die Unterthemen von … dann erneut laden.“ (de/en); „Erneut laden“ bleibt, kein Selbstversuch. `ansagen()`: gleicher Text → Zeile leeren, 100 ms später neu setzen (eigener Schritt wie der `LiveAnnouncer` des CDK — ein erster Versuch mit `afterNextRender` setzte beides im selben Zeichnen, der Spec sah keine Änderung); Frist beim Zerstören geräumt. Specs: 429 de/en, Statuszeile `['', Text]` |
| 11 | Doku/Texte: README „Fehler zeigt das Modul nie“ veraltet; „gekürzt“ verspricht „alle“; Test-Name in `test_ui_themenbaum_zweig.py:149` | bestätigt (ein Zweig ist selbst gedeckelt: 30/10) | README (Nachladen, Zustände), `gekuerzt` de/en „laden beim Aufklappen mehr; vollständig zeigt sie WLO“; Test umbenannt in `test_tool_mode_geht_ans_angebot_und_ohne_angebot_403_ohne_aufruf` mit Docstring: die heutigen Regeln sperren `browse_*` in keinem Modus (`domain/host_capabilities.erlaubt`), nur ein im Studio verborgenes Werkzeug fehlt |

**Stand Review U1-h (2026-11-03):** alle elf Befunde behoben (Tabelle oben).

**Prüfung Review U1-h:**
- **Backend:** neue/geänderte Tests vorher rot — `test_ui_themenbaum_zweig` (8 rot: 6 Kennungen, 2 × Anmeldung ohne Angebot), `test_zug_verbindung_pg` (1 rot: `('anmeldung', True, 1)`). Zielgruppe (Zweig, Verbindung, Body-Grenze, Themenbaum, Direktaktion, Review, Muster) 124 bestanden; OpenAPI-Tests (`test_openapi_contract`, `_additions`, `_public`, `test_i18n_messages`) grün. Ganze Suite mit Postgres (`uv run --frozen pytest -q -p no:cacheprovider`, 18:44 min): **7838 bestanden, 4 übersprungen, 0 Fehlschläge**. `ruff check src tests` sauber; `export_openapi.py` neu erzeugt, `--check` unverändert; `export_area_schemas.py --check` unverändert.
- **Frontend (nacheinander, nach dem Backend):** neue Specs gegen den alten Stand rot (`ui-module` 8: Fehler/zu, Aktionsleiste, Kreis mit `RangeError`, 429 de/en, Ansage, Ebene 9; `ui` 1: Status 403). Danach `ui-module` **92** (vorher 84), `ui` **1101**, `widget` **76**, `studio` **1934**. eslint der berührten Dateien sauber; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs` sauber; `module-register --pruefen` aktuell. Bündel (`npm run budget`): **615,47 kB roh / 179,91 kB gzip** (vorher 614,27 / 179,52; Grenze 200 kB). E2E nur `e2e/themenbaum.spec.ts`: **6/6** (der 320-px-Test jetzt bis Ebene 8: vorher rot mit 118 px Titel).
- Keine LLM-Aufrufe, keine Golden-/Eval-Läufe, keine Sichtprüfung im Browser über die E2E-Messung hinaus; Docker nicht angefasst.

### Offen (U1-h)

- **Haltbarkeit** (H-8): Nachgeladenes gilt bis zum Neuladen; Speichern in die Nachricht wäre ein eigener Schritt (Schreibweg ohne Zug, `eingabe` kennt nur eine Ebene Kinder) — Entscheid Nutzer.
- **Unbekannte Unterthemen** tragen einen Pfeil, bis ein Abruf zeigt, dass es keine gibt (der Server sagt es nicht vorher).
- **Sitzung weg** (Aufbewahrung): 404 → „nicht geladen“ am Knoten; ein neuer Zug legt die Sitzung wieder an.
- **Evaluation:** Nachladen ist kein Zug und dort nicht messbar; Gold-Züge öffnen Knoten weiter nur getippt (U1-g, Offen).
- Sichtprüfung nur einmal im hellen Thema (Bildschirmfoto „lädt …“ mit Kreisel); dunkles Thema und der Fehlerzustand nur über Specs/E2E-Text geprüft. Die schmalere Einrückung (Review #5) nur gemessen, nicht angesehen.
- **Dasselbe Thema an zwei nicht verwandten Stellen** (Review #4): Auf/Zu und Ladezustand gelten je Kennung — klappt man es an einer Stelle auf, ist es an der anderen auch offen. Kreise (Vorfahr im eigenen Zweig) sind abgefangen; ein Zustand je Pfad hieße, das Ersetzen gekürzter Listen anders zu lösen.
- **Lange Titel brechen unter den Pfeil** (gesehen bei der Messung zu Review #5): `.ui-themenbaum__zeile` ist ein umbrechender Flex-Container, ein Titel länger als die Zeile rutscht in eine eigene Zeile unter Pfeil — schon seit U1-e, nicht Teil des Reviews.
- **Weitere 4xx ohne neuen Versuch?** Nur 403 sperrt „Erneut laden“; 404 (Sitzung weg) und 422 (Kennung nicht in UUID-Form, seit Review #8) bieten ihn weiter an, obwohl er nicht hilft.
- `ui-themenbaum.component.ts` steht bei 375 Zeilen (vor dem Review 340; schon über der Schwelle).
