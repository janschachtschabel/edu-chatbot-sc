# Paket 14 — Studio in Arbeitsbereichen je Betriebsmodus

Stand: freigegeben 2026-10-17 („better coding workflow skill nutzen und umsetzen“), Phasen A–E umgesetzt, Review-Befunde behoben; offen nur Nutzer-Abnahme und Commit.

## 1 Ziel

Das Studio zeigt je Betriebsmodus nur, was dort wirklich gesteuert wird: ein **Agent-Arbeitsbereich**
und ein **Muster-Arbeitsbereich**, dazu gemeinsame Seiten, Auswertung und System. Der Agent bekommt
eigene Seiten (Übersicht mit Master-Skill, NodeID und Link ins Repositorium; Rolle & Grenzen;
Werkzeuge & Skills; Prompt & Probelauf). Materialformate werden wie im alten Studio als Liste mit
Detail bedient — mit gut lesbarer Vorschau der Vorlage.

## 2 Ausgangslage

- Paket 13 Phase E baute einen Umschalter „Agent | Muster | Beide“, der nur Bereiche **ohne jede
  Wirkung** ausblendet. Weil fast jede Seite einen Bereich mit „teilweise“ oder „nur Krise“ trägt,
  verschwindet in der Agent-Ansicht **keine einzige Seite** (Nutzer-Befund 2026-10-17: „kaum eine
  Umsetzung von dem, was gewünscht war“).
- Was der Agent tatsächlich liest (Code-Lesart 2026-10-17, `services/agent_kopf.py`,
  `domain/area_effects.py`): Rolle und Schutzregeln (`01-base/engine` → `agent_rolle`), die
  Leitplanken-Tabelle, **je Persona nur `label` und `formality`** (Anrede-Block) samt Rückfall aus
  `device-config.persona_formality`, Sicherheitsstufe, Werkzeug-Policy, Deckel (`engine.agent`),
  Wissen (RAG, MCP), Widget-Bereiche. Pattern, Domänenregeln, Plattformwissen, Tonalität,
  Basis-Persona wirken unter der Agent-Schleife **nur bei Krisen-/Drohungs-Zügen** (M01/M02 über den
  Muster-Weg). Intents, Entities, Signale, Platzhalter, Klassifikation, Materialtypen: keine Wirkung.
- Früherer Entscheid (Memory „master-skill-ist-steuerflaeche“, 2026-08-18/-21/-28): die Zuordnung
  Zielgruppe → du/Sie bleibt in den Personas (`formality`) und gilt für beide Maschinen; nicht in den
  Master-Skill kopieren.
- Altes Studio (`badboerdi/studio/src/components/CanvasFormatsEditor.tsx`, nur gelesen): Liste links
  (Filter Alle/Didaktisch/Analytisch, Emoji, Name, `id · Kategorie`), Formular rechts, `structure`
  als Roh-Textfeld. **Eine gerenderte Vorschau gab es dort nicht** — sie ist neu.

## 3 Entscheide des Nutzers (2026-10-17)

1. **Arbeitsbereiche je Modus** mit fest kuratierter Navigation (statt strengerem Filter).
2. **Anrede**: im Agent-Bereich eine kompakte Tabelle Zielgruppe → Anrede; volle Persona-Dokumente
   nur im Muster-Bereich.
3. **Schutzantworten**: M01 und M02 erscheinen im Agent-Bereich (unter „Rolle & Grenzen“) mit dem
   Hinweis, dass sie in beiden Modi gelten; alle anderen Pattern nur im Muster-Bereich.
4. **Keine Ansicht „Beide“**; „Alle Bereiche“ unter System bleibt als Rohzugang.

## 4 Ansätze

- **A — Strengerer Filter** über `area_effects` (Krise/Rand mit ausblenden). Wenig Umbau, aber die
  Seiten bleiben gemischt, Agent-Panels stecken weiter unter System, und jede neue Wirkungsstufe
  verschiebt still, was man sieht. *Verworfen (Nutzer-Entscheid 1).*
- **B — Kuratierte Arbeitsbereiche (gewählt).** Jede Seite trägt ihren Arbeitsbereich
  (`agent`, `muster`, `gemeinsam`, `auswertung`, `system`); die Navigation ist je Modus eine feste
  Liste. Abschnitte einer Seite sind ausdrücklich kuratiert (auch Feld-Ausschnitte eines Bereichs).
  `area_effects` bleibt die Quelle der Plaketten „Wirkt in …“ und eines Wächters, nicht der
  Sichtbarkeit. Vorhersagbar, prüfbar, passt zum Muster `curated-views.ts`.
- **C — Zwei getrennte Studio-Apps.** Maximale Trennung, aber doppelte Pflege gemeinsamer Seiten.
  *Verworfen: YAGNI.*

## 5 Design

### 5.1 Navigation je Arbeitsbereich

```text
AGENT                                   MUSTER
Agent                                   Muster
  Agent-Übersicht (Start)                 Übersicht (Start, Schichtenkarten)
  Rolle & Grenzen                         Identität
  Werkzeuge & Skills                      Domänenwissen
  Prompt & Probelauf                      Pattern
                                          Dimensionen
                                          Materialformate
Gemeinsam (beide)
  Begrüßung · Kontext-Aktionen · Tour & Lotse · Wissen · Anzeige · Datenschutz
Auswertung (beide, nach Maschine gefiltert — Paket 13 E5/E7)
  Sessions · Analyse · Evaluation · Lasttest · Safety-Logs · Kosten
System (beide)
  Betrieb · Alle Bereiche · Sicherung · Vorschau
```

Seitenbelegung (Bereich → Seite; ein Bereich hat **je Arbeitsbereich höchstens eine** Heimat):

| Seite | Arbeitsbereich | Abschnitte |
|---|---|---|
| `agent-uebersicht` (neu) | agent | Panel `agent-uebersicht` (Kopf: Vorgabe-Maschine + Hinweis, Master-Skill-Karte, Kacheln) |
| `agent-rolle` (neu) | agent | `01-base/engine` Felder `agent_rolle.*`; Panel `anrede`; `01-base/guardrails`; `01-base/safety-config` (Stufenwahl); `01-base/policy`; Gruppe `03-patterns` nur `m01`, `m02` („Schutzantworten“) |
| `agent-werkzeuge` (neu) | agent | Panel `agent-tools`; Panel `agent-skills`; `01-base/engine` Felder `agent.*` (Deckel) |
| `agent-prompt` (neu) | agent | Panels `agent-prompt`, `master-skill`, `agent-probe`, `agent-tester` |
| `uebersicht` | muster | unverändert (Schichtenkarten) |
| `identitaet` | muster | `safety-config`, `base-persona`, `guardrails`, `policy` (wie heute) |
| `domain-wissen` | muster | `domain-rules`, `wlo-plattform-wissen` (Tour/Lotse ziehen um) |
| `patterns` | muster | Gruppe `03-patterns`; `01-base/engine` Feld `muster_skills` + Panel `agent-skills` („Skill-Brücke“) |
| `dimensionen` | muster | 8 Reiter wie heute |
| `material-formate` | muster | neue Ansicht (§5.4); darunter `type-aliases`, `persona-priorities` als Formulare |
| `begruessung`, `kontext-aktionen`, `wissen`, `anzeige`, `datenschutz` | gemeinsam | wie heute |
| `fuehrung` (neu, „Tour & Lotse“) | gemeinsam | `website-tour`, `guide-mode`, `guide-rules` (aus Domänenwissen) |
| `betrieb` (neu) | system | `01-base/engine` Felder `mode`, `betrieb.*` (Vorgabe-Maschine, Streaming …) |
| Auswertung, `bereiche`, `sicherung`, `vorschau` | auswertung/system | wie heute |
| `agent` (alt) | — | entfällt; Inhalte auf die Agent-Seiten und `betrieb` verteilt; Route leitet um auf `agent-uebersicht` |

Panels mit `master-skill` stehen bewusst zweimal (Übersicht: Zustand; Prompt-Seite: Wortlaut in der
Kette) — die Übersicht nutzt eine kompakte Karte, kein zweites Vollpanel (§5.3).

### 5.2 Mechanik

- `StudioView.bereich: 'start' | 'agent' | 'muster' | 'gemeinsam' | 'auswertung' | 'system'`
  ersetzt `group` + `engines`. `start` gibt es nicht mehr als eigene Gruppe: die Startseite des
  Arbeitsbereichs steht oben im eigenen Block.
- `StudioAnsicht.ansicht: Engine` (nur `agent | pattern`); gemerktes `beide` zählt als „keine Wahl“
  → Vorgabe-Maschine. Umschalter im Kopf: zwei Radios „Agent | Muster“, Legende „Arbeitsbereich“.
- Navigation: `navGroups(ansicht)` = Block des Arbeitsbereichs + gemeinsam + auswertung + system.
- Route `''` leitet je Arbeitsbereich um (`redirectTo` als Funktion): Agent → `agent-uebersicht`,
  Muster → `uebersicht`. Beim Wechsel des Arbeitsbereichs auf einer Seite des anderen Bereichs
  navigiert die Hülle zur Startseite des neuen Bereichs.
- Per URL geöffnete Seite des anderen Arbeitsbereichs: Hinweis „Gehört zum Arbeitsbereich Muster“ +
  Knopf „Zum Arbeitsbereich Muster wechseln“ (der Paket-13-Hinweis `.cv-versteckt`, umgedeutet).
- `CuratedAreaSection.felder?: readonly string[]` → Feld-Ausschnitt über `pickFields` (bestehend,
  `schema-form` Eingang `paths`); gespeichert wird weiter das ganze Dokument.
- `CuratedAreaSection.dokumente?: readonly string[]` (nur `kind: 'group'`) → die Gruppen-Auswahl
  zeigt nur diese Dokumente (Schutzantworten M01/M02); Anlegen/Löschen dort aus.
- `ansicht-filter.ts`, `engines` an Panels und das Verbergen nach `area_effects` (Paket 13 E3/E4)
  entfallen — die Kuratierung ersetzt sie. Die Plakette „Wirkt in …“ bleibt.
- Analyse und Evaluation filtern weiter nach der Maschine des Arbeitsbereichs (Paket 13 E5/E7).

### 5.3 Agent-Übersicht

Eine Seite mit klarer Hierarchie, kein Kartenraster:

1. **Kopf**: „Agent-Arbeitsbereich“ + Zustandssatz der Vorgabe-Maschine („Der Server antwortet mit
   der Agent-Schleife“ / „… mit der Muster-Maschine; Einbettungen können die Agent-Schleife wählen“)
   + Link „Betriebsmodus ändern“ → `betrieb`.
2. **Master-Skill** (aus `GET /api/master-skill`, wie das Panel): Zustand an/aus/Fehler, **NodeID**
   (mit Kopierknopf), Version/Länge, Prüfsumme (12 Zeichen), abgerufen um, letzter Fehler; Links
   „Im Repositorium ansehen“ (`view_url`) und „Im md-editor bearbeiten“ (`edit_url`), Knopf
   „Neu laden“ (`POST /api/master-skill/reload`). Kein Wortlaut — der steht auf „Prompt & Probelauf“.
3. **Wegweiser** (Liste, keine Kacheln): Rolle & Grenzen (n Schutzregeln, Anrede für m Zielgruppen),
   Werkzeuge & Skills, Prompt & Probelauf, letzter Agent-Lauf der Evaluation (Gesamtnote, Datum).

Zustände: laden (Platz reserviert), Fehler je Karte mit Wiederholen, Master-Skill aus = Hinweis mit
Grund statt leerer Werte.

### 5.4 Materialformate (Muster)

Liste + Detail wie im alten Studio, mit lesbarer Vorschau:

- **Links**: Filter „Alle / Didaktisch / Analytisch (n)“ als Radiogruppe, Suchfeld (Name/Kennung),
  Liste als `<ul>` mit Knöpfen (Emoji, Name, `id · Kategorie`), gewählter Eintrag mit
  `aria-current`; „+ Neuer Materialtyp“.
- **Rechts**: Kopf (Emoji, Name, Kennung, Kategorie-Plakette) und zwei Reiter:
  - **Vorschau**: `structure` als gerendertes Markdown (Widget-`MarkdownRenderer` mit
    DOMPurify, Studio-Kontext ohne Sitzung/Trusted-Hosts — keine Bilder, keine externen Ladevorgänge);
    darunter „So bietet der Chatbot ihn an“: Chip-Text de/en, Aliase aus `type-aliases`, die auf
    diesen Typ zeigen, und Zielgruppen aus `persona-priorities`, die ihn führen (nur lesend).
  - **Bearbeiten**: Kennung (nur beim Anlegen), Name, Name (en), Emoji, Kategorie (Radios),
    Vorlage (Textfeld) mit Live-Vorschau daneben ab 60 rem, darunter sonst; Speichern / Verwerfen /
    Löschen (Rückfrage). Prüfung wie der Server: Kennung `^[a-z0-9_]+$`, eindeutig, Name nicht leer.
- **Speichern** über den bestehenden Bereichs-Endpunkt (`GET/PUT /api/config/data/05-canvas/material-types`
  mit `expected_version`, Konflikt → bestehende Konflikt-Komponente). Kein neuer Backend-Endpunkt.
- Darunter, aufklappbar: `type-aliases` und `persona-priorities` als bestehende Formulare.
- Wächter `test_material_type_labels` (Alias je Beschriftung) bleibt; die Vorschau zeigt einen
  fehlenden Alias als Warnung („Chip-Text ohne Alias — fällt auf ‚auto‘ zurück“).

### 5.5 Anrede je Zielgruppe (Agent)

Panel `anrede`: Tabelle (Zielgruppe, Anrede) über die Persona-Dokumente (`04-personas`), je Zeile
eine Auswahl `du | Sie | wie die Person` (Werte des Felds `formality`); Speichern je Zeile über den
bestehenden Gruppen-Speicherweg des Dokuments (Version je Dokument, Konflikt wie überall). Hinweis:
„Gilt in beiden Modi; die übrigen Persona-Einstellungen stehen im Muster-Arbeitsbereich.“ Der
Rückfall (`device-config.persona_formality`) wird nur angezeigt, mit Link auf „Anzeige“.

## 6 Globale Regeln

- Nur `boerdi-chat` ändern; `badboerdi` nur lesen.
- Studio: Signals, OnPush, kein RxJS-Abo; alle Texte über den Katalog (de/en), neue Teile in
  `i18n/catalogue/*`; Token statt Farbwerte; `check:tokens/a11y/contrast/radii` grün.
- Tests: Vitest je Komponente/Spec; Backend unberührt außer, falls nötig, einem Feld im
  Master-Skill-Endpunkt (keins vorgesehen — `node_id`, `edit_url`, `view_url` sind da).
- Dateien ≤ 300 Zeilen; `studio-views.ts` und `curated-pages-*` nach Arbeitsbereich aufteilen, falls
  sie die Grenze reißen.
- Browser-Abnahme nur gegen Wegwerf-DB (Memory „browser-abnahme-nur-wegwerf-db“); der Testcontainer
  wird danach mit neuem Image ersetzt.

## 7 Aufgaben

### Phase A — Mechanik der Arbeitsbereiche
Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` laden.
- **A1** `StudioAnsicht`: `Ansicht = Engine`; `beide` gemerkt → ignoriert. Spec: Startwert, gemerktes
  `beide`, Wahl. Umschalter: zwei Radios, Legende „Arbeitsbereich“ (Spec anpassen).
- **A2** `studio-views.ts`: `bereich` je Seite; neue Seiten `agent-uebersicht`, `agent-rolle`,
  `agent-werkzeuge`, `agent-prompt`, `fuehrung`, `betrieb`; `agent` entfällt (Weiterleitung).
  `navGroups(ansicht)`. Spec: je Arbeitsbereich die erwartete Seitenliste (Tabelle §5.1), keine
  Seite in beiden Fachblöcken.
- **A3** Routen: `''` je Arbeitsbereich; `agent` → `agent-uebersicht`; Wechsel auf fremder Seite →
  Startseite. Spec mit Router.
- **A4** Hinweis „gehört zum Arbeitsbereich …“ auf fremden Seiten (curated und eigene Seiten).
- **A5** Rückbau Paket 13 E3/E4: `ansicht-filter.ts`, `engines` an Panels, Verbergen in
  `curated-view`/`curated-tabs` entfernen; Specs entsprechend. Übersichtskarten nur im Muster-Start.

### Phase B — Kuratierung
Schritt 0: `/better-coding-workflow`.
- **B1** `CuratedAreaSection.felder` → `area-section` reicht `paths` an `schema-form`. Spec: nur die
  Felder `agent_rolle.*` erscheinen, Speichern sendet das ganze Dokument.
- **B2** `CuratedAreaSection.dokumente` → `group-section` filtert die Auswahl, Anlegen/Löschen aus.
  Spec: nur M01/M02 wählbar.
- **B3** Seiten-Daten neu: `curated-pages-agent.ts`, `curated-pages-muster.ts`, gemeinsame in
  `curated-pages-inhalt.ts`/`-betrieb.ts`; Katalogtexte. Wächter: je Arbeitsbereich jeder Bereich
  höchstens eine Heimat; jeder Bereich mit Wirkung in einer Maschine hat dort eine Heimat oder steht
  bewusst nur unter „Alle Bereiche“ (Liste mit Grund).

### Phase C — Agent-Seiten
Schritt 0: `/better-coding-workflow`, `/better-coding-frontend`.
- **C1** `agent-uebersicht.component` (§5.3) + Spec (Zustände, NodeID, Links, Neu laden, Vorgabe ≠
  Agent).
- **C2** Panel `anrede` (§5.5) + Spec (Tabelle, Speichern je Zeile, Konflikt, Fehler).
- **C3** Seiten `agent-rolle`, `agent-werkzeuge`, `agent-prompt`, `betrieb` als kuratierte Seiten.

### Phase D — Materialformate
Schritt 0: `/better-coding-workflow`, `/better-coding-frontend`.
- **D1** `core/material-types.ts` (Lesen/Schreiben über Bereichs-Endpunkt, Prüfregeln, Querbezüge
  Aliase/Prioritäten) + Spec.
- **D2** `markdown-vorschau.component` (Studio-Kontext für `MarkdownRenderer`) + Spec (XSS-Probe,
  kein `<img>`, Überschriften/Listen gerendert).
- **D3** `material-formate.component` Liste + Filter + Suche + Detail (Vorschau/Bearbeiten), Zustände
  laden/leer/Fehler/Konflikt + Spec (Tastatur, Auswahl, Speichern, Neuanlage, Löschen mit Rückfrage,
  Alias-Warnung).

### Phase E — Abnahme
- Volle Suiten (Studio, Backend unverändert grün), Gates, Build.
- Browser-Abnahme gegen Wegwerf-DB (beide Arbeitsbereiche, 375 px und Desktop, hell/dunkel).
- Testcontainer mit neuem Image ersetzen; Review (`/better-coding-review`) über Paket 14.

## 8 Abnahmekriterien

| Kriterium | Nachweis |
|---|---|
| Agent-Arbeitsbereich zeigt keine Pattern-/Dimensionen-/Materialformate-/Domänenregeln-Seite | Spec Navigation je Arbeitsbereich |
| Muster-Arbeitsbereich zeigt keine Agent-Seiten | dieselbe Spec |
| Agent-Übersicht nennt Master-Skill-Zustand, NodeID, Links ins Repositorium | Spec C1 + Browser |
| Anrede je Zielgruppe im Agent-Bereich änderbar, wirkt in beiden Modi | Spec C2 |
| Schutzantworten M01/M02 im Agent-Bereich, nur diese | Spec B2 |
| Materialformate: Liste, Filter, Vorschau gerendert und sicher, Bearbeiten, Speichern mit Konflikt | Spec D1–D3 + Browser |
| Kein Bereich mit Wirkung ohne Heimat im jeweiligen Arbeitsbereich | Wächter B3 |
| Studio-Suite, Gates, Build grün; Backend-Suite unverändert grün | Läufe |

## 9 Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Eine Einstellung mit Wirkung verschwindet aus beiden Arbeitsbereichen | Wächter B3 gegen `area_effects` |
| Zwei Seiten bearbeiten dasselbe Dokument (engine-Ausschnitte) und überschreiben sich | Versionierung je Dokument (409) wie heute; Ausschnitte nur in verschiedenen Seiten |
| Lesezeichen auf `/studio/agent` brechen | Weiterleitung auf `agent-uebersicht` |
| Markdown-Vorschau als XSS-Fläche | Widget-Renderer mit DOMPurify, Spec mit Probe |
| Startpaket wächst über 1,2 MB | Neue Seiten per `loadComponent`; Budget im Build prüfen |

## 10 Offene Fragen

Keine — die vier Entscheide aus §3 decken den Schnitt.

## 11 Log

| Datum | Schritt |
|---|---|
| 2026-10-17 | Nutzer-Befund zur Ansicht, Erkundung (Agent-Leser, altes Studio), Entscheide, Entwurf |
| 2026-10-17 | **A** gebaut: `Ansicht = Engine` (gemerktes `beide` wird ignoriert, Startwert = Vorgabe-Maschine), Umschalter mit zwei Radios und Wechsel auf die Startseite, wenn die aktuelle Seite dem anderen Arbeitsbereich gehört; `studio-views.ts` mit `group` je Seite, `navGroups(ansicht)`, `startView`, `workspaceOf`; Routen `''` → Startseite je Arbeitsbereich, `agent` → `agent-uebersicht`; Hinweis „gehört zum Arbeitsbereich …“ in der Hülle (gilt für alle Seiten); Paket-13-Verbergen zurückgebaut (`ansicht-filter.ts` gelöscht, `engines` an Panels, `verborgen` in `curated-view`/`curated-tabs`). |
| 2026-10-17 | **B** gebaut: `felder` (über `visiblePaths` des Schema-Formulars, gespeichert wird das ganze Dokument) und `dokumente` (Auswahl gefiltert, Anlegen/Löschen aus); Seiten neu geschnitten. Wächter: je Arbeitsbereich jeder Bereich höchstens eine Heimat (Feld-Ausschnitte disjunkt) und jeder Bereich eine Heimat in jedem Arbeitsbereich außer der Liste `NUR_MUSTER` mit Grund. **Abweichung:** die Liste ist ausdrücklich gepflegt statt aus `area_effects` abgeleitet (die Wirkungstabelle kennt Felder nicht, nur Bereiche); Muster-Seiten blieben in `curated-pages-inhalt.ts` statt einer neuen `curated-pages-muster.ts` (die Datei hält die Grenze, ein Umzug hätte nur verschoben). |
| 2026-10-17 | **C** gebaut: `agent-uebersicht` (Zustand aus der Vorgabe-Maschine + Link zu Betrieb, Master-Skill-Panel offen eingebettet mit NodeID, Editor- und Repositoriums-Link, Wegweiser, letzter Agent-Lauf), Panel `anrede` (Tabelle je Persona, Speichern je Zeile mit `expected_version`, 409 → Neu laden), Seiten `agent-rolle` (Rolle, Anrede, Schutzregeln, Sicherheitsstufe, Policy, Schutzantworten M01/M02), `agent-werkzeuge`, `agent-prompt`, `betrieb`. **Abweichungen:** statt einer kompakten Master-Skill-Karte das bestehende Panel (ein Ort für Neu laden und Links); kein Kopier-Knopf für die NodeID; Wegweiser ohne Zähler. Der Muster-Hinweis auf der Pattern-Seite schweigt, weil dort jetzt das Feld `muster_skills` steht. |
| 2026-10-17 | **D** gebaut: `core/material-types.ts` (Prüfregeln, Aliase, Vorrang — reine Funktionen; Lesen/Schreiben sitzt in der Komponente über `ConfigApi`), `markdown-vorschau` (Widget-`MarkdownRenderer` mit DOMPurify, Bilder/Medien/Stile verboten), Panel `material-typen` + `material-typ-detail` (Liste mit Filter und Suche, Vorschau gerendert mit Chip-Text/Aliasen/Vorrang und Alias-Warnung, Bearbeiten mit Live-Vorschau, Anlegen/Löschen mit Rückfrage, ganze Liste mit `expected_version`, 409 gemeldet; Entwurf sperrt die Liste). |
| 2026-10-17 | **E** Abnahme: ESLint, `check:tokens/a11y/contrast/radii` grün; Studio-Suite 139 Dateien / 1626 Tests grün; Backend unberührt (keine `.py`-Datei seit dem Plan geändert). Build 1,15 MB — Warnung 54,5 kB über 1,1 MB, rund 45 kB bis zur Fehlergrenze; **Abweichung:** neue Seiten nicht per `loadComponent` (§9), Hebel steht in `offene-befunde-und-todo.md`. Browser gegen Wegwerf-DB `boerdi_p14_browser`: Agent-Übersicht, Rolle & Grenzen (Anrede 6 Personas, nur M01/M02, nur `agent_rolle.rolle`), Wechsel Agent → Muster führt auf die Muster-Übersicht, Navigation je Arbeitsbereich vollständig; Materialformate (19 Typen, Filter 14/5, Vorschau gerendert, Bearbeiten sperrt Liste, Verwerfen gibt frei); Betrieb nur `mode` + `betrieb`; 375 px dunkel ohne Querscrollen, Hinweis „gehört zum Arbeitsbereich“ erscheint. Wegwerf-DB und Startkonfiguration danach entfernt. |
| 2026-10-17 | Testcontainer `boerdi-chat-test` (127.0.0.1:8180) mit Image `edu-chatbot-sc:paket14-lokal` ersetzt; `alembic upgrade head` + `import-config --werksabgleich` auf `boerdi_test`: 0 Änderungen. |
| 2026-10-17 | **Review** (`/better-coding-review`, frischer Prüfer): 1 major, 6 minor, 4 nits — behoben, je mit Test vorab: **#1** Startseite las den Arbeitsbereich vor dem Laden der Vorgabe (Vorgabe `pattern` → Agent-Übersicht, danach kippte die Navigation) → `redirectTo` wartet auf `StudioAnsicht.ermittle()`; ein gescheitertes Nachladen der Wirkungen behält die letzte Vorgabe (`linkedSignal`). **#2** Anrede zählt für den Verlassen-Schutz (`dirty`). **#3** Speichern auf der Vorschau mit Prüffehlern wechselt zum Formular. **#4** Konflikt in Materialformate und Anrede über `studio-save-conflict` wie §5.4 verlangt (Entwurf bleibt, „Trotzdem speichern“ gegen die gemeldete Version). **#5** Statuszeilen stehen leer bereit (F-M6). **#6** `link.external` im Studio-Katalog (Warn-Titel des Widget-Renderers). **#7** Umschalter stellt erst nach gelungener Navigation um; abgebrochene Rückfrage lässt Seite, Bereich und Radio stehen. **#8** Zähler zählt die Auswahl (`dokumente`). **#9** Vorrang mit vier Fällen (analytisch ohne Liste = „für keine Zielgruppe“). **#10** Kommentar in der Hülle. Offen gelassen: **#11** `group-section.component.ts` 312 Zeilen (Teilung Anlegen/Kopieren/Löschen als Folgearbeit); Alias-/Vorrang-Stand im Materialtyp-Panel wird erst beim Neuladen der Seite frisch, wenn darunter „Aliase und Vorrang“ gespeichert wird. Danach: ESLint, Gates grün; Studio 139 Dateien / 1639 Tests grün; Build 1,15 MB (Warnung 54,7 kB). |
