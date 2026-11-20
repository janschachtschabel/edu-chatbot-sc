import { describe, expect, it } from 'vitest';

import { modulAmPfad, parameterAus } from './modul-parameter';

/** Plan 2026-11-20, P6: welche Parameter ein Modul-Schritt nennen darf — aus dem Manifest. */
describe('modul-parameter (P6)', () => {
  const dok = { schritte: [
    { id: 'laden', typ: 'modul', modul: 'ui_upload', daten: {} },
    { id: 'lesen', typ: 'werkzeug', werkzeug: 'metadaten_lesen', argumente: {} },
    { id: 'ohne', typ: 'modul', daten: {} },
  ] };

  it('nur die Daten eines Modul-Schritts nennen ein Modul', () => {
    expect(modulAmPfad(dok, ['schritte', 0, 'daten'])).toBe('ui_upload');
    expect(modulAmPfad(dok, ['schritte', 1, 'argumente'])).toBeNull();
    expect(modulAmPfad(dok, ['schritte', 0, 'argumente'])).toBeNull();
    expect(modulAmPfad(dok, ['schritte', 2, 'daten'])).toBeNull();
    expect(modulAmPfad(dok, ['schritte', 9, 'daten'])).toBeNull();
    expect(modulAmPfad(undefined, ['schritte', 0, 'daten'])).toBeNull();
    expect(modulAmPfad({ ablaeufe: [dok] }, ['ablaeufe', 0, 'schritte', 0, 'daten'])).toBe('ui_upload');
  });

  it('liest Name, Beschreibung, erlaubte Werte, Vorgabe und Pflicht aus dienst.parameter', () => {
    const manifest = { dienst: { name: 'upload_angebot', parameter: {
      type: 'object', required: ['zweck'],
      properties: {
        zweck: { enum: ['bereitstellen', 'sammlungsstruktur'], description: 'Wofür.' },
        orte: { type: 'array', items: { enum: ['chat', 'wlo', 'namen'] }, description: 'Orte.' },
        erschliessen: { type: 'boolean', description: 'Häkchen.', default: true },
        hinweis: { type: 'string', maxLength: 300 },
      } } } };
    expect(parameterAus(manifest)).toEqual([
      { name: 'zweck', beschreibung: 'Wofür.', werte: ['bereitstellen', 'sammlungsstruktur'], liste: false, typ: null, vorgabe: null, pflicht: true },
      { name: 'orte', beschreibung: 'Orte.', werte: ['chat', 'wlo', 'namen'], liste: true, typ: 'array', vorgabe: null, pflicht: false },
      { name: 'erschliessen', beschreibung: 'Häkchen.', werte: [], liste: false, typ: 'boolean', vorgabe: 'true', pflicht: false },
      { name: 'hinweis', beschreibung: '', werte: [], liste: false, typ: 'string', vorgabe: null, pflicht: false },
    ]);
  });

  it('ohne Dienst (oder ohne Manifest) keine Parameter', () => {
    expect(parameterAus({ dienst: null })).toEqual([]);
    expect(parameterAus(undefined)).toEqual([]);
    expect(parameterAus({ dienst: { parameter: { properties: 'kaputt' } } })).toEqual([]);
  });
});
