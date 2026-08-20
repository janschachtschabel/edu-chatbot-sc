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
