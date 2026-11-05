import { describe, expect, it } from 'vitest';

import { tastenAktion } from '../_baum/baum-tasten';
import { ebenen, type Eintrag, flach } from './themenbaum-zweige';

/**
 * Tastatur des Themenbaums als reine Regel (Review U1 gesamt, Befund 8 — aus der Komponente
 * gezogen, Verhalten unverändert; die Komponenten-Spec prüft dieselben Tasten im DOM). Seit U2
 * liegt die Regel im gemeinsamen Baum-Kern (`_baum/baum-tasten.ts`); diese Spec prüft sie weiter
 * mit den Einträgen des Bestands.
 */
const KNOTEN = [
  { id: 'a', titel: 'Algebra', kinder: [{ id: 'a1', titel: 'Gleichungen' }, { id: 'a2', titel: 'Terme' }] },
  { id: 'g', titel: 'Geometrie' },
];

function liste(offen: string[] = []): Eintrag[] {
  return flach(ebenen(KNOTEN, new Set(offen), new Map()));
}

const istOffenIn = (offen: string[]) => (e: Eintrag) => offen.includes(e.knoten.id);

describe('tastenAktion', () => {
  it('↑ ↓ Pos1 Ende wechseln den Fokus; am Rand bleibt die Taste verbraucht', () => {
    const l = liste();
    const zu = istOffenIn([]);
    expect(tastenAktion('ArrowDown', l, '0', zu)).toEqual({ art: 'fokus', pfad: '1' });
    expect(tastenAktion('ArrowDown', l, '1', zu)).toEqual({ art: 'nichts' });
    expect(tastenAktion('ArrowUp', l, '1', zu)).toEqual({ art: 'fokus', pfad: '0' });
    expect(tastenAktion('ArrowUp', l, '0', zu)).toEqual({ art: 'nichts' });
    expect(tastenAktion('Home', l, '1', zu)).toEqual({ art: 'fokus', pfad: '0' });
    expect(tastenAktion('End', l, '0', zu)).toEqual({ art: 'fokus', pfad: '1' });
  });

  it('→ öffnet, auf einem offenen Eintrag geht es ins erste Kind; auf einem Blatt nichts', () => {
    expect(tastenAktion('ArrowRight', liste(), '0', istOffenIn([]))).toMatchObject({ art: 'aufklappen', eintrag: { pfad: '0' } });
    expect(tastenAktion('ArrowRight', liste(['a']), '0', istOffenIn(['a']))).toEqual({ art: 'fokus', pfad: '0-0' });
    expect(tastenAktion('ArrowRight', liste(), '1', istOffenIn([]))).toEqual({ art: 'nichts' });
  });

  it('← schließt einen offenen Eintrag, sonst zum Elternknoten', () => {
    expect(tastenAktion('ArrowLeft', liste(['a']), '0', istOffenIn(['a']))).toMatchObject({ art: 'zuklappen', eintrag: { pfad: '0' } });
    expect(tastenAktion('ArrowLeft', liste(['a']), '0-1', istOffenIn(['a']))).toEqual({ art: 'fokus', pfad: '0' });
    expect(tastenAktion('ArrowLeft', liste(), '0', istOffenIn([]))).toEqual({ art: 'nichts' });
  });

  it('Enter klappt einen aufklappbaren Eintrag, auf einem Blatt zeigt es die Inhalte; Leertaste nur klappen', () => {
    expect(tastenAktion('Enter', liste(), '0', istOffenIn([]))).toMatchObject({ art: 'umschalten', eintrag: { pfad: '0' } });
    expect(tastenAktion('Enter', liste(), '1', istOffenIn([]))).toEqual({ art: 'inhalte' });
    expect(tastenAktion(' ', liste(), '0', istOffenIn([]))).toMatchObject({ art: 'umschalten', eintrag: { pfad: '0' } });
    expect(tastenAktion(' ', liste(), '1', istOffenIn([]))).toEqual({ art: 'nichts' });
  });

  it('Tab und andere Tasten bleiben dem Browser; ohne Einträge nichts', () => {
    expect(tastenAktion('Tab', liste(), '0', istOffenIn([]))).toBeNull();
    expect(tastenAktion('a', liste(), '0', istOffenIn([]))).toBeNull();
    expect(tastenAktion('ArrowDown', [], '0', istOffenIn([]))).toBeNull();
  });

  it('ein unbekannter aktiver Pfad zählt als erster Eintrag', () => {
    expect(tastenAktion('ArrowDown', liste(), '9', istOffenIn([]))).toEqual({ art: 'fokus', pfad: '1' });
  });
});
