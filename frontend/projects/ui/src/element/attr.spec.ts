import { describe, expect, it } from 'vitest';

import { _attrIsTrue } from './attr';

/**
 * Charakterisierung der Attribut-Bool-Koerzierung — Verbatim-Port aus ALT
 * chat-text-utils.ts (dort kein Standalone-Spec). Gepinnt: `true`/`'true'`/
 * `'1'`/`'yes'` sowie der leere String (bloßes Attribut-Vorhandensein) →
 * true; alles andere (inkl. undefined/`'false'`/`'0'`/`'no'`) → false.
 */
describe('_attrIsTrue', () => {
  it('true-Fälle: boolean true, "true", "1", "yes", "" (Attribut vorhanden)', () => {
    expect(_attrIsTrue(true)).toBe(true);
    expect(_attrIsTrue('true')).toBe(true);
    expect(_attrIsTrue('TRUE')).toBe(true);
    expect(_attrIsTrue('1')).toBe(true);
    expect(_attrIsTrue('yes')).toBe(true);
    expect(_attrIsTrue('')).toBe(true);
    expect(_attrIsTrue('  true  ')).toBe(true);
  });

  it('false-Fälle: false, undefined, "false", "0", "no", sonstige', () => {
    expect(_attrIsTrue(false)).toBe(false);
    expect(_attrIsTrue(undefined)).toBe(false);
    expect(_attrIsTrue('false')).toBe(false);
    expect(_attrIsTrue('0')).toBe(false);
    expect(_attrIsTrue('no')).toBe(false);
    expect(_attrIsTrue('irgendwas')).toBe(false);
  });
});
