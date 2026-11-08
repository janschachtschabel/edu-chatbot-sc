# Auftrag an das MCP-Team: Volltexte und Metadaten für hochgeladene Inhalte

Stand 2026-11-07 · vom Chatbot-Team (BOERDi) · Grundlage: der Anwendungsfall „Strukturdokument + Inhalte ohne
Struktur“ (Ablaufskizze des Nutzers) und der Code beider Seiten (MCP-Klon `wlo-mcp-server-sc`, Stand S1–S7).

## 1. Ausgangslage

Der Ablauf, den der Chatbot steuert (Nutzer-Entscheid 2026-11-07: der **Chatbot** steuert auch die Kestra-Flows
über die B-API):

1. **Upload:** Die Person lädt im Chatbot Ordner und Dateien hoch (Modul `ui_upload`). Sie markiert, welche Datei ein
   **Strukturdokument** ist und welche **Inhalte** sind. Der Chatbot legt die Dateien über den MCP als Knoten im
   persönlichen Bereich an (`wlo_prepare_file_batch` → `wlo_store_batch_file` → `wlo_store_batch_manifest`) und
   vermerkt Struktur und Knoten im Vorgang.
2. **Volltext:** Aus jeder Datei (oder Webseite) entsteht ein Markdown-Volltext, der **an den Knoten gehängt**
   wird. Das macht **Flow 1 in Kestra** — Umwandeln und Anhängen geschehen dort, nicht im Chatbot (Nutzer
   2026-11-07). Der Chatbot startet den Flow und fragt ihn ab.
3. **Metadaten:** Auf den Volltexten werden Metadaten erzeugt und an die Knoten geschrieben.
4. **Struktur:** Themenbaum erzeugen und prüfen, Sammlungsstruktur und Kompendientexte anlegen, Inhalte zuordnen.
   Dafür gibt es schon `wlo_create_collection_tree`, `wlo_update_compendium` und `wlo_add_to_collections`.

Was die Lage bestimmt:

- **Die B-API erlaubt Flows derzeit nur das Lesen im Repository** (`edu-sharing-repo`); Schreiben (`-write`,
  `-content`) ist nicht nutzbar. Geschrieben wird deshalb **über den MCP mit den Rechten der angemeldeten Person**,
  wie bei allen Kurations-Werkzeugen.
- **Der MCP kann die Bytes privater Dateien nicht lesen** — euer eigener Befund in `services/write/batch-manifest.ts`
  (`eduservlet/download` 403, `GET …/content` 405, `…/textContent` leer). Den Volltext liefert deshalb der Aufrufer:
  der Chatbot hat die Bytes beim Upload in der Hand, ein Kestra-Flow gibt ihn als Ausgabe zurück.
- **Beim Ablauf entstehen schnell 50–200 Knoten.** Ein „Ja“ je Knoten ist nicht zumutbar; wie bei den Plänen (M5)
  braucht es **eine** Bestätigung für eine Liste.

## 2. Was fehlt

### W1 — Volltext an einen bestehenden Knoten hängen (`wlo_attach_fulltext`)

**Einordnung:** Im Ablauf hängt **Kestra** die Volltexte an (Flow 1, über die Schreibwege der B-API). Das Werkzeug im
MCP ist trotzdem gewollt — für andere Clients (KI-Hosts, Plugins), für einzelne Nachträge und als Weg, solange die
Schreibwege der B-API nicht nutzbar sind. Das **Lesen** des angehängten Volltexts (unten) braucht der Ablauf auf
jeden Fall: Themenbaum und Metadaten bauen darauf auf.

Heute ersetzt `wlo_update_content` mit Text oder Datei den **Inhalt** des Knotens — bei einer hochgeladenen Datei
wäre das Original weg. Gebraucht wird ein Weg, den Volltext **neben** die Datei zu legen.

- **Eingabe:** `nodeId*`, `markdown*`, `source` (`binary` · `website` · `manual`), optional `sourceUrl`,
  `language`, `replace` (vorhandenen Volltext ersetzen, Vorgabe `false`), `confirmToken`.
- **Zweistufig wie alle Kurations-Werkzeuge:** Die Vorschau nennt den Knoten (Titel), die Länge und ob ein
  vorhandener Volltext ersetzt würde. Die Antwort trägt `structuredContent.confirm`.
- **Ablage — bitte messen und entscheiden (F1):**
  - Unser Vorschlag ist ein **Kindobjekt** (`ccm:childio`, „Serienobjekt“) `volltext.md` (`text/markdown`) am
    Knoten. Die Datei bleibt unberührt, Rechte und Löschen hängen am Knoten.
  - Die Alternative wäre eine Text-Eigenschaft. `cm:description` ist schon vom Stapel-Manifest belegt,
    `cclom:general_description` ist die sichtbare Beschreibung — beides scheidet aus.
- **Lesen gehört dazu:** `get_wlo_content_text` und `get_nodes_details` mit `includeTextContent` sollen den
  angehängten Volltext liefern, wenn `textContent` leer ist. Das ist bei privaten Dateien immer der Fall, und sonst
  sieht kein Folgeschritt (Metadaten, Themenbaum) den Text.
- **Fehler** nach dem gemeinsamen Vertrag (§3): `not_found`, `forbidden`, `exists` (es gibt schon einen Volltext und
  `replace` ist `false`), `nothing_to_change` (gleicher Inhalt, per Prüfsumme), `too_large`, nach der Einlösung
  `outcomeOpen`.
- **Grenzen:** eine Größe je Volltext (Vorschlag 2 MB Markdown, F2).

### W2 — Volltexte für viele Knoten unter einer Bestätigung (`wlo_attach_fulltexts`, Plan)

- **Eingabe:** `items*` = [{`nodeId`, `markdown`, `source`, `sourceUrl?`}], bis 200 Einträge und insgesamt
  höchstens N MB (F2). Dazu `replace`, `confirmToken` und `continuationToken`.
- **Semantik wie `wlo_add_to_collections`:** eine Vorschau für alle mit Zahlen (neu, ersetzt, unverändert,
  abgelehnt), Ausführung in Abschnitten, `complete`, `progress {done, total}` und je Eintrag `status`/`code`.
- **Kein Replay über `confirmToken`:** Fortsetzen geht über `continuationToken` (wie M5).
- **Platz in `tools/call`:** Ein Aufruf trägt viel Text. Bitte sagen, ob der Rumpf dafür groß genug ist, oder einen
  Upload-Weg wie `/api/uploads` vorsehen (F2).

### W3 — Metadaten für viele Knoten unter einer Bestätigung (`wlo_update_contents`, Plan)

- **Eingabe:** `items*` = [{`nodeId`, Felder wie bei `wlo_update_content`}], bis 200 Einträge. Dazu `mode`
  (`write` · `suggest`), `confirmToken` und `continuationToken`.
- **`mode: suggest`** schreibt statt der Werte Vorschläge (wie `wlo_suggest_metadata`), zur redaktionellen
  Entscheidung. Welcher Weg Vorgabe wird, entscheidet die Redaktion (F5).
- **Vorschau je Knoten** mit der Änderungsmenge, wie heute bei `wlo_update_content`. In der Antwort steht eine
  Zusammenfassung, die Einzelheiten stehen im strukturierten Teil.
- **Ausführung wie W2:** Abschnitte, `progress`, je Eintrag `status`/`code`/`outcomeOpen`; Eigenschaften außerhalb
  der Feldfläche werden mit Code abgelehnt.

### W4 — Rolle im Stapel: Strukturdokument oder Inhalt

- **Eingabe:** `wlo_prepare_file_batch` nimmt je Eintrag `role` (`structure` · `content`, Vorgabe `content`).
- **Ablage:** Die Rolle steht im Manifest (`vorgang.json`, Format `wlo.ablage-vorgang@1` → `@2`) und in der
  Zusammenfassung in `cm:description`.
- **Lesen:** `wlo_list_my_batches` gibt die Rolle je Eintrag zurück.
- **Warum:** Heute weiß nur der Vorgang im Chatbot, welcher Knoten das Strukturdokument ist. Nach einem neuen
  Gespräch, auf einem anderen Gerät oder in einem Kestra-Flow ginge das verloren.
- **Am Knoten selbst (F4):** Soll die Rolle zusätzlich als Eigenschaft am Datensatz stehen, und in welcher, die das
  Inhaltsmodell kennt? Ohne eure Messung schlagen wir keine vor.

## 3. Gemeinsamer Vertrag (wie bisher)

- Verbindlich ist der strukturierte Teil. `confirm` gibt es in jeder Vorschau, `error.code` an jedem Fehler und
  `outcomeOpen` an jedem Fehler nach der Einlösung (Stand `9093a5d`).
- Für W1 gilt das Replay aus S3. Für W2 und W3 gilt die Plan-Semantik (`continuationToken`, Frist, `plan_*`) und
  `too_many_plans`.
- Das Budget zählt `tools/call`; ein Plan-Abschnitt ist ein Aufruf.
- Geschrieben wird nur mit persönlicher Anmeldung und den Rechten der Person am Knoten. Ein fremder Knoten in einer
  Sammlung bekommt `forbidden`, ohne Umweg über das Dienstkonto.

## 4. Reihenfolge

1. **W4**: klein, und es macht den Ablauf von Anfang an tragfähig.
2. **Lesen des angehängten Volltexts** (Teil von W1): Folgeschritte brauchen ihn, egal wer ihn anhängt.
3. **W3**: ohne Plan wären es 200 Bestätigungen.
4. **W1 (Schreiben) und W2**: sinnvoll, aber nicht im kritischen Pfad — im Ablauf hängt Kestra die Volltexte an.

Der Chatbot baut parallel: den Ablauf „Upload → Volltext (Kestra) → Metadaten → Struktur“, Start und Abfrage der
Flows, die Übergabe der angelegten Knoten (`structure_node_ids`, `content_node_ids`) an Flow 1.

## 5. Fragen an euch

| # | Frage |
|---|---|
| F1 | Wohin mit dem Volltext: Kindobjekt (`ccm:childio`) oder eine Eigenschaft? Bitte gegen das Staging-Repository messen. Kann die Person ein Kindobjekt an ihrem eigenen Knoten anlegen, und ist es mit Basic-Anmeldung wieder lesbar? |
| F2 | Größen: höchstens wie viel Markdown je Knoten und je Aufruf? Reicht der Rumpf von `tools/call`, oder braucht W2 einen Upload-Weg? |
| F3 | Findet die edu-sharing-Suche den angehängten Volltext (Volltextsuche), oder ist er nur für Folgeschritte da? |
| F4 | Rolle am Knoten: welche Eigenschaft, falls überhaupt? |
| F5 | Metadaten: direkt schreiben oder als Vorschlag? Darf `mode` beides können, oder legt der Server einen Weg fest? |
| F6 | Knoten in Sammlungen: Gilt W1/W3 auf eine Verknüpfung umgelenkt auf das Original, wie bei `wlo_update_content`? |

## 6. Gemessen am Staging (2026-11-07, eigener Testknoten, danach gelöscht)

| Prüfung | Ergebnis |
|---|---|
| Material im Eingang der Person anlegen (Basic) | 200. Ordner im Home anlegen: 403 — erwartet, normale Nutzer legen keine Ordner außerhalb des Workspaces an; Knoten und Sammlungsreferenzen dürfen sie anlegen |
| Datei bzw. Markdown an Material/Kindobjekt hochladen (`POST …/content`) | **500** — derselbe Staging-Fehler, den ihr seit dem 06.11. für Uploads meldet; F1 ist deshalb noch nicht messbar |
| Kindobjekt anlegen (`assocType=ccm:childio`, `aspects=ccm:io_childobject`) | 200, als Kind sichtbar |
| B-API `GET /api/v1/edu-sharing/repo/nodes/{id}` mit `X-Edu-User-Id` = Benutzername | **200**, der private Knoten der Person ist lesbar — die Kennung ist der Benutzername (`authority`) |
| … ohne `X-Edu-User-Id` | 400 |
| … mit erfundener Kennung | 403 |

Folgerung für die B-API (nicht für euch): Sie liest als die Person, die der Kopf nennt. Ob ein Schlüsselinhaber
mit dem Namen einer **anderen** echten Person deren private Knoten lesen kann, ist nicht getestet (kein zweites
Testkonto) — nach dem Ergebnis ist es zu erwarten. Das klären wir mit dem B-API-Team.

### Zu `POST/GET …/textContent` (Hinweis des Nutzers, 2026-11-08)

Ihr arbeitet mit `POST /node/v1/nodes/{repository}/{node}/textContent` („Change content of node as text“) und
`GET …/textContent`. Aus einer früheren Messung am Staging (31.07.2026, Wegwerf-Knoten, Skill-Doku
`wlo-content-files`) — bitte vor dem Einsatz an einem Knoten **mit hochgeladener Datei** nachmessen:

- **`POST /textContent` legt den Rumpf wörtlich als Inhalt ab:** `cclom:size` entsprach genau den gesendeten Bytes.
  Bei einem Knoten mit Datei droht damit, dass die **Datei ersetzt** wird. Das wäre genau der Fall, den W1
  vermeiden soll. Dann taugt der Endpunkt nur für Knoten ohne eigene Datei; sonst bleibt das Kindobjekt der Weg.
- **Bei einem Link-Datensatz (`ccm:wwwurl`) war er wirkungslos:** `200`, aber `GET` lieferte danach
  `{"text": null}`, weil das Repository den Volltext aus der Adresse erzeugt. Erfolg nur melden, wenn ein `GET` den
  Text zurückliefert.
- **`GET /textContent` stößt die Extraktion selbst an:** `?forceUpdate=true` erneuert sie, der Stand steht in
  `ccm:fulltext_status` (`CONTENT_AVAILABLE`, `TRANSFORM_ERROR_EXTERNAL` …). Die Antwort trug nur `text`; `raw` und
  `html` sind als optional zu behandeln.
- **Kein `JSON.stringify(text)` als Rumpf:** Die Anführungszeichen würden mitgespeichert.
- Jeder `POST` erzeugt eine neue Version.

## 7. Später zu klären (nicht Teil dieses Auftrags)

- **Benachrichtigung, wenn ein Flow fertig ist:** Sie soll im edu-sharing-Frontend erscheinen („Öffne den Chatbot
  erneut“). Wie das geht, klären wir später mit edu-sharing. Die B-API hat keinen Rückruf; der Chatbot holt
  Ergebnisse ab, sobald die Person wieder schreibt.
- **Den MCP hinter die B-API stellen:** langfristig, nicht Voraussetzung für diesen Auftrag.
