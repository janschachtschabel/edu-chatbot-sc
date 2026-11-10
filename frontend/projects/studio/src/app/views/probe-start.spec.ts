import { describe, expect, it } from 'vitest';

import { probeHref, startdatenPruefen } from './probe-start';

/** Paket AS-8b (Plan 2026-11-09 §5n, P-9): Startdaten der Probe und der Weg in die Vorschau. */
describe('startdatenPruefen', () => {
  it('leer heißt: ohne Startdaten', () => {
    expect(startdatenPruefen('')).toEqual({ ok: true, json: null });
    expect(startdatenPruefen('   \n')).toEqual({ ok: true, json: null });
  });

  it('ein JSON-Objekt geht kompakt hinaus', () => {
    expect(startdatenPruefen('{ "thema": "Optik",\n "stufe": 7 }'))
      .toEqual({ ok: true, json: '{"thema":"Optik","stufe":7}' });
  });

  it('kein JSON oder kein Objekt ist ein Fehler — mit Grund', () => {
    expect(startdatenPruefen('{kaputt')).toEqual({ ok: false, fehler: 'json' });
    for (const roh of ['[1]', 'null', '"x"', '3']) {
      expect(startdatenPruefen(roh)).toEqual({ ok: false, fehler: 'objekt' });
    }
  });
});

describe('probeHref', () => {
  it('führt relativ in die Vorschau, die Kennung kodiert', () => {
    expect(probeHref('sammlung_pruefen')).toBe('vorschau?ablauf=sammlung_pruefen');
    expect(probeHref('a&b')).toBe('vorschau?ablauf=a%26b');
  });

  it('ohne gültige Kennung kein Weg', () => {
    expect(probeHref('')).toBeNull();
    expect(probeHref(undefined)).toBeNull();
    expect(probeHref(3)).toBeNull();
  });
});

describe('startdatenPruefen — Grenzen wie im Widget (Review AS-8b, Befund 2)', () => {
  it('zu viele Schlüssel oder zu lang: ein eigener Grund statt einer stummen Probe', async () => {
    const { START_JSON_MAX, START_SCHLUESSEL_MAX } = await import('@boerdi/ui');
    const viele = Object.fromEntries(
      Array.from({ length: START_SCHLUESSEL_MAX + 1 }, (_, i) => [`k${i}`, i]));
    expect(startdatenPruefen(JSON.stringify(viele))).toEqual({ ok: false, fehler: 'schluessel' });
    const lang = { text: 'x'.repeat(START_JSON_MAX) };
    expect(startdatenPruefen(JSON.stringify(lang))).toEqual({ ok: false, fehler: 'gross' });
    const genau = Object.fromEntries(
      Array.from({ length: START_SCHLUESSEL_MAX }, (_, i) => [`k${i}`, i]));
    expect(startdatenPruefen(JSON.stringify(genau)).ok).toBe(true);
  });
});
