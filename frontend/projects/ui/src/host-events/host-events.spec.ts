import { describe, expect, it } from 'vitest';

import { WloCard } from '../cards/card-types';
import { DebugInfo } from '../grouping/message-types';
import {
  GuideSuggestionPayload,
  HostEventsContext,
  RoutingDebugPayload,
  maybeDispatchGuideNavigate,
  maybeDispatchGuideSuggestion,
  maybeDispatchRoutingDebug,
} from './host-events';

/**
 * Charakterisierung der Host-Event-Dispatcher — Verbatim-Port aus ALT
 * chat/host-events.ts (dort nur integrativ über chat.component.spec gedeckt).
 * Gepinnt: Navigate-Intent-Regex-Gate + Card-Link/guide_url-Auswahl, das
 * emit-Gate (`_attrIsTrue`) beider passiven Dispatcher, die Doppel-Ausgabe
 * (window-CustomEvent + Output-Kanal) und das Payload-Mapping aus DebugInfo.
 */
function card(fields: Partial<WloCard> & { link?: string; guide_url?: string }): WloCard {
  return fields as unknown as WloCard;
}

function makeCtx(over: { emitGuideSuggestion?: boolean | string; emitRoutingDebug?: boolean | string } = {}): {
  ctx: HostEventsContext;
  pageActions: Array<{ action: string; payload: any }>;
  suggestionOut: GuideSuggestionPayload[];
  routingOut: RoutingDebugPayload[];
} {
  const pageActions: Array<{ action: string; payload: any }> = [];
  const suggestionOut: GuideSuggestionPayload[] = [];
  const routingOut: RoutingDebugPayload[] = [];
  const ctx: HostEventsContext = {
    emitGuideSuggestion: () => over.emitGuideSuggestion ?? false,
    emitRoutingDebug: () => over.emitRoutingDebug ?? false,
    dispatchPageAction: (pa) => pageActions.push(pa),
    emitGuideSuggestionOutput: (p) => suggestionOut.push(p),
    emitRoutingDebugOutput: (p) => routingOut.push(p),
  };
  return { ctx, pageActions, suggestionOut, routingOut };
}

/** Sammelt window-CustomEvents des Namens während `fn` (mit Cleanup). */
function captureWindowEvent(name: string, fn: () => void): CustomEvent[] {
  const events: CustomEvent[] = [];
  const handler = (e: Event) => events.push(e as CustomEvent);
  window.addEventListener(name, handler);
  try {
    fn();
  } finally {
    window.removeEventListener(name, handler);
  }
  return events;
}

describe('maybeDispatchGuideNavigate', () => {
  it('Navigations-Wunsch + Card mit link → navigate-page_action', () => {
    const { ctx, pageActions } = makeCtx();
    maybeDispatchGuideNavigate('Bring mich hin', [card({ title: 'Mathe', link: 'https://x/mathe' })], ctx);
    expect(pageActions).toEqual([{ action: 'navigate', payload: { url: 'https://x/mathe', label: 'Mathe' } }]);
  });

  it('kein Navigations-Wunsch → kein dispatch', () => {
    const { ctx, pageActions } = makeCtx();
    maybeDispatchGuideNavigate('Zeig mir Mathe-Material', [card({ title: 'Mathe', link: 'https://x/mathe' })], ctx);
    expect(pageActions).toEqual([]);
  });

  it('Navigations-Wunsch aber keine Card mit link/guide_url → kein dispatch', () => {
    const { ctx, pageActions } = makeCtx();
    maybeDispatchGuideNavigate('Bring mich hin', [card({ title: 'Ohne Link' })], ctx);
    expect(pageActions).toEqual([]);
  });

  it('guide_url als Fallback für link', () => {
    const { ctx, pageActions } = makeCtx();
    maybeDispatchGuideNavigate('Lotse mich', [card({ title: 'G', guide_url: 'https://g' })], ctx);
    expect(pageActions[0].payload.url).toBe('https://g');
  });

  it('leere Cards → kein dispatch', () => {
    const { ctx, pageActions } = makeCtx();
    maybeDispatchGuideNavigate('Bring mich hin', [], ctx);
    expect(pageActions).toEqual([]);
  });
});

describe('maybeDispatchGuideSuggestion', () => {
  it('Gate aus (Default) → kein window-Event, kein Output', () => {
    const { ctx, suggestionOut } = makeCtx({ emitGuideSuggestion: false });
    const events = captureWindowEvent('badboerdi:guide-suggestion', () =>
      maybeDispatchGuideSuggestion('Frage', [card({ title: 'T', link: 'https://a' })], ctx),
    );
    expect(events.length).toBe(0);
    expect(suggestionOut.length).toBe(0);
  });

  it('Gate an + eligible Cards → window-Event + Output mit Top-1 + alternatives', () => {
    const { ctx, suggestionOut } = makeCtx({ emitGuideSuggestion: true });
    const cards = [
      card({ title: 'Top', node_id: 'n1', node_type: 'content', link: 'https://a' }),
      card({ title: 'Alt', node_id: 'n2', node_type: 'collection', link: 'https://b' }),
    ];
    const events = captureWindowEvent('badboerdi:guide-suggestion', () =>
      maybeDispatchGuideSuggestion('Frage', cards, ctx),
    );
    expect(events.length).toBe(1);
    const detail = events[0].detail as GuideSuggestionPayload;
    expect(detail.url).toBe('https://a');
    expect(detail.title).toBe('Top');
    expect(detail.query).toBe('Frage');
    expect(detail.alternatives).toEqual([{ url: 'https://b', title: 'Alt', node_id: 'n2', node_type: 'collection' }]);
    expect(suggestionOut.length).toBe(1);
    expect(suggestionOut[0].url).toBe('https://a');
  });

  it('Gate an aber keine eligible Card → nichts', () => {
    const { ctx, suggestionOut } = makeCtx({ emitGuideSuggestion: true });
    const events = captureWindowEvent('badboerdi:guide-suggestion', () =>
      maybeDispatchGuideSuggestion('Frage', [card({ title: 'Ohne Link' })], ctx),
    );
    expect(events.length).toBe(0);
    expect(suggestionOut.length).toBe(0);
  });
});

describe('maybeDispatchRoutingDebug', () => {
  it('Gate aus → nichts', () => {
    const { ctx, routingOut } = makeCtx({ emitRoutingDebug: false });
    const events = captureWindowEvent('badboerdi:routing-debug', () =>
      maybeDispatchRoutingDebug('Frage', { pattern: 'P' } as unknown as DebugInfo, ctx),
    );
    expect(events.length).toBe(0);
    expect(routingOut.length).toBe(0);
  });

  it('Gate an + debug → window-Event + Output mit gemapptem Payload', () => {
    const { ctx, routingOut } = makeCtx({ emitRoutingDebug: true });
    const debug = {
      pattern: 'PAT-07', intent: 'INT-03', state: 'state-5', persona: 'P-LK',
      tools_called: ['search_wlo_content'], signals: ['neugierig'],
      phase3_modulations: {
        tone: 'freundlich', length: 'kurz', formality: 'du', card_text_mode: 'kompakt',
        rag_areas: ['mathe'], sources: ['mcp'], _tone_modifier_override: true,
      },
    } as unknown as DebugInfo;
    const events = captureWindowEvent('badboerdi:routing-debug', () =>
      maybeDispatchRoutingDebug('Frage', debug, ctx),
    );
    expect(events.length).toBe(1);
    const d = events[0].detail as RoutingDebugPayload;
    expect(d.message).toBe('Frage');
    expect(d.pattern).toBe('PAT-07');
    expect(d.tools_called).toEqual(['search_wlo_content']);
    expect(d.rag_areas).toEqual(['mathe']);
    expect(d.sources).toEqual(['mcp']);
    expect(d.modifier).toEqual({ tone: 'freundlich', length: 'kurz', formality: 'du', card_text_mode: 'kompakt', override: true });
    expect(d.signals).toEqual(['neugierig']);
    expect(routingOut.length).toBe(1);
  });

  it('debug null → nichts', () => {
    const { ctx, routingOut } = makeCtx({ emitRoutingDebug: true });
    const events = captureWindowEvent('badboerdi:routing-debug', () =>
      maybeDispatchRoutingDebug('Frage', null, ctx),
    );
    expect(events.length).toBe(0);
    expect(routingOut.length).toBe(0);
  });
});
