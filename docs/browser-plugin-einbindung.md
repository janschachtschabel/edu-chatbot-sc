# Chatbot im Browser-Plugin einbinden

Anleitung für die **Entwickler des Browser-Plugins**: das Widget randlos in eine
fremde Seite setzen, es von außen steuern, seine Ereignisse mitlesen und im
Agent-Modus ein maschinenlesbares Ergebnis herausziehen.

Alles hier ist am Quelltext dieses Repositoriums belegt; die Fundstellen stehen
in Klammern. Wo etwas **nicht** geht, steht es ausdrücklich da — eine Zusage, die
sich beim Bauen als unwahr herausstellt, kostet mehr als eine fehlende.

**Verwandte Dokumente**

| Thema | Dokument |
|---|---|
| Agent-Schleife im Detail (Studio, Endpunkt, Deckel, `stop_reason`) | [`agent-modus.md`](agent-modus.md) |
| Warum der Schreibpfad im Browser läuft, und was das den Betreibern zusagt | [`plans/2026-08-12-einbettung-ohne-repo-aenderung.md`](plans/2026-08-12-einbettung-ohne-repo-aenderung.md) |
| Eingefrorener HTTP-Vertrag | [`api/openapi-v1.json`](api/openapi-v1.json) |

---

## 1. Was ausgeliefert wird

Ein **Custom Element** `<boerdi-chat>` in **einer einzigen Datei** — kein
Nachladen von Teilstücken zur Laufzeit, keine externen Schriften, keine
Dritt-Dienste (DSGVO-Vorgabe des Hauses).

| | |
|---|---|
| Stabile Adresse | `https://<chat-host>/widget/boerdi-widget.js` |
| Antwort | **302** auf `…/boerdi-widget.<12-hex>.js`; stabile URL `no-store`, gehashte `immutable` |
| Kopfzeile | `Access-Control-Allow-Origin: *` — das Laden aus fremden Seiten ist der Zweck |
| Umfang | eine Datei `main.js`, gemessen **525 KB** unkomprimiert (Stand 2026-08-13) |
| Isolation | **Shadow DOM** — Stile der Gastseite bluten nicht herein, unsere nicht hinaus |
| Fehlt das Bündel | **503** mit dem Namen des Build-Befehls, nicht 404 |

Belege: `backend/src/boerdi/api/widget.py:107-132`,
`frontend/projects/widget/src/app/widget/widget.component.ts:62`.

### Das Element in die Seite bekommen

Auf einer gewöhnlichen Seite sind es zwei Zeilen:

```html
<script src="https://chat.example.org/widget/boerdi-widget.js" defer></script>
<boerdi-chat api-url="https://chat.example.org"></boerdi-chat>
```

Im **Plugin** kommt eine Hürde dazu, die nicht von uns stammt, sondern von der
Erweiterungs-Plattform: ein Content-Script läuft in einer *isolierten Welt* mit
eigenen JS-Globalen. Ein dort definiertes Custom Element wertet die Elemente im
DOM der Seite nicht auf. Das Bündel muss deshalb in der **Hauptwelt** der Seite
laufen — üblich sind zwei Wege:

* `chrome.scripting.executeScript({ world: 'MAIN', … })` (MV3), oder
* ein `<script src="…">`-Tag injizieren — das unterliegt dann aber der **CSP der
  Gastseite**, und ein striktes `script-src` blockiert es.

> Dieser Absatz beschreibt das Verhalten der Erweiterungs-Plattform, nicht eine
> Eigenschaft unseres Bündels — wir haben ihn hier nicht nachgemessen. Prüft ihn
> gegen eure Zielbrowser. Von unserer Seite steht dem nichts entgegen: das
> Bündel ist eine Datei und wird für jede Herkunft freigegeben.

---

## 2. Randlos den Platz füllen

`embed-mode="frameless"` gibt Rahmen **und Platzierung** an die Gastanwendung ab:
kein Eulen-Knopf, keine eigene Kopfzeile, kein Panel-Rahmen, kein Schlagschatten,
keine Einflug-Bewegung — nur Verlauf und Eingabezeile, im Container des Hosts
(`frontend/projects/widget/src/app/widget/_widget-panel.scss:93-124`).

**Die eine Falle, und sie ist lautlos:** rahmenlos legt das Widget mit dem
Rahmen auch die **eigene Größe** ab. Es füllt `width: 100%` / `height: 100%`
seines Containers. Hat der Container keine Höhe, ist das Element **null Pixel
hoch** — man sieht nichts, und es gibt keine Fehlermeldung.

```html
<!-- Der Kasten gehört DIR: Höhe, Rahmen, Ecken. -->
<div style="block-size: min(32rem, 70vh);
            border: 1px solid #d1d5db; border-radius: .75rem;
            overflow: hidden;">
  <boerdi-chat
    api-url="https://chat.example.org"
    embed-mode="frameless"
    initial-state="expanded"
    show-language-buttons="false"
    show-debug-button="false">
  </boerdi-chat>
</div>
```

`initial-state="expanded"` ist rahmenlos praktisch Pflicht: es gibt keinen
Eulen-Knopf, der das Panel je öffnen würde. (Die Chat-Shell wird rahmenlos
deshalb auch sofort gemountet und nicht erst beim ersten Öffnen —
`widget.component.ts:327`.)

### Als Seitenspalte

Das ist der Fall, den ein Plugin meistens baut. Die Maße kommen aus **eurem**
Stilblatt; unten die Fassung, die auf `/widget/frameless` live läuft
(`backend/src/boerdi/api/widget_demo_html.py:90-99`):

```css
.spalte { block-size: min(32rem, 70vh); border: 1px solid #d1d5db;
          border-radius: .75rem; overflow: hidden; }

@media (min-width: 90rem) {
  .spalte { position: fixed; inset-block: 1.5rem; inset-inline-end: 1.5rem;
            inline-size: 22rem; block-size: auto; }
}
```

Unterhalb der Umbruchbreite ist die Spalte ein gewöhnlicher Kasten im Fluss —
kein Querscrollen, nichts verdeckt. Wer sie fest positioniert, muss dem
Seiteninhalt seinen Platz lassen (die Demo rückt dafür den Textkörper).

### Zum Ansehen

Drei Demo-Seiten am laufenden Backend, jede mit Bedienpult für alle Attribute:

| Seite | Einbau-Lage |
|---|---|
| `/widget/classic` | schwebender Knopf unten rechts |
| `/widget/inline` | rahmenloser Kasten mitten im Text |
| `/widget/frameless` | rahmenlose Spalte neben dem Inhalt |

---

## 3. Alle Parameter

Die 25 Attribute von `<boerdi-chat>`. Quelle der Wahrheit sind die `input()`s in
`widget.component.ts:86-177`; ein Test drüben pinnt den Satz und nennt beim
Bruch die Studio-Tabelle (`studio/src/app/views/widget-contract-data.ts`).

Alle Werte sind HTML-Attribute, also Zeichenketten. Boolesche Attribute nehmen
`"true"`/`"false"`.

### Grundlage

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `api-url` | — | Herkunft des Backends. **Ohne sie läuft nichts.** |
| `embed-mode` | `panel` | `panel` \| `frameless` (§2) |
| `size` | `small` | `small` \| `large` — **nur der Start**, danach gehört die Stufe dem Panel |
| `engine` | leer | `pattern` \| `agent` — leer = Vorgabe aus `01-base/engine` (§4) |
| `position` | `bottom-right` | Ecke des Eulen-Knopfs; rahmenlos wirkungslos |
| `initial-state` | `collapsed` | `collapsed` \| `expanded` |
| `primary-color` | leer | Akzentfarbe; validiert, schlägt bis in die Material-Token durch |
| `greeting` | — | Begrüßung überschreiben (sonst die aus dem Studio) |

### Sitzung

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `persist-session` | `true` | Sitzungs-ID über Seitenwechsel behalten |
| `session-key` | `boerdi_session_id` | Schlüssel im Speicher |
| `session-cookie-domain` | leer | z.B. `.wirlernenonline.de` für Subdomain-Teilung; leer = nur `localStorage`, herkunftsisoliert |
| `session-cookie-max-age` | `2592000` | Lebensdauer in Sekunden (30 Tage) |
| `trusted-domains` | leer | Komma-Liste von Hosts, an die die Sitzungs-ID per `?bsid=` weitergereicht werden darf. **Ergänzt** die Backend-Liste, kürzt sie nie |

### Seitenkontext

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `auto-context` | `true` | Adresse und Titel der Gastseite selbst erkennen |
| `page-context` | — | JSON-Objekt, das die Erkennung ergänzt bzw. ersetzt (§5) |

### Anzeige

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `show-debug-button` | `true` | Debug-Umschalter in der Kopfzeile |
| `show-language-buttons` | `true` | Mikrofon + Vorlesen (Altname, meint die Sprach-**Ausgabe**; zusätzlich an die Backend-Fähigkeit gekoppelt) |
| `inline-result-grouping` | `true` | `false` = flaches Karten-Gitter mit Seitenblättern statt Ergebnis-Boxen |
| `show-cards` | `auto` | `auto` \| `always` \| `never` — `auto` heißt: klein Textlinks, groß Kacheln |
| `theme` | `auto` | `auto` \| `light` \| `dark`. `auto` folgt dem `color-scheme` der Gastseite |
| `language` | leer | `de` \| `en`. Leer = nächstes `[lang]` im DOM, sonst Browser, sonst Deutsch. **Eine Nutzerwahl am Umschalter schlägt dieses Attribut** |

### Integration

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `intercept-edu-sharing-links` | `false` | `true` = Link-Klicks abfangen statt navigieren → Ereignis `linkClicked` mit Pfad+Query |
| `emit-guide-suggestion` | `false` | `boerdi:guide-suggestion` einschalten (§6) |
| `emit-routing-debug` | `false` | `boerdi:routing-debug` einschalten (§6) |
| `ticket` | — | edu-sharing-Ticket der Gastgeberseite. **Für Plugins nicht nutzbar** (§8) |

### Was zur Laufzeit noch wirkt

Nicht jedes Attribut lässt sich nachträglich per `setAttribute` umstellen. Das
ist kein Zufall, sondern jeweils eine Entscheidung im Code:

| Attribut | nach dem Start änderbar? |
|---|---|
| `initial-state` | **ja** — der erste Wert entscheidet den Start, spätere schalten das Panel um (`widget.component.ts:290-297`) |
| `engine`, `language`, `primary-color` | **ja** — hängen an Effects (`widget.component.ts:279-315`) |
| `page-context` | **nein, nicht unmittelbar.** Es hängt an keinem Effect: gelesen wird es in `ngOnInit` und danach nur noch, wenn der URL-Wächter eine Navigation bemerkt (`widget.component.ts:262,384`). Zur Laufzeit nehmt ihr `updateContext()` (§5) |
| `size` | **nein** — Startwert; danach gehört die Stufe dem Umschalter in der Eingabezeile, ein Effect überschriebe jede Handbedienung |
| `ticket` | **nein** — einmal in `ngOnInit` gelesen und sofort aus dem DOM getilgt |

---

## 4. Maschine wählen: Muster oder Agent-Schleife

| | **Muster-Engine** (`pattern`, Vorgabe) | **Agent-Schleife** (`agent`) |
|---|---|---|
| Ablauf | Klassifikator → Musterwahl → gebundene Werkzeugliste | Systemprompt + **voller** Werkzeug-Katalog, freie Schleife |
| Endet bei | einer Antwort | `submit_result`, Prosa, oder einem Deckel |
| Gut für | den Chat mit Menschen | Aufträge ohne Chat-Rahmen, maschinenlesbare Ergebnisse |

Drei Ebenen, von grob nach fein — die feinere gewinnt:

1. **Ganze Anlage** — Studio → *Agent & Maschine* (`01-base/engine`), wirkt ohne
   Neustart.
2. **Je Einbau** — das Host-Attribut `engine="agent"`. Genau dafür gibt es
   das: eine Einbettung ohne Chat-Rahmen will die Schleife oft, ohne dass
   deshalb der ganze Chatbot umgestellt wird — und A/B messen lässt sich nur,
   was sich je Einbau unterscheiden kann.
3. **Je Anfrage** — Kopfzeile `X-Boerdi-Engine: agent`. Undeklariert gelesen,
   steht also nicht im OpenAPI-Dokument; ein unbekannter Wert fällt still auf
   die Vorgabe zurück und bricht nichts.

Details, Deckel (`max_iterations` / `deadline_s` / `token_budget`) und die
Schreib-Regel: [`agent-modus.md`](agent-modus.md).

---

## 5. Anweisungen und Auslöser von außen

### Die JS-API des Elements

Sechs Methoden, auf dem Element-Prototyp
(`frontend/projects/widget/src/element-api.ts:33-40`):

```js
const chat = document.querySelector('boerdi-chat');

chat.openChatbot();     // öffnen, ans Ende scrollen, Eingabe fokussieren
chat.closeChatbot();    // schließen
chat.toggleChatbot();
chat.isChatbotOpen();   // → boolean
chat.resetSession();    // neue Sitzung
chat.updateContext({ … });  // Seitenkontext ergänzen
```

Ruft ihr sie, **bevor** das Element aufgewertet ist, bekommt ihr `undefined`
statt einer Ausnahme — bewusst so, aber es heißt eben auch: nichts ist passiert.
Wartet auf `customElements.whenDefined('boerdi-chat')`.

### Kontext als Anweisung

Der wirksamste Hebel von außen ist der **Seitenkontext**: er sagt dem Bot, worauf
die Person gerade schaut, und geht in Klassifikator *und* Antwort ein.

```html
<boerdi-chat
  api-url="https://chat.example.org"
  auto-context="false"
  page-context='{"page_kind":"collection","collection_id":"…-UUID-…"}'>
</boerdi-chat>
```

`auto-context="false"` schaltet die eigene Erkennung ab; sonst trägt sie Adresse
und Titel der Gastseite zusätzlich bei. Die Felder
(`frontend/projects/ui/src/page-context/page-context-detector.ts:35-66`):

| Feld | Bedeutung |
|---|---|
| `page_kind` | `topic` \| `collection` \| `content` \| `subject` \| `search` \| `other` |
| `node_id` | edu-sharing-UUID eines Einzelmaterials |
| `collection_id` | UUID einer Sammlung |
| `topic_page_slug` | Kürzel einer Themenseite, z.B. `klimawandel` |
| `subject_slug` | Fachkürzel, z.B. `biologie` |
| `search_query` | aktueller Suchbegriff der Gastseite |
| `search_filters` | `{ publisher?: string[] }` |
| `page_text` | Titel + erste ~3 KB sichtbarer Text |
| `page_url`, `page_host` | volle Adresse und Hostname |

`page_kind: "collection"` oder `"topic"` löst zusätzlich einen Vorabruf aus:
Anzahl der Materialien und die **Übersicht der freigegebenen Anleitungen
(Skills)** dieser Sammlung wandern in den Prompt — beide Maschinen bekommen sie,
Muster wie Agent. Den Volltext einer Anleitung holt das Modell danach gezielt
selbst (`search_skill` → `get_skill`).

Zur Laufzeit gibt es **zwei** Wege, und sie tun Verschiedenes
(`frontend/projects/ui/src/shell/lifecycle.ts:182-193`):

| Aufruf | Wirkung |
|---|---|
| `chat.updateContext({…})` | **mergt** in den bestehenden Kontext. Kein Ping, keine Nachricht. |
| SPA-Navigation (erkannt) | **ersetzt** den Kontext (stale IDs raus), setzt das Ping-Gate zurück und bietet eine Kontext-Begrüßung an |

Den zweiten Weg löst das Widget selbst aus: ein Wächter vergleicht alle **1,5 s**
`location.href` (`ui/src/widget/host-bridges.ts:4,97-102`). In einer SPA wie
edu-sharing braucht ihr dafür nichts zu tun.

### Was es nicht gibt

**Eine Nachricht von außen in den Chat schicken, geht nicht.** Die Chat-Shell
hat ein `sendMessage` (`ui/src/shell/chat-shell.component.ts:421`), aber es steht
**nicht** in `FORWARDED_METHODS` — das Element reicht es nicht durch, und die
Hülle hat selbst keins. Es gibt also keinen unterstützten Weg, dem Widget von
der Gastseite aus einen Satz zu diktieren.

Für einen gezielten Auftrag von außen ist der richtige Weg deshalb **nicht** das
Widget, sondern `POST /api/agent` (§7): dort ist „Anweisung rein, Ergebnis raus"
der ganze Vertrag, ohne Chat-Rahmen dazwischen.

---

## 6. Ereignisse mitlesen

Vier Ereignisse, auf `window`, mit `bubbles` und `composed` (sonst käme aus dem
Shadow-Root nichts an). Definition: `ui/src/host-events/event-names.ts:26-53`.

```js
window.addEventListener('boerdi:guide-suggestion', (e) => {
  const { url, title, node_id, node_type, query, alternatives } = e.detail;
});
```

| Ereignis | wann | Nutzlast |
|---|---|---|
| `boerdi:page-action` | der Bot schlägt eine Seiten-Aktion vor | `{action, payload}` — heute gefeuert: `navigate`, `show_results`, `canvas_show_cards` |
| `boerdi:query-meta` | nach jedem Bot-Zug mit Suche — **immer an**, kein Opt-in | `{queries: [{tool_name, query_type, search_term, criteria[], pagination, repository_url, search_url}]}` |
| `boerdi:guide-suggestion` | jeder Zug mit mindestens einem verlinkbaren Treffer — **`emit-guide-suggestion="true"` nötig** | `{url, title, node_id, node_type, query, alternatives[]}` |
| `boerdi:routing-debug` | jeder Bot-Zug — **`emit-routing-debug="true"` nötig** | `{message, pattern, intent, state, persona, tools_called[], rag_areas[], sources[], modifier{tone,length,formality,card_text_mode,override}, signals[]}` |

**Zwei Dinge, an denen man sich sonst die Zähne ausbeißt:**

*Doppelversand.* Solange der ALTE Chatbot parallel läuft, feuert jedes Ereignis
**zweimal** — neu zuerst (`boerdi:…`, das ist der Vertrag), dann noch einmal
unter `badboerdi:…` (das ist die Übergangs-Nachsicht). Hört **nur auf den neuen
Namen**, sonst verarbeitet ihr alles doppelt. Der alte Versand fällt nach dem
Cutover ersatzlos weg.

*`query-meta` kostet nichts extra.* Es ist immer an; `guide-suggestion` und
`routing-debug` sind Opt-in, und bei `false` entsteht weder Ereignis noch
Aufwand.

**Unbekannte `page-action` still übergehen.** Das Schema erklärt ein breiteres
Vokabular, als heute tatsächlich gefeuert wird — `navigate`, `show_collection`,
`show_results`, `share_content` plus vier `canvas_*`
(`backend/src/boerdi/api/schemas.py:294-306`); im Code entstehen davon zur Zeit
nur die drei aus der Tabelle. Behandelt die Liste als offen: was ihr nicht kennt,
ignoriert ihr, statt daran zu scheitern.

### Wer das Element in Angular einbaut

Vier Outputs mit identischer Nutzlast: `linkClicked` (Zeichenkette, nur mit
`intercept-edu-sharing-links`), `guideSuggestion`, `routingDebug`, `queryMeta`.

`page-action` ist **nicht** dabei — es erreicht eine Gastseite ausschließlich als
`window`-Ereignis. (Die Tabelle des ALTEN Chatbots führte es fälschlich als
Output; hier ist es richtiggestellt.)

---

## 7. Agent-Modus: strukturiertes Ergebnis

`POST /api/agent` ist der Weg für Gastgeber **ohne** Chat-Rahmen. Keine Sitzung,
keine Begrüßung, keine Muster — Anweisung rein, Text plus freies JSON raus.

### Zugang

Drei Wege, in dieser Reihenfolge geprüft
(`backend/src/boerdi/api/turn_auth.py`):

1. `AGENT_OPEN=true` — der ausdrückliche Ausweg für Testläufe. **Vorgabe: aus.**
2. Kopfzeile `WLO-Access-Block` mit **persönlicher** Anmeldung. Der ausdrücklich
   anonyme Block (`wlo-anon.v1`) zählt nicht.
3. Kopfzeile `X-Studio-Key` — Server-zu-Server.

**Für ein Plugin ist Weg 2 der vorgesehene.** Der Studio-Schlüssel ist der
Admin-Schlüssel und hat in einem Browser nichts zu suchen; genau deshalb wurde
der Endpunkt 2026-08-12 für die persönliche Anmeldung geöffnet — und im selben
Zug gedrosselt (`RATE_LIMIT_CHAT`, Vorgabe **20/Minute je IP**, sonst `429` mit
`X-RateLimit-*`). Die Prüfung der Kopfzeile ist eine **Form-, keine
Echtheitsprüfung**: belegen kann einen Zugangsblock nur der MCP-Server. Die
Mengenbremse ist die Kostenschranke, nicht der Riegel.

### Der Aufruf

```js
const antwort = await fetch('https://chat.example.org/api/agent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'WLO-Access-Block': zugangsblock,
  },
  body: JSON.stringify({
    instruction: 'Prüfe diese Inhalte auf Sachrichtigkeit und begründe kurz.',
    node_ids: [knotenId],
    collection_id: sammlungsId,
    result_schema: {
      type: 'object',
      properties: {
        note:        { type: 'integer', minimum: 0, maximum: 5 },
        begruendung: { type: 'string' },
      },
      required: ['note', 'begruendung'],
    },
  }),
});

if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
const { text, result, stop_reason, iterations, tools_called } = await antwort.json();
```

| Eingabe | Pflicht | Bedeutung |
|---|---|---|
| `instruction` | **ja** | Die Aufgabe im Klartext, ≤ 20 000 Zeichen, nicht leer |
| `collection_id` | nein | Sammlung, aus der die Anleitungen kommen — vorab über `get_skill_registry` aufgelöst |
| `node_ids` | nein | Die Inhalte, um die es geht — vorab über `get_nodes_details`, **höchstens 50** |
| `result_schema` | nein | JSON-Schema. Reist **wörtlich** in die Parameter des Abschluss-Werkzeugs `submit_result` |
| `write_mode` | nein | `propose` \| `execute`. `execute` verlangt immer eine angemeldete Person — sonst still `propose` |
| `allow_curation` | nein | `false` nimmt die kuratierenden Werkzeuge heraus, auch mit Anmeldung |
| `locale` | nein | `de` \| `en` |

### Das Ergebnis auslesen

```jsonc
{
  "text": "Beide Inhalte sind fachlich korrekt. Bei …",
  "result": { "note": 4, "begruendung": "…" },   // null OHNE result_schema
  "stop_reason": "submit",
  "iterations": 3,
  "tools_called": ["get_nodes_details", "get_wlo_content_text", "submit_result"]
}
```

**`stop_reason` gehört zur Auswertung, nicht ins Protokoll.** Ein Lauf, der an
der Frist abgeschnitten wurde, sähe von außen sonst aus wie einer, der fertig
geworden ist:

| `stop_reason` | heißt | `result` verlässlich? |
|---|---|---|
| `submit` | `submit_result` gerufen — die Ziellinie | **ja** |
| `text` | Prosa-Antwort ohne Werkzeug | nein (`null`) |
| `max_iterations` | Rundendeckel erreicht | nein |
| `deadline` | Frist abgelaufen | nein |
| `token_budget` | Budget aufgebraucht | nein |
| `no_progress` | Stillstand | nein |
| `error` | Fehler in der Schleife | nein |

Kurz: **prüft `stop_reason === 'submit'`, bevor ihr `result` benutzt.** Ohne
`result_schema` gibt es ohnehin nur `text`.

### Fortschritt zeigen

`POST /api/agent/stream`, gleicher Rumpf, Antwort als Server-Sent-Events:
`connected` → beliebig viele `phase` → `result` **oder** `error`. Ein
`end`-Rahmen kommt bewusst nicht, und **Token liefert der Strom nicht** — nur
Phasen. Wer nur das Ergebnis will, nimmt den normalen Endpunkt.

---

## 8. Schreiben — und warum das Plugin keinen Ausweis anfassen soll

Ein Plugin *könnte* mit der `cookies`-Berechtigung die `JSESSIONID` der
edu-sharing-Sitzung auslesen (`HttpOnly` schützt davor nicht) und sie an ein
Backend schicken. **Tut das nicht — wir nehmen sie auch nicht entgegen.** Das
Plugin würde damit zum Verwahrer eines Ausweises mit vollen Kontorechten und
ohne Ablaufdatum, und der Gewinn wäre null.

Der vorgesehene Weg: das Widget läuft **in** der edu-sharing-Seite, also
same-origin. Ein gewöhnliches `fetch` trägt die Sitzungs-Cookies automatisch mit,
ohne dass Code sie je anfasst. Der MCP-Server *bereitet* die Änderung vor
(Methode, Pfad, Rumpf), das Backend reicht sie als `prepared_write` durch, und
das Widget setzt sie ab — hinter einem Riegel aus Herkunftsprüfung,
Erlaubnisliste (heute drei Einträge) und einer Wer-bin-ich-Abfrage über die
gemeldete `authority`, nie über den Statuscode. Nichts wird ohne Bestätigung
geschrieben.

Das `ticket`-Attribut aus §3 gehört **nicht** hierher: es ist die Betriebsform
„das Repositorium bettet selbst ein und templatet den Ausweis der angemeldeten
Person serverseitig hinein". Ein Browser kann sich ein solches Ticket nirgends
holen — gemessen, es gibt in allen 317 API-Pfaden keinen Endpunkt dafür.

Volle Herleitung samt Messungen:
[`plans/2026-08-12-einbettung-ohne-repo-aenderung.md`](plans/2026-08-12-einbettung-ohne-repo-aenderung.md).

---

## 9. Häufige Fehler

| Symptom | Ursache |
|---|---|
| Der Kasten bleibt leer | `embed-mode="frameless"` ohne Höhe am Container (§2) |
| Element bleibt ein leeres Tag | Bündel lief in der isolierten Welt des Content-Scripts, nicht in der Hauptwelt (§1) |
| Der Chat startet geschlossen | `initial-state="expanded"` fehlt |
| Jedes Ereignis kommt doppelt | Auf `boerdi:…` **und** `badboerdi:…` gehört (§6) |
| `engine="agent"` wirkt nicht | Ausgeliefertes Widget-Bündel älter als das Attribut → neu bauen |
| `page-context` zur Laufzeit gesetzt, nichts passiert | Das Attribut wird nach dem Start nicht mehr gelesen — nehmt `updateContext()` (§3, §5) |
| `linkClicked` feuert nie | `intercept-edu-sharing-links="true"` fehlt |
| `guide-suggestion` feuert nie | `emit-guide-suggestion="true"` fehlt (Opt-in) |
| Klick auf einen Link der **Gastseite** bekommt kein `?bsid=` | Der Klick-Wächter greift nur im Shadow-Root des Widgets — die Navigation der Gastseite bleibt unangetastet. Wer die ID braucht, hängt sie selbst an |
| `result` ist `null` | Kein `result_schema` mitgegeben — oder `stop_reason !== 'submit'` |
| 401 / 403 an `/api/agent` | Keiner der drei Zugangswege greift (§7) |
| 429 | Drosselung, `RATE_LIMIT_CHAT` |
| 503 auf `/widget/boerdi-widget.js` | Bündel nicht gebaut — die Antwort nennt den Befehl |
