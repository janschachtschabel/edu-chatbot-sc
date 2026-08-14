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
| `page-context` | **nein, nicht unmittelbar.** Es hängt an keinem Effect: gelesen wird es in `ngOnInit` und danach nur noch, wenn der URL-Wächter eine Navigation bemerkt (`widget.component.ts:262,384`). Zur Laufzeit nehmt ihr `replaceContext()` bzw. `updateContext()` (§5) |
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

Sieben Methoden, auf dem Element-Prototyp
(`frontend/projects/widget/src/element-api.ts:40-48`):

```js
const chat = document.querySelector('boerdi-chat');

chat.openChatbot();     // öffnen, ans Ende scrollen, Eingabe fokussieren
chat.closeChatbot();    // schließen
chat.toggleChatbot();
chat.isChatbotOpen();   // → boolean
chat.resetSession();    // neue Sitzung
chat.updateContext({ … });   // Seitenkontext ERGÄNZEN (mergt)
chat.replaceContext({ … });  // Seitenkontext ERSETZEN (wie eine Navigation)
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

**Das gilt zur Laufzeit genauso.** Der Vorabruf hängt am Kontext, nicht am
Startvorgang: ein `replaceContext({page_kind:'collection', collection_id:'…'})`
mitten in der Sitzung schaltet den Chat ab dem nächsten Zug auf die Anleitungen
dieser Sammlung um. Für ein Plugin ist das der eine Hebel, der zählt — die
`collection_id` ist der Schlüssel zu den Skills, alles andere ist Beiwerk:

```js
// Die Person hat im Tab eine Sammlung offen → der Chat arbeitet ab jetzt
// mit deren Anleitungen.
chat.replaceContext({
  page_kind: 'collection',
  collection_id: 'f35c17d1-a29e-4b26-9d22-802682fad43d',  // „Geometrische Optik"
  page_url: tab.url,
  page_host: new URL(tab.url).hostname,
});
```

Zwei Dinge, die dabei oft falsch erwartet werden:

* **Die Übersicht nennt nur Titel, keine `nodeId`s** — bis zu 100, und darüber
  gekappt (`services/page_context.py:388-432`). Das Modell holt sich die ID über
  `search_skill` und den Volltext über `get_skill`. Das ist ein Aufruf mehr und
  gewollt: 100 Titel sind eine A4-Seite, 100 Titel mit IDs wären gut zwei.
* **Eine Themenseite ist eine Sammlung** — `page_kind: 'topic'` mit derselben
  `collection_id` führt zu denselben Anleitungen. Ihr müsst nicht unterscheiden.

Zur Laufzeit gibt es **zwei** Wege, und sie tun Verschiedenes
(`frontend/projects/ui/src/shell/lifecycle.ts:182-193`):

| Aufruf | Wirkung |
|---|---|
| `chat.updateContext({…})` | **mergt** in den bestehenden Kontext. Kein Ping, keine Nachricht. |
| `chat.replaceContext({…})` | **ersetzt** den Kontext (alte IDs raus), setzt das Ping-Gate zurück und bietet eine Kontext-Begrüßung an |
| SPA-Navigation (erkannt) | dasselbe wie `replaceContext`, nur vom Widget selbst ausgelöst |

Den letzten Weg löst das Widget selbst aus: ein Wächter vergleicht alle **1,5 s**
`location.href` (`ui/src/widget/host-bridges.ts:4,97-102`). In einer SPA wie
edu-sharing braucht ihr dafür nichts zu tun.

**Ergänzen oder ersetzen — die Wahl ist nicht kosmetisch.** `updateContext`
lässt stehen, was ihr nicht erwähnt. Wechselt die Person den Tab und ihr schickt
nur die neue `collection_id`, bleiben `node_id`, `search_query` und `page_url`
des vorigen Tabs im Kontext: der Bot spricht dann über zwei Seiten gleichzeitig.
Für einen Seitenwechsel ist `replaceContext` das Richtige — und nur dieser Weg
lässt den Bot die neue Seite auch von sich aus begrüßen.

### Der Sonderfall Seitenleiste (und warum der erste Versuch scheiterte)

Läuft das Widget in einer **Erweiterungs-Seitenleiste**
(`chrome-extension://<id>/sidebar/index.html`), gilt etwas, das auf einer
gewöhnlichen Gastseite nie auffällt: **die Leiste navigiert nicht.** Sie zeigt
einen fremden Tab an, ihre eigene Adresse bleibt dieselbe. Damit fallen zwei der
drei Wege aus, über die sonst ein Kontext hereinkommt:

| Weg | in der Seitenleiste |
|---|---|
| Attribut `page-context` | **nur beim Mounten.** Es wird in `ngOnInit` gelesen; ein späteres `setAttribute` bleibt folgenlos (§3) |
| URL-Wächter | **feuert nie** — `location.href` der Leiste ändert sich nicht |
| `replaceContext()` / `updateContext()` | **funktioniert**, und ist damit der einzige Weg für jeden Tab-Wechsel |

Dazu kam bis 2026-08-14 ein Fehler auf **unserer** Seite: die eigene Erkennung
(`auto-context`, Vorgabe an) nahm die Erweiterungs-Kennung als Hostnamen. Der Bot
begrüßte die Person dann mit *„Du bist auf dcchajcmmghejkhjmllhnmaggocmmjck — das
gehört nicht zu WLO."* Behoben: der Detektor beachtet nur noch `http`/`https`;
bei `chrome-extension:`, `moz-extension:`, `file:` und `about:` trägt er nichts
bei (`ui/src/page-context/page-context-detector.ts:78-90`). Was ihr mitgebt,
steht damit allein.

**Das Rezept:**

```js
// 1. Element bauen und den Kontext SCHON AM ELEMENT setzen — vor dem Einhängen.
const chat = document.createElement('boerdi-chat');
chat.setAttribute('api-url', 'https://chat.example.org');
chat.setAttribute('embed-mode', 'frameless');
chat.setAttribute('initial-state', 'expanded');
chat.setAttribute('auto-context', 'false');          // die Leiste ist nicht die Seite
chat.setAttribute('page-context', JSON.stringify(ctxFuerTab(aktiverTab)));
container.appendChild(chat);

// 2. Bei JEDEM Tab-/Seitenwechsel: ersetzen, nicht ergänzen.
await customElements.whenDefined('boerdi-chat');
chrome.tabs.onActivated.addListener(async () => {
  chat.replaceContext(ctxFuerTab(await aktivenTabHolen()));
});

// Aus einer Tab-URL wird der Kontext genauso gebaut wie sonst aus der Adresse
// der Gastseite — die Feldnamen stehen in der Tabelle oben.
function ctxFuerTab(tab) {
  const u = new URL(tab.url);
  const cid = u.searchParams.get('collectionId') ?? u.searchParams.get('id');
  return {
    page_kind: u.pathname.includes('/topic-pages') ? 'topic' : cid ? 'collection' : 'other',
    ...(cid ? { collection_id: cid } : {}),
    page_url: tab.url,
    page_host: u.hostname,
  };
}
```

Zwei Feinheiten, die Zeit sparen:

* **`auto-context="false"` ist hier keine Empfehlung, sondern nötig** — sonst
  mischt die Erkennung der Leiste (heute: nichts, früher: die Kennung) in euren
  Kontext hinein.
* Schickt `page_url` und `page_host` **mit**. Ihr seid die Einzigen, die sie
  kennen; ohne sie kann der Bot nicht beurteilen, ob die Person auf einer
  WLO-Seite steht oder auf einer fremden, die man vorschlagen könnte (M20).

### Den Chat auf ein Thema starten: `startTask`

```js
const chat = document.querySelector('boerdi-chat');
chat.replaceContext({ collection_id: 'a1b2c3…', page_text: seitentext });
chat.startTask('Fasse zusammen, worum es auf dieser Seite geht.');
```

Der Satz **erscheint im Verlauf**, aber als eigene Auftrags-Blase mit der Zeile
„Auftrag der Seite" — gestrichelt, ungetönt, klar keine Nutzernachricht.
Unsichtbar wäre bequemer und unehrlich: die Person sähe eine Antwort auf eine
Frage, die sie nie gestellt hat. Danach ist es eine **gewöhnliche
Unterhaltung** — der Auftrag ist der erste Zug, nicht ein Modus.

Zwei Dinge, die in einer Seitenleiste zählen:

* **Kontext zuerst, dann der Auftrag.** `startTask` schickt sofort; was der
  Agent wissen soll, muss vorher gesetzt sein.
* **Ist das Panel zu, öffnet es sich.** Und ist die Shell im Panel-Betrieb noch
  nicht gemountet (beim ersten Aufruf der Normalfall), wird der Auftrag
  **gehalten** und läuft nach dem Mount los. Ein still verschluckter
  Startbefehl wäre schlimmer als gar keiner.

`ui/src/shell/chat-shell.component.ts` (`startTask`) ·
`widget/src/app/widget/widget.component.ts` (Warteschlange).

### Was es nicht gibt

**Eine gewöhnliche Nachricht von außen einschleusen, geht weiterhin nicht.**
`sendMessage` steht nicht in `FORWARDED_METHODS`. Der unterstützte Weg ist
`startTask` — und der ist bewusst als Auftrag markiert. Wer eine Antwort ganz
ohne Chat-Rahmen will, nimmt `POST /api/agent` (§7).

---

## 6. Ereignisse mitlesen

Fünf Ereignisse, auf `window`, mit `bubbles` und `composed` (sonst käme aus dem
Shadow-Root nichts an). Definition: `ui/src/host-events/event-names.ts`.

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
| `boerdi:agent-result` | jeder Zug — **`result-schema` gesetzt UND `engine="agent"` nötig** (§7a) | `{result, stop_reason}`; `result` ist `null`, wenn dieser Zug keins hergab |

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

## 7a. Chat-Fenster MIT strukturiertem Ergebnis

Der Fall, für den es beides braucht: die Person soll mitreden **und** ihr wollt
am Ende maschinenlesbare Daten. Das geht seit 2026-08-14 in einem Stück.

```html
<boerdi-chat
  api-url="https://chat.example.org"
  engine="agent"
  result-schema='{"type":"object",
                  "properties":{"taxon_id":{"type":"string",
                    "description":"Die Vokabular-URI der Fachzuordnung"}},
                  "required":["taxon_id"]}'>
</boerdi-chat>
```

```js
const chat = document.querySelector('boerdi-chat');

// 1. Kontext: Sammlung (holt deren Skills vorab) + Seitentext.
chat.replaceContext({ collection_id: sammlungsId, page_text: seitentext });

// 2. Auftakt.
chat.startTask('Welchem Fach ordnest du diese Seite zu?');

// 3. Mitlesen — bei JEDEM Zug, auch bei denen, die die Person selbst tippt.
window.addEventListener('boerdi:agent-result', (e) => {
  const { result, stop_reason } = e.detail;
  if (result) uebernehmen(result.taxon_id);
  else if (stop_reason === 'deadline') hinweisAnzeigen('Zeit war zu knapp');
});
```

**Vier Dinge, die euch sonst kosten:**

* **`engine="agent"` ist Pflicht.** Ohne sie antwortet die Muster-Maschine, und
  das Schema wirkt **gar nicht** — kein `result`, kein Ereignis. Das Backend
  schreibt dann eine Warnzeile ins Protokoll (`nodes/respond.py`), aber im
  Browser seht ihr nur Stille. Setzt beides oder keins.
* **Jeder Zug kostet extra.** Mit Schema hängt der Lauf einen zusätzlichen
  Modellzug an (2–9 s gemessen) — auch bei „Danke!". Deshalb ist es opt-in je
  Einbau und nicht die Vorgabe.
* **`result` ist je Zug optional.** „Hallo" ergibt keine `taxon_id`. Euer Code
  muss `null` aushalten; der `stop_reason` sagt, ob nichts da war (`text`) oder
  ob der Lauf an einen Deckel stieß (`deadline`, `max_iterations`, …).
* **Das Attribut ist eine Zeichenkette.** Attribute eines Custom Elements sind
  immer Strings — achtet auf die Anführungszeichen (im Beispiel außen `'`,
  innen `"`). Kaputtes JSON kippt den Chat **nicht**: es gilt als „kein Schema",
  und in der Browser-Konsole steht eine `console.warn`-Zeile. Das ist die
  einzige Stelle, an der ihr den Tippfehler bemerkt — von außen sieht ein
  kaputtes Attribut sonst genauso aus wie ein weggelassenes.

Das Schema reist **wörtlich** in die Parameter des Abschluss-Werkzeugs. Zwei
Folgen: seine `description`-Texte liest das Modell (schreibt sie also als
Anweisung, nicht als Notiz für euch), und es ist auf **10 000 Zeichen**
gedeckelt — darüber lehnt das Backend die Anfrage mit 422 ab, statt ein halbes
Schema zu verwenden, das eine andere Form verlangen würde als ihr wolltet.

**In Angular** gibt es dieselbe Meldung als Output `agentResult`.

### Zum Anfassen: `examples/chrome-plugin/`

Genau dieser Abschnitt als lauffähige Erweiterung — eine Seitenleiste mit
Steuerung für Kontext (automatisch · manuell · aus), Auftrag, Schema und einer
Liste, die je Zug zeigt, was strukturiert herauskommt. Kein Build, keine
Abhängigkeiten; `examples/chrome-plugin/README.md` erklärt das Einrichten.

**Ein Punkt daraus, der jede Erweiterung betrifft:** Manifest V3 verbietet
nachgeladenen Code. In einer Erweiterungs-**Seite** (Seitenleiste, Popup,
Options-Seite) gilt `script-src 'self'` — das Bündel muss also mitgeliefert
und bei Backend-Updates neu geholt werden. Nur wenn ihr das Widget in die
**Gastseite** einhängt (§1), darf der Skript-Tag auf euer Backend zeigen.

---

## 7. Agent-Modus ohne Chat: `POST /api/agent`

`POST /api/agent` ist der Weg für Gastgeber **ohne** Chat-Rahmen. Keine Sitzung,
keine Begrüßung, keine Muster — Anweisung rein, Text plus freies JSON raus.
Wollt ihr stattdessen ein Chat-Fenster, in dem die Person mitreden kann, nehmt
§7a.

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

### Vollständiges Beispiel: taxonid aus dem Text der offenen Seite

Der Fall, den ein Plugin wirklich hat: die Person steht auf irgendeiner Seite,
ihr habt deren Text (ihr seid im Browser), und ihr wollt daraus ein
maschinenlesbares Metadatum — hier die **taxonid**, also die Vokabular-URI des
Schulfachs. Dazu sollen die **Anleitungen einer Sammlung** gelten, damit das
Ergebnis der Hauskonvention folgt und nicht der Laune des Modells.

```js
// Der Seitentext ist EURE Bringschuld — dazu unten mehr.
const seitentext = document.body.innerText.replace(/\s+/g, ' ').slice(0, 12000);

const antwort = await fetch('https://chat.example.org/api/agent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'WLO-Access-Block': zugangsblock,          // persönliche Anmeldung, §7
  },
  body: JSON.stringify({
    // Die Sammlung, aus der die Anleitungen kommen. Ihre Freigabeliste wird
    // VOR dem Auftrag geholt — „Anleitungen vor Gegenstand"
    // (`services/agent_run.py:64-74`).
    collection_id: 'f35c17d1-a29e-4b26-9d22-802682fad43d',

    instruction: [
      'Bestimme das Schulfach dieser Seite und gib die WLO-taxonid zurück.',
      'Falls unter den freigegebenen Anleitungen eine zur Metadaten-Anreicherung',
      'dabei ist, halte dich an sie.',
      'Prüfe die taxonid gegen das Vokabular (lookup_wlo_vocabulary,',
      'vocabulary="discipline"), statt sie aus dem Gedächtnis zu bilden.',
      'Gibt der Text kein Fach her: confidence 0 und leere taxon_id.',
      '',
      '--- Text der Seite ---',
      seitentext,
    ].join('\n'),

    result_schema: {
      type: 'object',
      properties: {
        taxon_id: {
          type: 'string',
          description: 'volle Vokabular-URI, z.B. '
            + 'http://w3id.org/openeduhub/vocabs/discipline/460',
        },
        label:       { type: 'string', description: 'deutsches Label, z.B. Physik' },
        confidence:  { type: 'number', minimum: 0, maximum: 1 },
        begruendung: { type: 'string' },
      },
      required: ['taxon_id', 'label', 'confidence'],
    },

    allow_curation: false,   // reine Auskunft → keine Schreibwerkzeuge im Katalog
    locale: 'de',
  }),
});

const { result, stop_reason, tools_called } = await antwort.json();
if (stop_reason !== 'submit') {
  throw new Error(`Lauf endete mit ${stop_reason} — result ist nicht verlässlich`);
}
// result → {
//   taxon_id: "http://w3id.org/openeduhub/vocabs/discipline/460",
//   label: "Physik", confidence: 0.9, begruendung: "…"
// }
```

**Was dabei serverseitig passiert**, in dieser Reihenfolge:

1. `collection_id` → `get_skill_registry` läuft **vor** eurer Anweisung; die
   Freigabeliste steht also schon im Gespräch, bevor der Auftrag kommt.
2. Jedes weitere Werkzeug-Ergebnis bekommt seine Registry angehängt, falls es
   eine mitbringt (`services/agent_loop.py:250-257`) — auch eine Sammlung, die
   der Agent selbst erst findet, bringt ihre Anleitungen mit.
3. Das Modell holt sich den Volltext der passenden Anleitung (`search_skill` →
   `get_skill`) und arbeitet danach.
4. `lookup_wlo_vocabulary({vocabulary:'discipline'})` liefert Label **und** URI
   je Fach; die URI **ist** die taxonid (gemessen: Physik =
   `…/vocabs/discipline/460`, Mathematik = `…/380`).
5. `submit_result` mit eurem Schema — wörtlich als Parameter des
   Abschluss-Werkzeugs.

`tools_called` zeigt hinterher, ob das auch wirklich so lief. Steht dort kein
`get_skill`, hat das Modell die Anleitung nicht gelesen — dann ist die Anweisung
zu unbestimmt, nicht der Bestand leer.

### Besonderheiten im Plugin

Sechs Dinge, die auf einer gewöhnlichen Gastseite nicht auffallen:

| | |
|---|---|
| **Der Seitentext ist eure Bringschuld** | `get_url_text` läuft auf dem *Server*. Einen Tab hinter Anmeldung, hinter Bezahlschranke oder auf `localhost` sieht er nicht — ihr schon. Schickt den Text in der `instruction` mit, statt auf das Werkzeug zu hoffen. |
| **≤ 20 000 Zeichen** | Die `instruction` ist gedeckelt; ein langer Artikel plus eure Anweisung reißt das. Kürzt den Text (oben: 12 000), sonst kommt `422`. |
| **Zugang: nur der Zugangsblock** | `WLO-Access-Block` mit **persönlicher** Anmeldung. Der Studio-Schlüssel ist der Admin-Schlüssel und hat in einer Erweiterung nichts zu suchen (§7). |
| **20 Läufe je Minute und IP** | `RATE_LIMIT_CHAT`. Ein Plugin, das bei **jedem** Tab-Wechsel einen Agent-Lauf startet, steht nach zwanzig Wechseln bei `429`. Startet Läufe auf eine ausdrückliche Handlung, nicht auf Navigation. |
| **CORS** | Eine Erweiterungs-Seite hat die Herkunft `chrome-extension://<id>`. Der Betreiber muss `CORS_ORIGINS` auf `*` lassen oder eure Herkunft eintragen (`main.py:140-147`); alternativ deckt ihr es über MV3-`host_permissions` ab. Klärt das **vor** dem Integrationstest — sonst sucht ihr den Fehler im Rumpf. |
| **`allow_curation: false` bei Auskunft** | Nimmt die vierzehn kuratierenden Werkzeuge aus dem Katalog. Weniger Auswahl heißt kürzere Läufe und keine Möglichkeit, versehentlich etwas vorzuschlagen. |

Und einer, der kein Nachteil ist: **`/api/agent` braucht kein Widget.** Für einen
Auftrag ohne Chat-Rahmen könnt ihr den Endpunkt direkt rufen — das Bündel, die
Seitenleiste und der ganze Kontext-Apparat aus §5 sind dafür nicht nötig. Beides
zu bauen ist trotzdem sinnvoll: der Chat für die Person, der Endpunkt für die
Automatik.

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
| `page-context` zur Laufzeit gesetzt, nichts passiert | Das Attribut wird nach dem Start nicht mehr gelesen — nehmt `replaceContext()` (§3, §5) |
| Der Bot sagt „Du bist auf `<Erweiterungs-Kennung>` — das gehört nicht zu WLO" | Die eigene Erkennung lief auf der Adresse der Seitenleiste. Ab 2026-08-14 trägt sie dort nichts mehr bei; setzt zusätzlich `auto-context="false"` und gebt den Kontext selbst mit (§5) |
| Der Bot spricht über die Sammlung des VORIGEN Tabs | `updateContext` mergt. Für einen Seitenwechsel ist `replaceContext` das Richtige (§5) |
| Nach dem Kontext-Wechsel begrüßt der Bot die neue Seite nicht | Auch das ist der Unterschied: nur `replaceContext` setzt das Ping-Gate zurück (§5) |
| `linkClicked` feuert nie | `intercept-edu-sharing-links="true"` fehlt |
| `guide-suggestion` feuert nie | `emit-guide-suggestion="true"` fehlt (Opt-in) |
| Klick auf einen Link der **Gastseite** bekommt kein `?bsid=` | Der Klick-Wächter greift nur im Shadow-Root des Widgets — die Navigation der Gastseite bleibt unangetastet. Wer die ID braucht, hängt sie selbst an |
| `result` ist `null` | Kein `result_schema` mitgegeben — oder `stop_reason !== 'submit'` |
| `boerdi:agent-result` kommt nie | `engine="agent"` fehlt am Element. Das Attribut `result-schema` allein wirkt nicht; die Warnung steht nur im Backend-Protokoll, nicht im Browser (§7a) |
| `result-schema` gesetzt, nichts passiert | Kaputtes JSON — es gilt dann als „kein Schema". Die `console.warn`-Zeile im Browser nennt es. Achtet auf die Anführungszeichen (außen `'`, innen `"`) (§7a) |
| `422` beim Chat-Zug | Das `result_schema` ist länger als 10 000 Zeichen. Abgelehnt statt gekürzt: ein halbes Schema verlangte eine andere Form, als ihr wolltet (§7a) |
| Der Auftrag aus `startTask` erscheint nicht | Leerer Text wird verworfen. Sonst wartet er, bis die Shell gemountet ist, und läuft dann (§5) |
| Der Bot antwortet auf den Auftrag ohne den Seitenkontext | `replaceContext()` **vor** `startTask()` — der Auftrag geht sofort raus (§5) |
| `tools_called` enthält kein `get_skill` | Das Modell hat die Anleitung nicht gelesen. Die Anweisung war zu unbestimmt — nennt die Aufgabe und verlangt ausdrücklich, sich an eine passende Anleitung zu halten (§7) |
| 422 an `/api/agent` | `instruction` über 20 000 Zeichen — meist der mitgeschickte Seitentext. Kürzen (§7) |
| CORS-Fehler in der Erweiterungs-Konsole | Die Herkunft `chrome-extension://<id>` steht nicht in `CORS_ORIGINS` des Betreibers (§7) |
| 401 / 403 an `/api/agent` | Keiner der drei Zugangswege greift (§7) |
| 429 | Drosselung, `RATE_LIMIT_CHAT` |
| 503 auf `/widget/boerdi-widget.js` | Bündel nicht gebaut — die Antwort nennt den Befehl |
