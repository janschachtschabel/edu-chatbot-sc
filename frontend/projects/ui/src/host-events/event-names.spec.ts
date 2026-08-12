import { describe, expect, it } from 'vitest';

import { dispatchHostEvent, HOST_EVENTS, legacyName } from './event-names';

/**
 * U5a: Die Ereignisse heißen `boerdi:…`. Während P11 der ALTE Chatbot noch
 * parallel läuft, feuert jedes Ereignis ZUSÄTZLICH unter seinem alten Namen
 * `badboerdi:…` — ein Embedder, der noch auf den alten Namen hört, merkt vom
 * Umzug nichts. Gepinnt wird beides: die neuen Namen und die Doppelung.
 */
function capture(names: string[], run: () => void): Array<{ name: string; detail: unknown }> {
  const seen: Array<{ name: string; detail: unknown }> = [];
  const handlers = names.map((n) => {
    const h = (e: Event) => seen.push({ name: n, detail: (e as CustomEvent).detail });
    window.addEventListener(n, h);
    return { n, h };
  });
  try {
    run();
  } finally {
    handlers.forEach(({ n, h }) => window.removeEventListener(n, h));
  }
  return seen;
}

describe('HOST_EVENTS — die Namen selbst', () => {
  it('alle vier tragen den neuen Präfix', () => {
    const namen = Object.values(HOST_EVENTS);
    expect(namen).toEqual([
      'boerdi:guide-suggestion',
      'boerdi:routing-debug',
      'boerdi:query-meta',
      'boerdi:page-action',
    ]);
    expect(namen.every((n) => n.startsWith('boerdi:'))).toBe(true);
  });

  it('legacyName setzt genau den alten Präfix davor', () => {
    expect(legacyName(HOST_EVENTS.pageAction)).toBe('badboerdi:page-action');
  });
});

describe('dispatchHostEvent — Doppelversand während P11', () => {
  it('feuert neu UND alt, mit identischer Nutzlast', () => {
    const detail = { action: 'navigate', payload: { url: 'https://x.test' } };
    const seen = capture(
      [HOST_EVENTS.pageAction, legacyName(HOST_EVENTS.pageAction)],
      () => dispatchHostEvent(HOST_EVENTS.pageAction, detail),
    );

    expect(seen.map((s) => s.name)).toEqual([
      'boerdi:page-action',
      'badboerdi:page-action',
    ]);
    // Dieselbe Referenz, nicht nur derselbe Inhalt: ein Empfänger, der die
    // Nutzlast weiterreicht, bekommt in beiden Kanälen dasselbe Objekt.
    expect(seen[0].detail).toBe(detail);
    expect(seen[1].detail).toBe(detail);
  });

  it('der neue Name kommt ZUERST — er ist der Vertrag, der alte die Nachsicht', () => {
    const seen = capture(
      [HOST_EVENTS.queryMeta, legacyName(HOST_EVENTS.queryMeta)],
      () => dispatchHostEvent(HOST_EVENTS.queryMeta, { queries: [] }),
    );
    expect(seen[0].name).toBe('boerdi:query-meta');
  });

  it('beide Kanäle verlassen den Shadow-Root (bubbles + composed)', () => {
    const gesehen: CustomEvent[] = [];
    const h = (e: Event) => gesehen.push(e as CustomEvent);
    window.addEventListener(HOST_EVENTS.routingDebug, h);
    window.addEventListener(legacyName(HOST_EVENTS.routingDebug), h);
    dispatchHostEvent(HOST_EVENTS.routingDebug, { pattern: 'M06' });
    window.removeEventListener(HOST_EVENTS.routingDebug, h);
    window.removeEventListener(legacyName(HOST_EVENTS.routingDebug), h);

    expect(gesehen).toHaveLength(2);
    expect(gesehen.every((e) => e.bubbles && e.composed)).toBe(true);
  });
});
