# W5 — Client auf den neuen WLO-MCP umstellen

**Stand 2026-07-30.** Entwurf zur Freigabe. Gebaut ist bisher nur **W5-1**
(Themenseite in einem Call, Beleg im Neubau-Plan). Alles Folgende ist geplant,
nicht umgesetzt.

Quelle: `../wlo-mcp-server-sc` — **Referenz, nie ändern**. Server live unter
`https://wlo-mcp.87.106.195.152.nip.io/mcp`; alle Zahlen hier sind gegen diese
Instanz gemessen, nicht aus der Doku übernommen.

## Ziel (Nutzer-Vorgabe 2026-07-30)

1. **Weniger MCP-Aufrufe** durch die Kombi-Tools des neuen Servers.
2. **Unsere Pattern bleiben** — nur die dort genannten Tools ziehen nach.
3. **Neu: Volltext.** Der Nutzer soll den *Inhalt* bekommen (ein Arbeitsblatt als
   Markdown), nicht nur Metadaten — anzeigen und bei Bedarf bearbeiten.

**Ausdrücklich draußen** (Nutzer-Entscheid): die 4 Widgets des Servers und
`docs/systemprompt_boerdi v2.md` — beides zielt auf den OpenAI-GPT-Store, nicht
auf unseren Chatbot.

## Ausgangslage, gemessen

| Befund | Wert |
|---|---|
| Tools auf dem Server | 23 |
| davon in unserer LLM-Liste | 12 |
| Pattern insgesamt | 16 (M01–M16) |
| davon mit namentlich genannten Tools | **9** (M05, M06, M08, M09, M10, M12, M13, M15, M16) |
| `get_wlo_content_text` | **0,9–1,1 s**, liefert echtes Markdown |

Zwei Dinge, die den Zuschnitt bestimmen:

* **`get_wlo_content_text` steht nicht in `_JSON_CAPABLE_TOOLS`** und antwortet
  deshalb in Markdown. Die Felder `source`, `reason` (`access_denied`,
  `no_text_no_url`, `extraction_failed`, `node_not_found`) und `truncated`
  bekommen wir erst mit `outputFormat: "json"`. Ohne sie können wir einen
  Rechte-Fall nicht von einem Extraktionsfehler unterscheiden.
* **Der Klassifikator kann das Kombi-Tool gar nicht vorschlagen.**
  `services/prefetch.py:174` lässt als LLM-Hint nur
  `{search_wlo_topic_pages, search_wlo_collections, search_wlo_content}` zu —
  `search_wlo_all` fehlt in der Menge. Empfiehlt das Modell es, fällt der Hint
  still auf die Heuristik zurück.

---

## W5-2 — Kombi-Tools: weniger Aufrufe (klein, messbar)

**a) `search_wlo_all` als zulässigen Klassifikator-Hint aufnehmen.**
Einzeiler in `_known_search_tools` plus ein Test. Heute kann das Modell den
Standard-Einstieg des Servers nicht wählen, obwohl der Antwort-Prompt ihn
ausdrücklich empfiehlt (`response_prompt_tools_text.py:211`) — eine Regel, die
ihren eigenen Weg blockiert.

**b) `search_wlo_within_collection` statt „alles holen und clientseitig sieben".**
Betrifft M08 (Sammlungs-Drilldown) und die Direkt-Aktion
`_handle_browse_collection`. Heute: `get_collection_contents` + Filterung bei
uns. Künftig: der Server filtert. **Vorher messen** — Trefferqualität gegen den
heutigen Weg, nicht nur die Laufzeit.

**c) `get_node_details` prüfen.** Laut Server-Doku „Alle Metadaten **+ Volltext**"
— falls das stimmt, ersetzt ein Aufruf `get_node_details` +
`get_wlo_content_text`. **Erst messen**, ob der Volltext wirklich mitkommt und
was er kostet; die Doku sagt an anderer Stelle 0,3 s für Details und 1–3 s für
Volltext, das passt nicht zusammen.

Abnahme je Punkt: Aufrufzahl vorher/nachher am echten Server, Trefferqualität
unverändert oder besser, Suite grün.

---

## W5-3 — Volltext: das fehlende Pattern (der eigentliche Neubau)

Hier entsteht Funktion, nicht nur eine Umstellung. Deshalb zuerst die
Entscheidungen, die **du** treffen musst — sie ändern den Bau grundlegend:

**Entscheidung 1: Ein Pattern oder zwei?**
* *Ein Pattern* „Inhalt anzeigen" (M17), Bearbeiten läuft über das vorhandene
  M11 (iterative Nachbearbeitung). Weniger neue Teile, nutzt Bestehendes.
* *Zwei Pattern* M17 „anzeigen" + M18 „damit arbeiten". Klarere Trennung, aber
  zwei neue Zustände in der State-Machine und zwei Klassifikator-Kategorien.

**Empfehlung: ein Pattern.** Wir haben mit M10/M11 bereits die Bearbeitungs-
Maschinerie; ein zweites Pattern dafür wäre Doppelung.

**Entscheidung 2: Wo erscheint der Volltext?**
Wir haben beide Kanäle schon: **Inline-Dokument** (Lese-Ansicht im Chat) und
**Canvas** (bearbeitbar). Naheliegend: anzeigen → Inline-Dokument, „damit
arbeiten" → Canvas übernimmt den Text. Das ist bewusst *keine* neue Anzeige-Art.

**Entscheidung 3: Was bei `access_denied`?**
Rund ein Teil der Materialien ist nicht öffentlich. Der Server sagt das sauber
(`reason: access_denied`) — daran ändert keine Konvertierung etwas, nur Rechte.
Soll der Bot das benennen („dieses Material ist nicht frei zugänglich, hier ist
der Link") oder still auf die Metadaten zurückfallen?

**Bauteile, wenn die drei Fragen entschieden sind:**

1. `get_wlo_content_text` in `_JSON_CAPABLE_TOOLS` + Parser für
   `{text, source, reason, truncated}` (test-first, Fehlerfälle zuerst).
2. Tool-Definition für das LLM (`TOOL_DEFINITIONS`) mit ehrlicher Beschreibung —
   inklusive „lohnt erst, wenn der Inhalt selbst gebraucht wird" (Server-Doku:
   für Titel/Fach/Lizenz genügt `get_node_details`).
3. Neue Pattern-Datei `m17-…md` im Bereich `03-patterns`, im Studio pflegbar wie
   alle anderen.
4. Klassifikator: neue Pattern-ID in Prompt und Zulassungsliste.
5. State-Machine: erlaubte Übergänge nach/von M17.
6. Anzeige: Inline-Dokument bzw. Canvas-Übergabe.
7. Golden-/Eval-Fälle für den neuen Weg — **Läufe startest du**, ich liefere die
   Fälle.

---

## W5-4 — Die neun Pattern mit Tool-Nennungen durchgehen

Erst nach W5-2/W5-3, weil sich dann erst entscheidet, was dort stehen soll.
Je Pattern: nennt es ein Tool, das es so nicht mehr gibt oder das durch ein
Kombi-Tool ersetzt wird? M16 ist mit W5-1 bereits erledigt (kein
`search_wlo_topic_pages` mehr im Themenseiten-Pfad).

**Kein Sammel-Commit.** Ein Pattern je Schritt, jeweils mit dem Beleg, warum die
neue Tool-Wahl besser ist — sonst ist bei einer Regression nicht auffindbar,
welche Änderung sie ausgelöst hat.

---

## Was ich NICHT vorschlage

* **Die 12 Server-Beschreibungen 1:1 übernehmen.** Unsere tragen boerdi-eigene
  Führung („Mappe Klassenangaben IMMER auf eine Bildungsstufe"), die der Server
  nicht kennt. Zusammenführen je Tool, kein Kopieren — steht als W4-Rest.
* **Die restlichen ungenutzten Tools auf Vorrat einbauen**
  (`find_wlo_skills`, `lookup_wlo_publishers`, `fetch`, `search`,
  `get_wikipedia_summary` — letzteres überschneidet sich mit unserem eigenen
  `services/wikipedia_service.py`). Jedes kostet Prompt-Platz und Tool-Auswahl-
  Rauschen; ohne konkreten Anlass bleibt es draußen.

## Reihenfolge

W5-2a (Einzeiler, sofort) → W5-3 nach deinen drei Entscheidungen → W5-2b/c mit
Messung → W5-4 Pattern-Durchgang.

---

# Umsetzungsstand

## ✅ W5-3a — Volltext strukturiert lesen (2026-07-30)

**Am MCP war nichts umzubauen.** `get_wlo_content_text` kann `outputFormat:
"json"` bereits (`content-text.ts:36`) und liefert dann den vollen Vertrag aus
`outputSchemas.ts:70`. Die Lücke lag bei uns: wir haben es nie angefragt.
Gebaut: `parse_content_text` (Boerdi-Namen, `reason="no_envelope"` statt
geratenem Text, wenn kein Envelope kommt) + Tool in `_JSON_CAPABLE_TOOLS`.

## ✅ W5-3b — Volltext-Tool für das Modell + Deckel auf 20000 (2026-07-30)

Beim Bauen aufgefallen: **`get_wlo_content_text` stand gar nicht in
`TOOL_DEFINITIONS`** — das Modell konnte den Volltext nicht anfordern. Jetzt
drin, mit einer Beschreibung, die den `access_denied`-Fall benennt und die
Alternative vorgibt (selbst erzeugen oder frei zugängliche Materialien suchen).

**Deckel 8000 → 50000.** Erst auf 20000 gesetzt („max. 10 A4-Seiten"), auf
Nutzer-Ansage dann auf die **harte Obergrenze des Tools** — belegt, nicht
angenommen: `maxChars=50000` läuft, `60000` weist der Server ab
(`MCP error -32602: Number must be less than or equal to 50000`). Zentral im
`call_mcp_tool` gesetzt wie `outputFormat`, damit ihn kein Aufrufer und kein
LLM-Toolcall vergessen kann; ein ausdrücklich mitgegebener Wert gewinnt.

Live vorher/nachher, dieselben Arbeitsblätter:

| | vorher (8000) | nachher |
|---|---|---|
| „Übungsmaterial zur Bruchrechnung" | 8003, **abgeschnitten** | 8839, vollständig |
| „Brüche verstehen und vergleichen" | 7903, **abgeschnitten** | **18262**, vollständig |

Das zweite Dokument verlor vorher über die Hälfte. In dieser Stichprobe reichten
schon 20000; 50000 kostet nichts zusätzlich, solange kein Text so lang ist —
`maxChars` ist eine Obergrenze, keine Anforderung.

**Beobachtung, nicht gebaut:** `get_wlo_content_text` hat kein Eintrag in
`_TOOL_ARG_MODELS`, ein LLM-Wert über 50000 liefe also erst serverseitig auf
einen Fehler, den `parse_content_text` als `reason="no_envelope"` sieht — für den
Nutzer sähe das aus wie „kein Text". Die Tool-Beschreibung nennt die Grenze; eine
Klammer im Client wäre erst nötig, wenn das real vorkommt.

## ✅ W5-2a — `search_wlo_all` ist das Standard-Suchtool (2026-07-30)

Nutzer-Entscheid: das Kombi-Tool ist der Standard und darf die Heuristik
überstimmen. Bis hierher fiel dieser Hint **still durch** — der Antwort-Prompt
empfiehlt das Tool ausdrücklich, die Zulassungsliste kannte es nicht, also
entschied bei I03/M06 die Themenseiten-Heuristik gegen die Absicht des Modells.

**Die Falle, die der Test vorher fand:** `spec_is_search_all` wählt den Parser.
Hätte ich nur die Zulassungsliste erweitert, wäre bei einem ausdrücklichen
Themenseiten-Wunsch der Name `search_wlo_all` stehen geblieben, während die
Flagge False ist — der Aufruf wäre mit den Primary-Argumenten rausgegangen und
die Antwort in den falschen Parser gelaufen. Deshalb die zusätzliche Zeile, die
den Themenseiten-Wunsch vorziehen lässt.

Vorrang, als Test gepinnt (`test_prefetch.py`):

1. Medientyp genannt („Video") → `search_wlo_content`
2. Nutzer sagt „Themenseite" → `search_wlo_topic_pages`
3. sonst / Hint `search_wlo_all` → `search_wlo_all`

Gesamt-Verifikation dieser drei Pakete: Backend **2199 pytest**, ruff sauber,
`export_openapi.py --check` unverändert.

## ✅ W6 — Der Config-Seed wird ausgeliefert (2026-07-30)

Nutzer-Entscheid: der letzte Redaktionsstand des alten Chatbots gehört als
**versionierter Seed in die Auslieferung**, damit eine frische Installation
startet, ohne dass der ALT-Baum daneben liegt; das Studio bleibt der Weg für
spätere Änderungen.

Vorher hing die gesamte Konfiguration am ALT-Baum: `CONFIG_SEED_DIR` war leer,
und `import-config` brauchte einen Pfad, den nur diese Arbeitskopie kennt.

* **55 Dateien** (29 YAML + 26 MD, 358 KB) nach `backend/seeds`; der ALT-Baum
  wurde dabei **nur gelesen** — nachgeprüft: keine Datei dort in den letzten
  Stunden verändert, `badboerdi.db` unverändert vom 11.07.
* `CONFIG_SEED_DIR` steht jetzt standardmäßig auf `seeds`.
* **Beweis der Gleichwertigkeit:** Import aus dem ALT-Baum und aus dem Seed
  ergeben **je 55 Bereiche, identische Schlüsselmengen, 0 inhaltliche
  Abweichungen**.
* **Lücke, die dabei auffiel:** das Prod-Image kopierte `backend/seeds` nicht —
  im Container hätte `CONFIG_SEED_DIR=seeds` auf ein nicht existierendes
  Verzeichnis gezeigt und der Import wäre ins Leere gelaufen. `COPY` ergänzt,
  ein Test wacht über die Zeile.

Damit ist der Ort für M17 geklärt: `backend/seeds/03-patterns/m17-….md`.
Verifikation: Backend **2205 pytest**, ruff sauber.

## ✅ W5-4a — Was die Pattern über ihre Werkzeuge sagen (2026-07-31)

Erster Schritt des Pattern-Durchgangs, jetzt möglich, weil die Pattern seit W6
im Repo liegen. **Geprüft wurde alles, geändert nur das Falsche:**

* **M16 log.** Das Pattern nannte `search_wlo_topic_pages` + `get_topic_page_content`
  und beschrieb eine zweistufige Pipeline — beides seit W5-1 überholt: der
  Resolver macht **einen** Aufruf, `get_topic_page_content` löst die Seite selbst
  auf. Frontmatter und Pipeline-Text korrigiert.
* **Die übrigen acht Pattern brauchten keine Anpassung.** M05/M06/M08/M09/M12
  nennen ausschließlich Tools, die es auf dem neuen Server unverändert gibt;
  M13/M15 nennen nur Tool-*Familien* (`search_wlo_*`). Kein erfundener Umbau.
* **Wächter dazu** (`test_config_seed_tree`): jeder in einem Seed-Pattern
  genannte Tool-Name muss in `TOOL_DEFINITIONS` existieren. Grund:
  `_select_active_tools` filtert die Definitionen gegen diese Liste — ein Name,
  den es nicht gibt, verschwindet **still**, und das Pattern sieht weniger
  Werkzeuge, als sein Autor glaubt. Heute stimmt alles; der Test hält es so.

## ✅ M17 — Volltext anzeigen (2026-07-31)

**Der Befund, der den Zuschnitt bestimmt hat:** `get_wlo_content_text` stand seit
W5-3b in `TOOL_DEFINITIONS`, war aber aus **keinem** Pattern erreichbar. Pattern
mit `tools:`-Liste schneiden die Tool-Liste auf ihre eigenen Namen zu, und keins
nannte das Volltext-Werkzeug; die Pattern ohne Liste haben `sources: llm/rag`
und bekommen den Suche-Fallback. Das Werkzeug war also gebaut, ohne Verbraucher —
der sechste Fall dieser Klasse in diesem Projekt.

**Warum der Text nicht durch das Antwort-LLM läuft.** Zwei Gründe, der zweite ist
ein Ausschlusskriterium, kein Qualitätsargument:

* **Wortlaut.** Ein Arbeitsblatt, mit dem jemand arbeiten will, muss unverändert
  ankommen. Eine Nacherzählung wäre ein anderes Dokument.
* **Länge.** Der Server liefert bis zu 50 000 Zeichen (~15 000 Token). Das passt
  in keine Antwort-Länge — ein LLM dazwischen *müsste* kürzen. Der
  LLM-vermittelte Pfad könnte die Anforderung also gar nicht erfüllen.

**Gebaut** (Bauart wie M16: deterministisch, LLM übersprungen):

* `services/content_text_action.py` — `show_content_text` als vierte
  Direkt-Aktion. Eigene Datei, weil `direct_actions.py` mit 519 Zeilen bereits
  über dem Schwellwert steht und in seinem eigenen Kopf den Split-Pfad nennt.
* `graph/nodes/preflight.py` — Dispatch + **dasselbe Sicherheits-Gate** wie die
  drei ALT-Aktionen (sonst wäre die neue Aktion ein Weg daran vorbei; zwei Tests
  pinnen Dispatch und Block).
* `seeds/03-patterns/m17-volltext-anzeigen.md` — Priorität 488 (bewusst unter der
  Such-Familie: ein falsches M17 wäre teurer als ein falsches M05),
  Diskriminatoren gegen M05/M16/M10/M11.
* **Kein** `display_rules`-Schalter für M17: die Box wird direkt gebaut (der
  Lead/Body-Split von `_build_inline_document` würde einem fremden Dokument den
  ersten Absatz herausreißen). Ein Knopf ohne Wirkung wäre schlimmer als keiner.

**Live gegen `https://wlo-mcp.87.106.195.152.nip.io/mcp` belegt:**

| Fall | Ergebnis |
|---|---|
| 3 Materialien zu „Arbeitsblatt Bruchrechnung" | Volltext in **1,1 s** je Abruf, 8839 / 1781 / 937 Zeichen, `truncated: false`, Wortlaut unverändert in der Box |
| `extraction_failed` (PhET-Arbeitsblatt) | benannt als *technisches* Problem, ausdrücklich **nicht** als Rechtefrage — plus die zwei Auswege als Quick-Replies |

Der Klassifikator sieht M17: Import des Seed-Baums ergibt **56 Bereiche**,
`load_pattern_definitions()` liefert M01–M17, und `_select_active_tools` gibt für
M17 `['get_wlo_content_text', 'search_wlo_content', 'get_node_details', …]` —
das Werkzeug ist erreichbar.

Verifikation: Backend **2216 pytest**, 2 skipped · ruff sauber · OpenAPI
unverändert.

## ✅ M17-Frontend — Der Knopf, der die Aktion auslöst (2026-07-31)

**Der Befund, der den Zuschnitt bestimmt hat:** `inline-result-grouping` steht
per Default auf `true`. Materialien erscheinen im Normalbetrieb also als
kompakte Zeilen in der Box „Ausgewählte Materialien" — **nicht** als Kachel im
Flach-Grid. Ein Knopf nur an der Kachel wäre im Normalbetrieb unsichtbar
gewesen; die Aktion hätte wieder keinen Verbraucher gehabt. Deshalb beide
Oberflächen:

* **Gruppen-Box** (Default): Icon-Knopf **neben** dem Link, nicht darin — ein
  Bedienelement im Anker wäre ungültiges HTML und für die Tastatur mehrdeutig.
  Name über `aria-label`, das **das Material benennt** (eine Box hat mehrere
  Zeilen, „Inhalt anzeigen" allein wäre mehrdeutig).
* **Flach-Grid**: beschrifteter Knopf „Inhalt anzeigen" in der bestehenden
  `.card-actions`-Leiste, gegated über `isInhalt()` — dieselbe Definition, die
  die Gruppen-Box zum Füllen ihrer Materialien-Liste benutzt.
* `showContentText` in `controllers/collection-actions.ts` + Shell-Delegate +
  beide Template-Bindungen + `public-api`-Export.

**Ein Bestandstest musste umgeschrieben werden**, nicht entschärft: 8-2i pinnte
„Nicht-Sammlung → gar keine Aktionsleiste". Das ist seit M17 nicht mehr wahr;
der Test sagt jetzt, was gilt (Einzelinhalt = genau eine Aktion), und ein
zweiter deckt weiter ab, dass eine Karte **ohne** `node_id` keine Leiste bekommt.

**Optisch geprüft** an einer statischen Probe mit dem echten kompilierten
Stylesheet (kein Backend nötig; danach entfernt):

| Messung | Ergebnis |
|---|---|
| Knopfgröße | 28 × 28 px — über dem WCAG-2.2-Minimum (SC 2.5.8: 24 px) |
| Zeilenhöhe | 28 px, Knopf rechtsbündig, **keine Überlappung** mit dem Link |
| Langer Titel | wird gekürzt (Link wächst, Knopf bleibt fest) |
| 320 px Breite | Link 204 px, Knopf 28 px, **kein horizontales Scrollen** |
| Gesperrter Zustand | `opacity: .45`, kein Zeiger |

Der Barrierefreiheits-Baum zeigt Link und Knopf als Geschwister, jeder Knopf mit
dem Materialtitel im Namen.

Verifikation: `npx ng test ui` → **460 passed** (52 Dateien) · `npm run
build:widget` → 416,49 kB / 110,52 kB übertragen, Budget-Gate grün ·
`npm run lint` → sauber.

## ✅ M17 — Weiterarbeiten am geholten Text (2026-07-31)

**Meine eigene Annahme war falsch, und das Nachsehen hat den Auftrag verkleinert.**
Ich hatte „Canvas-Übergabe" als offenen Punkt notiert. M11 (iterative
Nachbearbeitung) arbeitet aber gar nicht über Canvas-State, sondern über die
**Gesprächshistorie**: `_assemble_messages` legt `history[-10:]` in den Prompt,
und M11 rendert den vorigen Inhalt komplett neu. Es brauchte also keine
Übergabe — nur drei Kleinigkeiten, die alle fehlten:

1. **Der Volltext wurde nicht persistiert.** Der Handler speicherte die
   Begleitzeile („Hier ist der Inhalt von …"), nicht das Dokument. M11 hätte
   nichts zum Überarbeiten gehabt. `turn_persist` macht es für M09/M10 seit
   jeher richtig und sagt im Kommentar auch warum — der neue Handler zog nicht
   nach. Jetzt geht Lead **plus** Volltext in die Historie.
2. **Der Zug war nicht als M17 markiert.** Die Lernpfad-Direkt-Aktion setzt
   `session_state["last_pattern"] = "M09"`; der Volltext-Handler setzte nichts,
   also zeigte `last_pattern` weiter auf den Zug davor. Gesetzt — aber **nur bei
   vorhandenem Text**: ein `access_denied`-Fall als Vor-Inhalt zu markieren
   würde einen Bearbeiten-Zug auf ein leeres Dokument schicken (eigener Test).
3. **M11 kannte M17 nicht.** Seine Auswahlregeln nannten `last_pattern in
   M09/M10/M11`. Ergänzt, samt Hinweis, dass es sich um **fremdes** Material
   handelt (Quelle nennen, nicht als eigenes ausgeben).

Dazu die **Quick-Replies konkret gemacht**: aus „Daran weiterarbeiten" wurden
„Mach den Text kürzer" / „Formuliere es einfacher" — genau die Formulierungen,
über die M11 ausgewählt wird. Ein vager Chip wäre beim Klassifikator im
Nirgendwo gelandet, der Knopf also Dekoration.

Verifikation: Backend **2220 pytest**, 2 skipped · ruff sauber · Seed-Import
56 Bereiche.

## ✅ Karten-Darstellung nach Nutzer-Rückmeldung (2026-07-31)

Drei Punkte aus der Vorschau — einer war schon erfüllt, einer war mein Fehler.

**1. Symbol vorn und hinten.** Berechtigt, und ich habe es verursacht: der
Volltext-Knopf trug `article` — dieselbe Glyphe, die `getCardIcon` für den Typ
„Arbeitsblatt" vorn in der Zeile setzt. Die Zeile las sich, als stünde der
Inhaltstyp zweimal drin. Jetzt `visibility` (Auge = „anzeigen"): vorn der Typ,
hinten die Handlung. **Der erste Test dazu war zu schwach** — er verglich gegen
die Roh-Konstante, doch die Sanitizer-Pipe normalisiert das SVG, also war er
grün, obwohl die Symbole gleich aussahen. Der zweite vergleicht zwei
*gerenderte* Symbole an einer Arbeitsblatt-Karte und wurde erst rot, dann grün.

**2. Box als Standard, Kacheln optional — war schon so.** Das Host-Attribut
`inline-result-grouping` steht per Default auf `true` (Boxen); `="false"`
schaltet auf das Kachel-Raster. Nichts gebaut, nur nachgeprüft.

**3. Kacheln kleiner und einheitlich.** ALT rendert `.cards-list` einspaltig,
jede Karte über die volle Chat-Breite. Bewusste Abweichung: `auto-fill`-Raster
mit `minmax(260px, 1fr)` — mehrere Kacheln je Zeile, unter ~260 px automatisch
einspaltig. Für gleiche Größen drei Ergänzungen: `.wlo-card { flex: 1 }` (füllt
das Rasterfeld), Titel auf 2 Zeilen **reserviert** (nicht nur gekürzt),
Bildzeile auf 72 px reserviert.

**Gemessen an einer statischen Probe mit dem echten kompilierten Stylesheet:**

| Bühne | Spalten | Kachelbreite | Kachelhöhe | Vorschaubild | Titelhöhe |
|---|---|---|---|---|---|
| 720 px | 2 | 354 px (je) | **235 px (je)** | 92 × 72 (je) | 35 px (je) |
| 340 px | 1 | 340 px (je) | **235 px (je)** | 92 × 72 (je) | 35 px (je) |

Je Spalte genau **ein** Wert — keine ungleichen Höhen mehr. Der erste Durchlauf
zeigte noch 235 vs. 212: Kacheln **ohne** Vorschaubild waren flacher. Deshalb
die reservierte Bildzeile; ein Platzhalter-Bild wäre die Alternative gewesen,
aber leerer Raum ist ehrlicher als eine leere blaue Fläche.

Verifikation: `npx ng test ui` → **461 passed** · `npm run lint` → sauber ·
`npm run build:widget` → 416,57 kB / 110,45 kB, Budget-Gate grün.

## Offen an M17

* **Golden-Fälle** für den neuen Weg — Läufe startest du.
* **Live-Durchstich im Widget** (Knopf klicken → Box → „mach das kürzer") ist
  nicht gefahren; dafür braucht es Postgres + LLM-Schlüssel. Geprüft sind
  Verhalten, Barrierefreiheit, Layout und die Persistenz — nicht der
  Klassifikator-Sprung M17 → M11 im Betrieb.
* **Kostenpunkt, gemessen statt geraten:** ein geholtes Dokument steht danach
  bis zu 10 Züge lang in der Historie — bei den Live-Messungen 8839 bzw. 18262
  Zeichen (≈ 2 500 / 5 000 Token je Folge-Zug). Für M09/M10 gilt dasselbe, dort
  sind die Dokumente aber LLM-erzeugt und damit kleiner. Kein Deckel eingebaut:
  eine stille Kürzung wäre genau der Fehler, den dieses Projekt wiederholt
  gefunden hat. Falls es teuer wird, ist die Entscheidung deine.
