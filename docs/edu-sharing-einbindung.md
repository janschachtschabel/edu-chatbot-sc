# Chatbot im edu-sharing-Repositorium einbinden

Anleitung für die **Entwickler des Repositoriums**: das Widget eingebettet in
eine eigene Seite setzen, wahlweise mit Muster-Engine oder Agent-Schleife, die
**Anmeldung der angemeldeten Person durchreichen**, Kontext (z.B. die gerade
gezeigte Sammlung) auslösen, Ereignisse mitlesen und strukturierte Ergebnisse
abgreifen.

Alles hier ist am Quelltext belegt; Fundstellen stehen in Klammern. Wo etwas
**nicht** geht, steht es ausdrücklich da.

| Thema | Dokument |
|---|---|
| Dieselbe Sache aus Sicht eines **Browser-Plugins** (ohne Repo-Änderung) | [`browser-plugin-einbindung.md`](browser-plugin-einbindung.md) |
| Agent-Schleife im Detail (Studio, Deckel, `stop_reason`) | [`agent-modus.md`](agent-modus.md) |
| Herleitung + Messungen zu Sitzung, CSRF und Schreibpfad | [`plans/2026-08-12-einbettung-ohne-repo-aenderung.md`](plans/2026-08-12-einbettung-ohne-repo-aenderung.md) |
| Eingefrorener HTTP-Vertrag | [`api/openapi-v1.json`](api/openapi-v1.json) |

---

## 1. Die eine Entscheidung vorweg

Es gibt zwei Betriebsformen. Sie unterscheiden sich **nur** darin, ob ihr uns
einen Ausweis der angemeldeten Person mitgebt.

| | **A — ohne Ticket** | **B — mit Ticket** (empfohlen) |
|---|---|---|
| Was ihr baut | Widget einbetten | Widget einbetten **+ `ticket` templaten** |
| Lesen (Suche, Prüfen) | Dienstkonto des MCP-Servers | **als die angemeldete Person** |
| Schreiben | nur im Browser, same-origin, **eine** Anfrage je Bestätigung (§9) | serverseitig durch den MCP-Server, **auch mehrschrittig** |
| Zuschreibung einer Änderung | die Person (Browser-Sitzung) | die Person (Ticket) |
| Zweite Anmeldung nötig | nein | nein |

**B ist der bessere Tausch**, sobald ihr ohnehin einbettet: ein Ticket ist ein
begrenzter, widerrufbarer Ausweis. Der Aufwand dafür ist ein Attribut, das ihr
serverseitig ins Template schreibt (§3).

Was ihr **nicht** tun müsst: nichts an edu-sharing bauen, keinen Endpunkt
bereitstellen, keine Anwendung registrieren, keinen Reverse-Proxy einrichten.

**Was ihr entscheidet:** mit welchem Konto der MCP-Server liest.

| Wahl | Empfehlung |
|---|---|
| anonym | funktioniert; sieht nur öffentliche Inhalte |
| **Dienstkonto ohne Schreibrechte** | **empfohlen** — bessere Treffer, kein Risiko |
| Dienstkonto *mit* Schreibrechten | nicht nötig: in diesem Entwurf schreibt niemand über das Dienstkonto |

---

## 2. Einbetten

Ein **Custom Element** in einer einzigen Datei — kein Nachladen von Teilstücken
zur Laufzeit, keine externen Schriften, keine Dritt-Dienste (DSGVO).

| | |
|---|---|
| Stabile Adresse | `https://<chat-host>/widget/boerdi-widget.js` |
| Antwort | **302** auf `…/boerdi-widget.<12-hex>.js`; stabile URL `no-store`, gehashte `immutable` |
| Kopfzeile | `Access-Control-Allow-Origin: *` |
| Umfang | eine Datei, gemessen **525 KB** unkomprimiert (Stand 2026-08-13) |
| Isolation | **Shadow DOM** — eure Stile bluten nicht herein, unsere nicht hinaus |

Beleg: `backend/src/boerdi/api/widget.py:107-132`.

### Eingebettet, ohne eigenen Rahmen

`embed-mode="frameless"` gibt Rahmen **und Platzierung** an eure Oberfläche ab:
kein Eulen-Knopf, keine eigene Kopfzeile, kein Panel-Rahmen, kein Schatten
(`_widget-panel.scss:93-124`).

**Die eine Falle, und sie ist lautlos:** rahmenlos legt das Widget mit dem
Rahmen auch die **eigene Größe** ab und füllt `width/height: 100%` seines
Containers. Hat der Container keine Höhe, ist das Element **null Pixel hoch** —
man sieht nichts, und es gibt keine Fehlermeldung.

```html
<!-- einmal pro Seite -->
<script src="https://chat.example.org/widget/boerdi-widget.js" defer></script>

<!-- der Kasten gehört EUCH: Höhe, Rahmen, Ecken -->
<div class="boerdi-slot">
  <boerdi-chat
    api-url="https://chat.example.org"
    embed-mode="frameless"
    initial-state="expanded"
    show-debug-button="false">
  </boerdi-chat>
</div>
```

```css
.boerdi-slot { block-size: min(32rem, 70vh); overflow: hidden;
               border: 1px solid var(--eure-linie); border-radius: .75rem; }

/* Als Seitenspalte, ab genug Breite: */
@media (min-width: 90rem) {
  .boerdi-slot { position: fixed; inset-block: 1.5rem; inset-inline-end: 1.5rem;
                 inline-size: 22rem; block-size: auto; }
}
```

`initial-state="expanded"` ist rahmenlos praktisch Pflicht: es gibt keinen
Eulen-Knopf, der das Panel je öffnen würde. Die Chat-Shell wird rahmenlos
deshalb auch sofort gemountet statt erst beim ersten Öffnen
(`widget.component.ts:327`).

Zum Ansehen laufen am Backend drei Demo-Seiten mit Bedienpult für jedes
Attribut: `/widget/classic`, `/widget/inline`, `/widget/frameless`.

---

## 3. Die Anmeldung durchreichen — das Ticket

Das ist der Teil, den **nur ihr** liefern könnt.

### Warum ein Browser sich das nicht selbst holen kann

Gemessen am 2026-08-12 gegen `repository.staging.openeduhub.net`:

* `JSESSIONID` und `INGRESSCOOKIE` sind `HttpOnly` ⇒ **kein JavaScript liest
  sie**, und ohne `SameSite` (⇒ `Lax`) trägt ein fremd eingebettetes iframe sie
  gar nicht erst mit.
* In allen **317 Pfaden** von `/edu-sharing/rest/openapi.json` gibt es **keinen
  Token-Endpunkt**, der einem Browser einen weiterreichbaren Ausweis gäbe.
  `validateSession` liefert Status, keinen Ausweis; `appauth` wäre
  Identitätsübernahme.

Ein Ticket kann deshalb nur **serverseitig** entstehen — beim Rendern eurer
Seite. Genau das macht der md-editor heute in Produktion (`?ticket=…`).

### Der Weg, Station für Station

**1. Ihr templatet das Ticket ins Attribut.** Attribut, **nicht** URL: nur die
Seite selbst kann es liefern, ein Link von außen nicht — keine
Sitzungs-Fixierung per Link.

```html
<boerdi-chat
  api-url="https://chat.example.org"
  embed-mode="frameless"
  initial-state="expanded"
  ticket="${ticketDerAngemeldetenPerson}">
</boerdi-chat>
```

**2. Das Widget liest es einmal und tilgt es sofort aus dem DOM**
(`widget.component.ts:365-376`) — die md-editor-Regel „ein Ticket darf nirgends
liegenbleiben", hier fürs DOM statt für die Adresszeile.

**3. Es tauscht das Ticket still beim MCP-Server** (`session/ticket-login.ts`),
sobald die Anmelde-Adresse aus dem Config-Bündel da ist:

```
POST <mcp_auth_base>/auth/ticket     { "ticket": "…" }
→   { "ok": true, "block": "wlo2.…" }
```

Der Server prüft an der gemeldeten **`authority`**, nie am Statuscode — eine
ungültige Sitzung antwortet bei edu-sharing `200` mit `authority: esguest`.
Zurück kommt ein gewöhnlicher Zugangsblock, dessen Inhalt diesmal das Ticket
ist (upstream dann `EDU-TICKET <ticket>` statt `Basic`).

**4. Ab hier ist nichts mehr besonders.** Der Block liegt im `sessionStorage`
(`boerdi.mcp-access`) und reist bei jedem Zug als Kopfzeile
`WLO-Access-Block` mit (`session/mcp-access.ts:36,92-95`). Derselbe
Abmelde-Knopf, dieselbe Widerrufung. **Am Backend ist dafür keine Zeile
geändert worden** — der Block ist formgleich mit dem der OAuth-Anmeldung.

**5. Scheitert der Tausch, bleibt das Widget still.** Der Anmelde-Knopf steht
auf „Anmelden" (der Rückfall auf die Handanmeldung, den der md-editor „hybrid
fallback" nennt), und eine `console.warn`-Zeile nennt euch den Grund
(`chat-shell.component.ts:520-527`). Fünf Ausgänge, jeder ein eigenes Wort:

| Ausgang | heißt |
|---|---|
| `done` | getauscht, Block liegt — der einzige, der etwas verändert hat |
| `no-ticket` | kein Attribut gesetzt |
| `unavailable` | keine Anmelde-Adresse **oder** `/auth/ticket` antwortet 404 (Ausgabe abgeschaltet) |
| `rejected` | der Server hat entschieden: Ticket abgelaufen, Drossel, unbrauchbare Antwort |
| `unreachable` | er war nicht zu fragen (Netz) |

`rejected` vs. `unreachable` ist bewusst getrennt — der Unterschied entscheidet,
wo jemand suchen muss.

### Was dafür konfiguriert sein muss

| Wo | Was | Sonst |
|---|---|---|
| **Euer Template** | `ticket="…"` beim Rendern | Widget bleibt anonym |
| **MCP-Server** | `WLO_AUTH_PRIVATE_KEY` gesetzt (Blockausgabe an) | `/auth/ticket` → 404 → `unavailable` |
| **Chatbot-Backend** | `MCP_SERVER_URL` gesetzt | `mcp_auth_base` bleibt leer, kein Tausch, auch kein Anmelde-Knopf |

`mcp_auth_base` wird aus `MCP_SERVER_URL` abgeleitet und enthält **nur**
`scheme://host[:port]` — der Rest der Server-Registrierung ist Betriebswissen
und hat in einem öffentlichen Bündel nichts verloren (`api/config.py:302-320`).
Es reist im Boot-Bündel `GET /api/config/guide-mode`.

### Ehrliche Grenzen

* **Die Live-Probe steht aus.** Dass edu-sharing `EDU-TICKET <ticket>` als
  `Authorization` annimmt, belegt die Produktions-Praxis des md-editors — ein
  eigener Lauf braucht ein echtes Ticket, und das kann nur eine einbettende
  Seite liefern. Ihr seid die Ersten, die das prüfen können.
* **Stirbt die Repository-Sitzung, stirbt das Ticket.** Jeder Werkzeug-Aufruf
  endet dann 401; der Zugang endet mit der Sitzung. Gewollt — nur ohne eigenen
  Satz im Chat, der Anmelde-Status zeigt es.
* **Das Ticket wird nicht behalten.** Es verlässt das Modul genau einmal, zur
  Tauschstelle, und wird nirgends abgelegt. Ein Block ist nur gegen unseren
  MCP-Server brauchbar und dort widerrufbar; ein rohes Ticket wäre ein lebender
  Repository-Ausweis.

### Was wir bewusst nicht anbieten

| | warum nicht |
|---|---|
| Sitzungs-Cookies an unser Backend übergeben | technisch unmöglich, und unerwünscht: **die Sitzung eurer Nutzer verlässt den Browser nicht — wir können sie nicht sehen** |
| Endpunkt bei euch, der uns die Sitzung reicht | verlangt einen Bau am Repositorium; ausgeschlossen |
| `appauth` mit registrierter Anwendung | Identitätsübernahme per Bauart: wer es rufen darf, darf jeder sein |
| Dienstkonto mit Schreibrechten | jede Änderung liefe unter einem Sammelkonto, ohne Zuschreibung |

---

## 4. Alle Parameter

Die 25 Attribute von `<boerdi-chat>`. Quelle der Wahrheit sind die `input()`s in
`frontend/projects/widget/src/app/widget/widget.component.ts:86-177`; ein Test
pinnt den Satz. (Dieselbe Tabelle steht in
[`browser-plugin-einbindung.md`](browser-plugin-einbindung.md) — beide leiten
sich aus derselben Datei ab.)

Alle Werte sind HTML-Attribute, also Zeichenketten; boolesche nehmen
`"true"`/`"false"`.

### Grundlage

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `api-url` | — | Herkunft des Backends. **Ohne sie läuft nichts.** |
| `embed-mode` | `panel` | `panel` \| `frameless` (§2) |
| `size` | `small` | `small` \| `large` — nur der Start |
| `engine` | leer | `pattern` \| `agent` (§5) |
| `position` | `bottom-right` | Ecke des Eulen-Knopfs; rahmenlos wirkungslos |
| `initial-state` | `collapsed` | `collapsed` \| `expanded` |
| `primary-color` | leer | Akzentfarbe; validiert, schlägt bis in die Material-Token durch |
| `greeting` | — | Begrüßung überschreiben (sonst die aus dem Studio) |
| `start-replies` | leer | Einstiegs-Chips überschreiben, als **JSON-Array**: `start-replies='["Fach und Stufe?"]'`. `[]` = keine Chips |
| `show-welcome` | `true` | `"false"` = **leerer Chat**: keine Startnachricht, keine Chips — für Seiten, die selbst anmoderieren. Die Kontext-Begrüßung bleibt |

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
| `auto-context` | `true` | Adresse und Titel selbst erkennen — **kennt eure URL-Schemata bereits** (§6) |
| `page-context` | — | JSON-Objekt, das die Erkennung ergänzt bzw. ersetzt |

### Anzeige

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `show-debug-button` | `true` | Debug-Umschalter in der Kopfzeile |
| `show-language-buttons` | `true` | Mikrofon + Vorlesen (Altname, meint die Sprach-**Ausgabe**; zusätzlich an die Backend-Fähigkeit gekoppelt) |
| `inline-result-grouping` | `true` | `false` = flaches Karten-Gitter mit Seitenblättern statt Ergebnis-Boxen |
| `show-cards` | `auto` | `auto` \| `always` \| `never` — `auto`: klein Textlinks, groß Kacheln |
| `theme` | `auto` | `auto` \| `light` \| `dark`. `auto` folgt dem `color-scheme` eurer Seite |
| `language` | leer | `de` \| `en`. Leer = nächstes `[lang]` im DOM, sonst Browser, sonst Deutsch. Eine Nutzerwahl am Umschalter schlägt das Attribut |

### Integration

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `ticket` | — | **Der Ausweis der angemeldeten Person (§3).** Einmal gelesen, dann aus dem DOM getilgt |
| `intercept-edu-sharing-links` | `false` | `true` = Link-Klicks abfangen statt navigieren → `linkClicked` mit Pfad+Query. Für eine SPA, die selbst routen will |
| `emit-guide-suggestion` | `false` | `boerdi:guide-suggestion` einschalten (§7) |
| `emit-routing-debug` | `false` | `boerdi:routing-debug` einschalten (§7) |

### Was zur Laufzeit noch wirkt

| Attribut | nach dem Start änderbar? |
|---|---|
| `initial-state` | **ja** — der erste Wert entscheidet den Start, spätere schalten das Panel um (`widget.component.ts:290-297`) |
| `engine`, `language`, `primary-color` | **ja** — hängen an Effects (`widget.component.ts:279-315`) |
| `page-context` | **nein, nicht unmittelbar** — hängt an keinem Effect; gelesen in `ngOnInit` und danach nur bei erkannter Navigation (`widget.component.ts:262,384`). Zur Laufzeit nehmt ihr `replaceContext()` bzw. `updateContext()` (§6) |
| `size` | **nein** — Startwert; danach gehört die Stufe dem Umschalter in der Eingabezeile |
| `ticket` | **nein** — einmal in `ngOnInit` gelesen und getilgt |

---

## 5. Engine wählen

| | **Muster-Engine** (`pattern`, Vorgabe) | **Agent-Schleife** (`agent`) |
|---|---|---|
| Ablauf | Klassifikator → Musterwahl → gebundene Werkzeugliste | Systemprompt + **voller** Werkzeug-Katalog, freie Schleife |
| Endet bei | einer Antwort | `submit_result`, Prosa, oder einem Deckel |
| Gut für | den Chat mit Menschen | Aufträge ohne Chat-Rahmen |
| Kosten je Zug | eine Runde | bis zu `max_iterations` Runden |

Drei Ebenen, die feinere gewinnt:

1. **Ganze Anlage** — Studio → *Agent & Maschine* (`01-base/engine`), ohne
   Neustart wirksam. Dort stehen auch die vier Deckel:
   `max_iterations` (1–50), `deadline_s` (5–600), `token_budget` (≥ 1000),
   `write_mode` (`propose` \| `execute`).
2. **Je Einbau** — `engine="agent"` am Element. Damit stellt ihr **eine** Seite
   auf die Schleife, während der Rest der Anlage bei der Muster-Engine bleibt —
   und nur so lässt sich A/B überhaupt messen.
3. **Je Anfrage** — Kopfzeile `X-Boerdi-Engine: agent`. Undeklariert gelesen,
   steht also nicht im OpenAPI-Dokument; ein unbekannter Wert fällt still auf
   die Vorgabe zurück und bricht nichts.

Beachtet: `engine="agent"` ändert, **wie** der Chat antwortet — nicht, **was**
er zurückgibt. Ein Chat-Zug bleibt Text + Karten + Quick-Replies. Für ein
maschinenlesbares Ergebnis braucht ihr §8.

---

## 6. Kontext auslösen — z.B. die gezeigte Sammlung

### Meistens müsst ihr gar nichts tun

Die eingebaute Erkennung kennt eure URL-Schemata bereits
(`ui/src/page-context/page-context-detector.ts:98-160`):

| URL-Muster | ergibt |
|---|---|
| `/components/render/<uuid>` | `page_kind: content`, `node_id` |
| `/components/collections?id=<uuid>` | `page_kind: collection`, `collection_id` (+ `q` → `search_query`) |
| `/components/topic-pages?collectionId=<uuid>` | `page_kind: topic`, `collection_id` |
| `?node` / `?nodeId` / `?collection` / `?collectionId` | `content` bzw. `collection` |
| `/themenseite/<slug>` | `page_kind: topic`, `topic_page_slug` |

Mit `auto-context="true"` (Vorgabe) reist der Kontext also von selbst mit —
inklusive Titel, Hostname und voller Adresse.

### Was der Sammlungskontext auslöst

Steht `page_kind` auf `collection` oder `topic`, holt das Backend zusätzlich
zwei Dinge vorab und legt sie **beiden** Maschinen in den Prompt:

* die Anzahl der Materialien der Sammlung,
* die **Übersicht der freigegebenen Anleitungen (Skills)** dieser Sammlung —
  Titel, höchstens 100, gedeckelt auf eine A4-Seite.

Den Volltext einer Anleitung holt das Modell danach gezielt selbst
(`get_skill_registry` mit der `collection_id` → `get_skill` mit der `nodeId`
daraus). Damit weiß der Chatbot auf einer Sammlungsseite sofort, welche
redaktionellen Anleitungen für genau diese Sammlung gelten.

Der Vorabruf hängt am **Kontext**, nicht am Startvorgang: ein
`replaceContext({page_kind:'collection', collection_id:'…'})` mitten in der
Sitzung schaltet ab dem nächsten Zug auf die Anleitungen dieser Sammlung um.
Zwei Dinge, die dabei oft anders erwartet werden: die Übersicht nennt **nur
Titel, keine `nodeId`s** (deshalb der Umweg über `get_skill_registry`), und eine
**Themenseite ist eine Sammlung** — `page_kind: 'topic'` mit derselben
`collection_id` führt zu denselben Anleitungen.

### Selbst setzen

```html
<boerdi-chat
  api-url="https://chat.example.org"
  auto-context="false"
  page-context='{"page_kind":"collection","collection_id":"…-UUID-…"}'>
</boerdi-chat>
```

`auto-context="false"` schaltet die eigene Erkennung ab; sonst trägt sie Adresse
und Titel zusätzlich bei. Die Felder
(`page-context-detector.ts:35-66`): `page_kind` (`topic` \| `collection` \|
`content` \| `subject` \| `search` \| `other`), `node_id`, `collection_id`,
`topic_page_slug`, `subject_slug`, `search_query`, `search_filters`,
`page_text`, `page_url`, `page_host`.

### Zur Laufzeit umschalten — zwei Wege, zwei Wirkungen

Das ist der wichtige Unterschied für eine SPA
(`ui/src/shell/lifecycle.ts:182-193`):

| Aufruf | Wirkung |
|---|---|
| `chat.updateContext({…})` | **mergt** in den bestehenden Kontext. Kein Ping, keine Nachricht — leise Ergänzung |
| `chat.replaceContext({…})` | **ersetzt** den Kontext (alte IDs raus), setzt das Ping-Gate zurück und **bietet eine Kontext-Begrüßung an** |
| SPA-Navigation (erkannt) | dasselbe wie `replaceContext`, nur vom Widget selbst ausgelöst |

Den letzten Weg löst das Widget selbst aus: ein Wächter vergleicht alle
**1,5 s** `location.href` (`ui/src/widget/host-bridges.ts:4,97-102`). Für eine
Angular-SPA wie eure heißt das: **ihr müsst beim Routenwechsel nichts tun** —
der Wechsel wird bemerkt, der Kontext ersetzt, und auf einer adressierbaren
Seite begrüßt der Bot mit dem neuen Kontext.

**Wollt ihr das sofort statt nach bis zu 1,5 s, ist `replaceContext()` das
Richtige — nicht `updateContext()`.** Der Unterschied ist nicht kosmetisch: ein
Seitenwechsel per Merge ließe die `node_id` und den `search_query` der vorigen
Seite stehen, und der Bot spräche über zwei Seiten gleichzeitig. Ergänzen ist
für das gedacht, was **zusätzlich** zur Seite gilt und nicht in der URL steht —
etwa eine Auswahl in eurer Oberfläche:

```js
const chat = document.querySelector('boerdi-chat');
await customElements.whenDefined('boerdi-chat');

// Routenwechsel: ersetzen.
chat.replaceContext({ page_kind: 'collection', collection_id: gewaehlteId });

// Auswahl innerhalb derselben Seite: ergänzen.
chat.updateContext({ search_query: eingegebenerFilter });
```

### Die übrigen Steuerbefehle

Acht Methoden auf dem Element (`frontend/projects/widget/src/element-api.ts`):

```js
chat.openChatbot();   chat.closeChatbot();   chat.toggleChatbot();
chat.isChatbotOpen(); chat.resetSession();
chat.updateContext({ … });   chat.replaceContext({ … });
chat.startTask('Fasse zusammen, worum es hier geht.');
```

Vor der Aufwertung des Elements geben sie `undefined` zurück statt zu werfen —
bewusst so, aber es heißt eben auch: nichts ist passiert. Wartet auf
`customElements.whenDefined('boerdi-chat')`.

**`startTask` startet den Chat auf ein Thema** (seit 2026-08-14). Der Satz
erscheint als eigene Auftrags-Blase mit der Zeile „Auftrag der Seite" — nicht
als Nutzernachricht und nicht unsichtbar; danach ist es eine gewöhnliche
Unterhaltung. Setzt den Kontext **vorher** (`replaceContext`), denn `startTask`
schickt sofort. Ist das Panel zu, öffnet es sich; ist die Shell noch nicht
gemountet, wird der Auftrag gehalten und danach ausgeführt.

**Eine gewöhnliche Nachricht einschleusen, geht weiterhin nicht.** `sendMessage`
steht nicht in den durchgereichten Methoden. Das ist Absicht: was von der Seite
kommt, soll auch als solches erkennbar bleiben.

---

## 7. Ereignisse mitlesen

Vier Ereignisse, auf `window`, mit `bubbles` und `composed` (sonst käme aus dem
Shadow-Root nichts an) — `ui/src/host-events/event-names.ts:26-53`.

```js
window.addEventListener('boerdi:guide-suggestion', (e) => {
  const { url, title, node_id, node_type, query, alternatives } = e.detail;
  // z.B. „Bot empfiehlt"-Pin in eurer Sidebar setzen
});
```

| Ereignis | wann | Nutzlast |
|---|---|---|
| `boerdi:page-action` | der Bot schlägt eine Seiten-Aktion vor | `{action, payload}` — heute gefeuert: `navigate`, `show_results`, `canvas_show_cards` |
| `boerdi:query-meta` | nach jedem Zug mit Suche — **immer an**, kein Opt-in | `{queries: [{tool_name, query_type, search_term, criteria[], pagination, repository_url, search_url}]}` |
| `boerdi:guide-suggestion` | jeder Zug mit verlinkbarem Treffer — **`emit-guide-suggestion="true"` nötig** | `{url, title, node_id, node_type, query, alternatives[]}` |
| `boerdi:routing-debug` | jeder Bot-Zug — **`emit-routing-debug="true"` nötig** | `{message, pattern, intent, state, persona, tools_called[], rag_areas[], sources[], modifier{…}, signals[]}` |

**Doppelversand beachten.** Solange der ALTE Chatbot parallel läuft, feuert jedes
Ereignis **zweimal** — neu zuerst (`boerdi:…`, das ist der Vertrag), dann noch
einmal unter `badboerdi:…` (Übergangs-Nachsicht). Hört **nur auf den neuen
Namen**, sonst verarbeitet ihr alles doppelt. Der alte Versand fällt nach dem
Cutover ersatzlos weg.

**Unbekannte `page-action` still übergehen.** Das Schema erklärt ein breiteres
Vokabular, als heute tatsächlich gefeuert wird — `navigate`, `show_collection`,
`show_results`, `share_content` plus vier `canvas_*`
(`backend/src/boerdi/api/schemas.py:294-306`); im Code entstehen davon zur Zeit
nur die drei aus der Tabelle. Behandelt die Liste als offen: was ihr nicht kennt,
ignoriert ihr, statt daran zu scheitern.

`node_type` in `guide-suggestion` ist dreiwertig: `topic_page` \| `collection` \|
`content` — genug, um in eurer Oberfläche das richtige Ziel anzusteuern.

**Wer das Element in Angular einbaut** (ihr seid eine Angular-SPA), bekommt vier
Outputs mit identischer Nutzlast: `linkClicked` (Zeichenkette, nur mit
`intercept-edu-sharing-links`), `guideSuggestion`, `routingDebug`, `queryMeta`.
`page-action` ist **nicht** dabei — es erreicht eine Gastseite ausschließlich als
`window`-Ereignis.

---

## 8. Strukturierten Output erzeugen und abfangen

### Zuerst die Einordnung: zwei Wege, und sie sind verschieden

**Mit Chat-Fenster** — die Person soll mitreden und ihr wollt trotzdem Daten:
Attribut `result-schema` am Element plus `engine="agent"`. Je Zug feuert dann
`boerdi:agent-result` mit `{result, stop_reason}` (Angular-Output:
`agentResult`). Das ist seit 2026-08-14 der unterstützte Weg; vorher stand hier,
der Chat könne das nicht.

```html
<boerdi-chat api-url="…" engine="agent"
  result-schema='{"type":"object","properties":{"taxon_id":{"type":"string"}},
                  "required":["taxon_id"]}'></boerdi-chat>
```

```js
chat.replaceContext({ page_kind: 'collection', collection_id: id });
chat.startTask('Welchem Fach ordnest du diese Sammlung zu?');
window.addEventListener('boerdi:agent-result', (e) => {
  const { result, stop_reason } = e.detail;
  if (result) uebernehmen(result.taxon_id);
});
```

Vier Dinge dazu: **beide** Angaben sind nötig (ohne `engine="agent"` wirkt das
Schema gar nicht — das Backend warnt im Protokoll, im Browser bleibt es still);
jeder Zug kostet dann **einen zusätzlichen Modellzug (2–9 s gemessen)**, auch
„Danke!"; `result` ist **je Zug optional** (`null` aushalten, `stop_reason`
unterscheidet „nichts dabei" von „abgeschnitten"); und das Attribut ist eine
**Zeichenkette** — kaputtes JSON gilt als „kein Schema" und meldet sich nur als
`console.warn`. Das Schema ist auf 10 000 Zeichen gedeckelt (sonst 422).

**Ohne Chat-Fenster** — reiner Auftrag, kein Gespräch: **`POST /api/agent`**,
unverändert, siehe unten. Kein Widget nötig.

### Zugang

Drei Wege, in dieser Reihenfolge geprüft (`backend/src/boerdi/api/turn_auth.py`):

1. `AGENT_OPEN=true` — der Ausweg für Testläufe. **Vorgabe: aus.**
2. Kopfzeile `WLO-Access-Block` mit **persönlicher** Anmeldung. Der ausdrücklich
   anonyme Block (`wlo-anon.v1`) zählt nicht.
3. Kopfzeile `X-Studio-Key` — Server-zu-Server.

**Habt ihr §3 gebaut, habt ihr Weg 2 schon.** Der Block, den das Ticket
erzeugt hat, liegt im `sessionStorage` unter `boerdi.mcp-access` und ist
derselbe, den ihr hier mitschickt. Der Studio-Schlüssel ist der Admin-Schlüssel
und hat in einem Browser nichts zu suchen.

Dazu die Drosselung: `RATE_LIMIT_CHAT`, Vorgabe **20/Minute je IP**, sonst `429`
mit `X-RateLimit-*`. Die Prüfung der Kopfzeile ist eine **Form-, keine
Echtheitsprüfung** — belegen kann einen Block nur der MCP-Server; die
Mengenbremse ist die Kostenschranke.

### Erzeugen

`result_schema` reist **wörtlich** in die Parameter des Abschluss-Werkzeugs
`submit_result`; der Anbieter erzwingt die Form. Ihr könnt also jede Struktur
verlangen, ohne dass unser Code von ihr wissen muss.

```js
const block = sessionStorage.getItem('boerdi.mcp-access');  // aus §3

const antwort = await fetch('https://chat.example.org/api/agent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    ...(block ? { 'WLO-Access-Block': block } : {}),
  },
  body: JSON.stringify({
    instruction: 'Prüfe die Metadaten dieser Inhalte und schlage Korrekturen vor.',
    collection_id: aktuelleSammlung,          // löst die Skill-Registry vorab auf
    node_ids: markierteKnoten,                // höchstens 50
    result_schema: {
      type: 'object',
      properties: {
        befunde: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              node_id:     { type: 'string' },
              feld:        { type: 'string' },
              vorschlag:   { type: 'string' },
              zuversicht:  { type: 'number', minimum: 0, maximum: 1 },
            },
            required: ['node_id', 'feld', 'vorschlag'],
          },
        },
      },
      required: ['befunde'],
    },
    write_mode: 'propose',
    locale: 'de',
  }),
});
```

| Eingabe | Pflicht | Bedeutung |
|---|---|---|
| `instruction` | **ja** | Die Aufgabe im Klartext, ≤ 20 000 Zeichen, nicht leer |
| `collection_id` | nein | Sammlung, aus der die Anleitungen kommen — vorab über `get_skill_registry` |
| `node_ids` | nein | Die Inhalte — vorab über `get_nodes_details`, **höchstens 50** |
| `result_schema` | nein | JSON-Schema des gewünschten Ergebnisses |
| `write_mode` | nein | `propose` \| `execute`. `execute` verlangt immer eine angemeldete Person — sonst still `propose` |
| `allow_curation` | nein | `false` nimmt die kuratierenden Werkzeuge heraus, auch mit Anmeldung |
| `locale` | nein | `de` \| `en` |

Die Vorab-Abrufe laufen **vor** der Anweisung: erst was zu tun ist, dann woran
(`services/agent_run.py:64-74`). Schlägt einer fehl, kippt er den Auftrag nicht —
der Fehlschlag landet als Vermerk in der Kette, der Agent arbeitet weiter und
sagt im Ergebnis, dass ihm etwas fehlt (`services/agent_prefetch.py:58-67`).

Ein zweites, vollständig durchgerechnetes Beispiel — Schulfach als taxonid aus
einem Seitentext, mit Anleitung aus einer Sammlung und Prüfung gegen das
Vokabular — steht in
[`browser-plugin-einbindung.md`](browser-plugin-einbindung.md) §7. Der Endpunkt
ist derselbe; dort ist nur der Aufrufer ein anderer.

### Abfangen

```jsonc
{
  "text": "Zwei Datensätze haben eine unpassende Bildungsstufe. …",
  "result": { "befunde": [ … ] },     // null OHNE result_schema
  "stop_reason": "submit",
  "iterations": 4,
  "tools_called": ["get_skill_registry", "get_nodes_details", "submit_result"]
}
```

**`stop_reason` prüfen, bevor ihr `result` benutzt** — das ist der ganze Trick.
Ein an der Frist abgeschnittener Lauf sähe von außen sonst aus wie einer, der
fertig geworden ist:

```js
if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
const lauf = await antwort.json();

if (lauf.stop_reason !== 'submit') {
  // text steht trotzdem da und ist oft brauchbar — result NICHT.
  zeigeHinweis(lauf.text, lauf.stop_reason);
  return;
}
verarbeite(lauf.result);
```

| `stop_reason` | heißt | `result` verlässlich? |
|---|---|---|
| `submit` | `submit_result` gerufen — die Ziellinie | **ja** |
| `text` | Prosa-Antwort ohne Werkzeug | nein (`null`) |
| `max_iterations` | Rundendeckel erreicht | nein |
| `deadline` | Frist abgelaufen | nein |
| `token_budget` | Budget aufgebraucht | nein |
| `no_progress` | Stillstand: die Schleife kam nicht voran | nein |
| `error` | Fehler in der Schleife | nein |

Belegt in `backend/src/boerdi/services/agent_loop.py:139-260`.

### Fortschritt anzeigen

`POST /api/agent/stream`, gleicher Rumpf, Antwort als Server-Sent-Events:
`connected` → beliebig viele `phase` → `result` **oder** `error`. Ein
`end`-Rahmen kommt bewusst nicht, und **Token liefert der Strom nicht** — nur
Phasen, geeignet für „Hole `get_nodes_details` …". Wer nur das Ergebnis will,
nimmt den normalen Endpunkt.

```
event: phase
data: {"kind":"record","step":"agent_prefetch","label":"Hole get_nodes_details","data":{"tool":"get_nodes_details"}}
```

---

## 9. Schreiben

Zwei Wege, und welcher offensteht, hängt an eurer Entscheidung aus §1.

**Mit Ticket (B).** Der MCP-Server handelt serverseitig als die angemeldete
Person — alle Werkzeuge, auch die mehrschrittigen Fälle (Sammlung anlegen,
umbenennen, Inhalt ändern), die je zwei Aufrufe nacheinander brauchen. Gesteuert
über `write_mode` (`propose` = Vorschau + Rückfrage, `execute` = ausführen nach
Bestätigung). Der Bestätigungs-Wall gilt unverändert: **nichts wird ohne
Zustimmung geschrieben.**

**Ohne Ticket (A).** Der MCP-Server *bereitet* die Änderung nur vor (Methode,
Pfad, Rumpf), das Backend reicht sie als `prepared_write` durch, und das Widget
setzt sie same-origin ab — die Sitzungs-Cookies reisen automatisch mit, ohne
dass Code sie je anfasst. Der Riegel im Widget:

| Regel | wie sie hält |
|---|---|
| nur die Herkunft **eures** Repositoriums | die Adresse entsteht aus `origin() + path`; die Herkunft kommt nie aus der Anfrage |
| nur eine **Erlaubnisliste** aus Methode + Pfadmuster | heute drei Einträge: Material in eine Sammlung legen, herausnehmen, Metadaten vorschlagen (`type=AI` ist Teil des Musters — über diesen Weg kann kein Vorschlag einen Menschen als Urheber behaupten) |
| Ergebnis über die gemeldete `authority`, nie den Statuscode | **vor** dem Schreiben `GET …/rest/iam/v1/people/-home-/-me-`; ohne Person wird gar nicht geschrieben |
| abgelaufene Sitzung | `esguest` ⇒ eigener Satz mit Handlungsanweisung, Anfrage bleibt ungesendet |

**Höchstens eine vorbereitete Anfrage je Zug, und bei zweien keine.** Der
Bestätigungs-Wall lässt je Zug einen Schlüssel einlösen; zwei Vorbereitungen
sind kein Mehrfachfall, sondern ein gebrochener Zustand — dann ist nicht
feststellbar, welcher Änderung ein Mensch zugestimmt hat.

Deshalb trägt A die mehrschrittigen Fälle nicht: eine vorbereitete Anfrage ist
**eine** Anfrage, und ein halb geschriebener Datensatz im Browser wäre ein
Zustand, den niemand zurückrollen kann.

Volle Herleitung: [`plans/2026-08-12-einbettung-ohne-repo-aenderung.md`](plans/2026-08-12-einbettung-ohne-repo-aenderung.md).

---

## 10. Inbetriebnahme — Reihenfolge und Prüfpunkte

1. **Widget einbetten**, ohne Ticket, `embed-mode="frameless"`.
   → Der Chat erscheint im Kasten und antwortet. Erscheint nichts: hat der
   Container eine Höhe?
2. **Kontext prüfen**: auf einer Sammlungsseite fragen „Was liegt hier?".
   → Der Bot nennt die Sammlung und die Zahl ihrer Materialien.
3. **`MCP_SERVER_URL`** am Chatbot-Backend setzen.
   → Im Chat erscheint der Anmelde-Knopf; `GET /api/config/guide-mode` liefert
   ein nicht-leeres `mcp_auth_base`.
4. **`WLO_AUTH_PRIVATE_KEY`** am MCP-Server setzen.
   → `POST <mcp_auth_base>/auth/ticket` antwortet nicht mehr 404.
5. **`ticket` templaten.**
   → Der Anmelde-Knopf steht auf „angemeldet", ohne dass jemand geklickt hat.
   Steht er auf „Anmelden": Konsole lesen, das Wort dort benennt die Station
   (§3).
6. **Engine wählen** (§5) und, wenn ihr strukturierte Ergebnisse braucht, §8
   verdrahten.

### Häufige Fehler

| Symptom | Ursache |
|---|---|
| Der Kasten bleibt leer | `embed-mode="frameless"` ohne Höhe am Container (§2) |
| Der Chat startet geschlossen | `initial-state="expanded"` fehlt |
| Anmelde-Knopf bleibt auf „Anmelden" | Ticket-Tausch gescheitert — `console.warn` nennt den Ausgang (§3) |
| `unavailable` in der Konsole | `mcp_auth_base` leer (`MCP_SERVER_URL` fehlt) **oder** `/auth/ticket` → 404 (`WLO_AUTH_PRIVATE_KEY` fehlt) |
| `rejected` in der Konsole | Ticket abgelaufen oder Template liefert ein totes Ticket |
| Kontext bleibt nach Routenwechsel stehen | bis zu 1,5 s Wächter-Takt abwarten; sofort geht es mit `replaceContext()` (§6) |
| Der Bot spricht über die vorige Seite mit | Für einen Seitenwechsel `updateContext()` benutzt — das mergt und lässt alte IDs stehen. `replaceContext()` nehmen (§6) |
| Nach dem Kontextwechsel begrüßt der Bot die neue Seite nicht | Auch das ist der Unterschied: nur `replaceContext()` (und die erkannte Navigation) setzen das Ping-Gate zurück (§6) |
| `page-context` zur Laufzeit gesetzt, nichts passiert | Das Attribut wird nach dem Start nicht mehr gelesen — `replaceContext()` nehmen (§4, §6) |
| Jedes Ereignis kommt doppelt | Auf `boerdi:…` **und** `badboerdi:…` gehört (§7) |
| `result` ist immer `null` | Kein `result_schema` mitgegeben — oder `stop_reason !== 'submit'` (§8) |
| `boerdi:agent-result` kommt nie | `engine="agent"` fehlt. Das Schema allein wirkt nicht; die Warnung steht nur im Backend-Protokoll (§8) |
| `result-schema` gesetzt, nichts passiert | Kaputtes JSON — es gilt dann als „kein Schema". Die `console.warn`-Zeile im Browser nennt es (§8) |
| `422` beim Senden | Das `result_schema` ist länger als 10 000 Zeichen. Abgelehnt statt gekürzt: ein halbes Schema wäre ein anderes (§8) |
| Der Auftrag aus `startTask` erscheint nicht | Leerer Text wird verworfen; sonst wartet er auf die Shell und läuft nach dem Mounten (§6) |
| Der Bot antwortet auf den Auftrag, ohne die Sammlung zu kennen | `replaceContext()` **vor** `startTask()` rufen — der Auftrag geht sofort raus (§6) |
| Schreiben passiert nicht | `write_mode: execute` ohne persönliche Anmeldung → still auf `propose` zurückgefallen |
| 429 | Drosselung, `RATE_LIMIT_CHAT` |
| 503 auf `/widget/boerdi-widget.js` | Bündel nicht gebaut — die Antwort nennt den Befehl |
