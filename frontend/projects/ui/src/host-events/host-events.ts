/**
 * Host-Event-Dispatcher (Lotsen-Navigate / Guide-Suggestion / Routing-Debug)
 * — extrahiert aus ``chat.component.ts`` (Frontend-Split, 2026-07-09).
 *
 * Die drei Dispatcher informieren die Host-Seite über Bot-Turn-Ergebnisse:
 *   - ``maybeDispatchGuideNavigate``  → ``navigate``-page_action (Widget-Banner)
 *   - ``maybeDispatchGuideSuggestion`` → ``badboerdi:guide-suggestion``-CustomEvent
 *   - ``maybeDispatchRoutingDebug``    → ``badboerdi:routing-debug``-CustomEvent
 *
 * Plain functions statt Klasse — die Dispatcher halten keinen eigenen State.
 * Live-Zustand der ChatComponent kommt als :class:`HostEventsContext` mit
 * deferred Arrows herein (Muster ``TourContext``): die Gates
 * ``emitGuideSuggestion``/``emitRoutingDebug`` werden pro Aufruf frisch
 * gelesen (die Bestands-Spec setzt die Inputs NACH Konstruktion), und die
 * Ausgabe läuft über die Komponenten-Pfade (``dispatchPageAction`` liest
 * ``onPageAction`` live; die Angular-Outputs emitten in der Komponente).
 * Bodies verbatim übernommen — KEINE Logik-Änderung.
 *
 * NEU (boerdi-chat, Shell-Prereq 8-4S-0a): Imports umgehängt — `WloCard` →
 * `../cards/card-types`, `DebugInfo` → `../grouping/message-types` (beide schon
 * portiert), `_attrIsTrue` → `../element/attr` (mit host-events aus 8-5
 * vorgezogen). Gleiche Semantik.
 */
import { WloCard } from '../cards/card-types';
import { DebugInfo } from '../grouping/message-types';
import { _attrIsTrue } from '../element/attr';

/** Payload shape for the ``badboerdi:guide-suggestion`` CustomEvent and the
 *  ``(guideSuggestion)`` Output. Emitted at most once per bot-turn, when the
 *  host page has ``emit-guide-suggestion="true"`` and the response contains
 *  at least one Lotsen-eligible target (``card.link`` or ``card.guide_url``).
 *
 *  Hosts can listen via:
 *
 *  ```js
 *  window.addEventListener('badboerdi:guide-suggestion', (e) => {
 *    const s = e.detail; // GuideSuggestionPayload
 *    // show banner / switch iframe / etc.
 *  });
 *  ```
 *
 *  Or via Angular ``(guideSuggestion)`` Output when not consuming as Custom
 *  Element. Same payload either way.
 */
export interface GuideSuggestionPayload {
  /** Repo-aware target URL — for collections ``…/components/collections?id=…``,
   *  for content ``…/components/render/<uuid>``, for topic-pages the curated
   *  external page URL. Identical to ``card.link``. */
  url: string;
  /** Card title (display label). */
  title: string;
  /** edu-sharing node-ID (UUID). Empty when the card has no node_id. */
  node_id: string;
  /** Three-way classification: ``'topic_page'`` | ``'collection'`` | ``'content'``. */
  node_type: string;
  /** User query that produced this result — useful for context-aware host
   *  reactions (e.g. logging, analytics, pre-filling adjacent UIs). */
  query: string;
  /** All Lotsen-eligible cards from this turn, in display order. Lets hosts
   *  build their own ranked UI instead of being limited to the top-1. Max
   *  length equals the number of cards in the response. */
  alternatives: Array<Pick<GuideSuggestionPayload, 'url' | 'title' | 'node_id' | 'node_type'>>;
}

/** Welle C.4 (2026-05): Payload für ``badboerdi:routing-debug``.
 *  Auf ``window`` gefeuert nach jedem Bot-Turn, wenn der Host
 *  ``emit-routing-debug="true"`` gesetzt hat. Quellen-Daten kommen aus
 *  dem ``DebugInfo``-Block der ChatResponse — keine zusätzlichen
 *  Backend-Calls nötig.
 *
 *  Hosts können das Routing live beobachten und z.B. ein Routing-Panel
 *  oder A/B-Logging implementieren:
 *
 *  ```js
 *  window.addEventListener('badboerdi:routing-debug', (e) => {
 *    const d = e.detail; // RoutingDebugPayload
 *    console.log(d.pattern, d.intent, d.state, d.tools);
 *  });
 *  ```
 */
export interface RoutingDebugPayload {
  /** User-Nachricht, die den Turn ausgelöst hat. */
  message: string;
  /** Gewählter Pattern-ID (z.B. ``PAT-07``). */
  pattern: string;
  /** Classifier-Intent (z.B. ``INT-W-03``). */
  intent: string;
  /** Conversation-State (z.B. ``state-5``). */
  state: string;
  /** Persona-ID (z.B. ``P-W-LK``). */
  persona: string;
  /** Tatsächlich aufgerufene MCP-Tools für diesen Turn. */
  tools_called: string[];
  /** RAG-Areas, die in den Kontext geflossen sind (Pattern-gesteuert ab Welle B.4). */
  rag_areas: string[];
  /** Pattern.sources (``mcp``, ``rag``, ``web``). */
  sources: string[];
  /** Modulator-Ergebnis: tone/length/formality/card_text_mode aus tone-modifiers.yaml. */
  modifier: {
    tone: string;
    length: string;
    formality: string;
    card_text_mode: string;
    /** True wenn der Modifier den Pattern-Default überschrieben hat. */
    override: boolean;
  };
  /** Classifier-Signale (z.B. ``["orientierungssuchend", "neugierig"]``). */
  signals: string[];
}

/** Live-Zustand/Seiteneffekte der ChatComponent, die die Dispatcher
 *  brauchen — als deferred Arrows (Muster: ``TourContext``). */
export interface HostEventsContext {
  /** ``@Input() emitGuideSuggestion`` — LIVE gelesen (Web-Component-
   *  Attribute coercen zu String; Bool-Koersion via ``_attrIsTrue``). */
  emitGuideSuggestion: () => boolean | string;
  /** ``@Input() emitRoutingDebug`` — LIVE gelesen, wie oben. */
  emitRoutingDebug: () => boolean | string;
  /** Komponenten-``dispatchPageAction`` (host callback + Output + window-Event). */
  dispatchPageAction: (pa: { action: string; payload: any }) => void;
  /** ``guideSuggestion.emit`` der Komponente (Angular-Output-Kanal). */
  emitGuideSuggestionOutput: (payload: GuideSuggestionPayload) => void;
  /** ``routingDebug.emit`` der Komponente (Angular-Output-Kanal). */
  emitRoutingDebugOutput: (payload: RoutingDebugPayload) => void;
}

/** Phrases that turn a normal chat message into a "lotse mich"-request.
 *  Trigger only when the wording is unambiguous — bot-initiated
 *  navigation should not surprise the user. */
const GUIDE_NAV_INTENT_RE =
  /\b(bring(?:\s+du)?\s+mich\s+(?:da)?hin|navigiere\s+(?:mich\s+)?(?:zu|zur|zum)|lotse\s+mich|öffne\s+(?:die|das|den)?\s*(?:themenseite|sammlung|seite)|geh(?:e)?\s+zur|f(?:üh|ueh)re\s+mich|hin\s+zur|bring\s+mich\s+(?:zu|zur|zum))\b/i;

/** Inspect the just-sent user message; if it expresses a navigation
 *  wish AND the response has at least one card with a usable link,
 *  dispatch a ``navigate`` page-action so the widget banner appears.
 *  Picks the first card with a link (top result by relevance).
 *
 *  Card-Pipeline v2: bevorzugt ``link`` (vom build_card_link gesetzt);
 *  Fallback auf ``guide_url`` für Bestands-Backends.
 */
export function maybeDispatchGuideNavigate(
  userMessage: string,
  cards: WloCard[] | undefined,
  ctx: HostEventsContext,
): void {
  if (!userMessage || !cards || cards.length === 0) return;
  if (!GUIDE_NAV_INTENT_RE.test(userMessage)) return;
  const target = cards.find(c => !!((c as WloCard & { link?: string }).link
                                     || (c as WloCard & { guide_url?: string }).guide_url));
  if (!target) return;
  const url = (target as WloCard & { link?: string }).link
              || (target as WloCard & { guide_url?: string }).guide_url
              || '';
  if (!url) return;
  ctx.dispatchPageAction({
    action: 'navigate',
    payload: { url, label: target.title || url },
  });
}

/** Passive Top-1-Anzeige für Host-Integration.
 *
 *  Im Gegensatz zu :func:`maybeDispatchGuideNavigate` (die NUR bei
 *  expliziter Navigations-Anfrage feuert) wird hier bei JEDEM Bot-Turn
 *  ein ``badboerdi:guide-suggestion``-Event ausgelöst, sobald die
 *  Antwort mindestens eine Lotsen-eligible Card enthält. So kann z.B.
 *  eine Edu-Sharing-Sidebar einen "Bot empfiehlt"-Pin setzen oder ein
 *  WP-Theme einen Banner zeigen, ohne dass der User aktiv navigieren
 *  möchte.
 *
 *  Gated durch ``[emitGuideSuggestion]``. Bei ``false`` (Default) — kein
 *  Event, kein Effekt. Bei ``true`` — Event + Output bei jedem
 *  qualifizierten Turn.
 *
 *  Payload-Aufbau siehe :class:`GuideSuggestionPayload`. ``alternatives``
 *  enthält alle weiteren Lotsen-eligible Cards in Display-Reihenfolge,
 *  damit Hosts auch eine Top-N-UI bauen können.
 */
export function maybeDispatchGuideSuggestion(
  userMessage: string,
  cards: WloCard[] | undefined,
  ctx: HostEventsContext,
): void {
  if (!_attrIsTrue(ctx.emitGuideSuggestion())) return;
  if (!cards || cards.length === 0) return;

  // Eligible = hat einen ``link`` (Card-Pipeline v2) ODER ``guide_url``
  // (Backward-Compat) — beides sind allow-listed Lotsen-Targets.
  const eligible: Array<{ card: WloCard; url: string }> = [];
  for (const c of cards) {
    const link = (c as WloCard & { link?: string }).link
               || (c as WloCard & { guide_url?: string }).guide_url
               || '';
    if (link) eligible.push({ card: c, url: link });
  }
  if (eligible.length === 0) return;

  const top = eligible[0];
  const alternatives = eligible.slice(1).map(e => ({
    url: e.url,
    title: e.card.title || e.url,
    node_id: e.card.node_id || '',
    node_type: e.card.node_type || '',
  }));

  const payload: GuideSuggestionPayload = {
    url: top.url,
    title: top.card.title || top.url,
    node_id: top.card.node_id || '',
    node_type: top.card.node_type || '',
    query: userMessage || '',
    alternatives,
  };

  // Beide Kanäle: globales CustomEvent (Web-Component-Embed-Friendly) +
  // Angular-Output (für direkten Angular-Consumer). Hosts wählen den
  // Kanal, der zu ihrer Integration passt — die Daten sind identisch.
  window.dispatchEvent(new CustomEvent('badboerdi:guide-suggestion', {
    detail: payload,
    bubbles: true,
    composed: true,
  }));
  ctx.emitGuideSuggestionOutput(payload);
}

/** Welle C.4 (2026-05): Dispatch a ``badboerdi:routing-debug`` Custom-
 *  Event with the routing telemetry from the current turn. Gated by
 *  ``emitRoutingDebug`` — hosts opt in explicitly. Data is read from
 *  the existing ``DebugInfo`` block in the response — no additional
 *  backend round-trip.
 *
 *  Use cases:
 *    - Studio-Live-Debug-Panel (welches Pattern wurde aktiv?)
 *    - Embed-Hosts mit Routing-Awareness (z.B. "diese Antwort war
 *      Lotsen-getrieben, nicht Material-Suche")
 *    - A/B-Test-Logging beim Embedder
 */
export function maybeDispatchRoutingDebug(
  userMessage: string,
  debug: DebugInfo | null | undefined,
  ctx: HostEventsContext,
): void {
  if (!_attrIsTrue(ctx.emitRoutingDebug())) return;
  if (!debug) return;

  const mods = debug.phase3_modulations || {};
  const payload: RoutingDebugPayload = {
    message: userMessage || '',
    pattern: debug.pattern || '',
    intent: debug.intent || '',
    state: debug.state || '',
    persona: debug.persona || '',
    tools_called: Array.isArray(debug.tools_called) ? debug.tools_called : [],
    // rag_areas + sources kommen aus phase3_modulations (Pattern-Engine-Output)
    rag_areas: Array.isArray(mods['rag_areas']) ? mods['rag_areas'] : [],
    sources: Array.isArray(mods['sources']) ? mods['sources'] : [],
    modifier: {
      tone: String(mods['tone'] || ''),
      length: String(mods['length'] || ''),
      formality: String(mods['formality'] || ''),
      card_text_mode: String(mods['card_text_mode'] || ''),
      override: Boolean(mods['_tone_modifier_override']),
    },
    signals: Array.isArray(debug.signals) ? debug.signals : [],
  };

  window.dispatchEvent(new CustomEvent('badboerdi:routing-debug', {
    detail: payload,
    bubbles: true,
    composed: true,
  }));
  ctx.emitRoutingDebugOutput(payload);
}
