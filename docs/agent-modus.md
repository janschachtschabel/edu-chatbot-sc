# Agent-Modus verwenden

Kurzanleitung: die Agent-Schleife im Chat einschalten, das Widget in einen
Seitenbereich einbetten, und den Endpunkt `POST /api/agent` direkt ansprechen.

---

## 1. Zwei Maschinen, ein Unterschied

| | **Muster-Engine** (`pattern`, Vorgabe im Code) | **Agent-Schleife** (`agent`, Werksfassung) |
|---|---|---|
| Ablauf | Klassifikator → Musterwahl → gebundene Werkzeugliste | Systemprompt + **voller** Werkzeug-Katalog, freie Schleife |
| Endet bei | einer Antwort | `submit_result`, Prosa-Antwort, oder einem Deckel |
| Gut für | den Chat mit Menschen | Aufträge ohne Chat-Rahmen, maschinenlesbare Ergebnisse |

Im Code ist die Vorgabe `pattern`. Die ausgelieferte Werksfassung
(`seeds/01-base/engine.yaml`) setzt seit Paket 7 `mode: agent` — eine frische Anlage
antwortet also mit der Agent-Schleife, bis jemand im Studio umstellt.

**Eine Ausnahme gilt in jeder Maschine:** Erzwingt das Sicherheits-Gate ein
Muster (M01 bei Krise, M02 bei Drohung), beantwortet der Muster-Weg diesen Zug,
auch bei `agent` (SF-1, 2026-09-26). Die Muster-Kennung des Zuges
ist dann `M01` bzw. `M02`, nicht `AGENT`; die Pattern-Nutzung im
Studio zählt ihn deshalb unter „Muster". Die Maschine selbst steht seit AG-1 im
Debug-Block (`engine`, siehe unten), die Pattern-Nutzung wertet sie noch nicht
aus. Ein erklärtes `result-schema` bleibt für diesen Zug ohne Wirkung:
er liefert weder `result` noch einen Ende-Grund, also auch kein
`boerdi:agent-result`. Bei einer Erzwingung bleiben außerdem die Schnellwege
(Lernpfad, Canvas) in jeder Maschine aus (SF-1b), die Website-Tour überlässt
Krise und Drohung dem Gate (SF-1c), und beide Schutzmuster erzeugen keine
Quick-Replies (`quick_replies_mode: none`).

---

## 2. Agent-Schleife im Chat einschalten

### a) Für die ganze Anlage — Studio

**Studio → System → „Betrieb“** (Bereich `01-base/engine`, Feld `mode`; die Deckel
unter `agent` stehen im Agent-Arbeitsbereich auf „Rolle & Schutz“)

```yaml
mode: agent            # pattern | agent  (gespeichertes hybrid gilt als agent)

agent:
  max_iterations: 30     # 1 . 50
  deadline_s: 900        # 5 . 1800
  token_budget: 900000   # ≥ 1000
  write_mode: propose    # propose | execute  (das Sicherheits-Gate läuft immer)
  anonymous:             # AG-6: Deckel ohne angemeldete Person
    max_iterations: 30   # 1 . 50, vorbelegt wie oben
    deadline_s: 900      # 5 . 1800
    token_budget: 900000 # ≥ 1000

agent_rolle:             # AG-3: der Kopf des Agenten
  rolle: |               # Rolle, Arbeitsweise, Antwortform (Vorgabe im Modell)
    Du bist Boerdi, der Assistent von WirLernenOnline (WLO). …
  schutzregeln: [R-05, R-08, R-13, R-15]   # Kennungen aus 01-base/guardrails

muster_skills: false     # E-6: Skill-Werkzeuge auch in anderen Werkzeug-Mustern
```

**`anonymous` (AG-6)** gilt im Chat für Züge, hinter denen keine angemeldete Person
steht (kein persönlicher Zugangsblock; der öffentliche anonyme Block zählt nicht).
Die Maschine wählt jeder Client über `X-Boerdi-Engine`. Vorbelegt ist sie mit den
aktuellen Werten (Nutzer-Entscheid 2026-09-27: nicht hart deckeln, aber anbieten) —
die Vorgabe ändert also nichts. Wer sie senkt, bremst anonyme Züge; jeder Wert wirkt
als Minimum, ein anonymer Wert über dem normalen hebt nichts an, ein geleertes Feld
heißt „wie angemeldet". Die K0-Messung als Anhalt: kein Agent-Zug brauchte mehr als
75 s, 2 von 126 mehr als 400 000 Token. `/api/agent` ist nicht betroffen, er
verlangt einen Aufruferschlüssel.

Zwei Grenzen, die dazugehören (Review 2026-09-27):

* **Wer die normalen Deckel über die Vorgabe hebt, hebt die anonymen mit an oder
  leert sie.** Sonst bleiben anonyme Züge bei 30 Runden, 900 s und 900 000 Token —
  das Minimum macht die alte Vorgabe dann still zum Deckel.
* **„Angemeldet" prüft der Chatbot nur an der Form des Zugangsblocks.** Ein
  gefälschter Block hebt die anonymen Deckel auf; der MCP-Server weist ihn zwar ab,
  die Modellrunden bis dahin sind aber bezahlt. Die Mengenbremse gegen Missbrauch
  bleibt das Rate-Limit (`RATE_LIMIT_CHAT`), nicht dieser Deckel.

**`agent_rolle` (AG-3)** ist der Kopf jeder Agent-Kette im Chat und steht vor dem
Master-Skill. Daraus und aus zwei bestehenden Studio-Bereichen setzt
`services/agent_kopf.py` zusammen: die Rolle; die Anrede je Zielgruppe aus den
Persona-Einstellungen (`formality`: Lehrkraft und Entscheider siezen, Lerner:innen
duzen, Eltern und Redaktion wie die Person selbst); die Schutzregeln im Wortlaut der
Leitplanken, nur die genannten Kennungen (D-5); „antworte in der Sprache der Person,
sonst in der des Widgets". Die übrigen Leitplanken sind Arbeitsregeln der
Muster-Maschine und gelten im Agenten nicht.

**`muster_skills` (E-6)** gilt für die **Muster-Maschine**. Von Haus aus führen nur
M08, M09, M10, M18, M19 und M20 die Skill-Werkzeuge `get_skill_registry` und
`get_skill`. Mit dem Schalter bekommt jedes andere Muster, das ohnehin Werkzeuge
nutzt, beide dazu — aber nur, wenn Skills im Spiel sind: die Seite oder das Gespräch
meldet freigegebene Skills, oder ein Skill läuft gerade. Ob einer passt, entscheidet
das Modell. Nie dazu kommen sie bei Krise und Drohung (M01/M02), bei den Mustern ohne
Werkzeuge und bei einer Werkzeug-Sperre aus Safety oder Policy. Vorgabe aus. Kosten
nur in Zügen mit Skills: rund 600 Token je Modellaufruf für die zwei Beschreibungen,
dazu die Abrufe, wenn das Modell sie nutzt.

Unabhängig vom Schalter stehen Ladeweg, Vorrang-Regel und „Laufender Skill" nur noch
im Muster-Prompt, wenn der Zug die Werkzeuge hat. Die Übersicht der freigegebenen
Skills bleibt, mit dem Satz, dass sich in diesem Zug keiner laden lässt. Bis dahin
bekam ein Suchmuster die Anweisung „hol ihn mit `get_skill`" ohne `get_skill`.

Wirkt ohne Neustart. Alle vier Deckel sind nötig: ein MCP-Aufruf steht gemessen
bis 23 s, ohne Frist koennte ein Lauf mit 30 Runden eine halbe Stunde dauern.

Das Budget zählt `prompt + completion` **kumulativ über alle Runden**, und weil
die Nachrichtenkette wächst, wird der Prompt jede Runde neu berechnet. Bei
60 000 (Stand bis 2026-08-17) war deshalb nach drei Runden Schluss, während
`max_iterations` und `deadline_s` unberührt blieben — Messung und Begründung in
`docs/plans/2026-08-17-hybrid-muster-als-werkzeug.md` §8.

**Am 2026-08-18 gemeinsam angehoben** (12/90/120000 → 20/300/400000,
Nutzer-Entscheid). Gemeinsam, weil einzeln jeder Wert wirkungslos bliebe: wer
30 Runden erlaubt, aber die Frist bei 90 s laesst, bekommt fuenf. Die Reihenfolge,
in der die Deckel greifen, entscheidet die Messung — nicht die Absicht.

Zwei Folgen, die dazugehören:

* **Der Kosten-Deckel je Zug steigt auf das Sechsfache.** Er ist eine Vorgabe,
  keine Empfehlung: wer knapper rechnen muss, stellt ihn im Studio je Anlage ein.
* **Die neue Grenze ist das Kontextfenster des Anbieters, nicht mehr unsere.**
  Die Schleife kürzt die Nachrichtenkette nicht; 20 Runden mit großen
  Werkzeug-Ergebnissen können sie über das Fenster des Modells treiben. Das
  endet dann mit `stop_reason: "error"`, nicht mit einem sauberen Deckel.

### b) Je Einbau — Host-Attribut `engine`

Damit lässt sich **eine** Seite auf die Agent-Schleife stellen, während der Rest
der Anlage bei der Muster-Engine bleibt. Genau das braucht ein A/B-Vergleich.

```html
<boerdi-chat api-url="https://api.example.org" engine="agent"></boerdi-chat>
```

Werte: `pattern` · `agent` · leer/weglassen = die Vorgabe aus `01-base/engine`.

### c) Je Anfrage — Kopfzeile

```
X-Boerdi-Engine: agent
```

Undeklariert gelesen, steht also **nicht** im OpenAPI-Dokument. Ein unbekannter
Wert bricht nichts: er fällt auf die Vorgabe zurück und wird nur protokolliert.

**`hybrid` ist entfernt** (K1-1, 2026-09-27: die K0-Messung zeigte ihn zwischen
den beiden anderen Maschinen, ohne eigenen Mehrwert). Eine Einbettung, die ihn
noch anfordert — Attribut, Kopfzeile oder gespeichertes `mode: hybrid` —, bekommt
die Agent-Schleife, mit einer Warnung je Herkunft und Prozess im Log. Gold-Start
und Lasttest nehmen ihn dagegen nicht mehr an (422): ein Mess-Lauf misst die
Maschine, die er nennt.

> **Zum Ausprobieren ohne Code:** auf jeder Demo-Seite (`/widget/classic`,
> `/widget/inline`, `/widget/frameless`) steht im Bedienpult ein Schalter
> **„Maschine"**.

**Messen statt vermuten:** dieselbe Kopfzeile treibt die Golden-Suite v2 —
`evals/run_golden.py --engine pattern|agent` fährt je Engine einen Lauf
über 12 Anwendungsfall-Flows, `compare_golden.py` stellt zwei Läufe gegenüber
(Checks und Antwort-Struktur je Zug, keine Latenz — p50/p95 stehen nur im
Bericht des einzelnen Laufs). Im Studio wählt der Gold-Start die Engine direkt.
Details: `evals/README.md`.

---

## 3. Eingebettet in einen Seitenbereich

Rahmenlos heißt: das Widget legt mit dem Rahmen auch die **eigene Größe** ab.
Der Gastgeber stellt den Kasten — vergisst er die Höhe, ist das Element null
Pixel hoch und man sieht nichts, ohne Fehlermeldung.

```html
<!-- einmal pro Seite -->
<script src="https://api.example.org/widget/boerdi-widget.js" defer></script>

<!-- der Kasten gehört DIR: Höhe, Rahmen, Ecken -->
<div style="block-size: min(32rem, 70vh); border: 1px solid #d1d5db;
            border-radius: .75rem; overflow: hidden;">
  <boerdi-chat
    api-url="https://api.example.org"
    embed-mode="frameless"
    initial-state="expanded"
    engine="agent"
    show-language-buttons="false"
    show-debug-button="false">
  </boerdi-chat>
</div>
```

| Attribut | Wirkung |
|---|---|
| `embed-mode="frameless"` | füllt den Container, kein Eulen-Knopf, keine eigene Kopfzeile |
| `initial-state="expanded"` | offen von Anfang an (**nur der Start** — danach gehört der Zustand dem Panel) |
| `engine="agent"` | dieser Einbau fährt die Agent-Schleife |
| `show-language-buttons="false"` | Mikrofon + Vorlesen aus (ALT-Name, meint die Sprach-**Ausgabe**) |
| `show-debug-button="false"` | Debug-Knopf aus |

**Seitenkontext mitgeben** — wenn die Gastseite weiß, worauf sie steht:

```html
<boerdi-chat
  api-url="https://api.example.org"
  embed-mode="frameless" initial-state="expanded" engine="agent"
  auto-context="false"
  page-context='{"page_kind":"collection","collection_id":"…-UUID-…"}'>
</boerdi-chat>
```

`auto-context="false"` schaltet die eigene Erkennung ab; sonst trüge sie
zusätzlich Adresse und Titel der Gastseite bei. Die vollständige Attributliste
steht im Studio unter **Übersicht → Architektur & Referenz**.

---

## 4. Den Endpunkt direkt ansprechen

`POST /api/agent` ist der Weg für Gastgeber **ohne** Chat-Rahmen: Browser-Plugin,
edu-sharing-Einbettung, jede Maschine, die eine Aufgabe stellt und ein
maschinenlesbares Ergebnis auswerten will. Keine Sitzung, keine Begrüßung, keine
Muster — Anweisung rein, Text plus freies JSON raus.

### Zugang

Drei Wege, in dieser Reihenfolge geprüft:

1. `AGENT_OPEN=true` — der ausdrückliche Ausweg für Testläufe. **Vorgabe: aus.**
2. Kopfzeile `WLO-Access-Block` mit **persönlicher** Anmeldung (der anonyme Block zählt nicht).
3. Kopfzeile `X-Studio-Key` — Server-zu-Server.

Dazu die Drosselung: `RATE_LIMIT_CHAT`, Vorgabe **120/Minute je IP**, Antwort 429
mit `X-RateLimit-*`-Kopfzeilen. Die Prüfung des Zugangsblocks ist eine **Form**-,
keine Echtheitsprüfung — nur der MCP-Server kann einen Block belegen —, also ist
die Mengenbremse die Kostenschranke.

### Eingabe

```jsonc
{
  "instruction": "Prüfe diese Inhalte auf Sachrichtigkeit und begründe kurz.",
  "collection_id": "0fa8…-UUID",      // optional
  "node_ids": ["3b1c…", "9d4e…"],     // optional, höchstens 50
  "result_schema": {                   // optional
    "type": "object",
    "properties": {
      "note":     { "type": "integer", "minimum": 0, "maximum": 5 },
      "begruendung": { "type": "string" }
    },
    "required": ["note", "begruendung"]
  },
  "write_mode": "propose",            // optional: propose | execute
  "allow_curation": true,             // optional, Vorgabe true
  "locale": "de"                      // optional: de | en
}
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `instruction` | **ja** | Die Aufgabe im Klartext, ≤ 200 000 Zeichen, nicht leer |
| `collection_id` | nein | Sammlung, aus der die Anleitungen („Skills") kommen — **vorab** über `get_skill_registry` aufgelöst |
| `node_ids` | nein | Die Inhalte, um die es geht — vorab über `get_nodes_details` geholt, höchstens 50 |
| `result_schema` | nein | Verlangt eine maschinenlesbare Antwort in dieser Form. Reist wörtlich in die Parameter des Abschluss-Werkzeugs `submit_result` |
| `write_mode` | nein | Übersteuert `01-base/engine`. **`execute` verlangt immer eine angemeldete Person** — ohne sie fällt der Lauf still auf `propose` zurück (nur Vorschau) |
| `allow_curation` | nein | `false` nimmt die kuratierenden Werkzeuge heraus, auch mit Anmeldung |
| `locale` | nein | Sprache der Ausgabe |

Die Vorab-Abrufe laufen **vor** der Anweisung: erst was zu tun ist, dann woran.
Schlägt einer fehl, kippt er den Auftrag nicht — der Agent arbeitet weiter und
sagt im Ergebnis, dass ihm etwas fehlt.

### Ausgabe

```jsonc
{
  "text": "Beide Inhalte sind fachlich korrekt. Bei …",
  "result": { "note": 4, "begruendung": "…" },   // null ohne result_schema
  "stop_reason": "submit",
  "iterations": 3,
  "tools_called": ["get_nodes_details", "get_wlo_content_text", "submit_result"]
}
```

`stop_reason` gehört zur Antwort und nicht ins Protokoll: ein an der Frist
abgeschnittener Lauf sähe von außen sonst aus wie einer, der fertig wurde.

| `stop_reason` | heißt |
|---|---|
| `submit` | Das Modell hat `submit_result` gerufen — die Ziellinie |
| `text` | Es hat in Prosa geantwortet, ohne Werkzeug |
| `max_iterations` | Iterationsdeckel erreicht |
| `deadline` | Frist abgelaufen |
| `token_budget` | Token-Budget aufgebraucht |
| `no_progress` | Stillstand: die Schleife kam nicht mehr voran |
| `empty` | Das Modell lieferte dreimal weder Werkzeug noch Text |
| `error` | Fehler in der Schleife |
| `safety` | Das Sicherheits-Gate hat den Auftrag gestoppt, die Schleife lief nicht (AG-4 Teil B) |

Die vier Deckel stehen in `01-base/engine`; `submit` und `text` sind die beiden
Ziellinien.

**Sicherheits-Gate (AG-4 Teil B, 2026-09-27).** Der Auftrag durchläuft vor allem
anderen dasselbe Gate wie eine Chat-Nachricht (Regex, Moderation, Rechtsprüfung je
Stufe; fällt eine LLM-Stufe aus, bleibt das Regex-Gate). Eine Krise bekommt den
Krisentext aus dem Studio (`01-base/safety-config`, `crisis_message` und
`crisis_message_en`; Vorgabe: an die Familie oder die Ansprechperson der Einrichtung
wenden, ohne Telefonnummern), jedes andere hohe Risiko die Abweisung. Beides endet
mit `stop_reason: "safety"`, ohne Vorabruf und ohne LLM-Lauf. Mittleres Risiko
lässt den Lauf zu, ohne die gesperrten Werkzeuge. Der Chat antwortet auf eine Krise
weiter über das Muster M01.

**`empty` — der Aussetzer des Anbieters.** Kommt eine Antwort ohne
Werkzeugaufruf *und* ohne Inhalt, ist das keine Ziellinie: die Schleife
wiederholt den Aufruf mit **unveränderter** Nachrichtenkette, bis zu
`llm.LEERLAUF_VERSUCHE` mal (2, also drei Aufrufe insgesamt), und endet erst dann
mit `empty`.

Live gemessen am 21.08.2026 über 20 Züge derselben Volltext-Frage: **7
Aussetzer**, auffällig schnell (6–8 s statt 9–19 s), und der Zug endete stumm.
Sie treten unabhängig voneinander auf — dieselbe Eingabe, mal leer, mal
vollständig. Ein einziger zweiter Anlauf ließe rechnerisch ~12 % stumme Züge
übrig, zwei lassen ~4 %. Bezahlt wird das nur im Fehlerfall: wer beim ersten
Mal antwortet, ruft einmal.

Der zweite Anlauf ist ein echter — der b-api-Cache-Bust schickt je Aufruf
`clearCache` bzw. eine frische `user`-Kennung, der Anbieter kann die leere
Antwort also nicht bloß wiederholen. Ermahnt wird das Modell dabei nicht: es
gibt nichts richtigzustellen. Jeder Aussetzer kostet eine Iteration und wird
gebucht; Frist und Token-Budget prüfen vor jeder Runde und greifen unverändert.

**Der Muster-Modus trägt dieselbe Absicherung** (`services/tool_loop`, seit
21.08.2026) — es ist derselbe Anbieter und derselbe Aufruf. Dort gibt es kein
`stop_reason`; bleibt es nach allen Anläufen leer, sagt `graph/nodes/respond`
denselben Satz wie der Agent-Weg (`agent.failed`). Der Zweig greift
ausschließlich im Ausfall: ein Zug mit Text läuft unverändert, und M16 wie die
Schnellwege sehen ihn nie. Gemessen wurde der Aussetzer dort in 10 Zügen
**nicht** — Vorsorge, kein Befund. Die Zahl steht für beide Maschinen an einer
Stelle: `services/llm.LEERLAUF_VERSUCHE`.

Eine Einschränkung gilt nur dort: **auf dem Inline-Pfad (`respond_to_user`)
wird nicht wiederholt.** Mit `CHAT_TOKEN_STREAMING` ist der Text dort schon
zeichenweise beim Client (`text_delta`, Plan `2026-10-01-token-streaming`) — eine
zweite Antwort hängte sich sichtbar hinter die erste. Bleibt er leer (erreichbar,
wenn die Antwort nur aus Optionszeilen bestand), endet der Zug leer und bekommt
den ehrlichen Satz statt einer Wiederholung.

**Token-Streaming im Agent-Modus.** Gestreamt wird nur der Text von
`respond_to_user`, also nur mit `AGENT_INLINE_QUICK_REPLIES=1` (und
`CHAT_TOKEN_STREAMING=1`). Eine Runde mit dieser Antwort ist immer die letzte, ihr
Text wird nie verworfen. Freier Text vor einem Werkzeugaufruf geht nie hinaus.

**Das Ansage-Echo — die tatsächlich gemessene Live-Ursache.** Die stummen Züge
vom 21.08.2026 waren am Ende kein Aussetzer: das Modell antwortete, aber die
ganze Antwort war die Aktivierungszeile (`[ edu-sharing Skill ] Chatbot
Masterskill - aktiv`), die `mit_master_ansage` als Modell-Kopie entfernt —
richtig so, sonst stünde sie doppelt —, womit nichts übrig blieb.
`graph/nodes/respond_agent` prüft seither das **Ergebnis** der Komposition und
sagt im Leerfall den ehrlichen Satz (`agent.failed`) samt WARNING.

Die Quelle der Zeile ist der MCP-Server: er legt um jedes `get_skill`-Dokument
einen Abschnitt „## Aktivierung" mit der Bitte, die Zeile wörtlich als erste
Zeile der nächsten Antwort auszugeben. Seit der Server der Ansage-Setzer ist
(T2/T4), war diese Bitte hier überflüssig — und kollidierte mit „gib sie nicht
wörtlich wieder" (Rang-Block) und „Eine Ankündigung ist keine Antwort"
(Master-Skill selbst). Behoben wurde sie **redaktionell, nicht im Code**
(Nutzer-Entscheid 21.08.2026): der Master-Skill (`docs/skills/vorgehen.md`,
Sektion „Zuerst handeln, dann reden") übersteuert die Bitte — „Aktivierungszeilen
tippst du nie selbst". Messung, gleiche Volltext-Frage, frische Session je Zug:
vorher trug jeder dritte Zug nur den Ersatzsatz und rief kein Werkzeug (4 von
12); nachher **0 von 15**, und **15 von 15** riefen das Werkzeug — die
Echo-Warnung feuerte kein einziges Mal. Die sichtbare Ansage bleibt davon
unberührt, sie kommt vom Server.

### Syntax — curl

```bash
curl -sS -X POST https://api.example.org/api/agent \
  -H 'Content-Type: application/json' \
  -H "X-Studio-Key: $B_STUDIO_KEY" \
  -d '{
        "instruction": "Fasse die Inhalte in je einem Satz zusammen.",
        "node_ids": ["3b1c…", "9d4e…"],
        "result_schema": {
          "type": "object",
          "properties": {
            "zusammenfassungen": { "type": "array", "items": { "type": "string" } }
          },
          "required": ["zusammenfassungen"]
        }
      }'
```

### Syntax — fetch

```js
const antwort = await fetch('https://api.example.org/api/agent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'WLO-Access-Block': zugangsblock,   // die persönliche Anmeldung
  },
  body: JSON.stringify({
    instruction: 'Schlage Metadaten für diesen Inhalt vor.',
    node_ids: [knotenId],
    write_mode: 'propose',
  }),
});

if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
const { text, result, stop_reason, iterations, tools_called } = await antwort.json();
```

### Fortschritt mitlesen — `POST /api/agent/stream`

Gleicher Rumpf, Antwort als Server-Sent-Events. Rahmen in dieser Reihenfolge:

```
event: connected
data: {}

event: phase
data: {"kind":"record","step":"agent_prefetch","label":"Hole get_nodes_details","data":{"tool":"get_nodes_details"}}

event: result
data: {"text":"…","result":{…},"stop_reason":"submit","iterations":3,"tools_called":[…]}
```

Statt `result` kann `error` kommen (`{"message":"…"}`). Ein `end`-Rahmen wird
bewusst **nicht** gesendet. Der Strom liefert **keine** Token — nur `phase`.
Wer nur das Ergebnis will, nimmt `POST /api/agent`.

---

## 5. Ohne Code ausprobieren

**Studio → Agent → „Prompt & Probelauf“, Abschnitt „Auftrag testen (Gastanwendungen)“**: Formularfelder für alle sechs
Eingaben, darunter Ergebnis-JSON, `stop_reason`, Runden und gerufene Werkzeuge.
Der Studio-Proxy spritzt den Schlüssel serverseitig ein — deshalb sitzt das
Werkzeug dort und nicht auf einer öffentlichen Seite.

Ein Lauf fährt die **echte** Schleife und kostet entsprechend: dieselbe Klasse
wie ein Lasttest, nicht wie eine Suche.

---

## 6. Häufige Fehler

| Symptom | Ursache |
|---|---|
| Der Kasten bleibt leer | `embed-mode="frameless"` ohne Höhe am Container |
| Der Chat startet geschlossen | `initial-state="expanded"` fehlt — es ist ein **Start**-Wert |
| `engine="agent"` wirkt nicht | Das ausgelieferte Widget-Bundle ist älter als das Attribut → neu bauen und ins Backend-Image legen |
| Der Studio-Bereich ist leer | `01-base/engine.yaml` wurde nie in die DB importiert (Seed-Import) |
| 401/403 | Keiner der drei Zugangswege greift |
| 429 | Drosselung, `RATE_LIMIT_CHAT` |
| `result` ist `null` | Kein `result_schema` mitgegeben — dann gibt es nur `text` |
| Schreiben passiert nicht | `write_mode: execute` ohne persönliche Anmeldung → still auf `propose` zurückgefallen |
| Im Chat keine Vorschau-Box mit Knopf „Ja, so ausführen“ | Keine persönliche Anmeldung: der Agent-Zug reicht eine Schreib-Vorschau nur für eine angemeldete Person in die Sitzung (Paket 2, Nutzer-Entscheid 2026-08-12) — sonst bliebe das „ja“ beim Dienstkonto der Anlage |

## Maschine und Spur im Debug-Block (AG-1, 2026-09-26)

- **`debug.engine`** nennt die Maschine, an die der Zug ging: `pattern` oder
  `agent` (in Zügen vor K1-1 auch `hybrid`). Leer bleibt sie bei Zügen, die vor
  jeder Maschine antworten (Tour, Kontext-Begrüßung, Direktaktionen,
  Schreib-Abnahme). Ein Krisenzug nach
  SF-1 trägt die gewählte Maschine; die Umleitung zeigt das Muster `M01`/`M02`.
- **`debug.trace`** führt im Agent-Modus je Runde eine Zeile
  `agent_round` und zum Schluss `agent_stop` mit Ende-Grund und Rundenzahl. Eine
  Runde nennt ihre Werkzeuge in Aufrufreihenfolge, auch die virtuellen
  (`zeige_dokument`, `liefere_ergebnis`, `wissen_suchen` …), dazu Dauer und Token.
  Von den Argumenten stehen nur die **Namen** darin, nie die Werte: ein Wert kann
  Nutzerinhalt tragen. Die Werte stehen in der Zugakte (`debug._zugakte`, Paket
  18C/D). Den Debug-Block bekommt seit Paket 18C/D nur die Anlage selbst; das
  Studio zeigt die Zeilen im Gesprächsverlauf, das Debug-Panel des Widgets nur mit
  Freigabe. Der
  Muster-Weg führt keine Runden-Spur.
- **Zeile `skill`** (AG-5), in jeder Maschine: die Anleitung, die dieser Zug
  geholt hat, mit Knoten-Kennung und Titel. Das sind Angaben aus dem
  Repositorium und kein Nutzerinhalt; der Titel steht ohnehin in der Ansage über
  der Antwort. Holt ein Zug zwei Anleitungen, steht nur die letzte da, und ein
  fehlgeschlagener Abruf zählt nicht als geholt.
- **Nutzungsbuchung:** `usage_events.engine` (Migration 0004) übernimmt die
  Maschine aus dem Debug-Block. Auswertungen nach Maschine im Studio kommen mit
  den Studio-Paketen ST-7 und ST-9.

## Master-Skill als Prompt-Kopf (2026-08-18)

Im Agent-Modus kann eine im Repositorium gepflegte
Gesamtanleitung als stabiler Kopf des Systemprompts laufen — die Vorlage dafür
ist [`docs/skills/vorgehen.md`](skills/vorgehen.md).

| Schalter | Vorgabe | Wirkung |
|---|---|---|
| `MASTER_SKILL_ENABLED` | `false` | Betreiber-Vorgabe: an oder aus |
| `MASTER_SKILL_NODE_ID` | `535cabca-47e4-4cbf-9cab-ca47e40cbf4e` | Knoten der Anleitung (`get_skill`) |
| Attribut `master-skill="on\|off"` | fehlt | übersteuert die Vorgabe **je Einbettung**, in beide Richtungen |

**Warum weit vorn.** Der Block ist groß und zwischen zwei Zügen unverändert;
Anbieter mit Präfix-Caching berechnen ihn dann nur einmal. Genau eine Abweichung
von „ganz am Anfang": der eigene Rollen-Block bleibt davor. Er ist ebenso stabil,
kostet also keinen Cache-Treffer, und eigene Regeln gehören vor fremden Text.
Alles Wechselnde (Seitenkontext, Gastgeber-Rahmen, Verlauf) folgt dahinter —
sonst zerfiele das Präfix. Ein Test hält die Position fest
(`test_der_master_skill_steht_im_stabilen_praefix`).

**Was der Text NICHT darf.** Er ist kuratierter Inhalt, keine Systemanweisung.
Der Rahmen um ihn sagt das dem Modell ausdrücklich: er ergänzt die Rolle, hebt
aber weder Leitplanken noch Sicherheitsregeln auf.

**Im Takt geholt (seit 2026-10-18).** Ein Hintergrund-Lauf je Backend-Prozess holt
den Text alle 5 Minuten (`services/master_skill.TAKT_S`, gestartet im Lebenszyklus der
App); ein Chat-Zug liest nur den Speicher und wartet nie auf das Repositorium —
vorher bezahlte der erste Zug nach Ablauf den Abruf (1,2–23,3 s). Abgeschaltet holt der
Takt erst, nachdem der Skill einmal gebraucht wurde (Einbettung, Studio-Anzeige).

**Wenn der Abruf scheitert** — MCP weg, Knoten gelöscht, leerer Text — gilt der
**letzte gute Stand** weiter, und die Studio-Karte nennt den Fehler. Gibt es noch
keinen Stand (frischer Prozess, erster Abruf gescheitert), läuft der Zug ohne
Anleitung weiter, mit einer Warnung im Log; ein Fehlschlag wird nicht gespeichert,
der nächste Zug versucht es erneut.

**Was in den Master-Skill gehört (2026-09-28).** Er ist die Steuerfläche des
Agenten, die die Redaktion ohne Deployment ändert — so war er angelegt (Auftrag
2026-08-18: auch „die chatbot-eigenen Anteile … Ergebnisfenster,
Schnellantwort-Pillen, Struktur"). Hinein gehört deshalb, was flexibel bleiben
muss: das Vorgehen je Anliegen, Anrede-Regel und Arbeitsweise je Zielgruppe,
Suchstrategie, Didaktik und die Bedienung der Chat-Flächen. Beschreibt er
Mechanik, muss sie für den **Agent-Zug** stimmen — eine Dokument-Box entsteht dort
nur über `zeige_dokument`, der Überschriften-Rückfall gilt allein im Muster-Weg.
Woanders hin gehört:

| Was | Wo | Warum |
|---|---|---|
| Zuordnung Zielgruppe → du/Sie | Studio, Personas (`formality`); der Kopf listet sie | eine Quelle für beide Maschinen — die Kopien in den Mustern M09/M15 sind veraltet |
| was der Agent vom vorigen Zug sieht | Code (Verlauf, gespeicherte Dokumente) | kein Text wirkt auf etwas, das nicht im Prompt steht |
| ob Karten und Schnellantworten erscheinen | Code | ein Fehler dort ist keiner des Textes |
| Schutz-Umleitung, Schreib-Bestätigung, Ansage-Zeile | Code | muss auch ohne Master-Skill gelten |

**Übertragen.** `vorgehen.md` ist der Rumpf des Knotens; Titel, `nodeId` und den
Abschnitt „Aktivierung" davor erzeugt der MCP-Server. Die Redaktion ersetzt den
Rumpf im Knoten — im Studio über „Im Editor bearbeiten" auf der Master-Skill-Karte
(md-editor des Repositoriums) —, der Chat übernimmt ihn nach spätestens fünf Minuten
oder sofort über „Neu laden" auf der Agent-Seite des Studios. Wächter-Tests
(`test_master_skill_vorlage.py`, dazu drei in `test_mcp_tool_defs.py`) halten die
Regeln aus gemessenen Fehlern in der Vorlage fest.

**Nach dem Übertragen prüfen.** `uv run python scripts/check_master_skill.py` (aus
`backend/`, nur lesend) holt den Knoten wie der Chat und wendet die Wächter aus
`test_master_skill_vorlage.py` auf den Text unter dem Vorspann an; Rückgabe 0 = alle
Regeln erfüllt, 1 = mindestens eine verletzt, 2 = nicht abrufbar. Die drei
Werkzeug-Wächter in `test_mcp_tool_defs.py` laufen dort nicht mit. Der md-editor
formatiert beim Speichern um (Absätze einzeilig, `**M09**` statt `(M09)`); die
Wächter tragen beide Schreibweisen.

## Interne Wissensdatenbank (2026-08-18)

Bis zu diesem Tag hatte die Agent-Schleife **gar kein** internes Wissen: das
Werkzeug `query_knowledge` wird ausschließlich im Muster-Weg gebaut, hier lief
also jede Frage nach WLO, OER oder edu-sharing ins Modellgedächtnis. Seither
liegt `wissen_suchen` im Werkzeugsatz — sichtbar, sobald in
`05-knowledge/rag-config` Bereiche gepflegt sind.

| | Muster-Weg | Agent-Schleife |
|---|---|---|
| Werkzeug | `query_knowledge(area, query)` — **ein** Bereich, Pflichtfeld | `wissen_suchen(frage, bereiche?, ohne?)` — ohne Angabe **alle** |
| Vorabruf | `mode: always`-Bereiche vor dem ersten Modellzug | keiner |
| Muster kann es abschalten | ja, über `sources` ohne `rag` | nein — es bleibt erreichbar |

**Warum „alle" nicht teurer ist:** `get_rag_context` bettet die Frage einmal ein
und durchsucht die Bereiche nebenläufig; weil alle dieselbe Einbettung und
dasselbe Abstandsmaß benutzen, sind die Punktzahlen bereichsübergreifend
vergleichbar. Neun Bereiche kosten also eine Einbettung, nicht neun.

**Warum kein Vorabruf:** die Schleife beantwortet auch „hallo". Der Muster-Weg
kann vorab holen, weil ein Klassifikator vorher weiß, worum es geht; hier weiß
es das Modell selbst — und ruft, wenn es passt.

**Wenn die Datenbank ausfällt**, bekommt das Modell den Ausfall im Klartext als
Werkzeug-Ergebnis und kann ihn sagen. Der Zug bricht nicht ab: dieselbe Regel wie
beim Master-Skill.

### Einen Bereich für die Schleife abwählen

In `05-knowledge/rag-config` (Studio → **Wissen**) trägt jeder Bereich zwei
Schalter, und sie meinen verschiedene Maschinen:

```yaml
Interna:
  mode: on-demand   # Muster-Weg: Vorabruf oder Abruf auf Zuruf
  agent: false      # Agent-Schleife: gar nicht
```

`agent` fehlt = `true`. Die Vorgabe bleibt also „alle Bereiche für den Agenten";
abgewählt wird nur, wer es ausdrücklich sagt. Zwei Felder statt einem, weil
„im Muster vorab, in der Schleife gar nicht" sonst nicht ausdrückbar wäre.

### Die zwei Bereichslisten

Ein Bereich existiert an zwei Stellen, und sie können auseinanderlaufen:

| | Quelle | Bedeutung |
|---|---|---|
| Studio → Wissen → Liste | Datenbank (`rag_chunks.area`) | was **eingelesen** wurde |
| `05-knowledge/rag-config` | Konfiguration | was der Chatbot **durchsucht** |

Wer beim Einlesen einen neuen Bereichsnamen tippt, legt ihn nur links an. Seit
dem 18.08.2026 markiert die Liste solche Bereiche („Der Chatbot durchsucht
diesen Bereich NICHT …"). Das Verhalten bleibt absichtlich zweistufig: würde ein
eingelesener Bereich automatisch mitgesucht, wäre jeder Probe-Upload zugleich
eine Freigabe im Betrieb.

## Was die Einbettung hart überschreibt (Paket O, 2026-08-18)

Drei Angaben reisen seit diesem Tag im `environment` mit und wirken **nur** in
der Agent-Schleife:

| Attribut | Wirkung |
|---|---|
| `tool-mode="read-only\|curate\|full"` | nimmt die verbotenen Werkzeuge aus der Liste **und** sagt es dem Modell |
| `quick-replies='["…","…"]'` | erzwungene Schnellantworten je Zug; schlagen Generator, Canvas und Policy |
| `inline-result-grouping="false"` | war bis dahin rein visuell; jetzt weiß das Modell, dass es die Gliederung selbst schreiben muss |

Der Block dazu steht als dritte System-Nachricht — hinter dem Master-Skill, vor
dem Seitenkontext — und **nur bei Abweichung**: ein Satz über den Normalfall
kostete in jedem Zug Token und sagte nichts.

**Nachtrag Paket 7 (P4):** `tool-mode` und `inline-result-grouping` erreichen
inzwischen auch die Muster-Maschine — derselbe Block steht dort hinter dem Auftrag
der einbettenden Anwendung (`response_prompt_builder`); `tool-mode` filtert dort
seit Paket 4 auch die Werkzeuge.
