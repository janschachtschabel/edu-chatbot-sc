import { describe, expect, it } from 'vitest';

import { entryTitle } from './entry-title';
import { nextFreeKey } from './field-ids';
import { rootField } from './schema-to-fields';

/** Ein Eintrag mit allen vier Kandidaten — die Reihenfolge entscheidet. */
const ITEM = rootField({
  type: 'object',
  properties: {
    id: { type: 'string' }, name: { type: 'string' },
    label: { type: 'string' }, title: { type: 'string' }, note: { type: 'string' },
  },
});

describe('entryTitle (ST-3)', () => {
  it('nimmt title vor label vor name vor id', () => {
    expect(entryTitle(ITEM, { id: 'GV-1', label: 'L', title: 'Lehrkraft plant' }, 'x')).toBe(
      'Lehrkraft plant');
    expect(entryTitle(ITEM, { id: 'GV-1', name: 'N', label: 'L' }, 'x')).toBe('L');
    expect(entryTitle(ITEM, { id: 'GV-1', name: 'N' }, 'x')).toBe('N');
    expect(entryTitle(ITEM, { id: 'GV-1' }, 'x')).toBe('GV-1');
  });

  it('überspringt leere Werte', () => {
    expect(entryTitle(ITEM, { title: '  ', id: 'P-LEH' }, 'x')).toBe('P-LEH');
  });

  it('fällt ohne Kandidaten auf den übergebenen Namen zurück', () => {
    expect(entryTitle(ITEM, { note: 'nur eine Notiz' }, 'Eintrag 3')).toBe('Eintrag 3');
    expect(entryTitle(ITEM, 'kein Objekt', 'Eintrag 4')).toBe('Eintrag 4');
  });

  it('nimmt nur Felder, die das Modell kennt', () => {
    // Ein Schlüssel, der zufällig `title` heißt, aber nicht im Schema steht, ist
    // Beifang aus dem Rohtext — kein Titel.
    const ohneTitel = rootField({ type: 'object', properties: { id: { type: 'string' } } });
    expect(entryTitle(ohneTitel, { title: 'Beifang', id: 'I01' }, 'x')).toBe('I01');
  });
});

describe('nextFreeKey mit eigenem Stamm (ST-3, Duplizieren)', () => {
  it('hängt an den Stamm eine Zahl, bis er frei ist', () => {
    expect(nextFreeKey(['a'], 'a_kopie')).toBe('a_kopie');
    expect(nextFreeKey(['a', 'a_kopie'], 'a_kopie')).toBe('a_kopie_2');
  });

  it('bleibt ohne Stamm beim bisherigen neuer_eintrag', () => {
    expect(nextFreeKey(['neuer_eintrag'])).toBe('neuer_eintrag_2');
  });
});
