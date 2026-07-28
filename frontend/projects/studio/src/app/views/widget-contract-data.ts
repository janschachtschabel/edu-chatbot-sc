/**
 * The public contract of `<boerdi-chat>` as the studio documents it (9-5f / A5).
 *
 * Split out of `reference-data.ts` because it changes for a different reason: the
 * widget's host API, not the prompt architecture. The source of truth is
 * `WidgetComponent`'s inputs in `projects/widget/src/app/widget/widget.component.ts`,
 * and a test over there pins the attribute set and names this file when it
 * breaks — a documented attribute that never reaches its consumer is a bug this
 * project has already shipped twice (`data-position` in 8-5,
 * `inline-result-grouping` in 8-7).
 */

export interface HostAttribute {
  readonly group: string;
  readonly attr: string;
  readonly fallback: string;
  readonly desc: string;
}

/**
 * The 18 host attributes of `<boerdi-chat>` (§5.5). ALT's table listed 17 —
 * `inline-result-grouping`, the one 8-7 found dead, was the one it left out.
 */
export const HOST_ATTRIBUTES: readonly HostAttribute[] = [
  { group: 'Basis', attr: 'api-url', fallback: '—', desc: 'Backend-Basis-URL (Pflicht)' },
  {
    group: 'Basis', attr: 'position', fallback: 'bottom-right',
    desc: 'bottom-right | bottom-left | top-right | top-left',
  },
  {
    group: 'Basis', attr: 'initial-state', fallback: 'collapsed',
    desc: 'collapsed | expanded',
  },
  {
    group: 'Basis', attr: 'primary-color', fallback: 'leer',
    desc: 'Akzentfarbe; leer lässt den CSS-Default #1c4587 greifen',
  },
  { group: 'Basis', attr: 'greeting', fallback: '—', desc: 'Eigene Begrüßungsnachricht' },
  {
    group: 'Session', attr: 'persist-session', fallback: 'true',
    desc: 'Session in localStorage bzw. Cookie halten',
  },
  {
    group: 'Session', attr: 'session-key', fallback: 'boerdi_session_id',
    desc: 'localStorage-Schlüssel',
  },
  {
    group: 'Session', attr: 'session-cookie-domain', fallback: 'leer',
    desc: 'Gesetzt: Session im Cookie statt localStorage (Cross-Subdomain)',
  },
  {
    group: 'Session', attr: 'session-cookie-max-age', fallback: '2592000',
    desc: 'Cookie-Lebensdauer in Sekunden (30 Tage)',
  },
  {
    group: 'Session', attr: 'trusted-domains', fallback: 'leer',
    desc: 'Komma-Liste der Hosts, die die Session-ID per ?bsid= erhalten dürfen; '
      + 'ergänzt die Backend-Liste, kürzt sie nicht',
  },
  {
    group: 'Kontext', attr: 'auto-context', fallback: 'true',
    desc: 'Seitenkontext automatisch erfassen',
  },
  {
    group: 'Kontext', attr: 'page-context', fallback: '—',
    desc: 'JSON-Objekt mit zusätzlichem Kontext',
  },
  {
    group: 'Anzeige', attr: 'show-debug-button', fallback: 'true',
    desc: 'Debug-Umschalter in der Kopfzeile zeigen',
  },
  {
    group: 'Anzeige', attr: 'show-language-buttons', fallback: 'true',
    desc: 'Vorlese- und Mikrofon-Knopf zeigen (zusätzlich an die Backend-Capability gekoppelt)',
  },
  {
    group: 'Anzeige', attr: 'inline-result-grouping', fallback: 'true',
    desc: 'false = flaches Karten-Grid mit Seitenblättern statt der Ergebnis-Boxen',
  },
  {
    group: 'Integration', attr: 'intercept-edu-sharing-links', fallback: 'false',
    desc: 'true: Link-Klicks feuern linkClicked statt zu navigieren',
  },
  {
    group: 'Integration', attr: 'emit-guide-suggestion', fallback: 'false',
    desc: 'true: Lotsen-Treffer als badboerdi:guide-suggestion',
  },
  {
    group: 'Integration', attr: 'emit-routing-debug', fallback: 'false',
    desc: 'true: Routing-Telemetrie je Bot-Turn als badboerdi:routing-debug',
  },
];

export interface HostEvent {
  readonly name: string;
  readonly when: string;
  readonly payload: string;
}

/**
 * ALT InfoView:770-777 — corrected in one place: it listed `(pageAction)` among
 * the element's Angular outputs, but ALT's own widget only ever declared four
 * (`widget.component.ts:119-146`), the same four NEU has. `page-action` reaches
 * a host page as the window event only.
 */
export const HOST_EVENTS: readonly HostEvent[] = [
  {
    name: 'badboerdi:page-action', when: 'immer aktiv (nur als window-Event)',
    payload: '{action, payload} — navigate, show_results',
  },
  {
    name: 'badboerdi:query-meta', when: 'immer aktiv',
    payload: '{queries[]{tool_name, search_term, criteria[], pagination, search_url}}',
  },
  {
    name: 'badboerdi:guide-suggestion', when: 'emit-guide-suggestion="true"',
    payload: '{url, title, node_id, node_type, query, alternatives[]}',
  },
  {
    name: 'badboerdi:routing-debug', when: 'emit-routing-debug="true"',
    payload: '{pattern, intent, state, persona, tools_called[], sources[], modifier{}}',
  },
];

/** The Angular outputs, for hosts that embed the component programmatically. */
export const HOST_OUTPUTS: readonly string[] = [
  'linkClicked', 'guideSuggestion', 'routingDebug', 'queryMeta',
];

/** The embed sample, as a host page would write it. */
export const EMBED_SAMPLE = `<script src="/widget/boerdi-widget.js" defer></script>

<!-- Minimal: alle Defaults -->
<boerdi-chat api-url="https://api.example.de"></boerdi-chat>

<!-- Schlank: ohne Debug-Knopf -->
<boerdi-chat
  api-url="https://api.example.de"
  show-debug-button="false">
</boerdi-chat>

<!-- edu-sharing-Embed: eigenes Link-Routing, Routing-Telemetrie an -->
<boerdi-chat
  api-url="https://api.example.de"
  intercept-edu-sharing-links="true"
  emit-routing-debug="true">
</boerdi-chat>`;
