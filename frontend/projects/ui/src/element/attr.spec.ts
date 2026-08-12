import { describe, expect, it } from 'vitest';

import { _attrEnum, _attrIsTrue, resolveTheme } from './attr';

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

/**
 * Aufzählungs-Attribute (U1/U2/U4: `embed-mode`, `size`, `show-cards`, `theme`).
 * Der Wert kommt von einer FREMDEN Seite — ein Tippfehler darf das Widget nicht
 * in einen undefinierten Zustand bringen, sondern muss auf die Vorgabe fallen.
 */
describe('_attrEnum', () => {
  const MODES = ['panel', 'frameless'] as const;

  it('gibt den erlaubten Wert zurück, unabhängig von Schreibweise und Rand-Leerzeichen', () => {
    expect(_attrEnum('frameless', MODES, 'panel')).toBe('frameless');
    expect(_attrEnum('FRAMELESS', MODES, 'panel')).toBe('frameless');
    expect(_attrEnum('  frameless  ', MODES, 'panel')).toBe('frameless');
  });

  it('fällt auf die Vorgabe: unbekannt, leer, fehlend', () => {
    expect(_attrEnum('vollbild', MODES, 'panel')).toBe('panel');
    expect(_attrEnum('', MODES, 'panel')).toBe('panel');
    expect(_attrEnum(undefined, MODES, 'panel')).toBe('panel');
  });

  it('leerer String ist NICHT „vorhanden = erster Wert" wie bei _attrIsTrue', () => {
    // `<boerdi-chat embed-mode>` ohne Wert sagt nicht, WELCHER Modus gemeint
    // ist — die Vorgabe ist die einzige ehrliche Antwort.
    expect(_attrEnum('', MODES, 'panel')).not.toBe('frameless');
  });
});

/**
 * U4a — `theme`. Die Ableitung hat genau eine Entscheidung zu treffen, und die
 * ist der Grund, warum sie einen Namen bekommt: `auto` ist NICHT „hell". `auto`
 * heißt, dass das Widget nichts setzt und `color-scheme` von der Gastseite erbt
 * — genau das Verhalten, das der Dunkelmodus des Widgets heute schon hat und
 * das ein Vorgabewert `'light'` still abgeschaltet hätte.
 */
describe('resolveTheme', () => {
  it('light und dark werden zum gleichnamigen color-scheme', () => {
    expect(resolveTheme('light')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
    expect(resolveTheme('  DARK ')).toBe('dark');
  });

  it('auto, leer, fehlend und Unfug ergeben null — das Widget setzt nichts', () => {
    expect(resolveTheme('auto')).toBeNull();
    expect(resolveTheme('')).toBeNull();
    expect(resolveTheme(undefined)).toBeNull();
    expect(resolveTheme('nachtmodus')).toBeNull();
  });
});
