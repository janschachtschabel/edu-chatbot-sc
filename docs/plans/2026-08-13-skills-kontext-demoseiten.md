# Skills, Seitenkontext, Demoseiten (2026-08-13, abends)

Anlass: Live-Probe gegen Staging zeigte, dass die redaktionellen Skills einer
Sammlung im Betrieb **nicht** beim Modell ankommen. Dazu Nutzer-Befunde zu den
Demoseiten und zur Kontext-Bestätigung.

## 1. Befunde (live, `https://87.106.127.225.nip.io`)

Vier Züge, gleicher Seitenkontext (`page_kind: collection`, Optik
`9e7ae956-e9df-430f-bace-f3db4b910013`):

| Frage | Maschine | Muster | `tools_called` | Skill? |
|---|---|---|---|---|
| „plane eine unterrichtsstunde fuer optik" | pattern | M09 | `search_wlo_collections`, `get_collection_contents`×3, `generate_learning_path` | **keines** |
| dito | agent | AGENT | `search_skill`, `search_wlo_all` | freie Suche |
| „welche anleitungen gibt es fuer diese sammlung?" | pattern | M08 | `search_wlo_content`, `get_skill_registry` | ✅ „28 Skills" |
| dito | agent | AGENT | — | **keines**, fragt „welche Sammlung meinst du?" |

**B-1 M09 ruft kein Skill-Werkzeug**, obwohl es alle drei deklariert. Genau die
Aufgabe, für die „Stunde planen" (`5b29f470-…`) geschrieben wurde.

**B-2 Der Agent im Chat kennt den Seitenkontext nicht.** Er fragt nach einer
Sammlungs-ID, die in `page_context.collection_id` steht.

**B-3 Der MCP liefert die Registry frei Haus — wir lesen sie nicht.**
`get_collection_contents(Optik)` trägt am Knoten „Geometrische Optik" ein Feld
`skillRegistry` mit 28 Einträgen (nodeId + Titel). boerdi ruft mit
`outputFormat=json`, bekommt es also. `grep -rn "skillRegistry" backend/src/` →
**0 Treffer**. Es fällt auf den Boden.

> **Richtigstellung (2026-08-13, beim Bau von P1 nachgemessen).** Der erste Satz
> oben ist zu grob und hätte P1 an die falsche Stelle gebaut. Gemessen:
> `get_collection_contents(Optik)` im **Standardaufruf** (`contentFilter=files`)
> trägt **kein** `skillRegistry` — die Treffer sind Materialien. Erst
> `contentFilter=folders` liefert die Unter-Sammlungen, und **eine** davon
> („Geometrische Optik", `f35c17d1-…`) trägt es mit 28 Einträgen. Die Inhalte
> **dieser** Sammlung abzurufen bringt es wieder nicht mit. Das Feld hängt also
> am **Knoten, der eine Registry besitzt**, und nur, wenn dieser Knoten selbst
> als Trefferzeile auftaucht. Die richtige Naht ist damit nicht „bei
> Sammlungsabrufen", sondern „in jedem Ergebnis, das Knoten auflistet" — Suche,
> Auflistung, Baum, Knotendetails. Die Zahl 28 und der 0-Treffer-Befund stimmen.

**B-4 `search_skill` mit `collectionId` einer Sammlung liefert nichts.** Die
Skills liegen unter `AI-Skills/Skillset_Lehrtoolkit/`, nicht in der Sammlung;
die Sammlung führt nur die Freigabeliste. Die Werkzeugbeschreibung lädt zum
falschen Aufruf ein, und das Werkzeug sagt dem Modell dann, das Nichts sei
normal — der Chatbot arbeitet stumm ohne Anleitung weiter.

**B-5 Die Kontext-Bestätigung kommt, man sieht sie nur nicht.** Das Backend
antwortet auf `context_open` **und** `context_open_initial` zuverlässig
(`CTX:collection`, Gruß + Pills). Auf `/widget/classic` startet das Widget
geschlossen, die Shell ist nicht gemountet, `_greetOnFirstLoad` läuft erst beim
Öffnen.

**Nicht-Befunde** (geprüft, Nutzer-Annahme trifft nicht zu): der
`engine`-Schalter steht auf **allen drei** Live-Demoseiten
(`data-attr="engine"` je 1×). Und die Knöpfe brauchen keinen Hardcode —
`01-base/context-actions.yaml` ist Studio-pflegbar und kennt bereits alle sechs
Seitenarten.

## 2. Entscheidungen des Nutzers (2026-08-13)

1. **P1 ja** — `skillRegistry` lesen.
2. **P2 ja** — Muster nachschärfen, „eventuell auch in Systemprompts nennen".
3. **P3 `search_skill` deaktivieren** — „immer der Weg über die Sammlung",
   aus Mustern **und** Agent-Katalog heraus.
4. **P4 ja** — Agent im Chat: Seitenkontext + Registry-Vorabruf.
5. **P5 ja** — Demo-Simulator: Voreinstellung Sammlung + Optik-UUID.
6. **P6 ja** — Kontext-Bestätigung sichtbar, „auch bei den anderen Widgets".
7. **P7 neu** — Schnellantwort-Knöpfe je Seitenart (Listen unten).
8. **P8 neu** — Demoseiten zeigen den Einbindungscode und aktualisieren ihn.
9. **P9 neu** — „echter Unterschied zwischen embedded und rahmenlos" fehlt.

## 3. Zuschnitt

### P1 — `skillRegistry` lesen und zeigen
Der MCP hängt `skillRegistry: {nodeId, title, entries[]}` an **jeden Knoten, der
eine Registry besitzt** (siehe Richtigstellung zu B-3). Also nicht bei
Sammlungswerkzeugen ansetzen, sondern in **jedem** Ergebnis, das Knoten
auflistet, und dem Modell als Block zeigen. Damit sieht es den Katalog ohne
Extra-Aufruf — der wirksamste Hebel gegen B-1.

### P2 — Muster + Systemprompts
M08/M09/M10/M18/M19/M20: steht eine Sammlung (oder Themenseite) im Kontext,
`get_skill_registry` **vor** der eigenen Lösung; passt ein Eintrag zur Aufgabe,
`get_skill` und der Anleitung folgen. Dazu der Systemprompt der Agent-Schleife
(`agent_run._SYSTEM`) und der Antwort-Prompt der Muster-Engine.

### P3 — `search_skill` deaktivieren
Aus den `tools:`-Blöcken der Muster und aus `build_agent_tools`. Die Definition
bleibt im Katalog stehen (ein Wächter nennt sie), aber kein Pfad bietet sie an.
Begründung im Code: der Weg über die Sammlung ist der einzige, der die
redaktionelle Freigabe respektiert.

### P4 — Agent im Chat
Wie `/api/agent` mit `collection_id`: liegt eine Sammlung im `page_context`,
`get_skill_registry` vorab in die Nachrichtenkette. Behebt B-2 und B-1 für die
Agent-Seite in einem Schritt.

### P5 — Demo-Simulator vorbelegen
`kontext=collection` vorgewählt, Optik-UUID als Vorgabewert im Feld.

### P6 — Kontext-Bestätigung sichtbar
Auf einer Demoseite mit gesetztem Kontext den Chat geöffnet starten, damit die
Bestätigung erscheint (`initial-state="expanded"`), und im Hinweistext sagen,
dass die Bestätigung beim Öffnen kommt.

### P7 — Knöpfe je Seitenart (`01-base/context-actions.yaml`)

| Art | Knöpfe (Nutzer-Vorgabe) |
|---|---|
| `collection` | Sammlungsinhalte zeigen · Unterrichtsstunde planen · Sammlung kuratieren · Zu Lehrplänen beraten |
| `content` | Mehr Details zeigen · Volltext abrufen und bearbeiten · Inhalte remixen · Ähnliche Inhalte suchen |
| `topic` | Themenseiteninhalte zeigen · Unterrichtsstunde planen · Sammlung kuratieren · Zu Lehrplänen beraten |
| `search` | Videos zum Thema · Arbeitsblätter zum Thema |
| `home` | Informiere mich über WLO · Webseiten-Tour starten · Inhalte finden · Kontakt und mitmachen |
| `external` | unverändert — die zwei Beschriftungen sind **wörtlich** M20s `trigger_phrases`; frei formuliert löste der Chip sein Muster nicht aus |

Zwei Dinge sind dabei keine Beschriftungsfrage:
* „Webseiten-Tour starten" braucht den **richtigen Auslöser** (Nutzer-Hinweis),
  nicht nur den Text — es gibt einen Tour-Pfad im Backend.
* Bei `kind: text` **ist die Beschriftung die gesendete Nachricht**. Jede neue
  Zeile muss also ihr Muster treffen, sonst ist sie ein Knopf, der nichts tut.

### P8 — Einbindungscode live
Das Bedienpult setzt die Attribute am laufenden Element; derselbe Zuhörer kann
den `<pre>`-Block darunter neu schreiben. Dann zeigt die Seite genau den Code,
den eine externe Person für die eingestellte Kombination braucht.

### P9 — `/inline` vs. `/frameless`
Heute unterscheiden sie sich nur in `initial-state` — beide rahmenlos im selben
Kasten. Vorschlag: `/inline` bleibt der **Kasten im Textfluss**, `/frameless`
wird die **Spalte neben dem Seiteninhalt** (voller Höhe, ohne Rahmen) — der
realistische CMS-Fall und sichtbar anders.

## 4. Belege je Scheibe

### P2 + P3 — erledigt (2026-08-13, abends)

Beide fassen denselben Textblock an („## Freigegebene Anleitungen der
Redaktion", wortgleich in sechs Mustern), deshalb in einem Zug.

**Seeds.** Regelblock in **6** Mustern ersetzt (M08/M09/M10/M18/M19/M20),
`- search_skill` aus **5** `tools:`-Blöcken entfernt (M08 führte es nie). Neue
Regel: Registry **immer** vor der eigenen Lösung · **nicht** frei suchen ·
sonst normal lösen.

**Code.** `agent_tools.AUS_DEM_KATALOG = {"search_skill"}` — die Definition
bleibt im Katalog (der MCP-Server hat das Werkzeug, ein Bestands-Wächter prüft
seine Beschreibung), aber kein Pfad reicht sie dem Modell.

**Fünf Wächter hielten die ALTE Entscheidung fest.** Alle umgedreht statt
gelockert, jeder mit dem Grund im Docstring:

| Wächter | vorher | jetzt |
|---|---|---|
| `test_kein_katalog_werkzeug_ohne_muster` | `search_skill` musste ein Muster haben | Ausnahmeliste `STILLGELEGT`, begründet |
| `test_arbeitende_muster_haben_auch_den_zweiten_weg` | `search_skill` **in** M09/M10/M18/M19/M20 | umbenannt zu `test_kein_muster_bietet_die_freie_skill_suche_an`, jetzt `not in` — und M08 dazu |
| `test_die_gegenprobe_bleibt` (M10) | drei Skill-Werkzeuge aktiv | zwei aktiv + `search_skill not in` |
| `test_jedes_dieser_muster_erklaert_die_reihenfolge` | Schritt-Wörter inkl. `search_skill` | prüft die **Aussage** — das Wort steht jetzt in der Begründung, ein Test darauf wäre grün ohne etwas zu wissen |
| `test_config_seed_tree`-Erreichbarkeit | jedes Katalog-Werkzeug braucht ein Muster | Ausnahme mit Messung begründet |
| `test_skill_tools` | eine Konstante für „existiert" **und** „wird angeboten" | zwei Konstanten — seit heute fallen die auseinander |

**Abnahme:** `ruff` pass · **pytest 3271 passed**, 4 skipped (2:20).

### P1 — erledigt (2026-08-13, abends)

**Zuerst gemessen, dann gebaut** — und die Messung drehte den Zuschnitt: die
Planannahme („bei Sammlungsabrufen") hätte den Block an eine Stelle gebaut, an
der das Feld gar nicht ankommt. Die Richtigstellung steht bei B-3.

**Neu:** `services/mcp/parsers/skill_registry.py` (~180 Z.) mit
`parse_skill_registries` (Daten) und `skill_registry_note` (Block), über die
Parser-Fassade exportiert. Nachzügler zu W11 und der einzige Parser des Pakets,
der nicht für die Oberfläche liest, sondern für den Prompt.

**Wie gesucht wird:** rekursiv nach dem Schlüssel `skillRegistry` in jedem
Werkzeugergebnis — nicht nach Werkzeugnamen. Damit greift es bei Suche,
Auflistung, Baum und Knotendetails gleichermaßen, ohne eine Liste zu pflegen,
die beim nächsten Server-Feld veraltet. Unlesbarer Text gibt `""` und wirft
nicht.

**Vier Nahtstellen**, dieselbe Zählung wie `untrusted_text` sie für den
Fremdtext-Rahmen führt: Werkzeug-Schleife (`tool_loop`), beide
Prefetch-Injektionen (`tool_loop_messages`), Agent-Schleife (`agent_loop`).
Jede mit eigenem Test.

**Die eine Stelle, an der die Reihenfolge zählt:** der Block wird **nach** der
Redaktion angehängt. Im Box-Modus ersetzt `_redact_search_content_for_llm` den
Text von `get_collection_contents` vollständig durch eine Zusammenfassung — davor
eingebaut wäre der Block still verschwunden. `test_naht_1_ueberlebt_die_redaktion`
hält genau das fest, samt Gegenprobe, dass die Redaktion überhaupt lief.

**Vertrauensgrenze:** kein Rahmen — die Titel sind kurze strukturierte Felder,
dieselbe Klasse wie Kartentitel, und `untrusted_text` zieht die Linie
ausdrücklich bei Langform-Prosa. Stattdessen die Maßnahme, die zur Form passt:
jeder Titel wird auf **eine Zeile** gezwungen und gedeckelt (80 Zeichen), damit
er keinen eigenen Abschnitt aufmachen und sich nicht als Anweisungsblock tarnen
kann. Zwei Tests dazu.

**Deckel:** 3 Registries × 40 Einträge, Weggelassenes wird benannt. Gemessen:
28 Einträge ≈ 2400 Zeichen — gegen ~20000 für die volle `get_skill_registry`-
Antwort. Der Auszug trägt nur Titel und nodeId; Beschreibung und
Verwendungshinweis holt weiterhin das Werkzeug.

**Abnahme:** `ruff` pass · **pytest 3291 passed**, 4 skipped (2:18) — genau die
20 neuen Tests über dem Stand von P2/P3, keine Regression. **Nicht** live
geprüft: die Instanz läuft mit dem alten Stand, und hier gibt es kein `.env` für
einen Aufruf über boerdis eigenen Client. Die Wirkung im Betrieb ist erst nach
dem Deploy messbar.

### P4 — erledigt (2026-08-13, abends)

Zwei Dinge, ein Zug: der Agent-Modus im Chat sieht jetzt den Seitenkontext, und
steht eine Sammlung darin, steht ihre Freigabeliste schon in der Kette.

**Der Befund war schlicht.** `respond_agent` baute seine Nachrichtenkette selbst
— System, Verlauf, Nutzernachricht. Der Bestandsweg reicht den Seitenblock über
`response_prompt_builder` ein; hier fiel er weg. Daher B-2: der Agent fragte
nach einer Sammlungs-ID, die vor ihm stand.

**Vier Dateien, davon eine neu.**

| Datei | Was |
|---|---|
| `services/agent_prefetch.py` **(neu, 81 Z.)** | die Vorabruf-Mechanik, aus `agent_run` herausgelöst |
| `services/agent_run.py` | ruft den gemeinsamen Helfer; entscheidet weiter allein, **was** vorab geholt wird |
| `services/page_context.py` | neu `prompt_block()` — „aufgelöst schlägt heuristisch" als *eine* Funktion |
| `graph/nodes/respond_agent.py` | Seitenblock + Registry-Vorabruf in die Kette |

**Zwei Extraktionen statt zwei Handkopien.** Die Vorabruf-Mechanik trägt zwei
Regeln, die zusammengehören: die Paar-Bauart (ein `role=tool` ohne den
zugehörigen Aufruf wird vom Anbieter abgelehnt) und die Fehlerregel (ein
gelöschter Knoten darf den Lauf nicht kippen). Zweimal gepflegt wären sie
irgendwann auseinandergelaufen. Dasselbe bei `prompt_block`: die zweistufige
Auflösung stand als Handkopie in `response_prompt_builder` und
`classify_prompt`; der Agent-Modus wäre die dritte gewesen.

**Nur `collection_id` löst den Vorabruf aus** — das einzige Feld, aus dem ein
`collectionId`-Argument wird. Themenseiten sind im Bestand Sammlungen und tragen
es mit, brauchen also keine eigene Regel. Bewusst **nicht** `node_ids`: was auf
der Seite steht, sagt schon der Seitenblock.

**Zwei Zahlen im Bestand waren falsch, beide richtiggestellt:**

* `untrusted_text` sagte „**Drei** Nahtstellen" — geschrieben vor der
  Agent-Schleife. Gegengezählt: `grep -rn frame_untrusted src/` → **fünf**.
* P1 sagte „vier Nahtstellen" und übersah den Agent-Vorabruf. Er ist die fünfte
  und bekommt den Registry-Auszug jetzt ebenfalls — sichtbar bei
  `get_nodes_details`, dessen Knoten eine Registry tragen können wie jeder
  andere Treffer.

**Abnahme:** `ruff` pass · **pytest 3302 passed**, 4 skipped (2:25) — +11 über
P1, keine Regression. Tests zuerst, rot gesehen (`ImportError`), dann gebaut.
**Nicht** live geprüft, gleicher Grund wie bei P1: die Instanz läuft mit dem
alten Stand.

**Bewusst offen gelassen (nicht vergessen):** die zwei Bestandskopien der
zweistufigen Auflösung in `response_prompt_builder` und `classify_prompt` rufen
weiterhin ihre Handfassung statt `page_context.prompt_block`. Mechanisch, aber
sie formen den Prompt **jedes** Zuges — das gehört in einen eigenen Schritt mit
eigenem Golden-Lauf, nicht in ein Feature-Paket.

### P7 — erledigt (2026-08-13, abends)

Die bestellten Listen stehen. **Drei Dinge waren beim Bauen anders als gedacht**,
und alle drei stecken jetzt als Wächter in `tests/test_context_action_pills.py`.

**1. „Unterrichtsstunde planen" hätte den Skill ausgesperrt.** Das Wort
`unterrichtsstunde` steht in `lp_intent._lp_keywords`; geprüft wird auf
**Teilzeichenkette**, und der Lernpfad-Schnellweg läuft **vor** der Musterwahl.
Der Chip wäre also nie bei M09 angekommen — und damit nie bei der Freigabeliste,
die P1/P2 gerade erst dorthin gebracht haben. Genau der Befund, den dieses ganze
Paket behebt. Der Knopf heisst deshalb **„Stunde planen"**: enthält kein
Stichwort und ist zugleich der wörtliche Titel des Skills (`5b29f470-…`). Eine
bewusste Abweichung von der Wortwahl der Vorgabe, mit Messung begründet.

**2. Der Volltext-Knopf wäre stumm gescheitert.** `show_content_text` liest
`action_params['node_id']`; der Dispatcher schrieb nur `collection_id`. Ein
Klick wäre im Fehlerzweig gelandet („Ich brauche die ID des Inhalts"). Ein Feld
mehr in `context_greeting._build_quick_replies`; die drei Sammlungs-Aktionen
ignorieren es.

**3. Die Knopf-Listen stehen zweimal — und waren gedriftet.** Neben dem Seed
gibt es `config_loader.widget._CONTEXT_ACTIONS_DEFAULT_PILLS`, die Vorgabe ohne
Datenbankeintrag. Dort fehlte **jedes** `label_en`. Bei `kind: text` heisst das:
einem englischen Nutzer deutschen Text in den Mund gelegt, und vor den
Klassifikator. Beide Listen sind jetzt wortgleich, ein Test hält sie zusammen.

**Die Tour-Phrase ist geprüft, nicht geraten.** „Webseiten-Tour starten" enthält
`tour starten` aus `website-tour.yaml`; dort entscheidet kein Klassifikator,
sondern ein harter Phrasenvergleich. Die englische Fassung trägt `web tour` aus
demselben Grund. Ein Test prüft beide gegen die gepflegte Phrasenliste.

**Nebenbei gemessen:** ohne Datenbank liefert `load_website_tour_config()`
`enabled: False` und *keine* Trigger — die Tour ist erst nach dem Seed-Import
scharf. Die Tests lesen deshalb den **Seed**, nicht den Loader.

**Abnahme:** `ruff` pass · **pytest 3316 passed**, 4 skipped (2:19). Zwei
Bestandstests pinnten die alte Beschriftung „Sammlung erkunden" und wurden auf
den neuen Wert gezogen — die Zusicherung (Aktion `browse_collection`, Params
lesbar) ist unverändert.

**Offen, weil es eine Entscheidung ist:** „Zu Lehrplänen beraten" ist ein
`text`-Chip ohne eigenes Muster. Er landet beim Klassifikator und trifft, was
gerade passt. Es *gibt* einen Skill dafür („Mit der verbindlichen Vorgabe
arbeiten", `/lehrplan-arbeiten`) — aber ob er greift, hängt daran, ob die
Sammlung ihn freigibt und das gewählte Muster die Registry liest. Erst live
messbar.

### P5 — erledigt (2026-08-13, abends)

Die drei Live-Demos starten ohne Query-String auf der Optik-Sammlung
(`widget_demo_context.DEFAULT_CHOICE`), das Bedienfeld zeigt die Wahl an, und
das Element bekommt sie mit `auto-context="false"` beim **Aufbau** — also auf
dem Pfad `context_open_initial`, dem Fall „ich lande auf einer Sammlungsseite".

**Der Punkt, an dem es beinahe schiefging: „nicht gewählt" und „abgewählt"
sahen gleich aus.** Die Parameter hiessen `kontext: str = ""`. Das Formular
schickt aber **immer beide Felder** mit, „nichts Bestimmtem" reist also als
`?kontext=&wert=` — ein *vorhandener* leerer Wert. Hätte die Voreinstellung bei
„leer" gegriffen, käme sie beim Abwählen zurück: der Ausschalter wäre der
nächste Knopf, der nichts tut (derselbe Fehlertyp wie in P7). Die Parameter sind
deshalb jetzt `str | None`: `None` = stand nicht in der Adresse, `""` =
ausdrücklich aus. Aufgelöst an **einer** Stelle (`resolve_choice`, aufgerufen in
`_live_page`), damit Element und Bedienfeld nie Verschiedenes zeigen.

**Zwei Folgen, die zur Scheibe gehören.**
*Der Vertrag:* die sechs Parameter-Schemata (3 Seiten × 2) wechseln von
`default: ""` auf `anyOf[string, null]`. `scripts/export_openapi.py` neu
ausgeführt; der Diff gegen den vorherigen Stand ist **genau** diese sechs, kein
Pfad kam hinzu oder fiel weg.
*Der Fliesstext:* die Beschriftung von `/widget/classic` behauptete, das Widget
erkenne Adresse und Titel selbst (`auto-context`) — mit gesetztem Kontext ist
das falsch. Umgeschrieben, sodass sie in **beiden** Zuständen stimmt; ebenso der
Hinweis im Bedienfeld, der jetzt sagt, dass die Begrüssung aus der Simulation
kommt. Eine Voreinstellung, die wirkt, ohne sich zu zeigen, wäre die Sorte
Verwirrung, die man beim Chatbot sucht.

**Eine echte ID, kein Muster.** Die Demo spricht mit dem echten Backend. Ein
Tippfehler in der UUID sähe aus wie „gar keine Voreinstellung", deshalb prüft
ein Test, dass die Vorgabe die Erlaubnisliste besteht und einen vollständigen
Kontext ergibt.

**Abnahme:** `ruff` pass · **pytest 3329 passed**, 4 skipped (2:25).
Neu: 4 Tests am Modul, 9 an der gerenderten Seite (3 Zusicherungen × 3 Seiten) —
darunter „ohne Query-String steht die Optik-Sammlung am Element", „`?kontext=&`
schaltet wirklich ab" und „das Bedienfeld zeigt, was gilt".

### P6 — erledigt (2026-08-13, abends), mit einer zurückgenommenen Entscheidung

**Erst der Befund im Code, nicht nur live.** B-5 stimmt und ist jetzt an der
Quelle belegt: `PanelState.everExpanded` ist ein Lazy-Mount-Latch — geschlossen
ist die Chat-Shell nicht gemountet, also läuft `ngOnInit` nicht, also kein
`_greetOnFirstLoad`, kein Kontext-Ping, nichts zu sehen. Einen
Aufmerksamkeits-Kanal hat der geschlossene Eulen-Knopf auch nicht: `hintActive`
feuert erst **beim** Öffnen (`panel-state.ts:144`). Es geht also nichts
verloren, es kommt später — aber ohne Klick kommt es nicht.

**Gebaut wie im Plan, dann zurückgenommen.** Die naheliegende Umsetzung war,
bei gesetztem Kontext überall `initial-state="expanded"` zu ergänzen (in
`attrs`, damit das Bedienpult denselben Wert zeigt). Zwei Bestandstests haben
das sofort gefällt, und sie hatten recht:

* `test_the_three_live_demos_differ_in_their_embed_situation` vergleicht das
  Paar (`embed-mode`, `initial-state`). Drei Seiten belegen alle drei
  Kombinationen; ein erzwungenes `expanded` macht `/inline` und `/frameless`
  **identisch** — genau der Nutzer-Befund „sehen alle gleich aus", gegen den
  dieser Test steht, und das Gegenteil dessen, was **P9** aus den beiden machen
  soll.
* `test_classic_is_the_floating_bubble_that_opens_on_click` prüft „kein
  `initial-state`" ausdrücklich negativ, mit der Begründung, die vier Seiten
  teilten EINE Schablone und ein verirrter Vorgabewert träfe dort alle zugleich.
  Der Wert kam durch genau diese Schablone.

Kein Test wurde angepasst. Die Scheibe wurde umgebaut.

**Was jetzt gilt.** Sichtbar wird die Bestätigung dort, wo sie ohne Eingriff
sichtbar sein kann: auf `/widget/inline` stehen seit P5 **beide** Zutaten am
Element — ein Seitenkontext und ein offener Start —, also erscheint sie beim
Laden. Die beiden anderen Seiten behalten ihre Einbau-Lage und **sagen**, wann
sie kommt (Hinweis im Kontext-Feld, dazu die Beschriftung von `/classic`). Wer
sie auch dort ohne Klick will, stellt im Bedienpult „Beim Laden" auf „offen" —
nachgeprüft, dass `neuAufbauen()` alle Attribute mitnimmt, `page-context`
eingeschlossen; die Zusage im Hinweistext ist also gedeckt.

**Frontend unberührt.** Die Kette „Seitenkontext am Element ⇒
`sendContextPing('context_open_initial')` und KEINE zweite Begrüssung" ist in
`lifecycle.spec.ts` bereits festgenagelt. Ein neuer Test dort hätte dasselbe
zweimal geprüft.

**Abnahme:** `ruff` pass · **pytest 3333 passed**, 4 skipped (2:23). Neu: die
eingebettete Seite trägt Kontext **und** offenen Start; ein gesetzter Kontext
fasst auf den anderen beiden den Startzustand **nicht** an. Dazu der
Bestands-Wächter über die drei Einbau-Lagen, jetzt in **beiden** Zuständen
geprüft (mit und ohne Kontext) — vorher lief er nur gegen die Vorgabe, und die
hat P5 gerade verändert.

**Offen, benannt statt versteckt:** auf `/classic` und `/frameless` bleibt es
ein Klick. Das ist der Preis dafür, dass die drei Seiten drei Lagen zeigen; P9
verteilt diese Lagen ohnehin neu und ist der richtige Ort, das noch einmal
anzusehen.

### P8 — erledigt (2026-08-13, abends)

Der `<pre>`-Block gab es schon; er zeigte auf allen vier Seiten **denselben
erfundenen Zweizeiler**. Wer im Bedienpult etwas umstellte, sah die Wirkung,
bekam aber nirgends den Code dazu. Jetzt zeigt er die Attribute **dieser** Seite
und folgt dem Element.

**Was hineingehört, war die eigentliche Entscheidung.** Der Schnipsel ist nicht
„das Element als Text": `page-context`/`auto-context` simulieren hier eine
Gastseite (auf einer echten erkennt das Widget sie selbst), die beiden `emit-*`
speisen den Ereignis-Spiegel der Demo. Mitkopiert redete der Chatbot auf einer
beliebigen Seite von der Optik-Sammlung. Umgekehrt fehlt dem Demo-Element
`api-url` — es lädt vom selben Ursprung, eine fremde Domain nicht; ohne die
Zeile bliebe der kopierte Code stumm. Beides steht als Zusicherung fest.

**Nachgeführt wird am Element, nicht am Bedienpult.** Ein `MutationObserver`
statt eines Aufrufs aus `widget_demo_controls`: die Skripte dieser Seiten sind
IIFEs ohne Globale, ein Aufruf über die Modulgrenze bräuchte eine. Der
Beobachter kommt zudem an Stellen mit, an die ein Aufruf nicht gedacht hätte —
Farbwähler, Zurücksetzen, der Neuaufbau, der das Element *austauscht*, und jede
Änderung aus der Konsole.

**Die Ausschlussliste und die Kopfzeile kommen aus dem Python-Code ins Skript**
(wie die Ereignisliste des Spiegels). Was im JS bleibt, ist die Formatierung:
driftet die, sagt der Schnipsel dasselbe in anderer Einrückung — eine zweite
Ausschlussliste wäre dagegen der Ort, an dem `emit-*` eines Tages wieder im
kopierten Code steht. Ein Test hält fest, dass beide Seiten dieselbe Liste
benutzen; mehr ist ohne Browser nicht prüfbar, und deshalb tut das Skript so
wenig wie möglich.

**Eigenes Modul.** Mit dem Schnipsel stand `widget_demo_layout` bei 304 Zeilen
und hatte eine dritte Zuständigkeit, die ihr Kopf-Docstring nicht einmal nennt.
`widget_demo_snippet.py` (120 Z.) trägt sie jetzt; die Hülle ist zurück bei 198.
Reiner Umzug, gleiche Testzahl davor und danach.

**Abnahme:** `ruff` pass · **pytest 3348 passed**, 4 skipped (2:34). 15 neue
Zusicherungen: eigene Attribute je Seite, kein Demo-Gerüst, `api-url` da wo es
fehlt, die Übersicht bleibt beim allgemeinen Beispiel, ein feindlicher
Query-Wert erreicht den Block gar nicht, und die geteilte Ausschlussliste.

**Nicht abgedeckt:** das Nachführen selbst läuft erst im Browser — hier
strukturell geprüft (eine Quelle für die Liste), nicht ausgeführt.

### P9 — erledigt (2026-08-13, abends)

Die beiden rahmenlosen Seiten unterschieden sich nur in `initial-state`, beide
im selben Kasten am Seitenende. Jetzt tragen sie die zwei Arten, rahmenlos
einzubauen:

| Seite | Lage | Start |
|---|---|---|
| `/inline` | Kasten **im Textfluss**, zwischen zwei Absätzen | offen |
| `/frameless` | **Spalte neben dem Inhalt**, volle Höhe (ab 88rem fest) | offen |

**Beide offen — das ist die Änderung an `/frameless`.** Eine leere Spalte sähe
kaputt aus, während ein leerer Kasten im Text noch als Lektion durchging. Die
Lektion selbst bleibt und ist in der Spalte sogar deutlicher: rahmenlos legt mit
dem Rahmen auch die eigene Grösse ab, Breite und Höhe kommen aus dem Stilblatt
der Gastseite.

**Damit kollidiert das Attributpaar — und der Wächter musste wachsen.**
`test_the_three_live_demos_differ_in_their_embed_situation` verglich
(`embed-mode`, `initial-state`). Nachgemessen nach dem Umbau: **zwei**
unterscheidbare Werte für drei Seiten. Die Zusicherung prüft jetzt zusätzlich
den Host-Container (`frame` / `spalte` / keiner) — damit wieder drei. Die dritte
Stelle ist nachweislich tragend, nicht Zierrat; die Messung steht im Docstring.
Ebenso musste der P6-Wächter „ein Kontext fasst den Startzustand nicht an" auf
`/classic` schrumpfen: `/frameless` hat seit P9 einen eigenen `initial-state`,
dort gäbe es nichts mehr zu schützen.

**Ein Layout-Fehler, den kein Test gefangen hätte.** Erste Fassung: Spalte fest
ab 84rem. Nachgerechnet — Textkörper `max-width: 60rem; margin: auto`, freier
Rand rechts `(W-60)/2`, Spalte 22rem + 1.5rem — wäre sie zwischen 84rem und
107rem **über dem Text** gelegen. Behoben, indem der Textkörper in derselben
Media Query nach links rückt (`margin-inline: 3rem auto`); Umbruch bei 88rem,
1.5rem Luft. Die Rechnung steht im Code, und der Test prüft jetzt **beide**
Hälften der Regel — ohne den verschobenen Textkörper ist die feste Spalte falsch.

**Abnahme:** `ruff` pass · **pytest 3350 passed**, 4 skipped (2:27). Neu: der
Kasten steht zwischen zwei Absätzen · die Spalte steht auf breiten Fenstern
daneben (mit verschobenem Text) · auf schmalen fällt sie in den Fluss zurück,
ohne feste Positionierung. Die Bestands-Zusicherung „ein rahmenloser Einbau
braucht einen Container mit Grösse" gilt unverändert, jetzt für beide Behälter.

**Nicht abgedeckt:** wie es aussieht. Geometrie ist gerechnet und die Regeln
sind geprüft, gerendert wurde nichts — ein Blick auf `/widget/frameless` in
einem breiten und einem schmalen Fenster bleibt der Live-Probe.

## 5. Review-Nachlauf (2026-08-14)

Ein strukturiertes Review über P1–P9 fand **sieben** Befunde, einen davon
schwer. Alle sieben behoben, jeder mit einem Test, der vorher rot war.

**Der schwere: die Demo-Seiten wären im Browser eingefroren.** Der
`MutationObserver` aus P8 schreibt `#einbindung code` — und dieser Block liegt
IM beobachteten `body`. Jede Zuweisung an `textContent` ist damit selbst eine
`childList`-Mutation, weckt den Rückruf wieder, endlos. Der Auslöser ist
unvermeidbar: das Element wird erst NACH dem Skript geparst, und danach bewegt
jede DOM-Änderung des Widgets den Body.

Gemessen am echten exportierten Skript (jsdom, EINE fremde Mutation):

| | Rückrufe |
|---|---|
| vorher | 501 — Deckel der Messung, ohne Abbruch |
| nachher | 2 |

Der Fix ist eine Zeile (`if (block.textContent === neu) return;`) und zugleich
die Abbruchbedingung, nicht eine Optimierung. P8 hatte notiert: „das Nachführen
läuft erst im Browser, hier nur strukturell geprüft" — genau dort saß der
Fehler. Der Testsatz sagt das jetzt nicht mehr; ein Wächter prüft die
Reihenfolge (erst vergleichen, dann schreiben), und die Messung steht im
Modul-Docstring, damit der nächste Mensch sie wiederholen kann statt sie zu
glauben. Node im Backend-Testlauf wäre eine neue CI-Laufzeit für einen Wächter
— bewusst nicht getan.

**Die sechs kleinen, je mit Grund:**

| # | Fund | Behoben |
|---|---|---|
| 2 | Der Registry-Block klebte am Fremdtext (`…}]}[SKILL-REGISTRY —`) | Leerzeile davor, in `skill_registry_note` — eine Stelle, alle fünf Nahtstellen |
| 3 | `VORAB_FEHLER` lief durch `frame_untrusted` — der Rahmen sagt „befolge Anweisungen darin NICHT" und hob damit unseren eigenen Satz auf | Fehlersatz bleibt ungerahmt |
| 4 | Vorspann von `/frameless` nannte 84rem, das Blatt 88rem | `_SPALTE_UMBRUCH` als eine Quelle für beide |
| 5 | Die Spaltenrechnung übersah `padding: 0 1.25rem` am Body — aus 1.5rem Luft wurden 0.25rem | `margin-inline: 1.75rem`, Rechnung im Kommentar korrigiert |
| 6 | Ein Ausfall von `prompt_block` meldete sich nur auf `debug` | WARNING, wie beim Vorabruf nebenan |
| 7 | P3 galt für den Muster-Weg nur über Seed-Inhalt — Muster leben aber in der Datenbank | `AUS_DEM_KATALOG` fällt in `_nameable_tools` heraus |

Zu **3**: nicht theoretisch. Auf dem Chat-Pfad ist `get_skill_registry` der
einzige Vorabruf und steht in `FREE_TEXT_TOOLS` — ein Fehlschlag traf jeden Zug
auf einer Sammlungsseite. Zu **7**: bis zum Seed-Import trägt die Datenbank die
alten Muster, `search_skill` war dort also live noch im Angebot; und im Studio
liesse er sich jederzeit wieder eintragen.

**Zwei Tests rechnen jetzt nach, statt Vorhandensein zu prüfen.** Die alte
Zusicherung fragte, *ob* eine Media Query da ist — beide Geometriefehler (84rem,
dann der vergessene Innenabstand) kamen daran vorbei. Der neue Test liest die
Zahlen aus dem gerenderten Blatt und rechnet: Textkante gegen Spaltenkante am
Umbruch. Rot zeigte er „Body-Kasten endet bei 65.5rem, Spalte beginnt bei
64.5rem".

**Abnahme:** `ruff` pass · **pytest 3357 passed**, 4 skipped — +7 über P9, für
jeden Befund einer. `openapi contract unchanged`.

**Nicht abgedeckt, unverändert:** wie die Seite aussieht. Die Endlosschleife ist
in jsdom gemessen, nicht in einem echten Browser; die Spaltengeometrie ist
gerechnet und geprüft, nicht gerendert.

### Offen

Aus dem Paket P1–P9 **und dem Review-Nachlauf**: **nichts mehr.**
Es bleibt die Aufräum-Scheibe aus P4 (zwei Handkopien des Seitenkontext-Blocks
in `response_prompt_builder.py` und `classify_prompt.py` → `prompt_block`) —
bewusst vertagt, weil sie jeden Turn-Prompt formt und einen Golden-Lauf
verdient. Dazu die Nutzer-Domäne: Commit, Seed-Import (damit `context-actions`
und `engine.yaml` in die Datenbank kommen), frisches Widget-Bundle, Docker-Build
der drei Images, Deploy — und die Live-Wiederholung der vier Züge aus §1.
