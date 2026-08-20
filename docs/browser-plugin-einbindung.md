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

## 1a. Das Grundmuster: Kontext rein, Auftrag rein, Ergebnis raus

Fast jedes Plugin macht dieselben vier Dinge. Hier stehen sie einmal am Stück und
in der richtigen Reihenfolge; die Abschnitte dahinter erklären jeden Schritt
einzeln.

```js
await customElements.whenDefined('boerdi-chat');

// ── 1. Element bauen: eigene Ansprache, eigene Chips, Agent-Schleife ────────
const chat = document.createElement('boerdi-chat');
chat.setAttribute('api-url', 'https://chat.example.org/api');
chat.setAttribute('embed-mode', 'frameless');
chat.setAttribute('engine', 'agent');
chat.setAttribute('auto-context', 'false');     // ihr liefert den Kontext selbst
chat.setAttribute('greeting',
  'Hallo, ich bin BOERDi — die schlaue Eule von WirLernenOnline. ' +
  'Ich helfe beim Erschließen, Kuratieren und bei der Qualitätssicherung.');
chat.setAttribute('start-replies', JSON.stringify([
  'Qualitätssicherungsskills suchen und ausführen',
  'Inhalt kuratieren',
]));
// Was ihr maschinenlesbar zurückbekommen wollt (optional):
chat.setAttribute('result-schema', JSON.stringify({
  type: 'object',
  properties: {
    fach:       { type: 'string', description: 'Vokabular-URI aus `discipline`' },
    confidence: { type: 'number', description: '0.0 bis 1.0' },
  },
  required: ['fach'],
}));
// KEIN page-context beim Einhängen — sonst ersetzt die Kontext-Begrüßung
// eure Startnachricht (§4a).
document.getElementById('chatHalter').append(chat);

// ── 2. Ergebnisse mitlesen — VOR dem ersten Auftrag anmelden ───────────────
window.addEventListener('boerdi:agent-result', (e) => {
  const { result, stop_reason } = e.detail;
  if (result?.fach) uebernehmen(result.fach, result.confidence);
  else if (stop_reason !== 'text') hinweis(`Lauf endete mit ${stop_reason}`);
});

// ── 3. Kontext hineingeben — bei JEDEM Seitenwechsel erneut ────────────────
function seiteMelden() {
  chat.replaceContext({
    page_kind: 'other',                       // fremde Seite; WLO-Seiten: siehe §5
    page_url:  location.href,
    page_host: location.hostname,
    page_text: document.body.innerText.slice(0, 3000),
  });
}
seiteMelden();

// ── 4. Auftrag hineingeben (optional — sonst tippt die Person selbst) ──────
chat.startTask(
  'Ordne diese Seite einem Fach zu. Prüfe den Wert gegen das ' +
  '`discipline`-Vokabular und gib die URI zurück.');
```

**Die Reihenfolge ist nicht Geschmack.** Jede Zeile hat einen Grund, und drei
davon kosten sonst einen Nachmittag:

| Schritt | Warum gerade hier |
|---|---|
| Attribute **vor** dem Einhängen | `greeting`, `start-replies`, `show-welcome` werden beim Erstaufruf gelesen; rahmenlos ist das der Moment des Einhängens (§4a) |
| Zuhörer **vor** dem Auftrag | `startTask` schickt sofort; ein später angemeldeter Zuhörer verpasst den ersten Zug |
| Kontext **vor** dem Auftrag | `startTask` nimmt mit, was in diesem Moment gesetzt ist (§5) |
| `engine="agent"` **zusammen mit** `result-schema` | ohne die Agent-Schleife wirkt das Schema gar nicht — kein `result`, kein Ereignis, nur eine Zeile im Server-Protokoll (§7a) |

Was das Widget selbst mitbringt und ihr **nicht** bauen müsst: Sitzung, Verlauf,
Karten, Quick-Replies, Vorlesen, das Wiederherstellen nach einem Neustart.

Und was ihr **je nach Aufgabe** braucht:

| Ihr wollt … | Das ist der Weg | Abschnitt |
|---|---|---|
| eigene Startnachricht + Chips | `greeting` · `start-replies` | §4a |
| gar keine Startnachricht | `show-welcome="false"` | §4a |
| die offene Seite melden | `replaceContext({…})` | §5 |
| ein Feld nachreichen (gleiche Seite) | `updateContext({…})` | §5 |
| den Chat auf ein Thema starten | `startTask('…')` | §5 |
| maschinenlesbares Ergebnis | `result-schema` + `boerdi:agent-result` | §7a |
| Chat gar nicht anzeigen | `POST /api/agent` | §7 |

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

Dazu eine **Probierseite für Gastgeber** — nicht „wie sieht es aus", sondern „was
kann ich hineinreichen":

| Seite | Wozu |
|---|---|
| `/widget/edu-sharing-demo.html` | Redaktionsumgebung nachgestellt: 440-px-Seitenleiste mit Chat (⅔) und strukturierter Ausgabe (⅓), Hybrid-Modus. Begrüßung und Schnellantworten von der Seite überschreiben, Kontext (Sammlung/Themenseite/Einzelinhalt) beim Aufbau **oder** live nachreichen, Anweisung über `startTask()`, `result-schema` bearbeiten, alle fünf Ereignisse mitlesen |

Sie ist eine einzelne Datei (`frontend/projects/widget/src/edu-sharing-demo.html`),
ausgeliefert über die Asset-Route des Widget-Builds — deshalb ohne eigene Route und
ohne Vertragsänderung. Ein anderes Backend: `?api=https://…` anhängen.

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
| `start-replies` | leer | Einstiegs-Chips überschreiben, als **JSON-Array**; `[]` = keine Chips (§4a) |
| `show-welcome` | `true` | `"false"` = **leerer Chat**: keine Startnachricht, keine Chips (§4a) |

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
| `intercept-edu-sharing-links` | `false` | `true` = **ihr übernehmt die Navigation**: jeder Klick auf einen Link mit `/edu-sharing` im Pfad wird unterdrückt und nur als Ereignis `linkClicked` (Pfad+Query) gereicht. Unbehandelt ist jeder solche Klick tot — auch die Such-Pille. Vorgabe aus |
| `emit-guide-suggestion` | `false` | `boerdi:guide-suggestion` einschalten (§6) |
| `emit-routing-debug` | `false` | `boerdi:routing-debug` einschalten (§6) |
| `ticket` | — | edu-sharing-Ticket der Gastgeberseite. **Für Plugins nicht nutzbar** (§8) |

### Was zur Laufzeit noch wirkt

Ein `setAttribute` nach dem Einhängen wirkt **nicht bei jedem Attribut**. Das ist
kein Zufall, sondern je eine Entscheidung im Code — und für eine Erweiterung die
wichtigste Tabelle des ganzen Dokuments: in einer Seitenleiste lebt das Element
oft stundenlang, während der Nutzer Tabs wechselt und Einstellungen dreht.

Drei Klassen, alle am Quelltext geprüft (Stand 2026-08-14). Bewusst ohne
Zeilennummern: die veralten schneller als die Mechanismen.

**A · Wirkt sofort.** Hängt an einem Angular-`effect`, einem `computed` oder
einer Template-Bindung — die nächste Auswertung nimmt den neuen Wert.

| Attribut | wie es durchschlägt |
|---|---|
| `engine` | Effect → `shell.setEngine()`; gilt ab dem nächsten Zug |
| `result-schema` | Effect → `shell.setResultSchema()`; eigener Effect, damit es unabhängig von `engine` umstellbar ist. Gilt ab dem nächsten Zug |
| `master-skill` | Effect → `shell.setMasterSkill()`; eigener Effect aus demselben Grund. Gilt ab dem nächsten Zug. Drei Zustände: `"on"`, `"off"`, **fehlt** = Vorgabe des Betreibers (`MASTER_SKILL_ENABLED`). Das nackte Attribut ohne Wert gilt als „fehlt" — drei Zustände lassen sich durch Vorhandensein allein nicht ausdrücken |
| `tool-mode` | Effect → `shell.setToolMode()`. Gilt ab dem nächsten Zug. `read-only` \| `curate` \| `full` (Vorgabe); ein unbekannter Wert gilt als Vorgabe. Wirkt zweifach: die verbotenen Werkzeuge fehlen in der Liste, UND das Modell erfährt es — sonst verspräche es eine Änderung, die es gleich nicht ausführen kann |
| `quick-replies` | Effect → `shell.setQuickReplies()`, oder zur Laufzeit direkt `el.setQuickReplies([...])`. JSON-Array; gilt ab dem nächsten Zug und BLEIBT, bis jemand es ersetzt oder mit `[]` löscht. Schlägt Generator, Canvas-Vorgaben und Policy. Der Chip-Text IST die gesendete Nachricht — deshalb wird nie gekürzt, nur die Anzahl begrenzt (sechs) |
| `quick-replies-max` | Effect → `shell.setQuickRepliesMax()`, oder zur Laufzeit `el.setQuickRepliesMax(4)`. Mix-Modus (O-B2): die `quick-replies`-Chips zuerst, das Modell füllt bis zur Gesamtzahl auf (Klammer 1–6 serverseitig). Nur zusammen mit `quick-replies` wirksam; ohne Zahl überschreiben die Chips hart |
| `language` | Effect → `lang.resolve()` |
| `primary-color` | Effect → `applyPrimaryColor()` auf dem Host-Element |
| `initial-state` | Effect; der **erste** Wert entscheidet den Start (dort zählen auch `?bsid=` und eine laufende Tour mit), erst spätere Änderungen klappen auf und zu |
| `theme` | `computed` → Inline-Stil `color-scheme` am Host |
| `position` | CSS matcht das Attribut direkt (`:host([position="…"])`) — es gibt gar keinen Umweg über den Input |
| `embed-mode` | `computed` `frameless()`; schaltet Rahmen, FAB und Kopfzeile um |
| `show-cards`, `show-debug-button`, `show-language-buttons`, `inline-result-grouping` | werden beim Rendern gelesen (Getter/`computed` der Shell) |
| `intercept-edu-sharing-links`, `emit-guide-suggestion`, `emit-routing-debug` | werden beim Ereignis gelesen |
| `trusted-domains` | `computed`, mit der Backend-Liste gemergt |

**B · Wirkt erst beim nächsten Neustart des Chats.** Die Bindung ist live, aber
die einzige Stelle, die sie liest, läuft nur beim Öffnen und bei „Neu starten"
(bzw. `resetSession()`).

| Attribut | wann es greift |
|---|---|
| `greeting`, `start-replies`, `show-welcome` | beim Erstaufruf und bei jedem Neustart. Eine bereits gezeigte Begrüßung verschwindet **nicht** rückwirkend — wer sie loswerden will, setzt das Attribut vor dem ersten Öffnen (§4a) |

**C · Nur beim Start gelesen.** Danach führt kein Weg über das Attribut; wo es
einen anderen gibt, steht er dabei.

| Attribut | warum, und was stattdessen |
|---|---|
| `api-url` | Einmal in `ngOnInit` der Shell → `setBaseUrl()`. **Achtung:** die Shell hängt am Lazy-Gate, entsteht also erst beim ersten Öffnen — bis dahin wirkt eine Änderung sehr wohl. Danach hilft nur, das Element neu aufzubauen |
| `page-context` | Gelesen in `ngOnInit` und danach nur, wenn der URL-Wächter eine Navigation bemerkt. In einer Seitenleiste bemerkt er nie eine: die eigene Adresse ändert sich nicht. Nehmt **`replaceContext()`** (§5) |
| `auto-context` | Wird nur beim Auflösen des Seitenkontexts gelesen, also zusammen mit `page-context` |
| `persist-session`, `session-key`, `session-cookie-domain`, `session-cookie-max-age` | Die Sitzungs-Kaskade läuft einmal beim Start. Danach: `resetSession()` |
| `size` | Startwert; danach gehört die Stufe dem Umschalter in der Eingabezeile — ein Effect überschriebe jede Handbedienung |
| `ticket` | Einmal gelesen und sofort aus dem DOM getilgt: ein Ticket darf nirgends liegenbleiben |

Faustregel, wenn ihr unsicher seid: **alles, was den Verlauf oder die Sitzung
betrifft, ist Start-Zustand; alles, was nur die Darstellung oder den nächsten Zug
betrifft, ist live.** Und im Zweifel den sicheren Weg nehmen — das Element neu
aufbauen kostet die Sitzung, aber nie eine falsche Messung. Genau das tut das
Beispiel-Plugin bei jedem „Starten" (§7a).

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

## 4a. Begrüßung je Einbau — überschreiben oder abschalten

Von Haus aus öffnet der Chat mit einer Begrüßung und vier Einstiegs-Chips. Beides
pflegt die Redaktion im Studio (*Begrüßung* → `01-base/welcome-config.yaml`) und
gilt damit für **alle** Einbettungen. Wo das nicht passt, entscheidet der Einbau:

```html
<boerdi-chat
  api-url="https://chat.example"
  greeting="Ich helfe beim Erschließen dieser Seite."
  start-replies='["Fach und Stufe?","Qualität prüfen"]'>
</boerdi-chat>
```

```html
<!-- Leerer Chat: die Gastseite moderiert selbst an -->
<boerdi-chat api-url="https://chat.example" show-welcome="false"></boerdi-chat>
```

Die Rangfolge ist bei beiden dieselbe wie überall: **Attribut schlägt Studio.**

| gesetzt | Wirkung |
|---|---|
| `greeting="…"` | dieser Text statt dem aus dem Studio |
| `start-replies='["A","B"]'` | diese Chips statt denen aus dem Studio |
| `start-replies='[]'` | **keine** Chips — die Begrüßung bleibt |
| `show-welcome="false"` | **gar keine** Startnachricht, auch nicht nach „Neu starten" |

Drei Dinge, die man sonst erst im Betrieb merkt:

* **`start-replies` ist JSON, keine Komma-Liste.** Die Beschriftungen sind ganze
  Sätze und enthalten regelmäßig Kommas — am Komma getrennt zerfielen sie still.
  Kaputtes JSON wird verworfen (mit einer Zeile in der Konsole), es gilt dann die
  Studio-Vorgabe.
* **Nicht gesetzt ≠ leer.** Ein weggelassenes `start-replies` heißt „die
  Studio-Vorgabe gilt", `'[]'` heißt „ausdrücklich keine". Ohne diesen
  Unterschied ließen sich die Chips gar nicht abschalten.
* **`show-welcome="false"` betrifft NUR diese eine Nachricht.** Die
  Kontext-Begrüßung („Du bist auf der Sammlung X…") hängt am Seitenkontext und
  kommt weiter — wer auch sie nicht will, gibt keinen Kontext mit (§5). Das ist
  Absicht: auf einer erkannten Seite ist sie meistens genau das, was man will.

Der Host-Weg kennt keine zweite Sprache: wer je Einbau vorgibt, gibt genau das
vor, was dort stehen soll. Die Deutsch/Englisch-Umschaltung greift nur bei den
Studio-Werten.

### Der Zeitpunkt zählt

Alle drei Attribute gehören in Klasse **B** der Laufzeit-Tabelle (§3): die
Bindung ist live, gelesen wird sie aber nur beim Erstaufruf und bei jedem
Neustart. Praktisch heißt das:

* **Vor dem ersten Öffnen setzen.** Wer `show-welcome="false"` erst setzt,
  nachdem der Chat schon offen ist, findet die Begrüßung weiterhin im Verlauf —
  sie wurde bereits geschrieben, und nichts nimmt eine Nachricht zurück.
* **Im Panel-Betrieb ist „das erste Öffnen" später, als man denkt.** Die Shell
  hängt am Lazy-Gate: sie entsteht beim ersten Klick auf den Eulen-Knopf. Bis
  dahin dürft ihr die Attribute beliebig oft umstellen.
* **Rahmenlos gibt es kein Gate.** Dort entsteht die Shell sofort, also müssen
  die Attribute schon am Element stehen, wenn ihr es ins Dokument hängt — nicht
  erst danach.

Wer die Werte doch zur Laufzeit wechseln will, hat zwei ehrliche Wege:
`resetSession()` (leert den Verlauf und wendet sie an) oder das Element neu
aufbauen. Das Beispiel-Plugin nimmt den zweiten (§7a).

### Startnachricht UND Kontext-Meldung — die Reihenfolge entscheidet

Der häufigste Stolperstein im Plugin-Betrieb, und er sieht nach einem Fehler aus,
obwohl er Absicht ist: **liegt beim Öffnen schon ein Seitenkontext an, ersetzt die
Kontext-Begrüßung die Startnachricht.** Die Person soll EINE Eröffnung sehen, nicht
zwei — also stellt das Widget die statische Nachricht zurück, bis der Kontext-Ping
geantwortet hat. Kommt etwas („Du bist auf de.wikipedia.org …"), ist *das* die
Begrüßung; bleibt der Ping leer oder scheitert er, kommt die statische doch.

Wer beides will — erst die eigene Vorstellung, dann die Meldung zur Seite —,
hängt das Element **ohne** `page-context` ein und reicht den Kontext direkt danach
mit `replaceContext()` nach:

```js
const chat = document.createElement('boerdi-chat');
chat.setAttribute('api-url', 'https://chat.example');
chat.setAttribute('embed-mode', 'frameless');
chat.setAttribute('engine', 'agent');
chat.setAttribute('greeting',
  'Hallo, ich bin BOERDi — die schlaue Eule von WirLernenOnline. ' +
  'Ich helfe beim Erschließen, Kuratieren und bei der Qualitätssicherung.');
chat.setAttribute('start-replies', JSON.stringify([
  'Qualitätssicherungsskills suchen und ausführen',
  'Inhalt kuratieren',
]));
// KEIN page-context beim Einhängen — sonst übernimmt die Kontext-Begrüßung.
document.getElementById('chatHalter').append(chat);

// Erst jetzt die Seite melden: die Startnachricht steht bereits, die
// Kontext-Meldung kommt als zweite Nachricht darunter.
chat.replaceContext({
  page_kind: 'other',
  page_url: location.href,
  page_host: location.hostname,
  page_text: document.body.innerText.slice(0, 3000),
});
```

Reihenfolge im Chat: **1.** die Eulen-Vorstellung mit den zwei Chips, **2.** die
Meldung zur offenen Seite. Wer die Startnachricht *nicht* braucht, hängt den
Kontext gleich als Attribut an und spart den zweiten Aufruf.

**Im Panel-Modus greift das so nicht.** `replaceContext()` reicht an die Shell
durch (`this.shell()?.…`), und die entsteht dort erst beim ersten Klick auf den
Eulen-Knopf — ein Aufruf davor läuft still ins Leere. Rahmenlos
(`embed-mode="frameless"`, wie oben) gibt es das Problem nicht: die Shell steht
sofort. Im Panel-Betrieb also entweder auf das `chatbot-opened`-Ereignis warten
(§6) oder den Kontext doch als Attribut mitgeben.

Die beiden Chips sind gewöhnliche Nachrichten: ein Klick schickt die Beschriftung
als Text. „Qualitätssicherungsskills suchen und ausführen" landet damit auf
demselben Weg wie Rezept 1 (§5) — der Lauf holt die Registry und führt die
freigegebene Anleitung aus.

### Beim Seitenwechsel: keine zweite Startnachricht mehr (seit 17.08.2026)

Ein Plugin ohne Sidebar-API hängt das Widget bei jedem Seitenwechsel **neu ein**.
Beim Einhängen lädt es den gespeicherten Verlauf — und stellte ihm bisher immer
die Startnachricht voran, weil das Backend sie nicht persistiert. In eurem Fall
gab es sie aber nie: die Kontext-Begrüßung hatte eröffnet. Ergebnis war eine
Startnachricht, die bei jedem Seitenwechsel neu nachwuchs.

Seit dem 17.08.2026 prüft das Widget, **womit der Verlauf beginnt**: eröffnet ihn
eine Kontext-Begrüßung, wird nichts mehr davorgestellt. Beginnt er wie gewohnt mit
einer Frage der Person, bleibt alles beim Alten.

Zwei Folgen, die ihr kennen solltet:

* Nach einem Seitenwechsel steht die Eulen-Vorstellung **nicht** mehr oben im
  wiederhergestellten Verlauf — sie war nie Teil davon. Gesehen hat die Person sie
  trotzdem, beim ersten Öffnen.
* Prüft, ob euer Bündel den Fix hat:

  ```bash
  grep -c "CTX:" boerdi-widget.js
  ```

  `0` heißt: altes Bündel, die Startnachricht wächst weiter nach.

Beides zusammen — Startnachricht, Chips, danach die Kontext-Meldung — steht als
Prüfseite in `frontend/dist/widget/browser/probe-greeting.html`. Sie ist ein
Wegwerf-Artefakt im Build-Verzeichnis: der nächste `npm run build:widget` löscht
sie.

### Wie das Beispiel es macht

```js
const chat = document.createElement('boerdi-chat');
chat.setAttribute('api-url', basis);
chat.setAttribute('embed-mode', 'frameless');
chat.setAttribute('engine', 'agent');
chat.setAttribute('show-welcome', 'false');   // ← vor dem Einhängen
document.getElementById('chatHalter').append(chat);
```

Die Begründung dort in einem Satz: der Auftrag steht schon im Feld daneben und
geht sofort hinaus — eine Begrüßung wäre eine Nachricht, die niemand gelesen
hat, bevor die Antwort sie wegschiebt.

**Prüfen, ob euer Bündel es überhaupt kennt.** `show-welcome` und `start-replies`
gibt es seit dem 14.08.2026. Ein älteres Bündel ignoriert sie stillschweigend und
begrüßt weiter — von außen nicht von „falsch geschrieben" zu unterscheiden:

```bash
grep -c showWelcome boerdi-widget.js
```

`0` heißt: altes Bündel, neu holen (§1).

---

## 5. Anweisungen und Auslöser von außen

### Die JS-API des Elements

Neun Methoden, auf dem Element-Prototyp
(`frontend/projects/widget/src/element-api.ts:40-53`):

```js
const chat = document.querySelector('boerdi-chat');

chat.openChatbot();     // öffnen, ans Ende scrollen, Eingabe fokussieren
chat.closeChatbot();    // schließen
chat.toggleChatbot();
chat.isChatbotOpen();   // → boolean
chat.resetSession();    // neue Sitzung
chat.updateContext({ … });   // Seitenkontext ERGÄNZEN (mergt)
chat.replaceContext({ … });  // Seitenkontext ERSETZEN (wie eine Navigation)
chat.startTask('…');         // Zug starten — SICHTBAR als Auftrags-Blase (unten)
chat.setHostInstruction('…'); // Rahmen mitgeben — UNSICHTBAR (unten)
```

Ruft ihr sie, **bevor** das Element aufgewertet ist, bekommt ihr `undefined`
statt einer Ausnahme — bewusst so, aber es heißt eben auch: nichts ist passiert.
Wartet auf `customElements.whenDefined('boerdi-chat')`.

Zwei Ausnahmen von dieser Regel: `startTask` und `setHostInstruction` **warten**
auf die Shell, statt ins Leere zu laufen. Beide werden typischerweise sofort nach
dem Einbau gerufen, und die Shell ist da noch keinen Zyklus alt (rahmenlos) bzw.
bis zum ersten Öffnen gar nicht gemountet (Panel-Betrieb).

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
| `page_kind` | `topic` \| `collection` \| `content` \| `subject` \| `search` \| `other` — `editorial` (Prüftisch) setzt der Server selbst, sobald `page_url` auf `/components/editorial-desk` zeigt und eine `node_id` dabei ist; Hosts dürfen es auch direkt senden (nur zusammen mit `node_id` wirksam) |
| `node_id` | edu-sharing-UUID eines Einzelmaterials |
| `collection_id` | UUID einer Sammlung |
| `topic_page_slug` | Kürzel einer Themenseite, z.B. `klimawandel` |
| `subject_slug` | Fachkürzel, z.B. `biologie` |
| `search_query` | aktueller Suchbegriff der Gastseite |
| `search_filters` | `{ publisher?: string[] }` |
| `page_text` | Titel + erste ~3 KB sichtbarer Text |
| `page_url`, `page_host` | volle Adresse und Hostname |
| `title` | Seitentitel des Tabs (Alias: `document_title` gewinnt, wenn beide gesetzt) |

Alle **Text**felder dieser Tabelle — also alle außer `search_filters`, das ein Objekt bleibt — werden serverseitig zu Zeichenketten normalisiert: ein numerisches Enum als `page_kind` oder eine Zahl-ID (`collection_id: 4711` → `"4711"`) bricht den Zug also nicht. Nicht gesetzte Felder (`null`) bleiben ungesetzt.

`page_kind: "collection"` oder `"topic"` löst zusätzlich einen Vorabruf aus:
Anzahl der Materialien und die **Übersicht der freigegebenen Anleitungen
(Skills)** dieser Sammlung wandern in den Prompt — beide Maschinen bekommen sie,
Muster wie Agent. Den Volltext einer Anleitung holt das Modell danach gezielt
selbst (`get_skill_registry` mit der `collection_id` → `get_skill` mit der
`nodeId` daraus).

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
  gekappt (`services/page_context.py:388-432`). Das Modell holt sich die IDs über
  `get_skill_registry` (mit der `collection_id`, die derselbe Prompt-Block
  nennt) und den Volltext über `get_skill`. Das ist ein Aufruf mehr und
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

**Wann `updateContext` trotzdem das Richtige ist:** wenn ihr zur **selben** Seite
etwas nachreicht. Der klassische Fall ist der Seitentext, den ihr erst habt,
wenn das Content-Script geantwortet hat:

```js
chat.replaceContext({ page_kind: 'other', page_url: tab.url, page_host: host });
// … später, wenn der Text da ist — die Seite ist dieselbe geblieben:
chat.updateContext({ page_text: text.slice(0, 3000) });
```

**Wonach es aussieht, wenn ihr die beiden verwechselt:** nichts passiert.
`updateContext` schickt keinen Ping, also erscheint keine Nachricht — die
Methode wirkt tot, obwohl sie getan hat, was sie soll. Der Kontext ist gesetzt
und geht in den **nächsten** Zug ein, den die Person tippt.

**Eine Adresse ist eine Seite** (seit 2026-08-17). Die Kontext-Begrüßung meldet
sich pro Seite genau einmal je Sitzung. „Dieselbe Seite" heißt dabei:

| Seitenart | dieselbe Seite, wenn … |
|---|---|
| `collection`, `content`, `topic` | dieselbe **UUID** — Zählparameter an der URL ändern nichts |
| `search` | derselbe **Suchbegriff** |
| fremde Seite (`external`) | dieselbe **Adresse**, ohne `#anker` |
| eigene Seite ohne Objekt (`home`) | derselbe **Host** — sonst meldete sich der Bot auf jeder Unterseite neu |

Bis dahin galten fremde Seiten hostweise: der zweite Wikipedia-Artikel einer
Sitzung bekam keine Begrüßung mehr. Wer ein älteres Backend betreibt, sieht das
noch (`graph/nodes/context_greeting.py:_greeting_signature`).

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

### Der unsichtbare Rahmen: `setHostInstruction`

`startTask` schickt einen **Zug**. Manchmal wollt ihr aber keinen Zug, sondern
nur sagen, *wie* der Bot hier zu verstehen ist — und zwar so, dass die Person
davon nichts sieht und ihre eigene Frage stellt:

```js
chat.setHostInstruction(
  'Du bist im Kontext der Redaktionsumgebung von edu-sharing. Hilf bei dieser '
  + 'Sammlung: bewerte den Füllstand gegen den kompendialen Text, beantworte '
  + 'Fragen zu den Inhalten, schlage passende Materialien zu den Lehrplänen vor.'
);
```

Der Satz reist am **nächsten Zug** der Person mit und steht **nicht** im
Verlauf. Danach ist er verbraucht — für dauerhaft nach jedem Zug erneut setzen.

| | was passiert |
|---|---|
| `setHostInstruction(text)` | wartet auf die nächste Eingabe, unsichtbar |
| `setHostInstruction(text, { trigger: 'now', message: 'Füllstand prüfen' })` | zusätzlich sofort ein Zug — mit `message` als sichtbarer Auftrags-Blase |
| `setHostInstruction('')` | verwirft einen gesetzten Rahmen |

### Als Kuratierungswerkzeug: Rechte und feste Chips (seit 18.08.2026)

Ein Rahmen sagt dem Bot, *wie* er hier zu verstehen ist. Zwei Dinge kann er
nicht: verhindern, dass der Bot etwas verspricht, wozu ihm die Rechte fehlen —
und gezielte Antworten abfangen. Dafür gibt es zwei harte Schalter.

**Was der Bot in eurer Anwendung darf.** Drei benannte Modi, keine freie
Werkzeugliste (eine Umbenennung im MCP änderte sonst still eure Rechte):

```html
<boerdi-chat engine="agent" tool-mode="curate"></boerdi-chat>
```

| Modus | drin |
|---|---|
| `read-only` | nur lesende WLO-Werkzeuge |
| `curate` | dazu anlegen, ändern, einsortieren — weiterhin zweistufig mit Bestätigung; **ohne** Wikipedia und fremde Adressen |
| `full` | alles (Vorgabe) |

Der Modus wirkt **zweifach**: die verbotenen Werkzeuge fehlen in der Liste, und
das Modell erfährt die Grenze im Systemprompt. Ohne das Zweite verspräche es eine
Änderung, die es gleich nicht ausführen kann.

**Feste Schnellantworten je Zug.** Anders als `start-replies` (nur die
Begrüßung) gilt das für jeden Zug und schlägt Generator, Canvas-Vorgaben und
Policy:

```html
<boerdi-chat quick-replies='["Passt zur Sammlung","Passt nicht","Erschließen"]'></boerdi-chat>
```

```js
chat.setQuickReplies(['Passt zur Sammlung', 'Passt nicht', 'Erschließen']);
// … und wieder freigeben:
chat.setQuickReplies([]);
```

Der Chip-**Text** ist die Nachricht, die der Klick sendet — deshalb wird nie
gekürzt; zu viele werden hinten abgeschnitten (sechs). Die Liste bleibt gesetzt,
bis ihr sie ersetzt oder mit `[]` löscht: ein Kuratierungswerkzeug will dieselben
drei Knöpfe bei jedem Schritt, nicht einmal.

**Mix-Modus: eigene Chips + KI-Auffüllung (O-B2).** Nennt ihr zu euren Chips
zusätzlich eine **Gesamtzahl**, ersetzt die Liste nicht mehr alles — eure Chips
stehen vorn, und das Modell füllt die restlichen Plätze passend zum
Gesprächsverlauf auf:

```html
<boerdi-chat quick-replies='["Passt","Passt nicht"]' quick-replies-max="4"></boerdi-chat>
```

```js
chat.setQuickReplies(['Passt', 'Passt nicht']);
chat.setQuickRepliesMax(4);      // 2 eigene + bis zu 2 vom Modell
chat.setQuickRepliesMax(null);   // Mix aus → wieder hartes Überschreiben
```

Die Zahl ist der Deckel des ganzen Zuges (Klammer 1–6, serverseitig) und
schlägt auch die Studio-Anzeige-Regeln — ihr kennt eure Leiste selbst. Erzeugt
das Modell einen eurer Chips doppelt, fällt die Dublette weg (dann kommen eben
weniger an). Ohne Gesamtzahl bleibt alles beim harten Überschreiben; die Zahl
allein (ohne Chips) tut nichts. Gleiche Lebensdauer wie die Liste: bleibt, bis
ihr sie ersetzt oder mit `null` löscht.

**Wenn ihr selbst rendert.** `inline-result-grouping="false"` schaltet die
gruppierten Boxen ab — und sagt es dem Modell, damit es keine Boxen erwähnt, die
es bei euch nicht gibt, und die Treffer nicht zusätzlich als Linkliste aufzählt.
Beides zusammen ist die übliche Plugin-Einbettung:

```html
<boerdi-chat engine="agent" embed-mode="frameless"
             tool-mode="curate" inline-result-grouping="false"></boerdi-chat>
```

Vier Eigenschaften, auf die ihr euch verlassen könnt:

* **Wirkt in allen drei Maschinen.** Der Block sitzt in *beiden* Prompt-Wegen —
  `services/response_prompt_builder.py` (Muster) und
  `graph/nodes/respond_agent.py` (Agent *und* Hybrid). Anders als das
  `result-schema`, das nur über die Schleife wirkt.
* **Ein Kontext-Ping isst ihn nicht auf.** Wechselt die Seite gerade, während
  der Rahmen wartet, geht der automatische Kontext-Zug **ohne** ihn los; der
  Rahmen bleibt für die Eingabe der Person liegen.
* **Er hebt nichts auf.** Im Block steht ausdrücklich, dass die Anweisung nicht
  von der Person im Chat stammt und dass bei Widerspruch die Leitplanken und
  Sicherheitsregeln gelten. Er ist ein Rahmen, kein Generalschlüssel.
* **Kein Zeichendeckel** (seit 18.08.2026; vorher 2000 mit `422`). Lange
  Anleitungen samt Angaben über die Gastseite gehören hier hinein. Gekürzt
  wird nichts — was ihr schickt, steht im Prompt. Der Preis ist eures: der
  Rahmen reist in **jeden** Modellaufruf des Zuges, im Agent-/Hybrid-Modus
  also bis zu `max_iterations` mal, und zählt jedes Mal aufs Token-Budget.

Warum `'now'` seinen Zug **zeigt**, obwohl der Rahmen unsichtbar bleibt: das
Unsichtbare ist Rahmen, der Zug ist ein Zug. Eine Antwort auf eine Frage, die
die Person nie gestellt hat, ohne sichtbaren Anlass — das ist genau die Zeile,
die `startTask` oben schon nicht überschreitet.

Zum Anfassen: `/widget/edu-sharing-demo.html`, Abschnitte 2 und 3.

## Die Ausgabeflächen gelten in ALLEN Maschinen

Ein verbreitetes Missverständnis: die gegliederten Ergebnis-Boxen seien etwas,
das nur der Mustermodus kann. Das ist nicht so — und das ist gemessen, nicht
angenommen.

Die Boxen entstehen **im Widget** aus Feldern der Antwort (`cards` mit ihrem
`node_type`, `topic_pages`, `collection_link`, dazu `query_metas` für den
Absprung in die Suche). Diese Felder füllt der Zug unabhängig von der Maschine:
die Karten werden in der Schleife aus den Werkzeug-Treffern geerntet
(`collect_cards`), und `assemble` sowie `persist` laufen für alle drei Maschinen
denselben Weg.

**Live gemessen am 18.08.2026**, ein Zug mit `X-Boerdi-Engine: agent` auf
„Material zur Optik für Klasse 8":

```
cards 7 -> node_type: topic_page 2 · collection 2 · content 3
query_metas 1 (search_term gesetzt) · quick_replies 2 · display_rules vorhanden
```

Das sind genau die drei Töpfe, aus denen der Mustermodus seine Boxen baut.

### Beides ist je Einbettung abschaltbar

| Fläche | an | aus |
|---|---|---|
| Gegliederte Boxen | Vorgabe (`inline-result-grouping` fehlt oder `true`) | `inline-result-grouping="false"` → flache Kachel-Liste |
| Ergebnisfenster (JSON) | `result-schema="{…}"` gesetzt | Attribut weglassen |

Für ein Browser-Plugin, das die Gliederung selbst übernimmt, heißt das:

```html
<boerdi-chat engine="agent" inline-result-grouping="false"></boerdi-chat>
```

Die Karten kommen dann unverändert mit — nur die Gruppierung und das
Link-Strippen im Text bleiben aus. Wer die Kacheln gar nicht will, nimmt
zusätzlich `show-cards="false"`.



### Rezept 1: Sammlung prüfen lassen — mit der Anleitung der Redaktion

Die Person hat eine WLO-Sammlung offen, ihr wollt die **Sachrichtigkeit** ihrer
Inhalte prüfen lassen — und zwar nach der Anleitung, die an dieser Sammlung
freigegeben ist, nicht nach dem, was das Modell für richtig hält.

```js
const chat = document.querySelector('boerdi-chat');
await customElements.whenDefined('boerdi-chat');

// 1. Kontext ZUERST. Die collection_id ist der Schlüssel: sie holt die
//    Übersicht der freigegebenen Anleitungen vorab in den Prompt.
chat.replaceContext({
  page_kind:     'collection',
  collection_id: 'f35c17d1-a29e-4b26-9d22-802682fad43d',   // „Geometrische Optik"
  page_url:      tab.url,
  page_host:     new URL(tab.url).hostname,
});

// 2. Der Auftrag nennt die AUFGABE und verlangt die Anleitung ausdrücklich.
chat.startTask([
  'Prüfe die Sachrichtigkeit der Inhalte dieser Sammlung.',
  'Halte dich an die freigegebene Anleitung zur Qualitätssicherung,',
  'falls eine dabei ist — hol sie dir vorher.',
].join(' '));
```

**Warum die zweite Zeile im Auftrag steht.** Der Prompt nennt nur die **Titel**
der freigegebenen Anleitungen, keine `nodeId`s. Das Modell muss also selbst
zugreifen: `get_skill_registry(collection_id)` → `get_skill(nodeId)`. Ein
unbestimmter Auftrag („Schau mal drüber") lässt es das überspringen und aus dem
Gedächtnis antworten.

**Die Anleitung schlägt das Muster.** Gibt es für dieselbe Ausgabe ein
Haus-Muster *und* eine freigegebene Anleitung, gewinnt die Anleitung
(Redaktions-Regel, `domain/skill_precedence.py`). Das gilt auch dort, wo sonst
ein deterministischer Schnellweg die Werkzeugschleife abkürzt.

**Ohne passende Anleitung** greift das Haus-Muster **M19 Qualitätssicherung**:
Soll-Ist-Abgleich aus Kompendiumstext (`get_compendium_text`) gegen Inhaltsliste
(`get_collection_contents`), fachliche Gegenprobe über
`get_wikipedia_summary`/`get_url_text`. Das ist kein Ausfall, sondern der
Rückfall — nur eben ohne Hauskonvention.

**Nachprüfen, ob es geklappt hat:** im Debug-Block muss `tools_called` ein
`get_skill` enthalten. Fehlt es, war der Auftrag zu unbestimmt — nicht der Bot
kaputt.

So sah der Lauf oben aus (gemessen 2026-08-17, Maschine `pattern`, also die
Vorgabe — hier braucht es **keinen** Engine-Wechsel):

```
Muster:     M19 (Qualitätssicherung)
Werkzeuge:  get_skill_registry, get_skill, get_compendium_text,
            get_collection_stats, get_collection_contents,
            get_wlo_content_text ×3, get_node_details
Antwort:    „[ edu-sharing Skill ] Materialprüfung, Reihenprüfung und
             Kompendialtext-Gate – wird geladen …"
```

Die Zeile „Skill … wird geladen" ist keine Fehlermeldung, sondern der sichtbare
Beleg: die Anleitung der Redaktion hat den Zug übernommen.

### Rezept 2: Fremde Seite einordnen — Fach und Bildungsstufe

Die Person steht auf einem Wikipedia-Artikel, ihr wollt eine Einordnung nach
**Fach** und **Bildungsstufe** mit echten WLO-Vokabularen statt freier Prosa.

**Das hier braucht `engine="agent"`** — und das ist keine Vorsichtsmaßnahme,
sondern gemessen (2026-08-17, derselbe Artikel, derselbe Auftrag):

| Maschine | Muster | gerufene Werkzeuge | Ergebnis |
|---|---|---|---|
| `pattern` (Vorgabe) | M04 Wissens-Antwort | keins | „Ein gültiger WLO-Fachwert konnte nicht gegen das `discipline`-Vokabular geprüft werden" |
| `agent` | – | `lookup_wlo_vocabulary` ×2 | Fach mit URI; Stufe „nicht eindeutig bestimmbar" |
| `hybrid` | M20 Erschließen | `lookup_wlo_vocabulary` ×2 | **beide** Werte mit URI |

Im Muster-Modus entscheidet das **Muster** über die Werkzeugliste, und M04 führt
`lookup_wlo_vocabulary` nicht. Das Modell hat das ehrlich gesagt statt zu raten —
aber brauchbar ist die Antwort nicht. Setzt also:

```html
<boerdi-chat api-url="https://chat.example.org" engine="agent"> … </boerdi-chat>
```

```js
// 1. Kontext: die Adresse UND genug Text. Nur der Titel reicht nicht —
//    „Astronomische Einheit – Wikipedia" trägt keine Bildungsstufe.
chat.replaceContext({
  page_kind: 'other',                    // der Server macht daraus `external`
  page_url:  'https://de.wikipedia.org/wiki/Astronomische_Einheit',
  page_host: 'de.wikipedia.org',
  page_text: seitentext.slice(0, 3000),  // ~3 KB, wie die eigene Erkennung
});

// 2. Auftrag mit ausdrücklicher Vokabular-Prüfung.
chat.startTask([
  'Ordne diese Seite ein: Schulfach und Bildungsstufe.',
  'Prüfe beide Werte gegen die WLO-Vokabulare',
  '(lookup_wlo_vocabulary mit vocabulary="discipline" bzw. "educationalContext")',
  'statt sie aus dem Gedächtnis zu bilden.',
  'Gibt der Text nichts her, sag das — rate nicht.',
].join(' '));
```

**`page_kind: 'other'` ist richtig so.** `external` und `home` setzt ihr nicht
selbst: der Server entscheidet das an seiner gepflegten Hostliste
(`graph/nodes/page_context_enrich.py:_decide_host_kind`). Eine Liste, die sich
ohne Widget-Neubau ändern darf, gehört nicht ins Plugin.

**Die beiden Vokabulare** (`services/mcp/tool_defs.py`, `lookup_wlo_vocabulary`):

| `vocabulary` | Bedeutung | so kam es im Lauf oben zurück |
|---|---|---|
| `discipline` | Fächer | Astronomie → `http://w3id.org/openeduhub/vocabs/discipline/46014` |
| `educationalContext` | Bildungsstufen | Schule → `http://w3id.org/openeduhub/vocabs/educationalContext/schule` |

Der Aufruf liefert Einträge **mit URI**, und die ist der Filterwert für eine
spätere Suche. Lasst sie euch zurückgeben, statt sie zu bilden: die Nummer hinter
`discipline/` ist nicht zu erraten, und ein geratener Wert liefert still null
Treffer statt einer Fehlermeldung.

**Braucht ihr das Ergebnis maschinenlesbar**, hängt ein `result-schema` ans
Element und lest `boerdi:agent-result` mit — mit `engine="agent"`, sonst wirkt
das Schema gar nicht (§7a):

```html
<boerdi-chat api-url="https://chat.example.org" engine="agent"
  result-schema='{"type":"object","properties":{
      "fach":{"type":"string","description":"Vokabular-URI aus discipline"},
      "fach_label":{"type":"string"},
      "stufe":{"type":"string","description":"Vokabular-URI aus educationalContext"},
      "stufe_label":{"type":"string"},
      "confidence":{"type":"number","minimum":0,"maximum":1}},
    "required":["fach","stufe","confidence"]}'>
</boerdi-chat>
```

Ganz ohne Chat-Fenster geht dasselbe über `POST /api/agent` — dort steht das
ausgeführte Beispiel (§7).

**Eine Grenze, die ihr kennen müsst:** einordnen darf der Bot anonym, den
**Vorschlag in WLO schreiben** nicht. `wlo_suggest_metadata` zählt zu den
kuratierenden Werkzeugen und wird ohne hinterlegten Zugangsblock gar nicht erst
angeboten (`domain/write_confirm.py:CURATION_TOOLS`, Filter in
`services/response_tool_selection.py:_nameable_tools`). Der Bot kündigt also
nichts an, was der nächste Schritt zurücknimmt — er liest die Vokabulare und
sagt euch das Ergebnis. Zum Anlegen siehe §8.

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

**`linkClicked` verpflichtet.** Mit `intercept-edu-sharing-links="true"`
navigiert das Widget **nie** selbst — für alle `/edu-sharing`-Ziele seid ihr
dran, auch für die Such-Pille (`…/components/search?query=…`). Der häufigste
Stolperstein: ihr steht bereits auf `components/search`, und der Angular-Router
ignoriert Navigation auf dieselbe Route. Deshalb `onSameUrlNavigation`:

```ts
chat.addEventListener('linkClicked', (e: Event) => {
  const ziel = new URL((e as CustomEvent<string>).detail, location.origin);
  router.navigateByUrl(ziel.pathname + ziel.search, { onSameUrlNavigation: 'reload' });
});
```

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
  muss `null` aushalten; der `stop_reason` sagt, warum (Tabelle unten).
* **Das Attribut ist eine Zeichenkette.** Attribute eines Custom Elements sind
  immer Strings — achtet auf die Anführungszeichen (im Beispiel außen `'`,
  innen `"`). Kaputtes JSON kippt den Chat **nicht**: es gilt als „kein Schema",
  und in der Browser-Konsole steht eine `console.warn`-Zeile. Das ist die
  einzige Stelle, an der ihr den Tippfehler bemerkt — von außen sieht ein
  kaputtes Attribut sonst genauso aus wie ein weggelassenes.

Das Schema reist **wörtlich** in die Parameter des Ergebnis-Werkzeugs. Zwei
Folgen: seine `description`-Texte liest das Modell (schreibt sie also als
Anweisung, nicht als Notiz für euch), und es ist auf **200 000 Zeichen**
gedeckelt (seit 18.08.2026; vorher 10 000) — darüber lehnt das Backend die
Anfrage mit 422 ab, statt ein halbes Schema zu verwenden, das eine andere Form
verlangen würde als ihr wolltet. Ein echtes Schema ist ein bis zwei Kilobyte
groß; der Deckel trifft nur Ausreißer.

### Ergebnis und Chat-Antwort sind getrennt (seit 17.08.2026)

Im Chat liefert das Modell das Ergebnis über `liefere_ergebnis` — und das
**beendet den Lauf nicht**. Es antwortet danach ganz normal, und erst diese
Prosa schließt den Zug ab (`stop_reason: "text"`).

Der Grund ist gemessen. Bis dahin trug ein einziger Aufruf beides, Prosa *und*
Ergebnis, und beendete den Lauf dabei: an derselben Anfrage standen **196
Zeichen im Chat gegen 1932 im Ergebnis** — die Substanz landete dort, wo die
Person im Chat sie nie sieht. Nach der Trennung: **1179 gegen 1418**, beides
vollständig.

Was das für euch heißt:

* **`stop_reason: "text"` ist jetzt der Regelfall mit Schema** — nicht `submit`.
  Wer auf `submit` prüft, wartet vergeblich. Prüft auf `result != null`.
* **`submit_result` gibt es im Chat nicht mehr.** Es gehört `POST /api/agent`
  (§7), wo es keinen Chat gibt und `text` die Lieferung *ist*.
* **Die Antwort kostet ihren eigenen Zug.** Reißt dabei ein Deckel, holt das
  Backend sie mit **einem** Aufruf ohne Werkzeuge nach — ein geliefertes
  Ergebnis ohne Antwort daneben wäre der schlechtere Ausgang.
* **Zu kurze Chat-Antworten steuert ihr selbst**, ohne Schalter: gebt per
  `setHostInstruction` mit, was ihr wollt („Das Ergebnis rendere ich selbst,
  fass dich im Chat kurz" oder umgekehrt).

**Das Ereignis hängt am Schema, nicht am Chat.** Das Backend füllt
`result_stop_reason` nur, wenn ein `result-schema` gesetzt ist
(`nodes/respond_agent.py`, `if _schema:`) — ohne Schema bleibt es still, mit
Schema kommt es bei **jedem** Zug, auch wenn `result` null ist. Genau so ist es
gemeint: ein an der Frist abgeschnittener Lauf soll für euch nicht aussehen wie
einer, der nichts zu sagen hatte.

**Alle `stop_reason`-Werte** — die Schleife kennt genau sieben, und nur bei
zweien darf ein `result` erwartet werden:

| `stop_reason` | Bedeutung | `result` zu erwarten? |
|---|---|---|
| `text` | Der Lauf hat in Prosa geantwortet — **der Regelfall mit Schema**, seit `liefere_ergebnis` den Lauf nicht mehr beendet | **ja** |
| `submit` | `submit_result` gerufen. Im Chat kommt das nicht mehr vor; der Wert gehört `POST /api/agent` (§7) | **ja** |
| `deadline` | Frist erreicht (`deadline_s`, Vorgabe 300 s) | nein |
| `token_budget` | Token-Budget aufgebraucht | nein |
| `max_iterations` | Iterationsdeckel erreicht (Vorgabe 20) | nein |
| `no_progress` | Dasselbe Werkzeug zweimal mit denselben Argumenten — Stillstand | nein |
| `error` | Der Anbieter-Aufruf scheiterte | nein |

Behandelt die vier Deckel-Fälle sichtbar: sie heißen „die Anfrage war zu groß",
nicht „es hat nicht geklappt". Ein kleiner geschnittener Auftrag ist dann die
Antwort, kein Wiederholungsversuch mit demselben Text.

```js
window.addEventListener('boerdi:agent-result', (e) => {
  const { result, stop_reason } = e.detail;
  if (result) return uebernehmen(result);
  if (stop_reason === 'text') return;                 // reines Gespräch, kein Fehler
  hinweis({
    deadline:       'Das hat zu lange gedauert — bitte kleiner schneiden.',
    token_budget:   'Die Anfrage war zu umfangreich — bitte kleiner schneiden.',
    max_iterations: 'Zu viele Schritte — bitte kleiner schneiden.',
    no_progress:    'Der Lauf drehte sich im Kreis — bitte anders formulieren.',
    error:          'Der Dienst war kurz nicht erreichbar.',
  }[stop_reason] ?? `Unerwartetes Ende: ${stop_reason}`);
});
```

**Das Schema lässt sich zur Laufzeit wechseln.** Es hängt an einem eigenen
Effect (`resultSchema()`, nicht `engine()`) und gilt ab dem **nächsten** Zug —
ihr könnt also je Aufgabe eine andere Form verlangen, ohne das Element neu zu
bauen:

```js
chat.setAttribute('result-schema', JSON.stringify(schemaFuerDieseAufgabe));
chat.startTask('… und jetzt bitte die Bildungsstufe.');
```

**In Angular** gibt es dieselbe Meldung als Output `agentResult`.

### Zum Anfassen: `examples/chrome-plugin/`

Genau dieser Abschnitt als lauffähige Erweiterung — eine Seitenleiste mit zwei
Reitern: „Einstellungen" (Kontext automatisch · manuell · aus, Auftrag, Schema)
und „Chat" (oben das Gespräch, unten je Zug ein Eintrag mit dem, was strukturiert
herauskommt). Kein Build, keine Abhängigkeiten; `examples/chrome-plugin/README.md`
erklärt das Einrichten.

Der Rest dieses Abschnitts beschreibt, **wie es gebaut ist und wie ihr dasselbe
baut** — sechs Entscheidungen, die jede Erweiterung trifft, mit dem, was uns
jeweils dazu gebracht hat. Wer nur die Fassung zum Kopieren will: der Ordner ist
die Fassung, sie läuft ohne `npm install`.

#### 1 · Das Bündel muss mitreisen

Manifest V3 verbietet nachgeladenen Code. In einer Erweiterungs-**Seite**
(Seitenleiste, Popup, Options-Seite) gilt `script-src 'self'`; ein
`<script src="https://backend/widget/…">` wird gesperrt, auch bei einer entpackt
geladenen Erweiterung. Also holt ein Skript das Bündel einmal nach `vendor/` und
die Seite lädt es von dort:

```js
const s = document.createElement('script');
s.src = chrome.runtime.getURL('vendor/boerdi-widget.js');
s.onerror = () => zeigeFehler('Bündel nicht ladbar');
s.onload  = () => customElements.whenDefined('boerdi-chat').then(weiter);
document.head.append(s);
```

Ein **gewöhnlicher Skript-Tag**, kein `import()`: das Bündel ist ein klassisches
Skript, kein ES-Modul. Und `onerror` erledigt zwei Fälle mit einem Mechanismus —
Datei fehlt und Datei kaputt.

Dazu eine Frist: ein Bündel, das lädt aber nichts definiert, hinge sonst ewig,
und ewiges Warten sieht aus wie ein langsames Netz statt wie ein Fehler. Das
Beispiel gibt `whenDefined` zehn Sekunden und meldet danach.

Nur wenn ihr das Widget in die **Gastseite** einhängt (§1), darf der Skript-Tag
auf euer Backend zeigen — dort gilt die CSP der Gastseite.

#### 2 · Die eigene Erkennung abschalten und den Kontext selbst geben

In einer Seitenleiste hat `auto-context` nichts zu erkennen: die Adresse ist
`chrome-extension://<id>` und ändert sich nie, auch wenn nebenan der Tab
wechselt. Wer sie stehen lässt, bekommt einen Bot, der über die Erweiterung
spricht statt über die Seite.

```js
chat.setAttribute('auto-context', 'false');
```

Den Kontext gebt ihr selbst — und zwar mit **`replaceContext()`**, nicht mit
`updateContext()`: das eine ersetzt, das andere mergt, und beim Tab-Wechsel
überlebte sonst die Sammlungs-ID des vorigen Tabs (§5).

Die Adresse des Tabs holt ihr über `chrome.tabs`, nicht aus dem eigenen
`location`. Das Muster im Beispiel steht in `context.js` und ist bewusst
**nachgebaut statt importiert**: das Widget hat dieselbe Erkennung eingebaut,
sie zu importieren kettete das Beispiel an den Bauplan des Repositoriums.

#### 3 · Seitentext braucht zwei Klicks — und dieselbe Tab-Kennung

Adresse und Titel gibt `chrome.tabs` her. Der **Text** braucht eine
Host-Berechtigung für genau diese Seite, und `activeTab` genügt dafür **nicht**,
wenn die Erweiterung über die Seitenleiste bedient wird (gemessen 2026-08-14 auf
`de.wikipedia.org`: *„Extension manifest must request permission to access this
host"*).

Nachfragen lässt sich das nicht im selben Klick: `chrome.permissions.request`
verlangt eine Nutzergeste, und die ist nach `await chrome.tabs.query()`
verbraucht. Also zwei Schritte, zwei Knöpfe — und **beide meinen denselben
Tab**:

```js
// Schritt 1
const [aktiv] = await chrome.tabs.query({ active: true, currentWindow: true });
return { url: aktiv.url, titel: aktiv.title, tabId: aktiv.id, herkunft: `${new URL(aktiv.url).origin}/*` };

// Schritt 2 — eigener Klick, und die tabId aus Schritt 1 statt „der aktive Tab"
if (!await chrome.permissions.request({ origins: [herkunft] })) return;
const [t] = await chrome.scripting.executeScript({ target: { tabId }, func: () => document.body?.innerText || '' });
```

Wer in Schritt 2 erneut den aktiven Tab abfragt, liest nach einem Tab-Wechsel
zwischen den Klicks den Text von Seite B unter der Adresse von Seite A — bei
gleicher Herkunft ohne jede Fehlermeldung. Das ist uns im eigenen Review
aufgefallen, nicht im Betrieb; der Test dazu liegt in `scripts/check-tab.mjs`.

Den Text bei **20 000 Zeichen** kappen: das ist die Grenze des Agent-Endpunkts
und ungekappt der häufigste Grund für ein 422.

#### 4 · Berechtigungen erst dann, wenn sie gebraucht werden

Das Manifest verlangt nur `localhost`; jede andere Backend-Adresse wird zur
Laufzeit erfragt, für **genau diese eine Herkunft**:

```json
"host_permissions": ["http://localhost/*", "http://127.0.0.1/*"],
"optional_host_permissions": ["http://*/*", "https://*/*"]
```

```js
if (!await chrome.permissions.contains({ origins: [herkunft] })) {
  await chrome.permissions.request({ origins: [herkunft] });   // MUSS in der Nutzergeste liegen
}
```

`<all_urls>` im Manifest wäre einfacher und ist der Grund, warum viele
Erweiterungen im Store misstrauisch beäugt werden. Der Aufwand ist ein `await`
an der richtigen Stelle: als **erster** Ausdruck im Klick-Griff, vor allem
anderen — sonst ist die Geste verbraucht.

#### 5 · Vor jedem Lauf nachsehen, nicht raten

Eine falsche Backend-Adresse äußerte sich beim Ausprobieren erst dreißig Sekunden
später als *„Entschuldigung, es ist ein Fehler aufgetreten"* — ein Satz, der über
die Ursache nichts sagt. Ursache war die **Bündel-Adresse im Backend-Feld**: der
Chat-Client hängt `/api` an, was dort steht, und aus
`…/widget/boerdi-widget.js` wurde `…/boerdi-widget.js/api/chat/stream`
(gemessen: 404 gegen 200).

Zwei Lehren, beide billig:

* **Einen Knopf „Verbindung prüfen"**, der `GET {basis}/api/health` fragt und die
  Antwort zeigt — samt `repo`. Ob der Bot gegen Staging oder Produktion läuft,
  merkt man sonst erst am Ziel eines Karten-Links.
* **Den einen eindeutigen Tippfehler korrigieren und es SAGEN.** Endet der Pfad
  auf `.js`, ist es die Bündel-Adresse; gerechnet wird mit der Herkunft, und der
  Hinweis bleibt stehen. Ein Pfad-Präfix (`https://host/boerdi`, Reverse-Proxy)
  bleibt dagegen unangetastet — ein falsch geratener Wert ist schlimmer als ein
  falsch getippter, weil ihn niemand mehr sieht.

#### 6 · Das Element neu aufbauen, statt Attribute nachzuziehen

Bei „Starten" baut das Beispiel `<boerdi-chat>` neu auf. Das kostet die Sitzung,
und genau das ist gewollt: `api-url` und die Sitzungs-Attribute gehören zu
Klasse **C** der Laufzeit-Tabelle (§3) und würden sonst still den alten Wert
behalten — ein Versuchsaufbau, bei dem der halbe Zustand von vorhin überlebt,
misst das Falsche.

```js
halter.replaceChildren();
leereErgebnisse();                                  // Liste UND Zählung
const chat = document.createElement('boerdi-chat');
chat.setAttribute('api-url', basis);
chat.setAttribute('embed-mode', 'frameless');       // kein FAB, kein Rahmen
chat.setAttribute('engine', 'agent');
chat.setAttribute('auto-context', 'false');
chat.setAttribute('show-welcome', 'false');         // §4a
if (schema) chat.setAttribute('result-schema', JSON.stringify(schema));
halter.append(chat);

await customElements.whenDefined('boerdi-chat');
await new Promise(requestAnimationFrame);           // eine Runde fürs Aufwerten
chat.replaceContext(ctx);
chat.startTask(auftrag);
```

Das `requestAnimationFrame` ist Vorsicht mit Grund: die JS-API des Elements
(`openChatbot`, `replaceContext`, `startTask`, …) liegt auf dem Prototyp und
delegiert an die Komponenten-Instanz. Existiert die noch nicht, ist der Aufruf
ein **No-Op statt einer Exception** — bewusst so, damit eine frühe Gastseite
nichts zerbricht, aber eben auch: still. Eine Bildrunde kostet nichts und nimmt
diese Klasse von Fehlern aus dem Spiel.

Und: die Ergebnisliste gehört mit geleert. Sonst stehen Einträge zweier Läufe
mit verschiedenen Schemata untereinander und die Zählung läuft weiter — „Zug 5"
über der ersten Antwort des neuen Laufs.

#### Was der Ordner sonst noch zeigt

| Datei | wofür sie ein Muster ist |
|---|---|
| `background.js` | Der Dienst-Worker tut genau eins: `sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` |
| `tabs.js` | Zwei Reiter nach ARIA-Praxis (Pfeile, Home/End, roving `tabindex`). Der Chat wird beim Wechseln **versteckt, nie neu gebaut** — er hält Sitzung und Verlauf in seiner Instanz |
| `einstellungen.js` | Eingaben in `chrome.storage.local` (nicht `sync`: IDs und Seitentexte einer Arbeitssitzung gehören nicht über alle Geräte verteilt) |
| `schemas.js` | Fünf Auftrags-Vorlagen — und die Prüfung des Schema-Feldes. „Leer" ist gültig, „kaputt" nicht: ein Tippfehler darf keinen 90-Sekunden-Lauf kosten, der garantiert kein Ergebnis liefern kann |
| `scripts/check-*.mjs` | Sechs Prüfungen ohne Browser und ohne Abhängigkeiten (`npm run check`), in der CI verdrahtet |

Was das Beispiel **nicht** zeigt: einen Anmelde-Weg. Es gibt weder Ticket noch
Zugangsblock, der Bot arbeitet anonym und kann deshalb nichts schreiben. Für den
angemeldeten Betrieb siehe `docs/edu-sharing-einbindung.md` §3.

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
3. Das Modell holt sich den Volltext der passenden Anleitung mit `get_skill` —
   die `nodeId` dafür steht schon in der vorab geholten Registry aus Schritt 1 —
   und arbeitet danach.
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
| **CORS** | Erledigt seit 18.08.2026, doppelt: CORS ist **standardmäßig offen** (`CORS_ALLOW_ALL`, Vorgabe an), und selbst bei enger Liste dürfen `chrome-extension://` und `safari-web-extension://` (`CORS_ALLOW_EXTENSIONS`). **Safari brauchte das zwingend** — dort ist die UUID je Installation eine andere, ein Listeneintrag also unmöglich. Fragt beim Betreiber nach, falls der Schalter aus ist. |
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
| Der Chat legt sich über **eure** Kopfleiste und Navigation | Widget-Bündel älter als 2026-08-17 → neu bauen. Bis dahin überlebte `position: fixed; inset: 0` aus der 480-px-Vollbild-Regel den rahmenlosen Modus; in einer Seitenleiste unter 480 px riss sich das Panel damit aus seinem Flex-Platz. Gepinnt in `frontend/e2e/frameless.spec.ts` |
| Element bleibt ein leeres Tag | Bündel lief in der isolierten Welt des Content-Scripts, nicht in der Hauptwelt (§1) |
| Der Chat startet geschlossen | `initial-state="expanded"` fehlt |
| Jedes Ereignis kommt doppelt | Auf `boerdi:…` **und** `badboerdi:…` gehört (§6) |
| `engine="agent"` wirkt nicht | Ausgeliefertes Widget-Bündel älter als das Attribut → neu bauen |
| `page-context` zur Laufzeit gesetzt, nichts passiert | Das Attribut wird nach dem Start nicht mehr gelesen — nehmt `replaceContext()` (§3, §5) |
| Der Bot sagt „Du bist auf `<Erweiterungs-Kennung>` — das gehört nicht zu WLO" | Die eigene Erkennung lief auf der Adresse der Seitenleiste. Ab 2026-08-14 trägt sie dort nichts mehr bei; setzt zusätzlich `auto-context="false"` und gebt den Kontext selbst mit (§5) |
| Der Bot spricht über die Sammlung des VORIGEN Tabs | `updateContext` mergt. Für einen Seitenwechsel ist `replaceContext` das Richtige (§5) |
| Nach dem Kontext-Wechsel begrüßt der Bot die neue Seite nicht | Auch das ist der Unterschied: nur `replaceContext` setzt das Ping-Gate zurück (§5) |
| `updateContext()` aufgerufen, es passiert sichtbar nichts | Genau so ist es gedacht: kein Ping, keine Nachricht. Der Kontext wirkt ab dem nächsten Zug. Wollt ihr eine Begrüßung, nehmt `replaceContext` (§5) |
| Zweiter Artikel **desselben Hosts** wird nicht begrüßt | Backend älter als 2026-08-17: fremde Seiten wurden hostweise entdoppelt. Danach zählt die Adresse (§5) |
| Im wiederhergestellten Verlauf fehlen die Knöpfe der Kontext-Begrüßung | Quick-Replies werden nicht persistiert (`db_sessions.save_message`); der Verlauf trägt nur den Text. Beim Seitenwechsel kommt eine neue Begrüßung samt Knöpfen |
| Einordnung nach Fach/Stufe bleibt vage | Nur der Seitentitel im `page_text`. Schickt ~3 KB Text mit (§5, Rezept 2) |
| „Konnte nicht gegen das `discipline`-Vokabular geprüft werden" | Muster-Modus: das gewählte Muster (M04) führt `lookup_wlo_vocabulary` nicht. Für Einordnungen `engine="agent"` setzen (§5, Rezept 2) |
| `tools_called` bleibt leer, obwohl der Auftrag Werkzeuge nennt | Dasselbe: im Muster-Modus entscheidet das **Muster** über die Werkzeugliste, nicht der Auftragstext (§4, §5) |
| Der Bot bietet an, Metadaten in WLO zu schreiben, tut es aber nicht | Ohne Zugangsblock sind die kuratierenden Werkzeuge gar nicht im Katalog. Anonym geht Einordnen, nicht Schreiben (§5, Rezept 2 · §8) |
| `linkClicked` feuert nie | `intercept-edu-sharing-links="true"` fehlt |
| Klick auf die Such-Pille tut nichts, Material-Links gehen | `intercept-edu-sharing-links="true"` ist an und euer `linkClicked`-Handler behandelt `components/search` nicht — oder navigiert auf dieselbe Route ohne `onSameUrlNavigation: 'reload'` (§6a) |
| `guide-suggestion` feuert nie | `emit-guide-suggestion="true"` fehlt (Opt-in) |
| Klick auf einen Link der **Gastseite** bekommt kein `?bsid=` | Der Klick-Wächter greift nur im Shadow-Root des Widgets — die Navigation der Gastseite bleibt unangetastet. Wer die ID braucht, hängt sie selbst an |
| `result` ist `null` | Kein `result_schema` mitgegeben — oder `stop_reason !== 'submit'` |
| `boerdi:agent-result` kommt nie | `engine="agent"` fehlt am Element. Das Attribut `result-schema` allein wirkt nicht; die Warnung steht nur im Backend-Protokoll, nicht im Browser (§7a) |
| `result-schema` gesetzt, nichts passiert | Kaputtes JSON — es gilt dann als „kein Schema". Die `console.warn`-Zeile im Browser nennt es. Achtet auf die Anführungszeichen (außen `'`, innen `"`) (§7a) |
| `422` beim Chat-Zug | Das `result_schema` ist länger als 200 000 Zeichen. Abgelehnt statt gekürzt: ein halbes Schema verlangte eine andere Form, als ihr wolltet (§7a) |
| Der Auftrag aus `startTask` erscheint nicht | Leerer Text wird verworfen. Sonst wartet er, bis die Shell gemountet ist, und läuft dann (§5) |
| Der Bot antwortet auf den Auftrag ohne den Seitenkontext | `replaceContext()` **vor** `startTask()` — der Auftrag geht sofort raus (§5) |
| `tools_called` enthält kein `get_skill` | Das Modell hat die Anleitung nicht gelesen. Die Anweisung war zu unbestimmt — nennt die Aufgabe und verlangt ausdrücklich, sich an eine passende Anleitung zu halten (§7) |
| 422 an `/api/agent` | `instruction` über 20 000 Zeichen — meist der mitgeschickte Seitentext. Kürzen (§7) |
| CORS-Fehler in der Erweiterungs-Konsole | Seit 18.08.2026 sind `chrome-extension://` und `safari-web-extension://` **von sich aus erlaubt** (`CORS_ALLOW_EXTENSIONS`, Vorgabe an). Tritt der Fehler trotzdem auf: der Betreiber hat **beide** Schalter zu (`CORS_ALLOW_ALL=false` **und** `CORS_ALLOW_EXTENSIONS=false`) |
| Safari: `Preflight response is not successful. Status code: 400` | Dasselbe. Die 400 ist Starlettes „Disallowed CORS origin" — sie sagt nur, dass die Herkunft abgewiesen wurde, nicht dass mit dem Rumpf etwas nicht stimmt |
| 401 / 403 an `/api/agent` | Keiner der drei Zugangswege greift (§7) |
| 429 | Drosselung, `RATE_LIMIT_CHAT` |
| 503 auf `/widget/boerdi-widget.js` | Bündel nicht gebaut — die Antwort nennt den Befehl |
| Eigene Startnachricht erscheint beim Öffnen nicht | Es lag schon ein Seitenkontext an — die Kontext-Begrüßung ist dann die Eröffnung (§4a). Element ohne `page-context` einhängen, Kontext danach per `replaceContext()` |
| Bei jedem Seitenwechsel wächst eine Startnachricht nach | Bündel älter als 17.08.2026: `grep -c "CTX:" boerdi-widget.js` gibt `0` (§4a) |
| `replaceContext()` bleibt im Panel-Modus wirkungslos | Die Shell entsteht erst beim ersten Öffnen; vorher geht der Aufruf ins Leere (§4a) |
