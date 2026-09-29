import { describe, expect, it } from 'vitest';

import { describeProblem, parseProblems, pathKey } from './field-problems';

/** Übersetzer-Attrappe: gibt Schlüssel und Parameter lesbar zurück. */
const t = (key: string, params?: Record<string, string | number>): string =>
  params ? `${key}${JSON.stringify(params)}` : key;
const zahl = (wert: number): string => `#${wert}`;

describe('parseProblems (ST-2e)', () => {
  it('liest Pfad, Art, Meldung und Grenzen je Eintrag', () => {
    const [p] = parseProblems([
      {
        loc: ['display_rules', 'inline_documents', 'font_size_percent'],
        msg: 'Input should be greater than or equal to 70',
        type: 'greater_than_equal',
        ctx: { ge: 70 },
      },
    ]);
    expect(p).toEqual({
      path: ['display_rules', 'inline_documents', 'font_size_percent'],
      type: 'greater_than_equal',
      msg: 'Input should be greater than or equal to 70',
      ctx: { ge: 70 },
    });
  });

  it('zieht die Hülle `body.data` einer Anfrageprüfung ab — ein echtes `body` bleibt', () => {
    const [huelle, echt] = parseProblems([
      { loc: ['body', 'data', 'welcome'], msg: 'x', type: 'dict_type' },
      { loc: ['body'], msg: 'y', type: 'string_type' },
    ]);
    expect(huelle.path).toEqual(['welcome']);
    expect(echt.path).toEqual(['body']);
  });

  it('übergeht, was keine Prüfmeldung ist', () => {
    expect(parseProblems('nur ein Satz')).toEqual([]);
    expect(parseProblems([null, 'x', { msg: 'ohne Pfad' }])).toEqual([]);
  });

  it('bildet aus dem Pfad einen Schlüssel, wie ihn das Formular vergleicht', () => {
    expect(pathKey(['a', 0, 'b'])).toBe('a.0.b');
  });
});

describe('describeProblem (ST-2e)', () => {
  it('erklärt eine Grenze mit ihrem Wert, lokal formatiert', () => {
    const text = describeProblem(
      { path: ['x'], type: 'greater_than_equal', msg: 'm', ctx: { ge: 70 } }, t, zahl,
    );
    expect(text).toBe('validation.greater_than_equal{"ge":"#70"}');
  });

  it('nennt bei einer geschlossenen Auswahl die erwarteten Werte', () => {
    const text = describeProblem(
      { path: ['x'], type: 'literal_error', msg: 'm', ctx: { expected: "'a' or 'b'" } }, t, zahl,
    );
    expect(text).toBe('validation.literal_error{"expected":"\'a\' or \'b\'"}');
  });

  it('fällt ohne die Grenze auf die Meldung des Servers zurück — nie „Mindestens {ge}"', () => {
    // Im Browser gefunden: ein Backend ohne `ctx` (vor ST-2e) ließ den
    // Platzhalter roh stehen.
    const text = describeProblem(
      { path: ['x'], type: 'greater_than_equal', msg: 'Input should be >= 70', ctx: {} }, t, zahl,
    );
    expect(text).toBe('validation.other{"msg":"Input should be >= 70"}');
  });

  it('fällt bei einer unbekannten Art auf die Meldung des Servers zurück', () => {
    const text = describeProblem({ path: ['x'], type: 'neu_erfunden', msg: 'Server sagt', ctx: {} }, t, zahl);
    expect(text).toBe('validation.other{"msg":"Server sagt"}');
  });
});
