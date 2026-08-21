# Erschließungs-Kontext im Prüftisch (editorial-desk)

Live-Befund 2026-08-20 (Staging-Repo, `/components/editorial-desk?mode=audit&nodeId=…`):
Beim Erschließen eines Einzelinhalts triggert weder Begrüßung noch Aktion, und die
LLM-Antwort kennt den Inhalt nicht, obwohl der Rahmen das komplette
Metadaten-Formular als `page_text` mitliefert.

## Ursachen (aus dem Web-Protokoll + Code verifiziert)

1. **Z2-Nebenwirkung:** `page_context.prompt_block` = `render_for_prompt(...) or
   render_raw_for_prompt(...)`. Seit Z2 ist der unaufgelöste Block nie mehr leer
   (Platzhalter-Titel + Hinweis) → der `page_text`-Rohblock wird auf unauflösbaren
   Objekt-Seiten NIE erreicht. Die Z2-Note bittet sogar um ein Transkript, das im
   Request längst steht. Gleiches Muster handkopiert in
   `response_prompt_builder` und `classify_prompt` — Fix gehört IN
   `render_for_prompt`, dann heilt er alle drei.
2. **Kein Prüftisch-Begriff:** Die URL fällt in den generischen `?node`-Zweig →
   `page_kind=content`. `content` begrüßt nur mit aufgelöstem Titel
   (`_greeting_fields` → None bei `unresolved`), und anonym ist ein
   Prüftisch-Knoten grundsätzlich 403 → Gruß und Pills bleiben stumm — korrekt
   fürs Gate, falsch für die Situation.

## Pakete

### EK1 — `page_text` überlebt die Auflösungssperre (Root-Cause)
`services/page_context.py::render_for_prompt`: bei `meta.unresolved` und
vorhandenem `page_context.page_text` (a) Sichtbaren Seitentext als eigenen
Abschnitt anhängen (`_trim_text(…, 3000)` — Budget wie der gespeicherte Volltext: auf dem
Prüftisch liegen ~1800 Zeichen Listen-Harvest vor dem Formular, das
1500er-Rohblock-Budget schnitte genau das Wertvolle ab),
(b) Z2-Note zeigt dann auf diesen Text statt ein Transkript zu erbitten.
Aufgelöste Seiten unverändert (dort gibt es `text_content` aus dem Bestand).

### EK2 — Seitenart `editorial` (Prüftisch/Erschließung)
* `graph/nodes/page_context_enrich.py`: `_decide_editorial_kind` — Pfad
  `/components/editorial-desk` + `node_id` ⇒ `page_kind="editorial"`. Läuft vor
  `_decide_host_kind`; darf die positive `content`-Einstufung übersteuern, weil
  die URL die SITUATION eindeutig benennt (schärferes Indiz als der Objekttyp).
  Serverseitig, damit jeder Einbett-Weg (Repo-Rahmen, Chrome-Plugin, eigenes
  Widget) den Fix ohne Host-Änderung bekommt — Präzedenz: `home`/`external`.
* `services/config_loader/widget.py`: `_CONTEXT_ACTIONS_PAGE_KINDS` +
  Vorgaben (Gruß + 3 Text-Pills). `graph/nodes/context_greeting.py`:
  `_GREETABLE_KINDS` + `_greeting_fields`-Zweig — Gegenstand ist die Situation,
  NICHT der aufgelöste Titel (anonym nie lesbar); `{title}` darf im Gruß deshalb
  nicht vorkommen. `services/page_context.py`: Überschrift/Label + eine
  Erschließungs-Regelzeile; `includeTextContent` auch für `editorial`.
* `seeds/01-base/context-actions.yaml`: `greetings`/`greetings_en`/`pills`
  für `editorial` (Hinweise zum Inhalt · passende Sammlung suchen ·
  Kuratierungshilfe). Text-Pill-Beschriftung IST die gesendete Nachricht.

### EK3 — Seitentext auch ohne ID (Review-Befund B, Nachtrag)

Derselbe Griff wie EK1, aber für Seiten **ohne** auflösbare Kennung. Der
signaturlose Rückfall des Resolvers (`page_context.py`, „nur `document_title`")
baut ein unaufgelöstes Meta MIT Titel — der Block ist damit nie leer, und der
`or`-Rückfall auf `render_raw_for_prompt` griff auch dort nicht mehr. Betroffen
ist fast jede fremde Seite: das Plugin sendet den Tab-Titel immer mit, der
geerntete `page_text` lag ungenutzt im Request.

`render_for_prompt` trägt jetzt **zwei orthogonale Regeln** statt einer
verschachtelten:

1. Rechte-Note nur bei `unresolved` **und** vorhandener ID — ohne ID wäre sie
   sachlich falsch (keine fehlenden Leserechte, die Seite ist kein WLO-Objekt).
2. Abschnitt „Sichtbarer Text der Seite" bei `unresolved`, **sobald** ein
   `page_text` da ist — unabhängig von der ID, gleiches 3000er-Budget.

Warum das mehr ist als Bequemlichkeit: M20 könnte die Seite zwar selbst über
`get_url_text` holen, aber das kostet einen Rundlauf und scheitert genau dort,
wo es zählt — Login-/Cookie-Wände, JS-gerenderte Seiten und Schul-Intranets,
die der SSRF-Wächter absichtlich nie erreicht. Dort ist der Browser-Harvest die
einzige Textquelle.

### EK4 — Textfelder normalisieren (Review-Befund A, Nachtrag)

`environment.page_context` ist Freiform (`dict[str, Any]`), gelesen wurde es aber
überall als `(wert or "").strip()` — das wirft bei jedem **truthy** Nicht-String.
Falsy Werte (`0`, `""`, `None`) waren nie betroffen; deshalb fiel es nie auf.
Realistischer Auslöser: ein Gastgeber mit numerischem TypeScript-Enum
(`enum PageKind { Content, Collection }` → Inhaltsseite `0` läuft, Sammlungsseite
`1` bricht) oder mit Zahl-IDs aus der eigenen Datenbank. Folge war kein HTTP 500
— das Sicherheitsnetz in `api/chat.py` fängt es —, sondern eine Fehler-Blase bei
**jedem** Zug dieser Einbettung plus ein Stacktrace je Zug im Log.

Neu: `_normalize_strings` im Enrich-Knoten, dem ersten Leser dieser Felder im
Zug. `str()` statt Verwerfen, weil es den häufigsten Fall gleich mitheilt
(`collection_id: 4711` → `"4711"` ist eine brauchbare Kennung); `None` bleibt
`None`, damit kein Titel „None" im Prompt landet. Nicht-Textfelder
(`search_filters`, `widget`) bleiben unberührt.

### EK5 — Der Agent-Weg liest den angereicherten Kontext (Review-Befund, Nachtrag)

`ctx.env = req.environment.model_dump()` **kopiert** das verschachtelte
`page_context`-Dict (gemessen: `dumped["page_context"] is model.page_context`
→ `False`). Der Enrich-Knoten reichert die Kopie an; wer das Anfrage-Original
liest, sieht nichts davon. Der Muster-Weg liest `ctx.env` (`respond.py:94`), der
Klassifikator ebenfalls (`assess.py:101`) — der **Agent-/Hybrid-Weg** las
`ctx.req.environment.page_context` und damit weder `editorial` noch
`home`/`external` noch die EK4-Normalisierung. Für den Prüftisch hieß das:
Begrüßung und Pills kamen (der Gruß-Knoten liest `ctx.env`), die
Erschließungs-Regel im Prompt aber nicht — im live genutzten Modus.

Neu: `seite = (ctx.env or {}).get("page_context") or ctx.req.environment.page_context or {}`
in `respond_agent`. Der Rückfall hält Direktaufrufe ohne `setup` am Leben.

Die Lücke blieb unentdeckt, weil der Agent-Test-Helper `Environment(...)` direkt
baute und `ctx.env` leer ließ — eine Umgebung, die es im Betrieb nie gibt. Der
Helper bildet jetzt den `setup`-Knoten nach.

### EK7 — Nachgereichter Kontext pingt als Erstlade-Fall (Live-Befund 2026-08-21)

Auf dem Prüftisch blieb trotz EK1–EK5 die Standard-Begrüßung stehen. Hergang:
Der Repo-Rahmen reicht den Kontext erst NACH dem Shell-Mount per
`replaceContext` herein. (1) Beim Mount ist `parsedPageContext` leer → kein
Erstlade-Ping, die statische Begrüßung rendert. (2) `replaceContext` →
`onSpaContextChange` pingt — mit Default-Event `context_open`. (3) Backend-Gate 1
wertet `context_open` bei leerer History als verirrten Ping → bewusste Stille.
Der Streu-Ping-Schutz fraß den absichtlichen Laufzeit-Kontext.

Fix (Widget): `_maybeSendContextPing` wählt das Event nach der UNTERHALTUNG —
ohne Nutzer-Nachricht `context_open_initial`, sonst `context_open`. Neuer
`LifecycleContext`-Getter `hasUserMessages` (Shell: `sender === 'user'` im
Store). Deckt auch den Resume mit leergeräumter History ab.

### EK8 — `title` als Gastgeber-Alias für `document_title`

`document_title` setzt nur das Widget aus der eigenen Erkennung; Rahmen senden
den Tab-Titel naheliegend als `title`. Ohne Alias fiel er durch, und Gruß wie
Prompt zitierten den Z2-Platzhalter „Seite mit nicht auflösbarem Inhalt" als
Seitennamen. Neu: `_host_title()` (document_title gewinnt) an beiden
Lesestellen des Resolvers; `title` in `_STRING_FIELDS` der EK4-Härtung.

### EK9 — Prüftisch: die Maske ist nicht der Inhalt

Live-Befund 2026-08-21 (Staging, Knoten `56cea807…`): der Resolver NUTZT die
`node_id` (`get_node_details` mit `includeTextContent`), aber der frisch
eingereichte Knoten ist unveröffentlicht — anonym kommt ein LEERES Ergebnis
(live geprüft: `{"total":0}`), kein Fehler. Der Z2-Rückfall setzt dann den
Host-Titel („Redaktion - edu-sharing") als `Titel:`, und die Wo-bin-ich-Regel
weist das Modell an, ihn zu zitieren — der Bot erklärt die
Redaktionsoberfläche zum Inhalt und generiert Schnellantworten zu edu-sharing
statt zum Material. Zweiter Anteil: `page_text` ist auf dem Prüftisch die
Erschließungsmaske — innerText trägt Feldnamen und Hilfetexte, eingetragene
FORMULARWERTE (z. B. die Quell-URL des Materials) erscheinen darin nie; die
EK3-Note sagt aber „arbeite damit, statt nach dem Inhalt zu fragen".

Fix (nur `render_for_prompt`, Fall `editorial` + `unresolved`):
1. Titel-Zeile ehrlich: „Titel des Inhalts: noch unbekannt …" statt Host-Titel.
2. Rechte-Note-Variante: Maske erklärt (Werte fehlen im sichtbaren Text) +
   Arbeitsweg — Quell-URL erfragen bzw. aus der Nachricht nehmen → `get_url_text`.
3. Wo-bin-ich-Regel zitiert den Host-Titel nicht mehr.
4. Überschrift der Textsektion benennt die Maske.
5. Editorial-Regelzeile nennt die Inhaltsquelle je nach Auflösungslage.
6. Generik-Regeln (Seitentitel-als-Thema, Titel-Suche) laufen im Maskenfall
   über den Kernbegriff des Materials statt über den Oberflächen-Titel.

Resolver unangetastet: der Abruf über die `node_id` passiert bereits und wird
mit Leserechten (Service-Konto/Ticket) sofort wirksam; anonym ist ein
unveröffentlichter Knoten strukturell unsichtbar — das kann kein Backend-Code
ändern. Der Weg zum Inhalt ist deshalb die Quell-URL (`get_url_text` ist
SSRF-geschützt vorhanden).

### EK10 — Seitentext-Budget: 20 000 für die Antwort-Prompts

Nutzer-Entscheid 2026-08-21: Der Transport ist seit L1 ungedeckelt, aber
``render_for_prompt`` schnitt den Gastgeber-Seitentext bei 3000 Zeichen ab —
hinter Login-Wänden, in Intranets und auf dem Prüftisch ist dieser Text die
einzige Inhaltsquelle, der Rest wurde still verworfen. Neu:
``SEITENTEXT_PROMPT_BUDGET = 20 000`` (deckungsgleich mit dem
``get_wlo_content_text``-Deckel und dem Agent-Endpunkt-Richtwert der
Plugin-Doku) als Vorgabe für Muster-Antwort und Agent; der Klassifikator
übergibt ``page_text_budget=3000`` (wählt nur ein Muster, Volltext wäre dort
Kostenlast pro Zug). Die vier Beispiel-Snippets der Plugin-Doku
(``slice(0, 3000)``) ziehen auf 20 000 nach — sonst bliebe das Server-Budget
wirkungslos, weil die Gastgeber clientseitig weiter kappen.

**EK10b (noch am selben Tag):** Nutzer-Entscheid „alle auf 200 000" — die
Vorgabe heißt jetzt ``TEXT_PROMPT_BUDGET = 200 000`` (Skala des
``result_schema``-Deckels) und gilt für ALLE Textabschnitte des Blocks:
Seitentext, gespeicherter Volltext (vorher 3000), Kompendium (vorher 4000)
und den Heuristik-Rohblock (vorher 1500, jetzt parametrisiert). Zusätzlich
zieht ``AgentRequest.instruction`` von 20 000 auf 200 000 nach
(Vertrags-Änderung, OpenAPI neu erzeugt) — der alte Deckel war laut
Plugin-Doku der häufigste 422-Grund. Bewusste Ausnahme bleibt der
Klassifikator: 3000 je Textabschnitt (beide Pfade, Meta und Roh), sonst
zahlte jeder Zug den Volltext im teuersten Prompt.

## Nicht-Ziele
Kein Frontend-/Detektor-Umbau (der Rahmen ist fremder Code; die Erkennung ist
serverseitig vollständig). Kein OpenAPI-Delta (`page_context` ist Freiform).
MCP-Server unberührt.

## Log
| Paket | Stand |
|---|---|
| EK1 | ✅ 2026-08-20 — render_for_prompt hängt bei `unresolved` den `page_text` an (3000er-Budget), Note zeigt auf ihn statt Transkript zu erbitten; 4 Pins in test_page_context.py |
| EK2 | ✅ 2026-08-20 — `_decide_editorial_kind` (enrich, nur Pfad + node_id), Art `editorial` in Loader+Seed+Gruß+Ping-Liste, 3 Text-Pills, Überschrift/Regelzeile/Volltext-Flag; 10 neue Tests über 4 Dateien, Suite 4109/ui 830/studio 986 |
| EK3 | ✅ 2026-08-20 — zwei orthogonale Regeln in `render_for_prompt`; fremde Seiten nutzen den `page_text` jetzt, Rechte-Note bleibt dem ID-Fall vorbehalten; 2 Pins, Suite 4112 |
| EK4 | ✅ 2026-08-20 — `_normalize_strings` (12 Textfelder) im Enrich-Knoten; Zahl-Enums und Zahl-IDs brechen den Zug nicht mehr, `None` bleibt `None`; 4 Pins, Suite 4116 |
| EK5 | ✅ 2026-08-20 — `respond_agent` liest `ctx.env`; serverseitige Seitenart + Normalisierung erreichen den Agent-Prompt. Test-Helper bildet `setup` nach (verdeckte die Lücke); 1 Pin, Suite 4117 |
| EK7 | ✅ 2026-08-21 — Ping-Event nach Unterhaltungszustand (`hasUserMessages`); Prüftisch-Seitenleiste bekommt Gruß + Pills trotz nachgereichtem Kontext; 2 Pins, ui 832 |
| EK8 | ✅ 2026-08-21 — `_host_title` mit `title`-Alias an beiden Resolver-Rückfällen + `_STRING_FIELDS`; 3 Pins, Suite 4120 |
| EK7b | ✅ 2026-08-21 — CI-Nachlauf: 3 E2E-Pins auf den neuen Ping-Vertrag umgezogen (Begründung im Spec, Muster der Datei), Harness-`history`-Option + neuer Wiederkehrer-Test pinnt `context_open` bei echter History samt Restore-vor-Ping-Reihenfolge; E2E 49 passed |
| EK9 | ✅ 2026-08-21 — Prüftisch-Prompt ehrlich: Host-Titel nie als Inhaltstitel (Titel-Zeile, Wo-bin-ich-Regel, Schluss-Hinweis, 2 Generik-Regeln), Rechte-Note erklärt die Maske (Formularwerte fehlen im innerText) + Quell-URL-Weg via get_url_text, Sektions-Überschrift benennt die Maske; Resolver unberührt (nutzt die node_id bereits — anonym leer, live belegt). 3 Pins + 2 Zusatz-Assertions, Suite 4123 |
| EK10 | ✅ 2026-08-21 — `SEITENTEXT_PROMPT_BUDGET=20000` als Vorgabe in `render_for_prompt` (`page_text_budget`-Parameter), Klassifikator bleibt bei 3000; 4 Doku-Snippets auf 20 000 nachgezogen; Budget-Pin um-gepinnt + Parameter-Test + Klassifikator-Wächter |
| EK10b | ✅ 2026-08-21 — alle Textabschnitts-Budgets auf `TEXT_PROMPT_BUDGET=200000` (Seitentext/Volltext/Kompendium/Rohblock), `AgentRequest.instruction` 20 000→200 000 (OpenAPI neu erzeugt), Doku-Snippets + Agent-Grenze nachgezogen; Klassifikator-Ausnahme 3000 beidpfadig gepinnt; dazu Review-Befunde: EK9-Spec Punkt 6 + NIT-Assertion `_quelle` |
| EK9c | ✅ 2026-08-21 — Rechte-Note: eine im sichtbaren Text stehende Quell-URL (vom Rahmen angehängte Feldwerte) DIREKT mit get_url_text nutzen statt nachzufragen; Prüftisch-Einbindungsbeispiel (Feldwerte an page_text anhängen) in der Plugin-Doku; 1 Pin |
