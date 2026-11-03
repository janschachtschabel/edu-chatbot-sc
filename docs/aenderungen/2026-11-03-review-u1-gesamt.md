# Änderungsnotiz — Gesamt-Review Paket U1 (UI-Module)

Stand 2026-11-03 · Basis: U1-a … U1-h, Abstände, Master-Skill-Kurzfassung · Plan
[`docs/plans/2026-11-02-paket-u1-ui-module.md`](../plans/2026-11-02-paket-u1-ui-module.md)

**Warum:** Review aller U1-Änderungen im Backend, im Master-Skill und in der Doku, dazu der zweite
Golden-Lauf nach der Übertragung der Kurzfassung (Messung in
[`2026-11-03-master-skill-ui-module.md`](2026-11-03-master-skill-ui-module.md), „Messung nach dem
Upload“). Jeder Befund wurde am Code geprüft; wo testbar, kam zuerst ein roter Test. Der Teil
Frontend folgt in einem eigenen Abschnitt (anderer Bearbeiter).

## Backend

| # | Befund | Was sich ändert |
|---|---|---|
| 1 | MAJOR: geratene Box im Verlauf doppelt — gespeichert ist das Roh-Markdown (der M11-Folgezug braucht es), dazu derselbe Inhalt als Inhaltsrahmen-Block; nach dem Neuladen stand er zweimal da | Auf dem geratenen Weg (M09/M10/M11, `_build_inline_document`, auch die Schnellwege durch den Hauptweg) merkt sich der F-6-Nachtrag den gezeigten Vorspann unter `_anzeige_text` (`domain/ui_bloecke.ANZEIGE_TEXT_KEY`); `api/publikum.verlauf_fuer` zeigt ihn als `content`. Gespeicherter Text und Folgezug bleiben unverändert |
| 2 | MAJOR: Themenbaum im Muster-Modus zeigte das falsche Fach — der Selbstheilungs-Auflöser von `browse_collection_tree` ersetzte mit dem Fach-Hinweis jede Kennung, die kein Fachportal ist (Unterthema, Sammlung), durch das Portal und ergänzte bei `subject` eine `nodeId`, die beim Server vorgeht | `_resolve_browse_node_id`: übersteuert nur noch das Portal eines anderen Fachs; eine Kennung, die kein Portal ist, bleibt; mit `subject` und ohne `nodeId` wird nichts ergänzt. Bestehende Auflöser-Tests unverändert grün |
| 3 | MINOR: die offene Frage konnte an der Obergrenze von fünf Blöcken wegfallen, obwohl `_offene_frage` schon gemerkt war | `regeln_anwenden` behält die erste offene Frage immer und lässt dafür anzeigende Blöcke weg (wiederholt angewandt unverändert). Die Schleifen (Agent und Muster-Vorrunde) nehmen je Antwort höchstens vier anzeigende Blöcke samt Dokumenten an (`HOECHSTENS_ANZEIGENDE`); ein weiterer Aufruf bekommt „Nicht ausgeführt: … genug Blöcke“ (`GENUG_BLOECKE`), eine Antwort derselben Runde gilt dann wie bei einem fehlenden Block nicht. `respond_agent`/`respond` merken sich nur eine Frage, die die Regeln übersteht |
| 4 | MINOR: `x-nur-system` beim Annehmen allgemeiner Modul-Aufrufe nicht durchgesetzt | `modul_aufruf_annehmen` prüft gegen die Eingabe, wie die KI sie sieht (`_fuer_die_ki(…, pruefen=True)`); eine Aufzählung nur aus Systemwerten bleibt dort leer stehen statt wegzufallen |
| 5 | MINOR: Direktaktion `show_collection_tree` nahm weite Kennungen (`-userhome-`) | Nur noch `themenbaum.KNOTEN_UUID`, wie das Aufklappen (U1-h, Befund 8) |
| 6 | MINOR: nicht jeder Weg zu `ui` wandte die Regeln je Antwort an (`abgeleitet.ergaenzt` gab ohne Abgeleitetes die gelieferten Blöcke ungeprüft zurück) | `ergaenzt` wendet die Regeln immer an — damit auch `antwort_fuer` und der Verlauf |
| 7 | MINOR: Textfassungen bauten Markdown-Links ohne Maskierung und Adressprüfung | Gemeinsamer Helfer `abgeleitet.md_link(titel, url)`: `[`/`]` maskiert, Adresse nur http/https (Leerzeichen und runde Klammern kodiert), sonst Text ohne Link. Genutzt von Linkbox, Trefferliste (Karten und Such-Absprung) und Themenbaum (vorher ersetzte er Klammern) |
| 8 | MINOR: Datei-Wachstum und Zwillinge | Die UI-Helfer des Gold-Runners (`dokument_boxen`, `ui_bloecke`, `gezeigte_module`, `offene_frage`, `baue_ui_antwort`, `_trefferstufe`, Normalisierung, Textfassungen, Konstanten) stehen in `evals/ui_module_golden.py` (framework-frei); `run_golden.py` lädt sie über den Pfad wie `compare_golden.py` den Runner (985 statt 1087 Zeilen). `services/eval/runner.py` behält seine Zwillinge: er lädt heute nichts von `run_golden`, ist ein normales Paket-Modul ohne Datei außerhalb des Pakets (Prod-Befund 2026-08-22). Der Zwillings-Wächter vergleicht jetzt auch das Verhalten an denselben Antworten. Das Image kopiert die neue Datei mit (`Dockerfile`, Wächter `test_deploy_compose`) |
| 9 | NIT | `werkzeuge._EIGENER_WEG` und `schalter.schaltbar` nutzen `namen.OHNE_WIRKUNG_IN_TOOLS` |
| 10 | NIT: `namen.ENTSCHEIDUNG` im Quelltext ungenutzt | **Teilweise abgelehnt:** `run_golden.py`/`ui_module_golden.py` dürfen `boerdi.*` nicht importieren (framework-frei, im Image ohne Paket). Stattdessen hält der Zwillings-Wächter `ui_module_golden.ENTSCHEIDUNG == namen.ENTSCHEIDUNG`, und die Fehlermeldung von `pruefe_werkzeug_namen` nennt den Namen über die Konstante |
| 11 | NIT | Die Direktaktion führt `ui_themenbaum` in `tools_called` wie die Schleifen (vorher das MCP-Werkzeug) |
| 12 | Golden-Runner: falscher `qr`-Fehlschlag unter einer offenen Frage (dort gibt es absichtlich keine Schnellantworten) | `check_golden_turn`: steht ein offener abfragender Block in der Antwort, ist `qr` nicht gestellt (`None`); `qr: false` bleibt eine Aussage. Gilt auch im Studio (der Gold-Lauf dort lädt denselben Runner); der generative Runner hat keinen `qr`-Check |

## Master-Skill (`docs/skills/vorgehen-knapp.md`) und Werkzeugbeschreibung

| # | Befund | Was sich ändert |
|---|---|---|
| 13 | MAJOR: Widerspruch — „Ergebnisse dieses Zuges stehen davor“ und „Zuerst handeln … erst die Ergebnisse“ gegen M03 (Platzhalter: eine Frage vor jeder Suche; Erstellauftrag ohne Typ), dazu „Nicht für offene Fragen“ gegen die Themenfrage mit Freitext | Auswahlfeld: „… stehen davor, wenn das Vorgehen Werkzeuge braucht (erst suchen oder erklären, dann fragen); die Klärungsfragen aus M03 (nur Platzhalter, fehlender Typ) kommen ohne Suche.“ Zuerst handeln: „… erst die Ergebnisse dieses Zuges (falls das Vorgehen welche braucht), dann höchstens eine Frage.“ Dazu: „Die Themenfrage aus M03 mit drei konkreten Vorschlägen und Freitext zählt nicht als offene Frage.“ |
| 14 | MINOR: Begleittext neben dem Auswahlfeld unklar (Golden-Lauf: nur „Bitte wähle unten aus.“) | Unter „Auswahlfeld“: Begleittext (Ergebnisse, Einordnung, in der Anrede der Person) über `respond_to_user` (`text`, ohne `quick_replies`) in derselben Runde — so liest ihn die Schleife (`agent_loop`: Antwort derselben Runde, sonst die Prosa). Beschreibung von `ui_entscheidung` gleichsinnig, allgemein („über das Antwort-Werkzeug falls vorhanden“); Register neu erzeugt |
| 15 | MINOR: Lernende — Auswahlfeld oder Schnellantworten nach einer Erklärung? | M04: „Ändert eine offene Angabe den nächsten Schritt (Klasse, Vorwissen) → Auswahlfeld, sonst Schnellantworten mit Übungsangebot.“ |

Alle bisher gepinnten Sätze bleiben; drei neue Wächter in `tests/test_master_skill_vorlage.py`
(je Fassung Vorlage, Editor, Fett).

## Doku

- Plan: Kopf (U1-a … U1-h reviewt, Nacharbeiten mit Notizen), §15 „Offen (U1-e)“ (Kurzfassung auf
  `ui_themenbaum` umgestellt; offen `vorgehen.md`, `vorgehen-kompakt.md`,
  `response_prompt_tools_text.py`, Muster).
- `docs/offene-befunde-und-todo.md` §2: derselbe Stand; zweiter Golden-Lauf eingetragen.
- `docs/ui-module.md`: „KI soll das Modul gezielt wählen“ — Beschreibung allein reichte für
  `ui_entscheidung` nicht; Bündelgröße als „Stand 2026-11-03: 179,94 kB“.
- `frontend/projects/ui-module/README.md`: Fähigkeit `nachladen` (`zweig`, ohne sie 403);
  Beispielnamen für `module:neu`, die es noch nicht gibt.
- `docs/browser-plugin-einbindung.md`: `stop_reason` — neun Werte der Schleife plus `safety`
  davor; Zeilen `empty` und `safety`.

## Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Master-Skill | Die geänderte Kurzfassung in den WLO-Knoten übertragen, danach `scripts/check_master_skill.py` (die drei neuen Wächter schlagen gegen den alten Knoten an) | Danach Golden-Lauf (UI-Abläufe + Seed-Suite, Agent) |
| Image | Backend-Image neu bauen — `Dockerfile` kopiert jetzt auch `evals/ui_module_golden.py`; ohne sie startet kein Gold-Lauf aus dem Studio | |
| Widget | Kein neues Bündel aus diesem Teil (nur die Manifest-Beschreibung von `ui_entscheidung` und damit `register.generated.ts`/`manifeste.json`) | |
| Migration, Umgebung | keine | |

## Prüfung (Backend)

- Neu `tests/test_review_u1_gesamt.py` (Befunde 2–7, 11, 12; jeder Test vorher rot), dazu Tests
  in `test_turn_persist.py` und `test_publikum.py` (Befund 1), `test_mcp_arg_resolvers.py`
  (Befund 2), drei Wächter in `test_master_skill_vorlage.py` (13–15), Zwillings-Wächter in
  `test_eval_ui_module.py` (8, 10), `test_deploy_compose.py` (8). Angepasst: Direktaktions-Tests
  nutzen eine UUID statt `bbbb-2222` (5) und erwarten `ui_themenbaum` in `tools_called` (11).
- Gezielt (12 Testdateien): 462 bestanden.
- `uv run --frozen ruff check src tests ../evals`: sauber.
- Ganze Suite mit Postgres (`uv run --frozen pytest -q -p no:cacheprovider`): **7886 bestanden,
  4 übersprungen, 0 Fehlschläge** (18 min).
- `export_openapi.py --check` und `export_area_schemas.py --check`: unverändert (kein Modell
  geändert).
- `npm run module:register`, danach `node scripts/module-register.mjs --pruefen`: aktuell.
  Frontend-Suiten liefen hier nicht (folgen mit dem Frontend-Teil).
- Kein LLM-Aufruf, kein Golden-/Eval-Lauf, keine Docker-Aktion.

## Offen

- **Lange Vorlagen** `vorgehen.md`, `vorgehen-kompakt.md` und `response_prompt_tools_text.py`
  tragen die neuen Regeln (Auswahlfeld, Begleittext, Themenbaum) nicht.
- **Direktaktion „Lernpfad erstellen“** (`direct_actions`, Bestand) speichert den vollen Text ohne
  Inhaltsrahmen-Block: nach dem Neuladen steht der Plan als Text statt als Box (nicht doppelt,
  aber anders als live). Nicht in diesem Review geändert.
- **Themenbaum zum Unterthema im Agent-Modus** (GV-UI-1 Zug 2): der Agent rief wieder mit
  `subject`; Befund 2 betrifft nur den Muster-Weg (Fach-Hinweis der Klassifikation).

## Frontend

Jeder Befund am Quelltext geprüft; wo testbar, zuerst ein roter Test (rot bestätigt, außer bei
den reinen Ergänzungs-Tests 7 und 18, die das bestehende Verhalten festhalten).

### Widget und UI-Module

| # | Befund | Was sich ändert |
|---|---|---|
| 1 | MAJOR: offene Fragen veralteten im Widget nur bei getippten Zügen — das Backend schließt sie bei jedem Zug im Vordergrund | `shell-contexts.ts`: der POST der Karten-Aktionen (Volltext, Sammlung, Lernpfad, damit auch „Inhalte anzeigen“ im Themenbaum) und von „Weitere laden“ schließt vorher offene Fragen (`offeneFragenSchliessen`). `_host.addUserMessage` (nur der Tour-Start legt darüber eine Blase an) schließt wie `_sendCtx`. Tour-Tick, Kontext-Ping und `zweig` (kein Zug) lassen sie offen |
| 2 | Inhaltsrahmen/Linkbox/Themenbaum rechnen nach Sprachwechsel oder neuen vertrauten Seiten nicht neu | **Teilweise anders als vorgeschlagen:** Linkbox und Themenbaum (`host.link`) lesen über `trustedDomains()`/`t` schon Eingabe-Signale der Shell und rechneten neu (Spec bestätigt). Der Fehler steckte im Markdown: ein Cache-Treffer liest kein Signal — ein Inhaltsrahmen, dessen erstes Rendern den Cache traf (gleicher Text in zwei Antworten), blieb alt. `ShellRender` führt einen Stand (`signal`), den `clearCache` hochzählt und `markdown()` liest; damit hängt jedes `computed` über `host.markdown` am Cache, ohne neue Naht |
| 3 | `host.link()` ließ jedes Schema durch | `WidgetModulHost.link`: nur `http(s)://…`, sonst `{href: '', hinweis: ''}` |
| 4 | `treffer()` umging die Fähigkeit `oeffnen` | `BlockModulHost.treffer`: ohne `oeffnen` liefert der Kontext `withBsid`/`externalLinkWarning` leer; Kacheln, „beschäftigt“ und Übersetzer bleiben |
| 5 | Tore prüften nur den Modulnamen | Neu `ui-bloecke/modul-darstellbar.ts` (`blockDarstellbar`, `modulDarstellbar`: Register, gleiche Hauptversion, Daten da) — genutzt vom Platzhalter, `hatTrefferliste` (Shell), `hatLinkbox` (Register über `GroupingContext.modulRegister`, das `ShellRender` setzt) und `hatDokumentBox` (Template reicht das Register). Bei fremder Hauptversion bleiben Trefferboxen, Webseiten-Box und Druckleiste stehen |
| 6 | Fokusverlust (WCAG 2.4.3) | Entscheidung: während eines Zugs `aria-disabled` statt `disabled` (ohne Wahl weiter `disabled`; Wache in `senden()`); nach „Antworten“ geht der Fokus per `afterNextRender` an die Statuszeile (`tabindex="-1"`); ein schon beantworteter Block aus dem Verlauf zieht keinen Fokus. Themenbaum: „Inhalte anzeigen“ `aria-disabled` + Wache in `inhalte()`. Stil: `[aria-disabled='true']` wie `:disabled` |
| 7 | Tests fehlten | `chat-shell-ui-bloecke.spec.ts`: Frage aus dem Verlauf offen → beantworten (`ui_antwort` geht mit); beantwortet → nur lesend mit der Antwort des Servers. `e2e/entscheidung.spec.ts`: dieselben zwei Fälle nach dem Neuladen |
| 8 | Dateigrößen | Themenbaum: Markup in `ui-themenbaum.component.html`, Tasten als reine Regel in `themenbaum-tasten.ts` (+ eigene Spec, 6 Tests); Komponente 384 → 290 Zeilen, Verhalten gleich (alle Themenbaum-Specs unverändert grün). **Nicht gemacht:** `modul-naht.ts` in der Shell — die Naht bräuchte eine Schnittstelle so groß wie der verschobene Code (offene-befunde §5) |
| 9 | NIT: Rhythmus-Test maß, während der Zweig noch lud | `e2e/themenbaum.spec.ts`: erst messen, wenn „Algebra“ kein `aria-busy` mehr trägt |
| 10 | NITs | Kommentar `null` → `undefined` (`ui-bloecke.component.ts`); `schrift-skala.ts` ohne `as any`; doppelte Leerzeile in `public-api.ts` weg. README `nachladen`: war schon erledigt |
| 11 | NIT: Symbole ohne `aria-hidden` | Inhaltsrahmen (3) und Linkbox (2) |
| 12 | NIT: `themenbaumZweig` ohne Abbruch | Umgesetzt nach dem vorhandenen Muster der Nachfragen im Verlauf (Paket 9): `postChat` nimmt ein `signal`, `ChatApiClient.themenbaumZweig` und `collection-actions.themenbaumZweig` reichen es durch, die Shell legt je Zweig einen Abbruch in dieselbe Menge, die `ngOnDestroy` abbricht. Ein Sitzungswechsel verwirft wie bisher über `sitzungsWache` |
| 13 | NIT: `smooth` trotz weniger Bewegung | `ui-trefferliste`: `behavior: 'auto'` bei `prefers-reduced-motion: reduce` |
| — | `history-restore.ts`: eine Antwort nur aus Blöcken (ohne Text) fiel weg | Übersprungen wird nur ohne Text **und** ohne `ui_bloecke` |
| — | `collection-actions`: bei `veraltet()` kein `setLoading(false)` | **Abgelehnt:** gewollt (`session/session-id.ts`, `sitzungsWache`): das Laden gibt der Neustart frei (`lifecycle.restart`/`resetSession` setzen `false`); ein später Ausgang der alten Sitzung gäbe sonst die Eingabe mitten in einem neuen Zug frei (Review 2026-10-03). Tour, Kontext-Ping und `send-message` halten es genauso |

### Studio

| # | Befund | Was sich ändert |
|---|---|---|
| 14 | Veraltete Fehlermeldung auf „UI-Module“ | `fehler` wird in `setze`, `verwerfen` und nach erfolgreichem `neuLaden` geleert |
| 15 | `rm.row.tools.agent` unvollständig | Nennt `respond_to_user` (mit den Agent-Schnellantworten), `wissen_suchen`, `ui_inhaltsrahmen`, `ui_entscheidung`/`ui_themenbaum` (nur wenn das Widget sie meldet und sie auf „UI-Module“ aktiv sind) und `liefere_ergebnis` (de/en) |
| 16 | NIT | Werkzeug-Hinweis im Muster-Formular: „… sie auf der Seite „UI-Module“ aktiv sind …“ (de/en) |
| 17 | NIT | `evalStart.uiModule.hint`: „— ein Ablauf mit eigenem ui_module behält seine Liste“ (de/en); die gepinnte Spec in `eval-golden-start.component.spec.ts` mitgezogen |
| 18 | NIT | `ui-modul-vorschau.component.spec.ts`: je Beispiel (Trefferliste auch als Kacheln) kein `img[src^="http"]`, kein `iframe`, kein `srcset`/`source` mit `http` in `.umv-buehne` (15 Tests) |
| 19 | NIT | `lockLink`: `data_source` → `werkzeuge`; `agentTools.lock.studioOff` von `ui-module.ts` nach `agent-center.ts` neben die übrigen `agentTools.lock.*` (de/en) |

### Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Widget | Neues Bündel (Backend-Image neu bauen): Befunde 1–6, 11–13 und der Verlauf-Fix wirken erst damit | Danach Hard-Reload im Browser |
| Studio | Neues Studio-Image (Texte 15–17, Befunde 14, 19) | |
| Backend, Migration, Umgebung | keine | |

### Prüfung (Frontend, nacheinander)

- `npx ng test ui-module`: **105 bestanden** (8 Dateien).
- `npx ng test ui`: **1127 bestanden** (88 Dateien).
- `npx ng test widget`: **76 bestanden** (4 Dateien).
- `npx ng test studio`: **1951 bestanden** (158 Dateien); im ersten Lauf 1 rot — die gepinnte
  Satzfassung von `evalStart.uiModule.hint` (17), angepasst.
- eslint der berührten Dateien: sauber. `check:tokens`, `check:a11y`, `check:contrast`,
  `check:radii`, `check:docs`: sauber. `node scripts/module-register.mjs --pruefen`: aktuell (5 Module).
- `npm run build:widget`, `node scripts/check-widget-budget.mjs`: **617,34 kB roh / 180,52 kB gzip**
  (vorher 179,94 kB; Grenze 200 kB, eingehalten).
- `npx playwright test`: **81 bestanden** (vorher 79; +2 Neulade-Fälle der Entscheidung).
  `e2e/entscheidung.spec.ts` und `e2e/themenbaum.spec.ts` mit `--repeat-each 5`: **85 bestanden**.
- Studio-Produktionsbuild: gebaut, `index.html` ohne Inline-Skript.
- Backend nicht geändert. Kein LLM-Aufruf, kein Golden-/Eval-Lauf, keine Docker-Aktion, keine
  Sichtprüfung im Browser über die E2E-Tests hinaus.

### Offen (Frontend)

- In `offene-befunde-und-todo.md` §5 eingetragen, nicht geändert: `clearInput` in
  `send-message.ts` leert einen Entwurf auch bei Antworten von außen; Kontrast des gefüllten
  Knopfs „Antworten“ im gesperrten Zustand; `modul-naht.ts` (siehe 8); `showMoreCards` der Shell
  ohne `prefers-reduced-motion`; Build-Warnung NG8102 in `ui-bloecke.component.ts`.
- Fokus nach „Antworten“ nur per Spec geprüft (jsdom); mit Vorleser nicht angehört. Nach dem Zug
  holt die Shell den Fokus wie bisher ins Eingabefeld.
