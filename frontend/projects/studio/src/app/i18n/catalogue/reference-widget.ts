/**
 * Der Widget-Vertrag in der Referenz (C1-d5b2): Einbettung, die Host-Attribute,
 * die Ereignisse.
 *
 * Ohne Zahlen im Kopf, mit Absicht: die Liste ist zweimal gewachsen (`ticket`
 * 2026-08-12, `result-schema` + `boerdi:agent-result` 2026-08-14), und eine
 * mitgezaehlte Zahl im Fliesstext wird beim dritten Mal falsch, ohne dass ein
 * Test es merkt. Gezaehlt wird dort, wo es prueft: im Attribut-Waechter der
 * Widget-Spec.
 *
 * **Dieselbe Regel wie in C1-d5a2 — und derselbe Sonderfall, zweimal anders
 * entschieden.** Was im `<code>` steht, ist Bezeichner und bleibt Daten. Zwei
 * Spalten mischen aber:
 *
 *  - **Default** (22 Zellen): 19 sind echte Vorgabewerte (`true`, `2592000`,
 *    `bottom-right`), drei sind das deutsche Wort „leer". Hier traegt die
 *    Datenzeile ein *optionales* `fallbackKey` — die Bezeichner durch den
 *    Katalog zu schleifen hiesse ebenso viele Eintraege in der Erlaubnisliste,
 *    also lauter Rauschen fuer drei Woerter.
 *  - **Wann** (4 Zellen): zwei sind Prosa, zwei sind Attribut-Schreibweisen.
 *    Bei zwei gegen zwei ist die einheitliche Spalte billiger als die
 *    Verzweigung — deshalb gehen alle vier durch den Katalog, wie schon bei
 *    der Quellen-Spalte der Pattern-Wahl.
 *
 * Die Gruppen-Namen tragen einen **zweiten Auftrag**: `isGroupStart` vergleicht
 * die Gruppe einer Zeile mit der ihrer Vorzeile, damit sie nur einmal genannt
 * wird. Als Schluessel bleibt der Vergleich heil; als uebersetzter Text waere
 * er es auch, aber nur solange beide Sprachen dieselbe Reihenfolge haben — der
 * Schluessel macht die Unabhaengigkeit davon sichtbar.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE_WIDGET: CataloguePart = {
  de: {
    'rw.title': 'Widget-Einbettung (Web-Komponente)',
    'rw.intro':
      'Der Chat lässt sich als Custom Element `<boerdi-chat>` auf jeder Seite '
      + 'einbinden. Das Single-File-Bundle entsteht mit `npm run build:widget`.',
    // Die drei Kommentare des Einbettungs-Beispiels. Der Code selbst bleibt in
    // `widget-contract-data.ts` — zweimal gepflegt driftet er auseinander.
    'rw.sample.minimal': 'Minimal: alle Defaults',
    'rw.sample.lean': 'Schlank: ohne Debug-Knopf',
    'rw.sample.edu': 'edu-sharing-Embed: eigenes Link-Routing, Routing-Telemetrie an',

    'rw.attrTitle': 'Attribute',
    'rw.boolNote':
      'Alle Boolean-Attribute nehmen die Strings `"true"` und `"false"` — '
      + 'Attribute eines Custom Elements sind immer Strings.',
    'rw.col.group': 'Gruppe',
    'rw.col.attr': 'Attribut',
    'rw.col.default': 'Default',
    'rw.col.desc': 'Beschreibung',
    'rw.default.empty': 'leer',

    'rw.group.basis': 'Basis',
    'rw.group.session': 'Session',
    'rw.group.kontext': 'Kontext',
    'rw.group.anzeige': 'Anzeige',
    'rw.group.integration': 'Integration',

    'rw.attr.apiUrl': 'Backend-Basis-URL (Pflicht)',
    'rw.attr.embedMode': 'panel | frameless — rahmenlos ohne Kopfzeile und '
      + 'Aufklapp-Knopf, füllt den Container der Gastseite',
    'rw.attr.size': 'small | large — Anfangs-Größenstufe des Panels; '
      + 'umschaltbar über den Knopf in der Eingabezeile',
    'rw.attr.engine': 'pattern | agent — welche Maschine diesen Einbau '
      + 'beantwortet; leer nimmt die Vorgabe aus 01-base/engine (Kopfzeile '
      + 'X-Boerdi-Engine)',
    'rw.attr.resultSchema': 'JSON-Schema, in dem dieser Einbau sein Ergebnis '
      + 'erwartet; liefert je Zug boerdi:agent-result. Wirkt NUR mit '
      + 'engine="agent" und kostet dort einen zusätzlichen Modellzug (2–9 s)',
    'rw.attr.position': 'bottom-right | bottom-left | top-right | top-left',
    'rw.attr.initialState': 'collapsed | expanded',
    'rw.attr.primaryColor': 'Akzentfarbe; leer lässt den CSS-Default #1c4587 greifen',
    'rw.attr.greeting': 'Eigene Begrüßungsnachricht',
    'rw.attr.persistSession': 'Session in localStorage bzw. Cookie halten',
    'rw.attr.sessionKey': 'localStorage-Schlüssel',
    'rw.attr.sessionCookieDomain':
      'Gesetzt: Session im Cookie statt localStorage (Cross-Subdomain)',
    'rw.attr.sessionCookieMaxAge': 'Cookie-Lebensdauer in Sekunden (30 Tage)',
    'rw.attr.trustedDomains':
      'Komma-Liste der Hosts, die die Session-ID per ?bsid= erhalten dürfen; '
      + 'ergänzt die Backend-Liste, kürzt sie nicht',
    'rw.attr.autoContext': 'Seitenkontext automatisch erfassen',
    'rw.attr.pageContext': 'JSON-Objekt mit zusätzlichem Kontext',
    'rw.attr.showDebugButton': 'Debug-Umschalter in der Kopfzeile zeigen',
    'rw.attr.showLanguageButtons':
      'Vorlese- und Mikrofon-Knopf zeigen (zusätzlich an die Backend-Capability gekoppelt)',
    'rw.attr.inlineResultGrouping':
      'false = flaches Karten-Grid mit Seitenblättern statt der Ergebnis-Boxen',
    'rw.attr.showCards':
      'auto | always | never — Treffer als Kacheln mit Vorschaubild statt als '
      + 'Textlinks; auto heißt klein Textlinks, groß Kacheln',
    'rw.attr.theme':
      'auto | light | dark — auto heißt: das Widget setzt nichts und erbt das '
      + 'color-scheme der Seite',
    'rw.attr.language':
      'de | en; leer = die Seite entscheidet (nächstes [lang], sonst Browser, sonst '
      + 'Deutsch). Der Umschalter im Widget schlägt dieses Attribut',
    'rw.attr.interceptEduSharingLinks':
      'true: Link-Klicks feuern linkClicked statt zu navigieren',
    'rw.attr.emitGuideSuggestion': 'true: Lotsen-Treffer als boerdi:guide-suggestion',
    'rw.attr.emitRoutingDebug':
      'true: Routing-Telemetrie je Bot-Turn als boerdi:routing-debug',
    'rw.attr.ticket':
      'edu-sharing-Ticket der Gastgeberseite (Betriebsform „das Repositorium '
      + 'bettet ein"): einmal gelesen, sofort aus dem DOM entfernt und beim '
      + 'MCP-Server gegen einen Zugangsblock getauscht — die auf der Seite '
      + 'angemeldete Person ist dann auch im Chat angemeldet',

    'rw.eventsTitle': 'Events',
    'rw.col.event': 'Event',
    'rw.col.when': 'Wann',
    'rw.col.payload': 'Payload',
    'rw.when.pageAction': 'immer aktiv (nur als window-Event)',
    'rw.when.queryMeta': 'immer aktiv',
    'rw.when.guideSuggestion': 'emit-guide-suggestion="true"',
    'rw.when.routingDebug': 'emit-routing-debug="true"',
    'rw.when.agentResult': 'result-schema gesetzt + engine="agent"',

    'rw.outputs':
      'Angular-Outputs für programmatische Einbindung: `{outputs}`. `linkClicked` '
      + 'feuert nur mit `intercept-edu-sharing-links="true"`. Das ausführliche '
      + 'Payload-Schema steht in `docs/05-widget-javascript-api.md`.',
  },

  en: {
    'rw.title': 'Widget embedding (web component)',
    'rw.intro':
      'The chat can be embedded on any page as the custom element '
      + '`<boerdi-chat>`. The single-file bundle is built with '
      + '`npm run build:widget`.',
    'rw.sample.minimal': 'Minimal: all defaults',
    'rw.sample.lean': 'Lean: without the debug button',
    'rw.sample.edu': 'edu-sharing embed: own link routing, routing telemetry on',

    'rw.attrTitle': 'Attributes',
    'rw.boolNote':
      'All boolean attributes take the strings `"true"` and `"false"` — the '
      + 'attributes of a custom element are always strings.',
    'rw.col.group': 'Group',
    'rw.col.attr': 'Attribute',
    'rw.col.default': 'Default',
    'rw.col.desc': 'Description',
    'rw.default.empty': 'empty',

    'rw.group.basis': 'Basics',
    'rw.group.session': 'Session',
    'rw.group.kontext': 'Context',
    'rw.group.anzeige': 'Display',
    'rw.group.integration': 'Integration',

    'rw.attr.apiUrl': 'Backend base URL (required)',
    'rw.attr.embedMode': 'panel | frameless — frameless drops the header and '
      + 'the launcher button and fills the host container',
    'rw.attr.size': 'small | large — initial panel size step; switchable via '
      + 'the button in the composer row',
    'rw.attr.engine': 'pattern | agent — which engine answers for this embed; '
      + 'empty takes the default from 01-base/engine (header X-Boerdi-Engine)',
    'rw.attr.resultSchema': 'JSON schema this embed expects its result in; '
      + 'emits boerdi:agent-result per turn. Works ONLY with engine="agent" '
      + 'and costs one extra model round there (2–9 s measured)',
    'rw.attr.position': 'bottom-right | bottom-left | top-right | top-left',
    'rw.attr.initialState': 'collapsed | expanded',
    'rw.attr.primaryColor': 'Accent colour; empty lets the CSS default #1c4587 apply',
    'rw.attr.greeting': 'A greeting message of your own',
    'rw.attr.persistSession': 'Keep the session in localStorage or a cookie',
    'rw.attr.sessionKey': 'localStorage key',
    'rw.attr.sessionCookieDomain':
      'When set: session in a cookie instead of localStorage (cross-subdomain)',
    'rw.attr.sessionCookieMaxAge': 'Cookie lifetime in seconds (30 days)',
    'rw.attr.trustedDomains':
      'Comma-separated list of hosts allowed to receive the session id via ?bsid=; '
      + 'it extends the backend list, it does not shorten it',
    'rw.attr.autoContext': 'Capture the page context automatically',
    'rw.attr.pageContext': 'JSON object with additional context',
    'rw.attr.showDebugButton': 'Show the debug toggle in the header',
    'rw.attr.showLanguageButtons':
      'Show the read-aloud and microphone buttons (additionally tied to the backend '
      + 'capability)',
    'rw.attr.inlineResultGrouping':
      'false = a flat card grid with paging instead of the result boxes',
    'rw.attr.showCards':
      'auto | always | never — results as tiles with a preview image instead of '
      + 'text links; auto means text links when small, tiles when large',
    'rw.attr.theme':
      'auto | light | dark — auto means the widget sets nothing and inherits the '
      + 'page colour scheme',
    'rw.attr.language':
      'de | en; empty = the page decides (nearest [lang], else the browser, else '
      + 'German). The switch inside the widget beats this attribute',
    'rw.attr.interceptEduSharingLinks':
      'true: link clicks fire linkClicked instead of navigating',
    'rw.attr.emitGuideSuggestion': 'true: guide hits as boerdi:guide-suggestion',
    'rw.attr.emitRoutingDebug':
      'true: routing telemetry per bot turn as boerdi:routing-debug',
    'rw.attr.ticket':
      'edu-sharing ticket of the host page (the "repository embeds the chat" '
      + 'mode): read once, removed from the DOM right away and exchanged at the '
      + 'MCP server for an access block — the person signed in on the page is '
      + 'then signed in inside the chat as well',

    'rw.eventsTitle': 'Events',
    'rw.col.event': 'Event',
    'rw.col.when': 'When',
    'rw.col.payload': 'Payload',
    'rw.when.pageAction': 'always active (window event only)',
    'rw.when.queryMeta': 'always active',
    'rw.when.guideSuggestion': 'emit-guide-suggestion="true"',
    'rw.when.routingDebug': 'emit-routing-debug="true"',
    'rw.when.agentResult': 'result-schema set + engine="agent"',

    'rw.outputs':
      'Angular outputs for embedding programmatically: `{outputs}`. `linkClicked` '
      + 'only fires with `intercept-edu-sharing-links="true"`. The full payload '
      + 'schema is in `docs/05-widget-javascript-api.md`.',
  },
};
