# Paket U2 — Themenbaum: Bestand und KI-Entwurf (Plan 2026-11-04)

Stand: **umgesetzt 2026-11-04** (U2-a … U2-f, siehe §6 „Stand“, §7 „Offen“, §8 „Prüfung“). Änderungsnotiz:
[`aenderungen/2026-11-04-paket-u2-themenbaum-entwurf.md`](../aenderungen/2026-11-04-paket-u2-themenbaum-entwurf.md).

Bezug: Plan U1 ([`2026-11-02-paket-u1-ui-module.md`](2026-11-02-paket-u1-ui-module.md), §3, §14–§18),
Konzept [`2026-10-24-ablaeufe-und-ui-module.md`](2026-10-24-ablaeufe-und-ui-module.md) §6.3
(Dokumenttyp `wlo.sammlungsstruktur@1`) und §16.14–16.15 (Kestra, Dienste als reine Funktionen).

## 1 Auftrag (Nutzer 2026-11-04, wörtlich gekürzt)

> „Das Themenbaum UI kann nur vorhandene Sammlungsstrukturen aus dem Repo abbilden und keine von der
> KI neu generierten Bäume. … wollen aber als zweiten Usecase auch neue Themenbäume mit KI erzeugen
> und dann anzeigen bearbeiten und später übergeben an andere Dienste. Neben den rein technischen
> Aspekt müssen die beiden UseCases sauber erkannt werden.“

- **Entscheid B:** zwei Module mit gemeinsamem Baum, „klar als 2 Modulordner getrennt“.
- **Erzeugung:** top-down — obere Ebene, dann je Punkt die Ebene darunter, eine dritte nur wenn nötig;
  nicht jeder Punkt bis ganz unten; oben 5–20 Punkte, Vorgabe 10; je Knoten Titel, Beschreibung,
  Keywords, Fach und Bildungsstufe nur, wenn erkannt.
- **Bearbeiten:** umbenennen, hinzufügen, löschen, hoch/runter, ein-/ausrücken (Drag & Drop später).
- **Mehrdeutigkeit** (Empfehlung, ohne Widerspruch): „Themenbaum für <Fachportal/Sammlung>“ ohne
  Hinweis → Bestand + Schnellantwort „Neue Gliederung dazu entwerfen“; ausdrücklich „entwirf /
  gliedere / neue Struktur / Unterrichtsreihe / Sammlung zu Thema X“ oder ein Thema ohne Sammlung →
  Entwurf; Brücke „Als Entwurf bearbeiten“ im Bestandsbaum.

## 2 Befunde am Code (2026-11-04)

| Befund | Beleg |
|---|---|
| Der Themenbaum ist an die Datenquelle `browse_collection_tree` gebunden; seine Knoten kennen nur `id`, `titel`, `url`, `anzahl`, `mehr` — keine Beschreibung, keine Keywords | `ui-themenbaum/manifest.json`, `ui_module/themenbaum.py` |
| Asynchrone Modul-Aufrufe gibt es nur für MCP-Datenquellen (`_UMFORMER` kennt ein Werkzeug); die Parameter der KI sind deren `argumente` | `ui_module/datenquelle.py`, `werkzeuge.werkzeug_aus_manifest` |
| Der async-Zweig der Agent-Schleife kennt keine abfragenden Module (keine `frage`, keine zweite-Frage-Sperre); er bekommt weder Token-Zähler noch Frist | `services/agent_loop.py:612-634` |
| Der Antwortweg abfragender Module setzt die Form von `ui_entscheidung` voraus (`frage`, `optionen`, `gewaehlt`) | `ui_module/antwort.py` (`merke_frage`, `_grund`, `antwort_block`, `frage_block`) |
| Fester Satz unter einer Frage: „Bitte wähle unten aus.“ für jedes abfragende Modul | `agent_abschluss.antwort_oder_ersatz`, `graph/nodes/respond.py:519` |
| LLM mit JSON: `llm.chat_completion(response_format={"type": "json_object"}, usage_acc, phase, frist_s)`; Parallelität je Anbieter über `llm_parallel.platz("live")` (`LLM_MAX_CONCURRENCY`). Wichtig (drittes Review): auf dem Responses-Weg muss „json“ in einer Eingabe-Nachricht stehen — `legal.py` tat das bis 2026-11-05 nicht und war deshalb KEIN gutes Vorbild | `services/eval/judge_v2.py:30`, `services/llm.py:228` |
| Frist der Agent-Schleife: `ende` (Zeit der Ereignisschleife), `innerhalb(ende, …)`; Muster-Schleife ohne Laufrist | `services/agent_frist.py`, `services/tool_loop_module.py` Kopf |
| Jeder getippte Zug macht offene Fragen im Widget sofort `veraltet`; eine Modul-Antwort geht nur über `host.antworten` | `ui/src/ui-bloecke/fragen-status.ts`, `shell/chat-shell.component.ts:328-341, 483-486` |
| Register nimmt nur Ordner `ui-*` | `frontend/scripts/module-register.mjs:34-35` |
| Für Fach/Bildungsstufe gibt es im Backend keine Vokabular-Abbildung; der MCP-Server löst Labels auf | `services/mcp/tool_defs.py` (Beschreibungen „Label ODER URI“) |
| Server-Fehler beim Aufklappen: das Widget zeigt „nicht geladen“, die Konsole nennt den Status nicht | `ui-themenbaum.component.ts` (`laden`), `controllers/collection-actions.themenbaumZweig` |

## 3 Entscheide

| # | Frage | Entscheid | Warum |
|---|---|---|---|
| T-1 | Ordner | `ui-themenbaum/` (Bestand, unverändert im Zweck) und neu `ui-strukturentwurf/` (`ui_strukturentwurf`, abfragend). Gemeinsamer Kern in `projects/ui-module/src/_baum/` (kein `ui-`-Präfix → das Register übergeht ihn): Tastenregel (`baum-tasten.ts`), Lesereihenfolge (`flach`), Ansage-Zeile (`baum-ansage.ts`), SCSS-Mixin `_baum.scss` (gleiches Aussehen, Klassen je Modul-Präfix). ESLint verbietet Importe zwischen Modul-Ordnern | Entscheid B; zwei Ordner sind im Studio, in der Grafik und im Register sichtbar getrennt |
| T-2 | Kennzeichnung | Bestand: Marke **„Aus WLO“** im Kopf. Entwurf: **„Entwurf (KI)“**, aus der Brücke **„Entwurf (aus WLO)“** | Ein Entwurf darf nie wie Bestand aussehen |
| T-3 | Datenmodell | `ui_strukturentwurf.eingabe` = `wlo.sammlungsstruktur@1` (Teilmenge aus §6.3): Wurzel `titel`, `quelle` (`ki`/`wlo`), `thema?`, `fach?`, `bildungsstufe?`, `wurzel_wlo_id?`, `gekuerzt?`, `knoten[]`; Knoten `{id, titel, beschreibung?, keywords[]?, fach?, bildungsstufe?, wlo_id?, ausstehend?, kinder[]?}`. Ebenen ausdrücklich als `$defs` `ebene1…ebene4` (Tiefe im Schema geprüft). Deckel: oben ≤ 30 (Erzeugung 5–20, die Brücke übernimmt bis 30), Kinder ≤ 15, Tiefe ≤ 4 (Erzeugung ≤ 3), **gesamt ≤ 250 Knoten**, Titel ≤ 120, Beschreibung ≤ 300, Keywords ≤ 8 × ≤ 40, Kennung `^[A-Za-z0-9_-]{1,40}$`, eindeutig (Code-Prüfung `domain/strukturentwurf.fehler`). `vokabular`-URIs, `typ`, `konfidenz`, `fuellstand`, `inhalte` aus §6.3 fehlen bewusst (Offen) | Schlimmster Fall ~220 KB < 256 000 Zeichen Block-Deckel; JSON Schema kann Gesamtzahl und Eindeutigkeit nicht ausdrücken |
| T-4 | Werkzeug und Dienst | Neues Manifest-Feld **`dienst: {name, parameter}`**: das Backend erzeugt die Daten selbst; die KI sieht nur `parameter` (den Auftrag). `ui_module/dienst.py` (Verzeichnis der Dienste), `ui_module/aufruf.py` (eine Weiche: Datenquelle oder Dienst). Die Schleifen fragen `ist_asynchron(name)`. Datenquelle und Dienst schließen sich aus (Katalog-Prüfung) | Parameter ≠ Block-Daten wie bei der Datenquelle; der Dienst ist eine reine Funktion Auftrag → Struktur und lässt sich später als B-API/Kestra-Job ausführen (§16.15) |
| T-5 | Auftrag | `{thema (≤200, Pflicht), fach?, bildungsstufe?, anzahl_oben 5–20 (Vorgabe 10), tiefe 1–3 (Vorgabe 2), hinweise? (≤600), vorlage? (bool), vertiefen? (≤20 Kennungen)}`. `vorlage: true` = der Entwurf, den die Person **mit dieser Nachricht** geschickt hat, ist die Grundlage; vorhandene Knoten bleiben, vertieft werden die genannten (`vertiefen`) bzw. alle Blätter bis `tiefe` | Verfeinern ohne verlorene Bearbeitungen; Umstellen und Umbenennen macht die Person im Widget |
| T-6 | Erzeugung | Top-down im Backend (`services/strukturentwurf_dienst.py`, Aufforderungen in `strukturentwurf_prompt.py`): **Ebene 1** ein Aufruf (Titel, Fach/Stufe falls erkannt, `anzahl_oben` Knoten mit `beschreibung`, `keywords`, `unterthemen` 0–8); **Ebene 2** je Knoten mit `unterthemen > 0` ein Aufruf, parallel; **Ebene 3** nur bei `tiefe = 3`, nur für Knoten mit `unterthemen > 0`, höchstens 24 Aufrufe. Eigener Deckel **5 gleichzeitige Aufrufe je Entwurf** über dem Anbieter-Deckel (`chat_completion` → `platz("live")`, `LLM_MAX_CONCURRENCY`). JSON über `response_format: json_object`, gebucht im Token-Zähler des Zugs (Phase `strukturentwurf`) | Vorgabe Nutzer; ein Entwurf belegt nie alle Plätze des Chats |
| T-7 | Frist | Der Dienst bekommt ein Fristende (Agent: Fristende des Laufs minus 15 s Reserve für den Begleitsatz; Muster-Weg und Brücke: 90 s ab Start). Vor jeder Ebene: weniger als 8 s übrig → Ebene entfällt. Je Aufruf `frist_s = min(Rest, 40 s)`. Fehlt Ebene 1 → Fehler an die KI (kein Block). Fehlt eine tiefere → der Knoten trägt **`ausstehend: true`** („Unterthemen fehlen noch“); die Quittung nennt die Zahl | „liefern, was da ist“; die Person/KI vertieft später (`vertiefen`) |
| T-8 | Fach und Bildungsstufe | Klartext-Labels. Bildungsstufe nur aus der festen Liste der WLO-Labels (`Elementarbereich`, `Primarstufe`, `Sekundarstufe I`, `Sekundarstufe II`, `Berufliche Bildung`, `Hochschule`, `Erwachsenenbildung`, `Fortbildung`; Synonyme wie „Grundschule“ → `Primarstufe`), sonst weggelassen. Fach als Label ≤ 60 Zeichen. Am Knoten nur, wenn es von der Wurzel abweicht | Keine Abbildung auf URIs im Backend vorhanden (Befund); URIs über `lookup_wlo_vocabulary` später (Offen) |
| T-9 | An die KI | Quittung kurz: Titel, Zahlen (oben, gesamt, ausstehend) und die Titel der ersten Ebene; „dein Zug endet, zähle nichts auf“. Im Folgezug geht der mitgeschickte Entwurf **kompakt** (Titel und Einrückung, ≤ 6000 Zeichen, gerahmt `[ENTWURF DER PERSON …]`) vor die Nachricht | Anders als beim Bestand darf der Entwurf zur KI (er stammt von ihr bzw. von der Person); kompakt hält die Kette klein |
| T-10 | Zug-Bedeutung | **abfragend.** „Übernehmen“ → `host.antworten({…Struktur, uebernommen: true, bearbeitet}, „Entwurf … übernommen“)`. **Getippte Nachricht, solange der Entwurf offen ist** → das Widget schickt den aktuellen Stand automatisch mit (`uebernommen: false`, `bearbeitet` ja/nein): neue Host-Methode **`vormerken(daten)`** (Fähigkeit `antworten`); die Shell hängt den vorgemerkten Stand eines noch offenen Blocks als `ui_antwort` an getippte Züge (Eingabefeld, Schnellantwort) und setzt ihn `beantwortet` statt `veraltet`. Karten- und Direktaktionen nehmen ihn nicht mit (dort `veraltet` wie bisher). Immer mitgeschickt, nicht nur bei Bearbeitung: sonst kennte der Folgezug den Entwurf nicht (Verfeinern, Rückfragen) | Bearbeitungen gehen nie verloren; die Regeln „höchstens eine offene Frage“ und „jeder Vordergrund-Zug schließt die Frage“ bleiben — der Zug schließt sie, nur eben mit Antwort |
| T-11 | Bearbeiten | Baum nach APG Tree View (wie Bestand) plus Bearbeitungsleiste (`role="group"`) und Detailfeld für den aktiven Knoten (Titel, Beschreibung, Keywords — **keine Eingabefelder im Baumeintrag**, APG; „Umbenennen“/F2 springt ins Titelfeld, Esc zurück in den Baum). Knöpfe: Unterpunkt, Punkt danach, Löschen, Hoch, Runter, Einrücken, Ausrücken, Rückgängig (Stapel 20). Tasten im Baum: F2, Entf, Alt+↑/↓ (verschieben), Alt+→/← (ein-/ausrücken), Strg+Z; `aria-keyshortcuts` an den Knöpfen. Tiefe 4 wird beim Einrücken/Unterpunkt durchgesetzt (Knopf `aria-disabled` mit Grund). Ansage je Aktion (`aria-live`). Nur lesend bei `beantwortet`/`veraltet` | Abweichung „inline umbenennen“: ein Feld im `treeitem` widerspräche dem Muster, das der Bestand einhält (E-8) |
| T-12 | Herunterladen | JSON (`{"typ": "wlo.sammlungsstruktur@1", …}`) und Markdown (eingerückte Liste mit Beschreibung und Keywords) über `host.herunterladen` — auch im Nur-lesen-Zustand | Löst nichts aus; die Übergabe an Dienste bleibt offen |
| T-13 | Brücke | Bestand bekommt unter dem Baum **„Als Entwurf bearbeiten“** für die Wurzel (`wurzel_id`) → neue Host-Aktion `alsEntwurf` (Fähigkeit `oeffnen`) → Direktaktion **`edit_collection_as_draft`** `{collection_id, title}` → `services/strukturentwurf_aktion.py`: Angebot (Entwurf im Studio aktiv, vom Widget gemeldet; Baum-Werkzeug angeboten — gleiche Prüfung wie `themenbaum_aktion.angebot`), `browse_collection_tree` mit den Vorgaben des Bestands, Umformung **ohne LLM** (Titel, Beschreibung ≤ 300, Keywords ≤ 8, `wlo_id`), Block `ui_strukturentwurf` (`quelle: wlo`), Frage gemerkt, gespeichert. **Bewusst:** Bestandsknoten erreichen die KI erst, wenn die Person den Entwurf übernimmt oder dazu schreibt — dann sieht die KI seine Kompaktfassung (die Garantie „Bestand nie an die KI“ gilt für `ui_themenbaum` weiter) | Kein neuer Endpunkt; Drosselung und Sicherheitsprüfung wie jede Direktaktion |
| T-14 | Absicht erkennen | Werkzeugbeschreibungen schließen sich aus („zeigt nur, was es in WLO gibt“ ↔ „neue Gliederung, die es so noch nicht gibt“). Master-Skill `vorgehen-knapp.md`: M08 Mehrdeutigkeits-Regel, „Oberfläche ansteuern“ Abschnitt Entwurf, „Immer gültig“ Form. Wächter in `test_master_skill_vorlage.py` | U1-Lehre: die Beschreibung allein reicht nicht (Golden-Lauf 2026-11-03) |
| T-15 | „Unterthemen vorschlagen“ je Knoten ohne Zug | **Nicht in U2** (Offen): ein Endpunkt mit LLM ohne Zug läse von der Person bearbeitete Titel ohne Sicherheitsprüfung (offener LLM-Durchgang); als Direktaktion ginge die ganze Struktur durch die Moderation. Ersatz: getippte Bitte → KI ruft `ui_strukturentwurf` mit `vorlage` + `vertiefen` (normaler Zug mit Prüfung) | Sicherheit vor Bequemlichkeit |
| T-16 | Muster-Modus | wie die anderen Modul-Werkzeuge über `tools:`; die Vorrunde ruft den Dienst mit Token-Zähler und 90 s. `vorlage` gibt es dort nicht (die Muster-Schleife kennt die Antwort des Zugs nicht; die KI bekommt sie trotzdem gerahmt) | kleinster Eingriff |
| T-17 | Bündel | statisch, solange unter 190 kB gzip; sonst Nachladen nach U-F2 (Mechanismus fehlt noch) | gemessen in U2-f |
| T-18 | Aufklappen hinter einem Proxy (Nutzertest Server) | Nicht blind ändern. Das Widget schreibt bei einem Fehler `boerdi: Unterthemen nicht geladen — StreamHttpError status=…` in die Konsole; Betriebsnotiz: der Proxy (z. B. B-API) muss `/api/ui/*` durchreichen | Ursache liegt vermutlich außerhalb des Codes |

## 4 Aufgaben (Tests zuerst; je Teilpaket zuerst `/better-coding-workflow`, bei UI zusätzlich `/better-coding-frontend`)

**U2-a Gemeinsamer Baum (Frontend, verhaltensgleich)**
Schritt 0: `/better-coding-workflow` + `/better-coding-frontend`.
1. `_baum/baum-tasten.ts` (generisch über `BaumEintrag`), `_baum/baum-ansage.ts`, `_baum/baum-flach.ts`, `_baum/_baum.scss`; Spec `_baum/baum-tasten.spec.ts`.
2. `ui-themenbaum` nutzt sie; `themenbaum-tasten.ts` entfällt (Spec bleibt als Bestandsprobe gegen `_baum`); Marke „Aus WLO“; Specs und E2E grün.
3. ESLint: keine Importe zwischen `ui-*`-Ordnern; Register-Test: `_baum` wird übergangen.

**U2-b Vertrag und Backend-Kern**
Schritt 0: `/better-coding-workflow`.
1. Schema `dienst` + Typ; Katalog: Datenquelle und Dienst schließen sich aus (Test zuerst).
2. `domain/strukturentwurf.py`: Deckel, `fehler`, `normalisieren`, Kennungen, Bildungsstufen; `domain/strukturentwurf_text.py`: Textfassung, Kompaktfassung, Quittung (Tests zuerst).
3. Manifest `ui_strukturentwurf` (Beispiele: KI-Entwurf, aus WLO, ausstehend, tief) + Register.

**U2-c Dienst und Schleifen**
1. `services/strukturentwurf_prompt.py`, `services/strukturentwurf_dienst.py` (LLM-Naht ersetzbar; Tests mit Attrappe: Ebenen, Parallelität ≤ 5, Frist → `ausstehend`, Ebene 1 scheitert → Fehler, Buchung, Deckel).
2. `ui_module/dienst.py`, `ui_module/aufruf.py`, `werkzeuge` (`ist_asynchron`, Parameter aus `dienst`, Angebot).
3. Agent-Schleife: async-Zweig mit abfragenden Modulen (zweite Frage vor dem Aufruf abgewiesen, `frage`), Umgebung (Zähler, Frist, `vorlage`); `respond_agent` reicht die Vorlage; Muster-Vorrunde.
4. Antwortweg je Modul (`ui_module/antwort.py` + `strukturentwurf_antwort.py`): merken, prüfen (Schema + `fehler`), Rahmen `ENTWURF` (Endmarke), Frage-Block, fester Satz `agent.entwurf`.

**U2-d Brücke**
1. Direktaktion `edit_collection_as_draft` (`services/strukturentwurf_aktion.py`, `preflight`), Umformung Bestand → Entwurf (`ui_module/strukturentwurf_bestand.py`), Texte `action.draft.*`.

**U2-e Widget**
Schritt 0: `/better-coding-workflow` + `/better-coding-frontend`.
1. Vertrag: `ModulHost.vormerken`, `KartenAktion` + `alsEntwurf`; `BlockModulHost`, `WidgetModulHost`, Shell (`modulVormerken`, getippte Züge), `collection-actions.alsEntwurf`, Studio-`VorschauModulHost`.
2. Modul `ui-strukturentwurf`: Regeln ohne Angular (`entwurf-regeln.ts`: hinzufügen, löschen, verschieben, ein-/ausrücken, Tiefe, Kennungen; `entwurf-export.ts`: JSON/Markdown), Komponente, Texte, Spec je Beispiel, Tasten, Rückgängig, nur lesend.
3. Bestand: Knopf „Als Entwurf bearbeiten“; Konsolenzeile beim Ladefehler (T-18).
4. E2E `e2e/strukturentwurf.spec.ts` (gemocktes Backend: bearbeiten, übernehmen, getippt mitgeschickt, 320 px).

**U2-f Absicht, Evaluation, Doku**
1. Werkzeugbeschreibungen beider Manifeste, Master-Skill + Wächter.
2. `evals/ui-module-flows.yaml`: Bestand, Entwurf, mehrdeutig, Gegenprobe; `ui_antwort: {uebernehmen: true}` im Gold-Lauf.
3. Doku: `docs/ui-module.md`, READMEs, Änderungsnotiz, offene Befunde; Bündel messen.

## 5 Prüfung (Plan)

- Backend: neue Tests (Domain, Dienst, Aufruf, Schleifen, Antwortweg, Brücke, Master-Skill), dann `uv run --frozen ruff check src tests ../evals`, ganze Suite einmal; OpenAPI und Bereichs-Schemas `--check`.
- Frontend nacheinander: `npx ng test ui-module`, `ui`, `widget`, `studio`; eslint der berührten Dateien; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs`; `node scripts/module-register.mjs --pruefen`, `node --test scripts/module-register.test.mjs`; `npm run build:widget` + `node scripts/check-widget-budget.mjs`; Playwright ganz einmal, neue Specs `--repeat-each 5`.
- Keine LLM-Aufrufe in Tests (Attrappen), keine Golden-/Eval-Läufe.

## 6 Stand (2026-11-04)

Umgesetzt wie entschieden (T-1 … T-18, außer T-15). Abweichungen vom Plan:

- `flach` liegt in `_baum/baum-tasten.ts` (keine eigene `baum-flach.ts`); `themenbaum-zweige.ts`
  reicht es weiter, `themenbaum-tasten.ts` entfällt (die Spec prüft die Regel weiter mit den
  Einträgen des Bestands).
- „Inline umbenennen“ als Detailfeld (T-11, siehe dort); Enter auf einem Blatt öffnet das Titelfeld.
- Tasten zum Verschieben **Alt+Umschalt+Pfeil** statt Alt+Pfeil: Alt+← ist in Chrome „Zurück“.
- Die Brücke gilt der **Wurzel** des Bestandsbaums (ein Knopf unter dem Baum), nicht dem aktiven
  Knoten; sie übernimmt zwei Ebenen (die Vorgaben des Themenbaums), nicht im Widget Nachgeladenes.
- Die Bildungsstufe ist im Schema eine Aufzählung der WLO-Labels (nicht nur Text).
- `dateiname` im Entwurf ist eine eigene Kopie der acht Zeilen aus `ui-inhaltsrahmen` (Module
  importieren einander nicht).

## 7 Offen

- **Übergabe an andere Dienste** (Kestra/B-API-Job „Sammlung anlegen“, Freigabe vor dem Schreiben
  wie M18): Konzept §16.15; bis dahin ist der Download (`wlo.sammlungsstruktur@1`) die Übergabe.
- **„Unterthemen vorschlagen“ je Punkt ohne Zug** (T-15): bräuchte eine Sicherheitsprüfung für von
  der Person geschriebene Titel; heute nur über eine getippte Bitte (`vorlage` + `vertiefen`).
- **Drag & Drop** (Nutzer: später).
- **Vokabular:** Fach und Bildungsstufe als Klartext; URIs (`lookup_wlo_vocabulary`) und die
  Felder `vokabular`, `typ`, `herkunft`, `konfidenz`, `fuellstand`, `inhalte` aus §6.3 fehlen.
- **Sprache der Erzeugung:** der Dienst schreibt Deutsch (Aufforderung fest), auch bei englischer
  Oberfläche.
- **Muster-Modus:** ohne `vorlage` (die Muster-Schleife kennt die Antwort des Zugs nicht); kein Seed
  nennt das Modul in `tools:`.
- **Wurzel-Titel** des Entwurfs ist nicht bearbeitbar; Fach/Stufe je Punkt nur lesend sichtbar
  (Herunterladen).
- **Zeit mit dem echten Modell** ungemessen (Golden-Lauf GV-UI-9/12, startet der Nutzer); ebenso,
  ob die Erkennung trägt (GV-UI-8 … 12) — erst nach dem Übertragen des Master-Skills.
- **Aufklappen hinter dem Proxy** (T-18): Ursache auf dem Server nicht geklärt; die Konsole nennt
  jetzt den Status.
- **Speicher:** bis ~220 KB je Nachricht (Block bzw. `_ui_antwort`).
- `services/agent_loop.py` steht bei 761 Zeilen (vorher 746; schon über der Schwelle).

## 8 Prüfung (Ergebnis, 2026-11-04)

**Backend** (Postgres lief, `boerdi-chat-dev-postgres-1`; nicht angefasst):
- Neue Tests, vor dem Code geschrieben; rot gesehen bei Katalog (4 von 8), Antwortweg (8), Verteiler der
  Brücke, Gold-Zug (4), sonst Importfehler. Die Master-Skill- und Ablauf-Wächter entstanden nach dem
  Text (sie prüfen neue Sätze):
  `test_ui_modul_dienst_katalog` (8), `test_ui_strukturentwurf_daten` (12), `test_strukturentwurf_dienst`
  (17), `test_ui_strukturentwurf_aufruf` (17), `test_ui_strukturentwurf_agent` (8),
  `test_ui_strukturentwurf_antwort` (15), `test_ui_strukturentwurf_aktion` (17),
  `test_golden_ui_strukturentwurf` (4, rot gesehen); Wächter in `test_master_skill_vorlage` (+2 je
  Fassung), `test_golden_ui_module_flows` (+1). Angepasst (Modul-Menge festgeschrieben):
  `test_ui_entscheidung_muster`, `…_review`, `test_ui_entscheidung`, `test_ui_modul_schalter`,
  `test_config_choices`, `test_agent_prompt_preview`; Attrappen-Signatur `modul_vorlage` in
  `test_respond_agent`, `test_agent_prompt_preview`, `test_agent_loop._lauf`.
- Ganze Suite `uv run --frozen pytest -q -p no:cacheprovider`: **7992 bestanden, 4 übersprungen,
  3 Fehlschläge** (16:40 min) — alle drei schrieben die Modul-Menge fest (`test_ui_entscheidung`,
  `test_ui_entscheidung_muster_review`, `test_ui_modul_schalter`); danach angepasst, die berührten
  28 Testdateien zusammen **774 bestanden**. Die ganze Suite lief danach nicht noch einmal.
- `uv run --frozen ruff check src tests ../evals`: sauber. `export_openapi.py --check` und
  `export_area_schemas.py --check`: unverändert (kein Eintrag in `bewusste-vertragszusaetze.md`).

**Frontend** (nacheinander, nach dem Backend): `ng test ui-module` **141** (11 Dateien; die
Bestands-Specs unverändert grün nach dem Umbau auf `_baum/`), `ng test ui` **1131**, `ng test
widget` **76**, `ng test studio` **1959**. eslint der berührten Dateien sauber (die neue Regel gegen
Modul-zu-Modul-Importe mit einer Probedatei gegengeprüft); `check:tokens`, `check:a11y`,
`check:contrast`, `check:radii`, `check:docs` sauber; `module-register --pruefen` aktuell,
`module-register.test.mjs` 10/10. Bündel (`build:widget` + `check-widget-budget`): **650,57 kB roh /
188,18 kB gzip** (vorher rund 180,5 kB gzip; Grenze 200, Warnung 190) — statisch im Haupt-Bündel
(T-17); Angulars eigene Roh-Warnung (650 kB) ist um 0,57 kB überschritten. Playwright ganz:
**85 bestanden**; `strukturentwurf.spec.ts` + `themenbaum.spec.ts` mit `--repeat-each 5`: **60/60**.
Sichtprüfung: Bildschirmfotos des Entwurfs bei 420 und 320 px (hell).

Kein MCP-Server-Code geändert. Keine LLM-Aufrufe in Tests, keine Golden-/Eval-Läufe.

## 9 Review-Befunde U2 (2026-11-04, behoben)

Je Befund erst am Code geprüft (alle bestätigt), dann ein roter Test, dann die kleinste Änderung.

Nachträge zu §6 (Abweichungen): `vertiefen` trifft **Titel** (wie im Entwurf, ohne Groß-/Kleinschreibung,
Leerraum normalisiert), nicht bis zu 20 Kennungen wie in T-5; gleiche Titel vertiefen alle Treffer.
Die Daten-Helfer liegen in `ui_module/` (wie `themenbaum.py`), nicht in `domain/`. Unmögliche
Bearbeitungen sind **nicht** `aria-disabled` (T-11): der Knopf bleibt bedienbar, die Statuszeile sagt
den Grund („Schon ganz oben.“) — das ist ehrlicher als ein stummer gesperrter Knopf.

**Backend**

| # | Befund | Änderung |
|---|---|---|
| B1 | MAJOR: die Sicherheitsprüfung las Titel/Beschreibung/Schlagworte je Punkt gemischt und kappte bei 12 000 Zeichen — ein Titel hinter langen Beschreibungen und das Fach der Wurzel gingen ungeprüft in die Kompaktfassung | seit dem Gegenreview (Befund 3, unten): geprüft wird **genau die Kompaktfassung** (≤ 6000 Zeichen) **vor** der Nachricht |
| B2 | MAJOR: `vertiefen` überschrieb vorhandene Unterpunkte | anhängen bis zum Kinder-Deckel; die vorhandenen Titel gehen als `vorhanden` in die Aufforderung; ohne Platz kein Aufruf |
| B3 | MAJOR: feste Parallelität 5 belegte bei einem Anbieter-Deckel von 2 alle Plätze; das Warten auf einen Platz lief bis `LLM_SLOT_WAIT_S` über das Fristende | `parallel()` = min(5, max(1, Anbieter-Deckel // 2)) (`llm_parallel.anbieter_deckel`); `platz_frist_s` = Rest bis zum Fristende — läuft sie ab, scheitert nur der Aufruf, der Zug gilt nicht als ausgelastet |
| B4 | MINOR: Umbrüche in Titeln/Fach gingen roh in die Kompaktfassung | `strukturentwurf.normalisiert` in `antwort_pruefen` (gilt auch für die Vorlage) |
| B5 | MINOR: `vertiefen` ohne Treffer/ohne Blatt/ohne `vorlage` meldete Erfolg mit unverändertem Entwurf | Grund `nichts_zu_vertiefen` mit eigenem Text (Titel genau wie im Entwurf); `vertiefen` ohne `vorlage` → Fehler `argumente` |
| B6 | MINOR: Plan-Abweichungen undokumentiert | oben nachgetragen |
| B7 | NIT: die Quittung bat um einen Begleitsatz, den kein Modell mehr liest (die Runde endet mit dem Entwurf) | Quittung ohne Bitte; Kommentar zur 15-s-Reserve (nur der Fehlerweg); Manifest-Beschreibung und **Master-Skill**: „den kurzen Begleitsatz in derselben Runde über `respond_to_user`“ (Wächter) |

**Frontend**

| # | Befund | Änderung |
|---|---|---|
| F1 | MAJOR: scheiterte der Zug nach „Übernehmen“/getippter Nachricht (`wiederOffen`), fiel der Stand auf den KI-Entwurf zurück | `linkedSignal` mit Quelle (Knoten, nur lesend) behält beim Wechsel zurück nach offen den gesendeten Stand |
| F2 | MAJOR: Esc in einem Feld schloss das ganze Chat-Fenster | `stopPropagation`; Spec und E2E (Fenster bleibt, Fokus am Punkt) |
| F3 | MAJOR: Strg+Z nach Hinzufügen/Einrücken verlor den Fokus | aktiver Punkt bleibt, sonst Geschwister/Elternpunkt; Vorfahren aufgeklappt; Fokus zurück, wenn er im Baum stand |
| F4 | MINOR: nach „Übernehmen“ ging der Fokus verloren | Statuszeile `tabindex="-1"`, Fokus wie `ui-entscheidung` |
| F5 | MINOR: ein Auftrag des Gastgebers (`startTask`) nahm den Entwurf mit | `!this._hostTurn` in `sendMessage` |
| F6 | MINOR: die ESLint-Regel fing den Alias `@boerdi/ui-module/ui-*` nicht | Alias-Muster und `@boerdi/ui-module` ergänzt (Probedatei: 2 Fehler) |
| F7 | MINOR: Markdown-Export übernahm Umbrüche und Auszeichnung roh | eine Zeile je Text, `\` `` ` `` `*` `_` `[` `]` `<` `>` `~` und der senkrechte Strich maskiert |
| F8 | MINOR: Schlagworte wurden still gekappt | Hinweis am Feld (`aria-describedby`), Ansage beim Überschreiten |
| F9 | MINOR: „Als Entwurf bearbeiten“ auch bei im Studio abgeschaltetem Entwurf | Block-Daten `entwurf_moeglich` (Backend, `themenbaum.daten_aus`, Manifest `ui_themenbaum` ergänzt); Knopf nur dann |
| F10 | MINOR: Knöpfe der Leiste schoben den Fokus in den Baum | aus der Leiste bleibt er am Knopf |
| F11 | MINOR: Shell-Weg ohne Tests | `chat-shell-strukturentwurf.spec.ts` (Eingabefeld, Schnellantwort, Aktion, Gastgeber-Auftrag, Fehler → wieder offen) |
| F12 | NIT: Vormerkungen blieben stehen | nur lesend und beim Zerstören `vormerken(null)` |
| F13 | NIT: JSON ohne `gekuerzt` | ergänzt |
| F14 | NIT: `aria-keyshortcuts` an Knöpfen, deren Tasten nur im Baum gelten; Strg+Umschalt+Z; Mac ohne Entf | Attribute entfernt, Tasten im Hinweistext; Umschalt ausgenommen; Rücktaste löscht wie Entf |
| F15 | NIT: wer den letzten Punkt löscht, verlor den Fokus | Fokus auf „Punkt hinzufügen“ |

**Prüfung nach dem Review (2026-11-05):** neue Tests vorher rot (Backend: Antwortweg 2, Dienst 5,
Aufruf 1, Quittung 1, Brücken-Kennzeichen 1, Master-Skill-Wächter 3 Fassungen; Frontend: Komponente
9, Export 2, Shell 1 — Gastgeber-Auftrag). Ganze Backend-Suite mit Postgres: **8003 bestanden,
4 übersprungen, 1 Fehlschlag** (`test_sessions_admin_pg::test_optimize_database_runs_vacuum_without_raising`,
`ConnectionDoesNotExistError` mitten im VACUUM — einzeln 5/5 grün, nicht U2). ruff sauber;
OpenAPI und Bereichs-Schemas `--check` unverändert. Frontend nacheinander: `ui-module` **152**,
`ui` **1136**, `widget` **76**, `studio` **1959** (im ersten Lauf ein Kippler in
`agent-tools.component.spec.ts`, von U2 unberührt; zwei Wiederholungen grün). eslint sauber,
`check:*` sauber, `module-register --pruefen` aktuell, Test 10/10. Bündel **652,12 kB roh /
188,91 kB gzip** (Angulars Roh-Warnung 650 kB um 2,12 kB überschritten; eigene Warnung 190 kB
gzip nicht). Playwright ganz **86 bestanden**; `strukturentwurf` + `themenbaum` `--repeat-each 5`
**65/65**.

**Gegenreview (2026-11-05), drei Reste — bestätigt und behoben, je Test zuerst rot:**

| # | Befund | Änderung |
|---|---|---|
| G1 | MINOR: die Frist je Aufruf begann erst nach dem Platz (`llm.py`) — Warten plus Aufruf konnten bis zu 40 s über das Fristende laufen (Reserve 15 s) | `_Lauf.rufe` läuft in `asyncio.timeout_at(frist_ende)`; Test: Fristende 0,3 s, Attrappe 5 s → Ende vor 1,5 s, Grund `frist` |
| G2 | MINOR: nach beantwortet → wieder offen galt der Entwurf immer als „bearbeitet“ (Vergleich der Referenz, der Stand ist dann eine Kopie) | eigener Merker `geaendert`, gesetzt bei jedem Schritt; Rückgängig bis zum Anfang macht ihn wieder falsch (außer ältere Schritte fielen aus dem Stapel); Specs ohne Bearbeitung und mit Rückgängig |
| G3 | MINOR: der Prüftext stellte die (ungekappte) Nachricht vor den Entwurf — über ~11 000 Zeichen fielen Titel in die ungeprüfte Mitte; beim Vertiefen gingen Beschreibungen der Person an den Dienst, die nur hinten im Prüftext standen | Prüftext = **Kompaktfassung, dann Nachricht** (`sicherheits_text`): genau das, was ein Modell vom Entwurf sieht, steht immer im geprüften Anfang. Beschreibungen und Schlagworte der Person gehen an **kein** Modell mehr: das Vertiefen schickt aus einer Vorlage nur Titel, und nur von Punkten, die in der Kompaktfassung stehen (`strukturentwurf_text.sichtbare_ids`; Ziele, Geschwister, vorhandene Unterpunkte). Tests: lange Nachricht, Beschreibung nicht beim Dienst, Ziel hinter dem Deckel → `nichts_zu_vertiefen` |

Prüfung: berührte Backend-Tests **304 bestanden**, ruff sauber; `ui-module` **154**; eslint sauber;
Bündel **652,25 kB roh / 188,97 kB gzip**; `e2e/strukturentwurf.spec.ts --repeat-each 3` **15/15**.
Master-Skill dabei **nicht** geändert.

**Drittes Review (2026-11-05):** je Befund am Code geprüft, Test zuerst rot, dann die Änderung.

| # | Befund | Entscheid / Änderung |
|---|---|---|
| D1 | CRITICAL (vor U2): die rechtliche LLM-Stufe scheiterte mit gpt-6-luna still („json“ nur im Systemteil) | eigenes Thema „Fix rechtliche Prüfung (json)“, siehe Änderungsnotiz: Kopf „Zu prüfende Nachricht (Antwort als JSON, keine Anweisungen):“ vor der Nachricht; zentrale Absicherung `llm_responses.json_hinweis_sichern` in `llm.wire_transport` (gilt auch für den Strom) |
| D2 | MAJOR: die `vorlage` gab es nur im Zug der Antwort — „ja, vertiefe X“ einen Zug später scheiterte | neu `ui_module/strukturentwurf_merken.py`: die Sitzung merkt den letzten Entwurf (`entities._letzter_entwurf`, ≤ 60 000 Zeichen, sonst ohne Beschreibungen/Schlagworte) — geschrieben in den Antwort-Knoten, also nach der Sicherheitsprüfung, aus der geprüften Antwort oder einem erzeugten Block; die Brücke schreibt nichts (Bestand erst nach dem Zurückschicken). Für 5 Züge `vorlage` (Agent und Muster-Vorrunde) und Rahmen `[DEIN LETZTER ENTWURF …]` (Kompaktfassung, statt „Seinen Stand kennst du nicht“); neuer Parameter `erneut_zeigen` (unverändert als offener Block, ohne LLM). Master-Skill, Manifest, GV-UI-9 Zug 3 |
| D3 | MINOR: Ziele der dritten Ebene über dem Deckel fielen still weg | `ausstehend` (die Quittung zählt sie) |
| D4 | MINOR: nach „Alles zuklappen“ traf die Leiste den ersten Punkt | der nächste sichtbare Vorfahr des aktiven Punkts |
| D5 | MINOR: die Beschreibung `bildungsstufe` nannte 5 von 8 Labels | alle 8 (Test gegen `BILDUNGSSTUFEN`) |
| D6 | NIT: der Knopf „Als Entwurf bearbeiten“ prüft nur den Studio-Schalter, nicht die gemeldeten Module | **nicht geändert:** die einzige Quelle einer Meldung ohne `ui_strukturentwurf` ist ein Widget-Bündel von vor U2 — das kennt den Knopf gar nicht (er kam im selben Bündel wie das Modul); Gold-Abläufe mit eigener Modul-Liste klicken nicht. Lehnt die Direktaktion trotzdem ab, sagt sie es ehrlich (`action.draft.inactive`). Die Prüfung bräuchte die gemeldeten Module in der Datenquelle (heute ohne Umgebung) — Aufwand ohne Nutzen. Offen notiert |
| D7 | NIT: ein `thema` nur aus Leerzeichen ging durch | `"pattern": "\\S"` (getrimmt wurde schon) |
| D8 | NIT: der Ersatztitel der Brücke war fest deutsch | `action.draft.ohneTitel` (de/en) |
| D9 | NIT: Doku (Parallelität im README, Vorbild für JSON-Aufrufe in §2) | berichtigt |

Dazu: `antwort.entwurf_vorlage` entfernt (vom Entwurfs-Speicher abgelöst).

Prüfung drittes Review (2026-11-05): ganze Backend-Suite mit Postgres **8036 bestanden,
4 übersprungen, 0 Fehlschläge** (19:31 min); ruff sauber; OpenAPI und Bereichs-Schemas `--check`
unverändert. Frontend nacheinander: `ui-module` **155**, `ui` **1136**, `widget` **76**, `studio`
**1959**; eslint und `check:*` sauber; `module-register --pruefen` aktuell. Bündel **652,35 kB roh /
189,01 kB gzip** — knapp unter der eigenen Warnschwelle 190 kB; das nächste Modul sollte nachgeladen
werden (U-F2). Playwright ganz **86**; `strukturentwurf` + `themenbaum` `--repeat-each 3` **39/39**.

**Gegenreview Entwurfs-Speicher + json-Absicherung (2026-11-05):** je Befund am Code geprüft, Test
zuerst rot (`tests/test_ui_strukturentwurf_gegenreview2.py`, `test_llm_json_hinweis.py`).

| # | Befund | Entscheid / Änderung |
|---|---|---|
| E1 | MAJOR: die Brücke ließ einen älteren `_letzter_entwurf` stehen — der Folgezug sah den alten KI-Entwurf als Rahmen/Vorlage statt des Bestands-Entwurfs | `strukturentwurf_aktion` entfernt `entities[KEY]` vor `update_session` |
| E2 | MINOR: `json_hinweis_sichern` änderte das Nachrichten-Dict des Aufrufers | neue Liste mit kopiertem Dict unter `kwargs["messages"]`; Aufrufer-Liste und -Dict unverändert |
| E3 | MINOR: `erneut_zeigen` zeigte einen gekürzt gemerkten Entwurf (>60 000 Zeichen, ohne Beschreibungen/Schlagworte) als bearbeitbar — beim Übernehmen wären die Texte der Person still verloren | Marke `_ohne_texte` beim Kürzen; `erneut_zeigen` lehnt dann ab (`_FEHLER["ohne_texte"]`: herunterladen aus dem früheren Entwurf oder neu/vertieft); Vertiefen bleibt möglich (kopiert nur Wurzelfelder, Marke geht nicht in den Block) |
| E4 | MINOR: `DebugInfo.entities` mit `_`-Schlüsseln in den Direktaktionen | **kein Code nötig:** `schemas_debug.DebugInfo._ohne_interne_schluessel` (Audit 2026-09-29) filtert für jeden Erzeuger, Sitzungszustand unberührt. Test für die Brücke (Antwort + gespeicherte Nachricht ohne `_geheim` und ohne gemerkten Entwurf) war ohne Änderung grün; kein zweiter Filter |
| E5 | NIT: der Antwort-Zug zählte schon herunter (nur 4 echte Folgezüge mit Rahmen) | `strukturentwurf_merken.rahmen_fuer_zug(entities, geprueft)`: im Antwort-Zug merken, kein Rahmen, kein Herunterzählen; danach 5 Folgezüge. Beide Antwort-Knoten (`respond.py`, `respond_agent.py`) nutzen es; Test im Merken-Test angepasst |

Prüfung: berührte und verwandte Backend-Tests (25 Dateien: strukturentwurf/themenbaum/direct_actions/
respond/golden-UI/json) **608 bestanden**; ruff sauber; OpenAPI und Bereichs-Schemas `--check`
unverändert. Da `respond.py`/`respond_agent.py`/`ui_module/dienst.py` berührt: ganze Backend-Suite
mit Postgres **8041 bestanden, 4 übersprungen, 0 Fehlschläge** (17:35 min). Master-Skill **nicht**
geändert; Manifest unverändert (Frontend nur README).
