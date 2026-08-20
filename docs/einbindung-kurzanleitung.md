# BOERDi einbinden — Kurzanleitung

Kompakte Referenz für Integratoren. Ausführlich: `browser-plugin-einbindung.md`
(Browser-Erweiterung) und `edu-sharing-einbindung.md` (Repository-Seiten).

---

## 1. Minimal-Einbau

```html
<script type="module" src="https://<host>/widget/boerdi-widget.js"></script>

<boerdi-chat
  api-url="https://<host>"
  engine="agent">
</boerdi-chat>
```

Das war's. Alles Weitere sind Vorgaben, die ihr überschreiben könnt.

**Empfohlener Start für eine Anwendung mit eigenem Kontext:**

```html
<boerdi-chat
  api-url="https://<host>"
  engine="agent"
  master-skill="on"
  tool-mode="read-only"
  embed-mode="frameless"
  initial-state="expanded"
  auto-context="false"
  emit-routing-debug="true">
</boerdi-chat>
```

---

## 2. Alle Attribute

### Basis

| Attribut | Vorgabe | Werte / Bedeutung |
|---|---|---|
| `api-url` | — | **Pflicht.** Backend-Basis-URL |
| `embed-mode` | `panel` | `panel` \| `frameless` (ohne Rahmen, FAB und Kopfzeile) |
| `size` | `small` | `small` \| `large` — Anfangsgröße, zur Laufzeit umschaltbar |
| `engine` | *(leer)* | `pattern` \| `agent` \| `hybrid`; leer = Vorgabe aus `01-base/engine` |
| `result-schema` | *(leer)* | JSON-Schema als **String**; schaltet den strukturierten Ausgang ein |
| `master-skill` | *(leer)* | `on` \| `off`; fehlt = Betreiber-Vorgabe. Nur `agent`/`hybrid` |
| `tool-mode` | `full` | `read-only` \| `curate` \| `full`. Nur `agent`/`hybrid` |
| `ticket` | — | EDU-TICKET; der Bot handelt dann als die angemeldete Person |

### Darstellung

| Attribut | Vorgabe | Werte |
|---|---|---|
| `position` | `bottom-right` | `bottom-right` \| `bottom-left` \| `top-right` \| `top-left` |
| `initial-state` | `collapsed` | `collapsed` \| `expanded` |
| `theme` | `auto` | `auto` \| `light` \| `dark` |
| `primary-color` | *(leer)* | Akzentfarbe, sonst `#1c4587` |
| `language` | *(leer)* | `de` \| `en`; leer = Browsersprache |
| `show-cards` | `auto` | `auto` (klein → Links, groß → Kacheln) \| `true` \| `false` |
| `inline-result-grouping` | `true` | `false` = keine gruppierten Boxen — **und das Modell erfährt es** |
| `show-welcome` | `true` | Begrüßungsblase zeigen |
| `show-debug-button` | `true` | Debug-Umschalter in der Kopfzeile |
| `show-language-buttons` | `true` | Mikro- und Vorlese-Knöpfe |

### Start und Schnellantworten

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `greeting` | — | Eigene Begrüßung; schlägt die Studio-Vorgabe |
| `start-replies` | *(leer)* | JSON-Array — Chips **nur** unter der Begrüßung |
| `quick-replies` | *(leer)* | JSON-Array — Chips **je Zug**, höchstens 6 |
| `quick-replies-max` | *(leer)* | Mix-Modus: Gesamtzahl 1–6 — eigene Chips zuerst, KI füllt den Rest |

### Sitzung

| Attribut | Vorgabe |
|---|---|
| `persist-session` | `true` |
| `session-key` | `boerdi_session_id` |
| `session-cookie-domain` | *(leer)* |
| `session-cookie-max-age` | `2592000` (30 Tage) |

### Kontext und Ereignisse

| Attribut | Vorgabe | Bedeutung |
|---|---|---|
| `auto-context` | `true` | Adresse und Titel selbst erkennen; `false` = ihr liefert |
| `page-context` | — | JSON-Objekt, siehe §5 |
| `trusted-domains` | *(leer)* | Kommaliste, wird mit der Backend-Liste gemergt |
| `emit-routing-debug` | `false` | `true` → Ereignis `boerdi:routing-debug` |
| `emit-guide-suggestion` | `false` | `true` → Ereignis `boerdi:guide-suggestion` |
| `intercept-edu-sharing-links` | `false` | `true` → Repo-Links werden abgefangen; **ihr müsst `linkClicked` behandeln**, sonst sind die Klicks tot |

---

## 3. Begrüßung und Start-Chips hartcodieren

```html
<boerdi-chat
  api-url="https://<host>"
  engine="agent"
  greeting="Ich helfe dir bei dieser Sammlung. Was brauchst du?"
  start-replies='["Was steckt in dieser Sammlung?","Lücken prüfen","Stunde planen"]'>
</boerdi-chat>
```

Chips **je Zug** statt nur am Anfang:

```html
<boerdi-chat quick-replies='["Passt","Passt nicht","Erschließen"]'></boerdi-chat>
```

```js
chat.setQuickReplies(['Passt', 'Passt nicht', 'Erschließen']);
chat.setQuickReplies([]);   // wieder freigeben
// Mix: 2 eigene Chips, das Modell füllt bis 4 auf
chat.setQuickReplies(['Passt', 'Passt nicht']);
chat.setQuickRepliesMax(4);
```

**Regeln:** Der Chip-**Text** ist die gesendete Nachricht — als Anfrage formulieren,
nicht als Etikett. Höchstens sechs (überzählige fallen weg, der Text wird nie
gekürzt). Die Liste bleibt gesetzt, bis ihr sie ersetzt oder leert.

### Vorrang (gemessen, gilt in allen drei Maschinen)

| | Begrüßungstext | Start-Chips |
|---|---|---|
| 1. stärkste | **Kontext-Begrüßung des Backends**, sobald ein Seitenkontext erkannt ist („Ich sehe 125 Materialien und 3 freigegebene Skills") | — |
| 2. | `greeting`-Attribut | `start-replies`-Attribut |
| 3. schwächste | Studio-Vorgabe (`01-base/welcome-config`) | Studio-Vorgabe |

**Die Falle:** Wer `page-context` mitgibt, sieht sein `greeting` **nicht** — die
Kontext-Begrüßung gewinnt. Die Chips bleiben davon unberührt. Wollt ihr euren
eigenen Text sehen, gebt beim Aufbau keinen Kontext mit (später per
`replaceContext` nachreichen) oder schaltet die Blase mit `show-welcome="false"` ab.

Die Studio-Vorgabe könnt ihr ohne Anmeldung nachlesen:

```bash
curl -s https://<host>/api/config/guide-mode | jq .welcome
```

### Drei Auswege, je nach Absicht

```html
<!-- a) eigener Text: Kontext erst NACH dem Aufbau nachreichen -->
<boerdi-chat greeting="Ich helfe dir hier. Was brauchst du?"
             start-replies='["Sammlungsinhalte zeigen","Stunde planen"]'>
</boerdi-chat>
<script>
  chat.replaceContext({ page_kind: 'collection', collection_id: '…' });
</script>

<!-- b) gar keine Begrüßungsblase -->
<boerdi-chat show-welcome="false"></boerdi-chat>

<!-- c) Kontext-Begrüßung behalten, nur eigene Chips  ←  meist die beste Wahl -->
<boerdi-chat page-context='{"page_kind":"collection","collection_id":"…"}'
             start-replies='["Stunde planen","Lücken prüfen"]'>
</boerdi-chat>
```

Bei (c) nennt der Backend-Satz echte Zahlen aus der Sammlung („Ich sehe 125
Materialien und 3 freigegebene Skills dazu"), und die Chips steuert ihr trotzdem
selbst.

### Zentral im Studio statt je Einbau

Reiter **Begrüßung** → `01-base/welcome-config.yaml`, je Sprache ein Satz Felder:

| Feld | Bedeutung |
|---|---|
| `greeting` · `greeting_en` | Begrüßungstext |
| `quick_replies` · `quick_replies_en` | die Start-Chips |
| `tour_reply` · `tour_reply_en` | welcher Chip die Web-Tour startet |

Welche Sprache gilt, entscheidet `language` (sonst der Browser). Änderungen wirken
ohne Neustart und ohne Deployment.

### Maschinen-unabhängig

Die Begrüßung ist **kein Modellzug**: das Widget baut sie aus den Attributen bzw.
aus `GET /api/config/guide-mode`. `engine` kommt in diesem Weg nicht vor —
`pattern`, `agent` und `hybrid` verhalten sich identisch (im Agent-Modus
nachgemessen, 2026-08-19).

---

## 4. JS-API

```js
await customElements.whenDefined('boerdi-chat');
const chat = document.querySelector('boerdi-chat');

chat.openChatbot();          // öffnen, ans Ende scrollen, Eingabe fokussieren
chat.closeChatbot();
chat.toggleChatbot();
chat.isChatbotOpen();        // → boolean
chat.resetSession();         // neue Sitzung

chat.updateContext({ … });   // Seitenkontext ERGÄNZEN (mergt)
chat.replaceContext({ … });  // Seitenkontext ERSETZEN (wie eine Navigation)

chat.startTask('…');                 // Zug — SICHTBAR als Auftrags-Blase
chat.setHostInstruction('…');        // Rahmen — UNSICHTBAR, kein Verlaufseintrag
chat.setQuickReplies([...]);
chat.setMasterSkill(true|false|null);
chat.setToolMode('read-only'|'curate'|'full');
chat.setResultSchema({ … });
```

Vor dem Upgrade liefern die Methoden `undefined` statt eines Fehlers — es passiert
dann nichts. Nur `startTask` und `setHostInstruction` warten auf die Shell.

---

## 5. Kontext aktiv reinreichen

### Sammlung (nodeId)

```js
chat.replaceContext({
  page_kind: 'collection',
  collection_id: '9e7ae956-e9df-430f-bace-f3db4b910013',
});
chat.setQuickReplies([
  'Was steckt in dieser Sammlung?',
  'Lücken gegen das Kompendium prüfen',
  'Stunde planen',
]);
```

`collection_id` ist der Schlüssel zu den Skills: das Backend holt die
Skill-Registry dieser Sammlung **vorab**, und der Seitenblock listet die
freigegebenen Anleitungen mit Titel.

### Themenseite

```js
chat.replaceContext({
  page_kind: 'topic_page',
  collection_id: '…-UUID-…',          // Themenseiten hängen an einer Sammlung
  topic_page_slug: 'optik',
});
chat.setQuickReplies(['Inhalte der Themenseite zeigen', 'Ähnliche Themenseiten']);
```

### Einzelinhalt

```js
chat.replaceContext({
  page_kind: 'content',
  node_id: '…-UUID-…',
});
chat.setQuickReplies(['Volltext anzeigen', 'Ähnliche Inhalte suchen']);
```

### Fremde Webseite (Browser-Erweiterung)

```js
chat.replaceContext({
  page_kind: 'external',
  url: location.href,
  title: document.title,
  collection_id: '…-UUID-…',          // Zielsammlung, wenn bekannt
});
chat.setQuickReplies(['Seite prüfen', 'In WLO aufnehmen', 'Metadaten vorschlagen']);
```

**Reihenfolge:** erst Kontext, dann Auftrag. `startTask` nimmt mit, was in diesem
Moment gesetzt ist.

---

## 6. Prompt aktiv reinreichen

| Weg | sichtbar? | Lebensdauer |
|---|---|---|
| `startTask(text)` | **ja**, als Auftrags-Blase | ein Zug, sofort |
| `setHostInstruction(text)` | nein | ein Zug, wartet auf die Eingabe |
| `setHostInstruction(text, {trigger:'now', message:'…'})` | `message` ja, Rahmen nein | löst sofort aus |
| `setHostInstruction('')` | — | verwirft den Rahmen |

```js
// sichtbar
chat.startTask('Fasse zusammen, worum es auf dieser Seite geht.');

// unsichtbar — die Person stellt ihre eigene Frage, der Rahmen reist mit
chat.setHostInstruction(
  'Du bist in der Redaktionsumgebung. Bewerte den Füllstand gegen den '
  + 'kompendialen Text und schlage passende Materialien vor.'
);

// unsichtbarer Rahmen + sofortiger Zug
chat.setHostInstruction('…Rahmen…', { trigger: 'now', message: 'Füllstand prüfen' });
```

Der Rahmen ist **einmalig** — für dauerhaft nach jedem Zug neu setzen.
Kein Zeichendeckel (seit 18.08.2026), eine ganze Schritt-Anleitung passt hinein.

### Strukturierter Output (optional)

```html
<boerdi-chat
  engine="agent"
  result-schema='{"type":"object","properties":{
      "eignung":{"type":"string","enum":["geeignet","ungeeignet"]},
      "begruendung":{"type":"string"},
      "fach":{"type":"string"}},
    "required":["eignung","begruendung"]}'>
</boerdi-chat>
```

```js
chat.addEventListener('boerdi:agent-result', (e) => {
  console.log(e.detail);        // das Objekt nach eurem Schema
});
```

Nur mit `engine="agent"` oder `hybrid`; kostet einen zusätzlichen Modellzug (2–9 s
gemessen), deshalb opt-in. Der Chat antwortet **zusätzlich** in Prosa — das
Ergebnis geht an eure Anwendung, nicht an die Person. Höchstens 200 000 Zeichen,
sonst `422`. Ohne Schema gibt es das Werkzeug nicht.

---

## 7. Master-Skill und Werkzeug-Erlaubnis

```html
<boerdi-chat master-skill="off" tool-mode="read-only"></boerdi-chat>
```

```js
chat.setMasterSkill(false);   // aus
chat.setMasterSkill(true);    // an
chat.setMasterSkill(null);    // zurück auf die Betreiber-Vorgabe
```

`master-skill` hat **drei** Zustände — das nackte Attribut ohne Wert gilt als
„nichts gesagt", nicht als „an". Als Aus gelten `off`, `false`, `0`, `no`, `aus`.

`tool-mode` wirkt zweifach: die verbotenen Werkzeuge fehlen in der Liste **und**
das Modell erfährt es, damit es nichts verspricht, was es nicht kann.

Beide nur mit `engine=agent|hybrid` — im Mustermodus wirkungslos.

---

## 8. Anzeige steuern

### Im Chat

```html
<boerdi-chat
  embed-mode="frameless"          <!-- ohne Rahmen, für Seitenleisten -->
  size="large"
  initial-state="expanded"
  theme="light"
  primary-color="#1c4587"
  show-cards="true"
  inline-result-grouping="false"  <!-- keine Boxen; das Modell weiß es -->
  show-welcome="false"
  show-debug-button="false"
  show-language-buttons="false">
</boerdi-chat>
```

### Außerhalb — die Ereignisse

```js
chat.addEventListener('boerdi:agent-result',   e => …);  // strukturiertes Ergebnis
chat.addEventListener('boerdi:collection-id',  e => …);  // erkannte Sammlung
chat.addEventListener('boerdi:node-id',        e => …);  // erkannter Einzelinhalt
chat.addEventListener('boerdi:topic-slug',     e => …);  // erkannte Themenseite
chat.addEventListener('boerdi:page-action',    e => …);  // Leinwand / Lotse
chat.addEventListener('boerdi:query-meta',     e => …);  // was gesucht wurde
chat.addEventListener('boerdi:printable-canvas', e => …); // druckbarer Inhalt
chat.addEventListener('boerdi:guide-suggestion', e => …); // nur mit emit-guide-suggestion
chat.addEventListener('boerdi:routing-debug',  e => …);  // nur mit emit-routing-debug
```

**Zuhörer vor dem Auftrag anmelden** — `startTask` schickt sofort, ein später
angemeldeter Zuhörer verpasst den ersten Zug.

Wollt ihr die Treffer selbst rendern: `inline-result-grouping="false"` setzen und
`boerdi:query-meta` mitlesen.

---

## 9. Die fünf häufigsten Fehler

1. Methoden vor `customElements.whenDefined('boerdi-chat')` gerufen → passiert nichts.
2. `startTask` vor dem Kontext → der Zug läuft ohne ihn.
3. Ereignis-Zuhörer nach `startTask` angemeldet → erster Zug verpasst.
4. `<boerdi-chat master-skill>` ohne Wert → gilt als „nichts gesagt", nicht als „an".
5. `result-schema` als Objekt statt als String im HTML-Attribut → gilt als kaputt
   und damit als „kein Schema"; die Meldung steht nur in der Browser-Konsole.
