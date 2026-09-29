// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { newProbeSession } from './chat-probe-api.service';

describe('newProbeSession (ST-8e)', () => {
  it('heißt studio-<uuid>, damit die Herkunft sie nicht als echtes Gespräch zählt', () => {
    expect(newProbeSession()).toMatch(/^studio-[0-9a-f-]{36}$/);
    expect(newProbeSession()).not.toBe(newProbeSession());
  });

  // `randomUUID` gibt es nur in sicheren Kontexten (https, localhost) — ein
  // Studio über http ohne localhost soll den Probelauf trotzdem öffnen können.
  // Derselbe Rückfall wie im Widget (`ui/src/session/session-id.ts`).
  it('fällt ohne randomUUID auf getRandomValues zurück', () => {
    const original = Object.getOwnPropertyDescriptor(crypto, 'randomUUID');
    Object.defineProperty(crypto, 'randomUUID', { value: undefined, configurable: true });
    try {
      expect(newProbeSession()).toMatch(/^studio-[0-9a-f]{32}$/);
    } finally {
      if (original) Object.defineProperty(crypto, 'randomUUID', original);
      else delete (crypto as { randomUUID?: unknown }).randomUUID;
    }
  });
});
