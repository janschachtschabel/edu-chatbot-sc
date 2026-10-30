import { describe, expect, it } from 'vitest';

import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
import { createTranslator } from '../i18n/dictionary';
import { drosselHinweis, httpFehler } from './http-fehler';

// Paket 18F (3.5): ein nicht-ok-Abruf als Fehler mit Status und Wartezeit — für Verlauf, Strom
// und POST eine Stelle; ein 429 wird im Widget zum eigenen Satz, mit Wartezeit, wenn sie kommt.
function antwort(status: number, retryAfter?: string): Response {
  return {
    ok: false, status,
    headers: { get: (k: string) => (k === 'Retry-After' ? retryAfter ?? null : null) },
  } as unknown as Response;
}

describe('httpFehler', () => {
  it('trägt Status und Wartezeit aus Retry-After', () => {
    const e = httpFehler(antwort(429, '30'), 'Chat error');
    expect(e.status).toBe(429);
    expect(e.retryAfterMs).toBe(30_000);
    expect(e.message).toBe('Chat error: 429');
  });

  it('ohne Kopf keine Wartezeit; 0 heißt sofort, nicht fehlt', () => {
    expect(httpFehler(antwort(429), 'x').retryAfterMs).toBeUndefined();
    expect(httpFehler(antwort(429, '  '), 'x').retryAfterMs).toBeUndefined();
    expect(httpFehler(antwort(429, '0'), 'x').retryAfterMs).toBe(0);
  });

  it('ein Datum oder Unfug zählt nicht als Wartezeit', () => {
    expect(httpFehler(antwort(429, 'Wed, 21 Oct 2026 07:28:00 GMT'), 'x').retryAfterMs)
      .toBeUndefined();
    expect(httpFehler(antwort(429, '-5'), 'x').retryAfterMs).toBeUndefined();
  });
});

describe('drosselHinweis', () => {
  const de = createTranslator(DE, DE);
  const en = createTranslator(EN, DE);

  it('429 mit Wartezeit → der Satz mit Sekunden (aufgerundet)', () => {
    const e = { status: 429, retryAfterMs: 1_500 };
    expect(drosselHinweis(de, e)).toBe(de('error.rateLimitedWait', { sekunden: 2 }));
    expect(drosselHinweis(de, e)).toContain('2');
  });

  it('429 ohne Wartezeit (oder 0) → der Satz ohne Zahl', () => {
    expect(drosselHinweis(de, { status: 429 })).toBe(DE['error.rateLimited']);
    expect(drosselHinweis(de, { status: 429, retryAfterMs: 0 })).toBe(DE['error.rateLimited']);
  });

  it('englisch', () => {
    expect(drosselHinweis(en, { status: 429 })).toBe(EN['error.rateLimited']);
  });

  it('kein 429 → null (der Aufrufer zeigt seinen eigenen Fehler)', () => {
    expect(drosselHinweis(de, { status: 500 })).toBeNull();
    expect(drosselHinweis(de, new Error('offline'))).toBeNull();
    expect(drosselHinweis(de, null)).toBeNull();
  });
});
