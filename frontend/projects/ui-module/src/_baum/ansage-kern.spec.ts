import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ANSAGE_PAUSE_MS, AnsageKern } from './ansage-kern';
import { BaumAnsage } from './baum-ansage';

/** Paket BU-2 (BU-f): die Regel der Statuszeile ohne Angular — für Komponenten und Custom Elements. */
describe('AnsageKern', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('ein neuer Text steht sofort', () => {
    const gesetzt: string[] = [];
    const kern = new AnsageKern((t) => gesetzt.push(t));
    kern.sagen('Eins');
    kern.sagen('Zwei');
    expect(gesetzt).toEqual(['Eins', 'Zwei']);
    expect(kern.text).toBe('Zwei');
  });

  it('derselbe Text: erst leeren, nach der Pause neu setzen (sonst sagt der Vorleser nichts)', () => {
    const gesetzt: string[] = [];
    const kern = new AnsageKern((t) => gesetzt.push(t));
    kern.sagen('Gleich');
    kern.sagen('Gleich');
    expect(gesetzt).toEqual(['Gleich', '']);
    vi.advanceTimersByTime(ANSAGE_PAUSE_MS);
    expect(gesetzt).toEqual(['Gleich', '', 'Gleich']);
  });

  it('aufraeumen hält eine wartende Ansage an; eine neue Ansage ersetzt sie', () => {
    const gesetzt: string[] = [];
    const kern = new AnsageKern((t) => gesetzt.push(t));
    kern.sagen('A');
    kern.sagen('A');
    kern.sagen('B');
    vi.advanceTimersByTime(ANSAGE_PAUSE_MS);
    expect(gesetzt).toEqual(['A', '', 'B']);
    kern.sagen('B');
    kern.aufraeumen();
    vi.advanceTimersByTime(ANSAGE_PAUSE_MS);
    expect(gesetzt.at(-1)).toBe('');
  });

  it('BaumAnsage (Angular) folgt derselben Regel', () => {
    const ansage = new BaumAnsage();
    ansage.sagen('X');
    ansage.sagen('X');
    expect(ansage.text()).toBe('');
    vi.advanceTimersByTime(ANSAGE_PAUSE_MS);
    expect(ansage.text()).toBe('X');
  });
});
