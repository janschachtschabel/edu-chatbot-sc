import { describe, expect, it, vi } from 'vitest';

import {
  _attrEnum, _attrIsTrue, _attrJsonObject, _attrJsonStringArray, resolveTheme,
} from './attr';

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

/**
 * `_attrJsonObject` (2026-08-14, erster Konsument `result-schema`). Der Wert ist
 * ungeprüfte Eingabe einer FREMDEN Seite — gepinnt ist deshalb vor allem, was
 * bei Unsinn passiert: `null` statt Wurf, plus eine Zeile in der Konsole, weil
 * ein kaputtes Attribut von außen sonst genauso aussieht wie ein fehlendes.
 */
describe('_attrJsonObject', () => {
  it('liest ein JSON-Objekt', () => {
    expect(_attrJsonObject('{"type":"object","required":["a"]}'))
      .toEqual({ type: 'object', required: ['a'] });
  });

  it('leer / undefined → null, und zwar STILL (kein Fehler der Gastseite)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(_attrJsonObject('')).toBeNull();
    expect(_attrJsonObject('   ')).toBeNull();
    expect(_attrJsonObject(undefined)).toBeNull();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it('kaputtes JSON → null MIT Meldung', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(_attrJsonObject('{type: object,,}')).toBeNull();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('Array, Skalar und null sind keine Objekte → null MIT Meldung', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(_attrJsonObject('[1,2,3]')).toBeNull();
    expect(_attrJsonObject('"text"')).toBeNull();
    expect(_attrJsonObject('42')).toBeNull();
    expect(_attrJsonObject('null')).toBeNull();
    expect(warn).toHaveBeenCalledTimes(4);
    warn.mockRestore();
  });
});

/**
 * `_attrJsonStringArray` (2026-08-14, erster Konsument `start-replies`).
 *
 * Der eine Fall, der die Form bestimmt: das LEERE Array. `[]` heißt „diese
 * Einbettung will KEINE Chips" und muss sich deshalb von „Attribut nicht
 * gesetzt" unterscheiden lassen — sonst führe der Weg zurück in die
 * Studio-Vorgabe, und das Abschalten wäre unmöglich. Darum `string[] | null`
 * und nicht `string[]`.
 */
describe('_attrJsonStringArray', () => {
  it('liest ein JSON-Array von Zeichenketten', () => {
    expect(_attrJsonStringArray('["Was kannst du?","Suche starten"]'))
      .toEqual(['Was kannst du?', 'Suche starten']);
  });

  it('[] ist eine AUSSAGE (keine Chips) und kommt als leeres Array zurück', () => {
    expect(_attrJsonStringArray('[]')).toEqual([]);
    expect(_attrJsonStringArray('  [ ]  ')).toEqual([]);
  });

  it('leer / undefined → null („nicht gesetzt"), und zwar still', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(_attrJsonStringArray('')).toBeNull();
    expect(_attrJsonStringArray('   ')).toBeNull();
    expect(_attrJsonStringArray(undefined)).toBeNull();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it('kaputtes JSON und Nicht-Arrays → null MIT Meldung', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(_attrJsonStringArray('["A",')).toBeNull();
    expect(_attrJsonStringArray('{"a":1}')).toBeNull();
    expect(_attrJsonStringArray('"A"')).toBeNull();
    expect(warn).toHaveBeenCalledTimes(3);
    warn.mockRestore();
  });

  it('trimmt und wirft Leeres raus — dieselbe Regel wie bei der Studio-Config', () => {
    // C13 (Audit 2026-07-09): ungetrimmte Einträge ließen den Tour-Chip-
    // String-Match in der Shell fehlschlagen. Der Host-Weg darf sich hier
    // nicht anders verhalten als der Config-Weg, sonst hinge es am Zufall,
    // über welchen der beiden ein Chip hereinkam.
    expect(_attrJsonStringArray('["  Tour  ","", "   "]')).toEqual(['Tour']);
  });

  it('Zahlen und Objekte im Array werden verworfen, nicht stringifiziert', () => {
    // `String({})` ergäbe „[object Object]" als Chip-Beschriftung — ein
    // sichtbarer Unfall statt eines stillen Weglassens.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(_attrJsonStringArray('["A",42,{"b":1},null,"B"]')).toEqual(['A', 'B']);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
