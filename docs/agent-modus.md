# Agent-Modus verwenden

Kurzanleitung: die Agent-Schleife im Chat einschalten, das Widget in einen
Seitenbereich einbetten, und den Endpunkt `POST /api/agent` direkt ansprechen.

---

## 1. Zwei Maschinen, ein Unterschied

| | **Muster-Engine** (`pattern`, Vorgabe) | **Agent-Schleife** (`agent`) |
|---|---|---|
| Ablauf | Klassifikator → Musterwahl → gebundene Werkzeugliste | Systemprompt + **voller** Werkzeug-Katalog, freie Schleife |
| Endet bei | einer Antwort | `submit_result`, Prosa-Antwort, oder einem Deckel |
| Gut für | den Chat mit Menschen | Aufträge ohne Chat-Rahmen, maschinenlesbare Ergebnisse |

Die Vorgabe ist bewusst `pattern`: ohne Pflege ändert sich am ausgelieferten
Chatbot nichts.

---

## 2. Agent-Schleife im Chat einschalten

### a) Für die ganze Anlage — Studio

**Studio → Agent & Maschine → „Welche Maschine antwortet"** (Bereich `01-base/engine`)

```yaml
mode: agent          # pattern | agent

agent:
  max_iterations: 12   # 1 … 50
  deadline_s: 90       # 5 … 600
  token_budget: 60000  # ≥ 1000
  write_mode: propose  # propose | execute
  safety: true
```

Wirkt ohne Neustart. Alle vier Deckel sind nötig: ein MCP-Aufruf steht gemessen
bis 23 s, ohne Frist könnte ein Lauf mit 12 Runden acht Minuten dauern.

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

> **Zum Ausprobieren ohne Code:** auf jeder Demo-Seite (`/widget/classic`,
> `/widget/inline`, `/widget/frameless`) steht im Bedienpult ein Schalter
> **„Maschine"**.

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

Dazu die Drosselung: `RATE_LIMIT_CHAT`, Vorgabe **20/Minute je IP**, Antwort 429
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
| `instruction` | **ja** | Die Aufgabe im Klartext, ≤ 20 000 Zeichen, nicht leer |
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
| `error` | Fehler in der Schleife |

Die vier Deckel stehen in `01-base/engine`; `submit` und `text` sind die beiden
Ziellinien.

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

**Studio → Agent & Maschine → „Agent testen"**: Formularfelder für alle sechs
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
