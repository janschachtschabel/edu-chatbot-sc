# Vorschlag: neues MCP-Werkzeug `get_node_collections`

**Stand:** 2026-08-01 · **Alles hierin live gemessen** gegen
`wlo-mcp.87.106.195.152.nip.io/mcp` und `redaktion.openeduhub.net`.

---

## 1. Die Lücke

Die Frage **„in welcher Sammlung liegt dieses Material?"** ist über den MCP
derzeit nicht beantwortbar:

| Weg | Ergebnis |
|---|---|
| `get_node_details(includeParents=true)` | `parents: []` — bei **jedem** getesteten Inhalt |
| `get_node_breadcrumb(nodeId=<Material>)` | „Kein Pfad … verfügbar (evtl. ein Datei-Knoten)" |
| `includeRaw` | keine `ccm:*`-Felder (siehe §6) |

Getestet an vier Materialien, darunter zwei, die **nachweislich** in der Sammlung
„Biologie-Breakouts" liegen — sie kamen aus deren eigenem
`get_collection_contents`-Listing. Bei **Sammlungs**-Knoten funktioniert
`includeParents`; nur der dokumentierte Anwendungsfall („find which Sammlung a
content item is in") ist der, der nicht geht.

**Für einen LLM-Client ist der stille Leerfall die eigentliche Gefahr:** das
Modell antwortet daraufhin „liegt in keiner Sammlung". Eine falsche Auskunft ist
schlimmer als eine fehlende. Wir haben den Parameter deshalb bewusst nicht an
unser Modell durchgereicht.

---

## 2. Warum ein eigenes Werkzeug — und kein Flag

`get_node_details` ist laut eigener Beschreibung **„fast by default (~0,3 s):
metadata only"**. Genau dafür wird es im Zug oft und beiläufig aufgerufen. Die
Sammlungs-Zugehörigkeit kostet aber **zwei zusätzliche REST-Aufrufe** (§4) — als
Flag würde sie den schnellen Pfad für alle verteuern, obwohl die Frage selten
gestellt wird.

Hinzu kommt die Richtung der Nutzung: in der Praxis läuft fast alles
**Sammlung → Inhalt** (Drilldown, Themenseiten, Suche). Der Rückwärts-Weg ist ein
Sonderfall — und Sonderfälle gehören in ein eigenes, klar benanntes Werkzeug, das
das Modell nur dann wählt, wenn die Frage wirklich gestellt wurde.

**Namensvorschlag: `get_node_collections`.** Es steht dann direkt neben
`get_node_breadcrumb`, und die beiden ergänzen sich zu einer vollständigen
Antwort auf „wo ist das eingeordnet?":

| Knotentyp | Werkzeug |
|---|---|
| Sammlung | `get_node_breadcrumb` — Pfad von der Wurzel |
| Material | `get_node_collections` — die Sammlungen, die es führen |

---

## 3. Vorgeschlagenes Schema

```jsonc
{
  "name": "get_node_collections",
  "description":
    "Zeigt, in WELCHEN WLO-Sammlungen ein Material geführt wird — die Antwort auf \
'wo ist das eingeordnet?' / 'wo finde ich mehr davon?'. Gilt für Material-/Inhalts-Knoten; \
für die Einordnung einer SAMMLUNG im Themenbaum ist get_node_breadcrumb zuständig. \
Ein Material kann in mehreren Sammlungen liegen, in keiner ist ebenfalls normal.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "nodeId": {
        "type": "string",
        "description": "nodeId des Materials. Die ID aus einem Sammlungs-Listing \
funktioniert genauso wie die aus einer Suche — der Server löst intern auf."
      },
      "outputFormat": { "type": "string", "enum": ["markdown", "json"], "default": "markdown" }
    },
    "required": ["nodeId"]
  }
}
```

**Der Satz zu `nodeId` ist der wichtigste am ganzen Vorschlag.** Siehe §4.

### Antwort (`outputFormat: "json"`)

```jsonc
{
  "nodeId": "5a19e0e1-92ec-…",        // die aufgelöste ORIGINAL-ID
  "requestedNodeId": "c2e9b9ca-…",    // was der Aufrufer geschickt hat
  "wasReference": true,               // hilft beim Debuggen von Client-Fehlern
  "count": 2,
  "collections": [
    { "nodeId": "9eed3b28-…", "title": "Ernährung",          "topicPageUrl": null },
    { "nodeId": "e97d981a-…", "title": "Biologie-Breakouts",  "topicPageUrl": null }
  ]
}
```

Bei null Treffern **nicht** stumm ein leeres Array liefern, sondern wie bei
`get_wlo_content_text` einen benannten Grund mitgeben:

```jsonc
{ "count": 0, "collections": [], "reason": "not_in_any_collection" }
```
bzw. `"node_not_found"`. Der Unterschied zwischen „liegt in keiner Sammlung" und
„diesen Knoten gibt es nicht" ist für die Formulierung der Antwort entscheidend —
dieselbe Begründung wie bei den `reason`-Codes des Volltext-Werkzeugs.

---

## 4. Umsetzung — zwei Aufrufe, und ein Fallstrick

### Der Fallstrick zuerst

```
GET /usage/v1/usages/node/{ORIGINAL_ID}/collections   →  ✅ alle Sammlungen
GET /usage/v1/usages/node/{REFERENCE_ID}/collections   →  ❌ leeres Array, KEIN Fehler
```

edu-sharing legt beim Einsortieren in eine Sammlung einen **Reference-Knoten** mit
eigener nodeId an; das Original bleibt am ursprünglichen Ort. `children/references`
— und damit auch `get_collection_contents` im MCP — geben die **Reference**-IDs
zurück. Genau die liefern beim Usage-Lookup nichts.

Das ist mit hoher Wahrscheinlichkeit auch die Ursache des heutigen
`includeParents`-Verhaltens.

### Ablauf

```ts
async function getNodeCollections(nodeId: string) {
  // 1. Reference → Original auflösen. IMMER, nicht nur bei leerem Ergebnis.
  const meta = await es.get(
    `/node/v1/nodes/-home-/${nodeId}/metadata?propertyFilter=-all-`);
  const original: string = meta.node.originalId || nodeId;

  // 2. Usages abfragen und auf Sammlungen reduzieren.
  const usages = await es.get(
    `/usage/v1/usages/node/${original}/collections`);   // Array

  const collections = (usages ?? [])
    .filter(u => u.collectionUsageType === "ACTIVE")
    .map(u => formatNode(u.collection));                // eure bestehende Normalisierung

  return { nodeId: original, requestedNodeId: nodeId,
           wasReference: original !== nodeId, collections };
}
```

`formatNode` wiederverwenden lohnt: `u.collection` ist ein **vollständiger
Knoten** (Titel, Beschreibung, Icon, Zugriff, …), also dieselbe Form, die eure
Such-Werkzeuge ohnehin normalisieren. Damit passt die Ausgabe ohne Sonderweg zu
allen anderen Antworten.

### Belegte Kette (nachvollziehbar ohne Login)

```
Reference    c2e9b9ca-8389-494f-ba24-f45da654d9c2   (aus get_collection_contents)
  originalId     → 5a19e0e1-92ec-47db-9a19-779d4d576485
  ccm:original   → ['5a19e0e1-92ec-…']
  cclom:location → ['ccrep://local/5a19e0e1-92ec-…']
  aspects        → enthält ccm:io_reference

GET https://redaktion.openeduhub.net/edu-sharing/rest/usage/v1/usages/node/5a19e0e1-92ec-47db-9a19-779d4d576485/collections
  → HTTP 200, 2 Einträge, collectionUsageType=ACTIVE
     „Ernährung"          9eed3b28-4aba-4316-a50a-56d5b594bb40
     „Biologie-Breakouts" e97d981a-b1bc-4360-81e7-2fa54c88bfee
```

Beide Aufrufe liefen **ohne Authentifizierung** mit HTTP 200.

### Kosten

Zwei REST-Roundtrips. Der erste (Metadaten) entfällt, wenn ihr die
`originalId`-Auflösung ohnehin cached — sie wird für Schreibvorgänge an
Sammlungs-Inhalten sowieso gebraucht.

### Was NICHT tun

* **Kein stiller Fallback** „erst mit der übergebenen ID probieren, bei leerem
  Ergebnis auflösen". Ein leeres Array ist ein legitimes Ergebnis („liegt in
  keiner Sammlung"); es als „vermutlich Reference" zu deuten, macht den
  Normalfall langsam und den Sonderfall mehrdeutig. Immer zuerst auflösen.
* **Nicht an `get_node_details` anhängen** — siehe §2.
* `/usage/v1/usages/node/{id}` (ohne `/collections`) liefert **alle** Usages,
  auch Kurse und Fremd-Apps. Für diesen Zweck ist die `/collections`-Variante
  richtig.

---

## 5. Was mit `includeParents` geschehen sollte

Zwei saubere Wege, einer davon reicht:

* **Entfernen**, wenn `get_node_collections` kommt — dann gibt es genau einen Weg
  zur Antwort statt eines funktionierenden und eines stillen.
* **Oder** für Inhalts-Knoten intern über denselben Usage-Weg füllen. Dann bitte
  zusätzlich: `parents[0]` ist derzeit **der Knoten selbst** (der funktionierende
  Sammlungs-Fall liefert einen Pfad *einschließlich* des eigenen Knotens). Wer
  `parents[0]` als „Elternknoten" liest, bekommt sich selbst zurück.

Nicht empfehlenswert ist der Status quo: ein Flag, das dokumentiert ist, keinen
Fehler wirft und trotzdem nie das Versprochene liefert. Genau daran hätten wir
uns fast eine falsche Nutzerauskunft eingehandelt.

---

## 6. Vier weitere Beobachtungen aus derselben Runde

1. **`includeRaw` hält seine Beschreibung nicht.** Versprochen sind „the original
   `ccm:*` / `cclom:*` property URIs"; geliefert werden fünf Vokabular-Felder in
   URI-Form (`disciplines`, `educationalContexts`, `learningResourceTypes`,
   `license`, `userRoles`). Der Property-Bag ist über den MCP nicht erreichbar —
   entweder die Beschreibung anpassen oder die Felder wirklich durchreichen.
2. **Widerspruch zwischen zwei Beschreibungen.** `search_wlo_collections` sagt
   „In WLO ist eine Sammlung dasselbe wie eine Themenseite";
   `search_wlo_topic_pages` sagt „sucht Sammlungen und prüft dann, WELCHE davon
   eine Themenseite haben". Gemessen bei „Mathematik": 5 Sammlungen, 1
   Themenseite. Ein LLM-Client, der Beschreibungen ernst nimmt, wird hier
   fehlgeleitet — uns hätte es fast eine bewusste Korrektur gekostet.
3. **`find_wlo_skills` steht in `tools/list`, ist aber nicht konfiguriert.** Jeder
   Aufruf endet mit „Keine Skill-Sammlung konfiguriert. Setze
   `WLO_SKILLS_COLLECTION_ID`…". Vorschlag: bis zur Konfiguration aus der
   Werkzeugliste ausblenden — sonst bietet jeder Client ein Werkzeug an, das
   niemals funktioniert.
4. **Ein unbekannter Knoten ergibt HTTP 500 statt 404.** Beim Usage-Endpunkt auf
   dem Staging-Repository (`repository.staging.openeduhub.net`) kam für eine
   fremde nodeId HTTP 500; die OpenAPI-Spezifikation sieht dafür 404 vor. Das
   betrifft die edu-sharing-Seite, nicht den MCP — aber es macht die
   Fehlerbehandlung im MCP schwerer, wenn „gibt es nicht" nicht von „kaputt"
   zu trennen ist.

---

## 7. Nutzen für den Chatbot (zur Priorisierung)

Ehrlich eingeordnet: **kein Blocker.** Unsere Abläufe verlaufen fast
ausschließlich Sammlung → Inhalt; die Rückwärtsfrage stellt der Bot heute
nirgends. Sinnvoll wäre das Werkzeug für drei Dinge, die wir bisher nicht
anbieten:

* „Wo finde ich mehr davon?" — von einem gefundenen Material zur kuratierten
  Sammlung, in der es steckt (redaktionell stärker als eine zweite Suche).
* Einordnung eines Treffers im Gespräch („das stammt aus der Sammlung X").
* Der Sprung vom Material zu einer Themenseite, wenn die führende Sammlung eine
  hat.

Das ist Komfort, keine Grundfunktion — entsprechend zu priorisieren.
