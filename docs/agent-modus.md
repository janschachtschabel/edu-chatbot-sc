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
mode: agent            # pattern | agent | hybrid

agent:
  max_iterations: 30     # 1 . 50
  deadline_s: 900        # 5 . 1800
  token_budget: 900000   # ≥ 1000
  write_mode: propose    # propose | execute
  safety: true
```

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

## Master-Skill als Prompt-Kopf (2026-08-18)

Im Agent- **und** Hybrid-Modus kann eine im Repositorium gepflegte
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

**Wenn der Abruf scheitert** — MCP weg, Knoten gelöscht, leerer Text — läuft der
Zug **ohne** Anleitung weiter, mit einer Warnung im Log. Ein Fehlschlag wird
nicht zwischengespeichert, damit eine kurze Störung nicht eine Viertelstunde
nachwirkt. Der Erfolgsfall bleibt 15 Minuten im Prozess: je Zug erneut zu holen
wäre bei 1,2–23,3 s je MCP-Aufruf unbrauchbar.

## Interne Wissensdatenbank (2026-08-18)

Bis zu diesem Tag hatte die Agent-Schleife **gar kein** internes Wissen: das
Werkzeug `query_knowledge` wird ausschließlich im Muster-Weg gebaut, hier lief
also jede Frage nach WLO, OER oder edu-sharing ins Modellgedächtnis. Seither
liegt `wissen_suchen` im Werkzeugsatz — sichtbar, sobald in
`05-knowledge/rag-config` Bereiche gepflegt sind.

| | Muster-Weg | Agent und Hybrid |
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
  agent: false      # Agent + Hybrid: gar nicht
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
Agent und Hybrid:

| Attribut | Wirkung |
|---|---|
| `tool-mode="read-only\|curate\|full"` | nimmt die verbotenen Werkzeuge aus der Liste **und** sagt es dem Modell |
| `quick-replies='["…","…"]'` | erzwungene Schnellantworten je Zug; schlagen Generator, Canvas und Policy |
| `inline-result-grouping="false"` | war bis dahin rein visuell; jetzt weiß das Modell, dass es die Gliederung selbst schreiben muss |

Der Block dazu steht als dritte System-Nachricht — hinter dem Master-Skill, vor
dem Seitenkontext — und **nur bei Abweichung**: ein Satz über den Normalfall
kostete in jedem Zug Token und sagte nichts.
