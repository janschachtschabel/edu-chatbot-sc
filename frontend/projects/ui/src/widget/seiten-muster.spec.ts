import { describe, expect, it } from 'vitest';

import { normalisierterPfad, seitePasst } from './seiten-muster';

/**
 * AS-7b (Plan 2026-11-09 §5m, F-3/F-7): dieselben Pfadmuster wie im Backend
 * (`domain/seiten_muster.py`) — `*` als einziger Platzhalter, linear, auf dem normalisierten Pfad.
 * Die Fälle spiegeln `tests/test_ablauf_seite.py`, damit Widget und Backend gleich entscheiden.
 */
describe('seiten-muster (AS-7b)', () => {
  it.each([
    ['/mitmachen/', ['/mitmachen*'], true],
    ['https://wirlernenonline.de/mitmachen/?x=1#a', ['/mitmachen*'], true],
    ['/MITMACHEN', ['/mitmachen'], true],
    ['/home/', ['/mitmachen*'], false],
    ['/fach/physik/optik/', ['/fach/*/optik'], true],
    ['/', ['/'], true],
    ['', ['/'], true],
    ['/a/b/c', ['/*/b/*'], true],
    ['/a/b/c', ['/*/c/*'], false],
    ['/a', ['/a*a'], false],
    ['/aa', ['/a*a'], true],
    ['/x', ['*'], false],
    ['/mitmachen/', ['/mitmachen/*'], true],
    ['/mitmachen-xyz', ['/mitmachen/*'], false],
    ['/', ['/*'], true],
  ] as const)('%s gegen %j → %s', (seite, muster, passt) => {
    expect(seitePasst(seite, muster)).toBe(passt);
  });

  it('ist linear — eine lange, fast passende Seite braucht keine Zeit', () => {
    const beginn = performance.now();
    expect(seitePasst(`/${'a'.repeat(50_000)}`, ['/*a*a*a*b'])).toBe(false);
    expect(performance.now() - beginn).toBeLessThan(200);
  });

  it('normalisiert wie das Backend und kappt lange Pfade', () => {
    expect(normalisierterPfad('https://host/A/B/?q#f')).toBe('/a/b');
    expect(normalisierterPfad(`/${'x'.repeat(5000)}`).length).toBeLessThanOrEqual(1000);
  });
});

describe('seiten-muster — wie das Backend (Review AS-7b, Befund 5)', () => {
  it('Muster mit Leerraum am Rand gelten, fremde Zeichen nicht', () => {
    expect(seitePasst('/a', [' /a '])).toBe(true);
    expect(seitePasst('/a?b', ['/a?b'])).toBe(false);
    expect(seitePasst('/a', ['/a[b]'])).toBe(false);
  });

  it('„//“ wird wie im Backend zum leeren Pfad', () => {
    expect(normalisierterPfad('//')).toBe('');
  });
});

describe('seiten-muster — Komma (Querschnitts-Review AS-7, Befund 9)', () => {
  it('ein Muster mit Komma gilt nicht — wie im Backend', () => {
    expect(seitePasst('/a,b', ['/a,b'])).toBe(false);
  });
});
