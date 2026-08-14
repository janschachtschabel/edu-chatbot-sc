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
 *
 * **Seit C1-d5b2 stehen hier nur noch Bezeichner und Struktur.** Attributnamen,
 * Vorgabewerte und Payload-Formen sind Code und bleiben; jede Prosa-Zelle trägt
 * einen Katalog-Schlüssel (`i18n/catalogue/reference-widget.ts`). `fallbackKey`
 * ist optional, weil 20 der 25 Vorgabewerte echte Werte sind und nur fünf das
 * Wort „leer" meinen.
 */

export interface HostAttribute {
  readonly groupKey: string;
  readonly attr: string;
  /** Vorgabewert, wörtlich — oder leer, wenn `fallbackKey` ihn benennt. */
  readonly fallback: string;
  /** Nur wo der Vorgabewert ein WORT ist statt eines Wertes. */
  readonly fallbackKey?: string;
  readonly descKey: string;
}

/**
 * The 25 host attributes of `<boerdi-chat>` (§5.5). ALT's table listed 17 —
 * `inline-result-grouping`, the one 8-7 found dead, was the one it left out.
 * `language` came with C1-c, `embed-mode` with U1, `size` with U2a,
 * `show-cards` with U2b, `theme` with U4a.
 */
export const HOST_ATTRIBUTES: readonly HostAttribute[] = [
  {
    groupKey: 'rw.group.basis', attr: 'api-url', fallback: '—',
    descKey: 'rw.attr.apiUrl',
  },
  {
    groupKey: 'rw.group.basis', attr: 'embed-mode', fallback: 'panel',
    descKey: 'rw.attr.embedMode',
  },
  {
    groupKey: 'rw.group.basis', attr: 'size', fallback: 'small',
    descKey: 'rw.attr.size',
  },
  {
    groupKey: 'rw.group.basis', attr: 'engine', fallback: '',
    fallbackKey: 'rw.default.empty', descKey: 'rw.attr.engine',
  },
  {
    groupKey: 'rw.group.basis', attr: 'result-schema', fallback: '',
    fallbackKey: 'rw.default.empty', descKey: 'rw.attr.resultSchema',
  },
  {
    groupKey: 'rw.group.basis', attr: 'position', fallback: 'bottom-right',
    descKey: 'rw.attr.position',
  },
  {
    groupKey: 'rw.group.basis', attr: 'initial-state', fallback: 'collapsed',
    descKey: 'rw.attr.initialState',
  },
  {
    groupKey: 'rw.group.basis', attr: 'primary-color', fallback: '',
    fallbackKey: 'rw.default.empty', descKey: 'rw.attr.primaryColor',
  },
  {
    groupKey: 'rw.group.basis', attr: 'greeting', fallback: '—',
    descKey: 'rw.attr.greeting',
  },
  {
    groupKey: 'rw.group.session', attr: 'persist-session', fallback: 'true',
    descKey: 'rw.attr.persistSession',
  },
  {
    groupKey: 'rw.group.session', attr: 'session-key', fallback: 'boerdi_session_id',
    descKey: 'rw.attr.sessionKey',
  },
  {
    groupKey: 'rw.group.session', attr: 'session-cookie-domain', fallback: '',
    fallbackKey: 'rw.default.empty', descKey: 'rw.attr.sessionCookieDomain',
  },
  {
    groupKey: 'rw.group.session', attr: 'session-cookie-max-age', fallback: '2592000',
    descKey: 'rw.attr.sessionCookieMaxAge',
  },
  {
    groupKey: 'rw.group.session', attr: 'trusted-domains', fallback: '',
    fallbackKey: 'rw.default.empty', descKey: 'rw.attr.trustedDomains',
  },
  {
    groupKey: 'rw.group.kontext', attr: 'auto-context', fallback: 'true',
    descKey: 'rw.attr.autoContext',
  },
  {
    groupKey: 'rw.group.kontext', attr: 'page-context', fallback: '—',
    descKey: 'rw.attr.pageContext',
  },
  {
    groupKey: 'rw.group.anzeige', attr: 'show-debug-button', fallback: 'true',
    descKey: 'rw.attr.showDebugButton',
  },
  {
    groupKey: 'rw.group.anzeige', attr: 'show-language-buttons', fallback: 'true',
    descKey: 'rw.attr.showLanguageButtons',
  },
  {
    groupKey: 'rw.group.anzeige', attr: 'inline-result-grouping', fallback: 'true',
    descKey: 'rw.attr.inlineResultGrouping',
  },
  {
    groupKey: 'rw.group.anzeige', attr: 'show-cards', fallback: 'auto',
    descKey: 'rw.attr.showCards',
  },
  {
    groupKey: 'rw.group.anzeige', attr: 'theme', fallback: 'auto',
    descKey: 'rw.attr.theme',
  },
  {
    groupKey: 'rw.group.anzeige', attr: 'language', fallback: '',
    fallbackKey: 'rw.default.empty', descKey: 'rw.attr.language',
  },
  {
    groupKey: 'rw.group.integration', attr: 'intercept-edu-sharing-links',
    fallback: 'false', descKey: 'rw.attr.interceptEduSharingLinks',
  },
  {
    groupKey: 'rw.group.integration', attr: 'emit-guide-suggestion', fallback: 'false',
    descKey: 'rw.attr.emitGuideSuggestion',
  },
  {
    groupKey: 'rw.group.integration', attr: 'emit-routing-debug', fallback: 'false',
    descKey: 'rw.attr.emitRoutingDebug',
  },
  {
    groupKey: 'rw.group.integration', attr: 'ticket', fallback: '—',
    descKey: 'rw.attr.ticket',
  },
];

export interface HostEvent {
  readonly name: string;
  readonly whenKey: string;
  readonly payload: string;
}

/**
 * ALT InfoView:770-777 — corrected in one place: it listed `(pageAction)` among
 * the element's Angular outputs, but ALT's own widget only ever declared four
 * (`widget.component.ts:119-146`), the same four NEU has. `page-action` reaches
 * a host page as the window event only.
 *
 * Die Namen tragen seit U5a (2026-08-09) den Präfix `boerdi:`. Solange der ALTE
 * Chatbot parallel läuft, feuert das Widget jedes Ereignis ZUSÄTZLICH unter
 * `badboerdi:…` (`ui/src/host-events/event-names.ts`). Diese Tabelle zeigt
 * bewusst nur den neuen Namen: sie ist der Vertrag, den ein NEUER Einbau
 * umsetzen soll — der alte ist eine Übergangs-Nachsicht, die nach dem Cutover
 * verschwindet und dann als falsche Zeile stehenbliebe.
 */
export const HOST_EVENTS: readonly HostEvent[] = [
  {
    name: 'boerdi:page-action', whenKey: 'rw.when.pageAction',
    payload: '{action, payload} — navigate, show_results',
  },
  {
    name: 'boerdi:query-meta', whenKey: 'rw.when.queryMeta',
    payload: '{queries[]{tool_name, search_term, criteria[], pagination, search_url}}',
  },
  {
    name: 'boerdi:guide-suggestion', whenKey: 'rw.when.guideSuggestion',
    payload: '{url, title, node_id, node_type, query, alternatives[]}',
  },
  {
    name: 'boerdi:routing-debug', whenKey: 'rw.when.routingDebug',
    payload: '{pattern, intent, state, persona, tools_called[], sources[], modifier{}}',
  },
  {
    name: 'boerdi:agent-result', whenKey: 'rw.when.agentResult',
    payload: '{result, stop_reason} — result ist null, wenn der Zug keins ergab',
  },
];

/** The Angular outputs, for hosts that embed the component programmatically. */
export const HOST_OUTPUTS: readonly string[] = [
  'linkClicked', 'guideSuggestion', 'routingDebug', 'queryMeta',
];

/**
 * The embed sample, as a host page would write it.
 *
 * Der Code steht einmal da, die drei Kommentare kommen aus dem Katalog: eine
 * zweite Sprachfassung des Beispiels wäre eine zweite Stelle, an der ein neues
 * Attribut nachgetragen werden müsste — und die eine, die man vergisst.
 */
export const EMBED_SAMPLE = `<script src="/widget/boerdi-widget.js" defer></script>

<!-- {minimal} -->
<boerdi-chat api-url="https://api.example.de"></boerdi-chat>

<!-- {lean} -->
<boerdi-chat
  api-url="https://api.example.de"
  show-debug-button="false">
</boerdi-chat>

<!-- {edu} -->
<boerdi-chat
  api-url="https://api.example.de"
  intercept-edu-sharing-links="true"
  emit-routing-debug="true">
</boerdi-chat>`;
