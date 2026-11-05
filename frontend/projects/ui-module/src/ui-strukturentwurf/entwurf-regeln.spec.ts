import { describe, expect, it } from 'vitest';

import {
  type Ablehnung, anzahl, ausruecken, einruecken, finde, hinzufuegen, type EntwurfKnoten, HOECHSTE_TIEFE, loeschen,
  neueKennung, setzeFelder, verschieben,
} from './entwurf-regeln';

/**
 * Paket U2-e (Plan 2026-11-04, T-11): die Bearbeitungsregeln des Strukturentwurfs ohne Angular —
 * unveränderliche Bäume, jede Regel gibt den neuen Baum oder einen Grund zurück, warum nicht.
 */
const BAUM: readonly EntwurfKnoten[] = [
  { id: 'a', titel: 'A', kinder: [{ id: 'a1', titel: 'A1' }, { id: 'a2', titel: 'A2' }] },
  { id: 'b', titel: 'B' },
  { id: 'c', titel: 'C', kinder: [{ id: 'c1', titel: 'C1', kinder: [{ id: 'c11', titel: 'C11' }] }] },
];

const titel = (b: readonly EntwurfKnoten[]): string =>
  b.map((k) => (k.kinder?.length ? `${k.titel}(${titel(k.kinder)})` : k.titel)).join(' ');

function ok<T>(r: T): Exclude<T, Ablehnung> {
  if (r && typeof r === 'object' && 'grund' in r) throw new Error(`abgelehnt: ${(r as Ablehnung).grund}`);
  return r as Exclude<T, Ablehnung>;
}

describe('entwurf-regeln', () => {
  it('findet einen Knoten samt Ebene und Eltern', () => {
    expect(finde(BAUM, 'c11')).toMatchObject({ ebene: 3, eltern: 'c1', index: 0 });
    expect(finde(BAUM, 'x')).toBeNull();
    expect(anzahl(BAUM)).toBe(7);
  });

  it('ändert Felder unveränderlich', () => {
    const neu = ok(setzeFelder(BAUM, 'a1', { titel: 'Neu', keywords: ['x'] }));
    expect(finde(neu, 'a1')?.knoten).toMatchObject({ titel: 'Neu', keywords: ['x'] });
    expect(finde(BAUM, 'a1')?.knoten.titel).toBe('A1');
    expect(neu[1]).toBe(BAUM[1]);                      // unberührte Zweige bleiben dieselben
  });

  it('fügt einen Unterpunkt und einen Punkt danach ein', () => {
    const kind = ok(hinzufuegen(BAUM, 'b', 'kind', { id: 'n1', titel: 'N' }));
    expect(titel(kind.baum)).toBe('A(A1 A2) B(N) C(C1(C11))');
    const danach = ok(hinzufuegen(BAUM, 'a1', 'danach', { id: 'n2', titel: 'N' }));
    expect(titel(danach.baum)).toBe('A(A1 N A2) B C(C1(C11))');
    const oben = ok(hinzufuegen([], null, 'danach', { id: 'n3', titel: 'N' }));
    expect(titel(oben.baum)).toBe('N');
  });

  it('ein Unterpunkt unter Ebene 4 wird abgelehnt', () => {
    const tief = ok(hinzufuegen(BAUM, 'c11', 'kind', { id: 'd', titel: 'D' })).baum;
    expect(finde(tief, 'd')?.ebene).toBe(HOECHSTE_TIEFE);
    expect(hinzufuegen(tief, 'd', 'kind', { id: 'e', titel: 'E' })).toEqual({ grund: 'tiefe' });
  });

  it('löscht samt Unterpunkten und nennt, wohin der Fokus geht', () => {
    const r = ok(loeschen(BAUM, 'a'));
    expect(titel(r.baum)).toBe('B C(C1(C11))');
    expect(r.fokus).toBe('b');
    expect(ok(loeschen(BAUM, 'a2')).fokus).toBe('a1');           // letztes Geschwister → davor
    expect(ok(loeschen(BAUM, 'c11')).fokus).toBe('c1');           // einziges Kind → Eltern
    expect(ok(loeschen([{ id: 'x', titel: 'X' }], 'x')).fokus).toBeNull();
  });

  it('verschiebt innerhalb der Geschwister', () => {
    expect(titel(ok(verschieben(BAUM, 'b', -1)))).toBe('B A(A1 A2) C(C1(C11))');
    expect(titel(ok(verschieben(BAUM, 'a1', 1)))).toBe('A(A2 A1) B C(C1(C11))');
    expect(verschieben(BAUM, 'a', -1)).toEqual({ grund: 'oben' });
    expect(verschieben(BAUM, 'c', 1)).toEqual({ grund: 'unten' });
  });

  it('rückt ein (letztes Kind des Punkts davor) und aus (Geschwister nach dem Eltern)', () => {
    expect(titel(ok(einruecken(BAUM, 'b')))).toBe('A(A1 A2 B) C(C1(C11))');
    expect(einruecken(BAUM, 'a')).toEqual({ grund: 'erster' });
    expect(titel(ok(ausruecken(BAUM, 'a1')))).toBe('A(A2) A1 B C(C1(C11))');
    expect(ausruecken(BAUM, 'b')).toEqual({ grund: 'oberste' });
  });

  it('Einrücken hält die Tiefe ein — der ganze Zweig zählt', () => {
    // C hat zwei Ebenen darunter; unter B eingerückt kommen C1 und C11 auf Ebene 3 und 4: erlaubt.
    const r = ok(einruecken(BAUM, 'c'));
    expect(finde(r, 'c11')?.ebene).toBe(4);
    // Ein Zweig mit vier Ebenen unter einen Punkt eingerückt hätte eine fünfte.
    const vier: EntwurfKnoten[] = [{ id: 'x', titel: 'X' }, {
      id: 'y', titel: 'Y', kinder: [{ id: 'y1', titel: 'Y1', kinder: [{ id: 'y2', titel: 'Y2', kinder: [{ id: 'y3', titel: 'Y3' }] }] }],
    }];
    expect(einruecken(vier, 'y')).toEqual({ grund: 'tiefe' });
  });

  it('höchstens 15 Unterpunkte und 250 Punkte', () => {
    const voll: EntwurfKnoten[] = [{ id: 'v', titel: 'V', kinder: Array.from({ length: 15 }, (_, i) => ({ id: `v${i}`, titel: 'K' })) }];
    expect(hinzufuegen(voll, 'v', 'kind', { id: 'z', titel: 'Z' })).toEqual({ grund: 'kinder' });
    expect(hinzufuegen(voll, 'v3', 'danach', { id: 'z', titel: 'Z' })).toEqual({ grund: 'kinder' });
    const viele: EntwurfKnoten[] = Array.from({ length: 25 }, (_, i) => ({
      id: `o${i}`, titel: 'O', kinder: Array.from({ length: 9 }, (_, j) => ({ id: `o${i}-${j}`, titel: 'K' })),
    }));
    expect(anzahl(viele)).toBe(250);
    expect(hinzufuegen(viele, 'o0-1', 'danach', { id: 'z', titel: 'Z' })).toEqual({ grund: 'gesamt' });
  });

  it('neue Kennungen sind eindeutig und passen zur Form', () => {
    const eins = neueKennung(BAUM);
    expect(eins).toMatch(/^[A-Za-z0-9_-]{1,40}$/);
    const mit = ok(hinzufuegen(BAUM, 'b', 'kind', { id: eins, titel: 'N' })).baum;
    expect(neueKennung(mit)).not.toBe(eins);
  });
});
