import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ABSTAENDE_MS, AUTOMATISCH_MS, FortschrittAblauf } from './fortschritt-ablauf';

/**
 * Paket K1b: das Nachfragen von `ui_fortschritt`. Erst nach 5 s, dann in wachsenden Abständen bis
 * 60 s, nicht während die Seite verborgen ist, nach 30 Minuten nur noch per Knopf. `fertig` oder
 * `fehler` → einmal abholen (nicht während eines Zugs). 409 → abgeschlossen, 401/403 → Halt,
 * alles andere → weiter versuchen.
 */
const DATEN = { ablauf: 'lesen', kuerzel: '0123456789ab', text: 'Ich lasse das Dokument lesen.' };

function lage(antworten: Array<Record<string, unknown> | Error> = []) {
  const zustand = { sichtbar: true, beschaeftigt: false };
  const auftrag = vi.fn(async (schritt: { schritt: string }) => {
    if (schritt.schritt === 'abholen') return { gesendet: true };
    const a = antworten.shift() ?? { stand: 'laeuft' };
    if (a instanceof Error) throw a;
    return a;
  });
  const zeichne = vi.fn();
  const ablauf = new FortschrittAblauf({
    host: () => ({ auftrag }) as never, daten: () => DATEN, beschaeftigt: () => zustand.beschaeftigt,
    sichtbar: () => zustand.sichtbar, zeichne,
  });
  return { ablauf, auftrag, zustand, zeichne };
}

const fehler = (status: number) => Object.assign(new Error(`x ${status}`), { status });
const staende = (auftrag: ReturnType<typeof lage>['auftrag']) =>
  auftrag.mock.calls.map(([s]) => (s as { schritt: string }).schritt);

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('FortschrittAblauf', () => {
  it('fragt erst nach 5 s, dann nach 10, 20, 30, 60 und weiter alle 60 s', async () => {
    const { ablauf, auftrag } = lage();
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[0] - 1);
    expect(auftrag).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(auftrag).toHaveBeenCalledTimes(1);
    for (const [i, ms] of [...ABSTAENDE_MS.slice(1), 60_000, 60_000].entries()) {
      await vi.advanceTimersByTimeAsync(ms - 1);
      expect(auftrag).toHaveBeenCalledTimes(i + 1);
      await vi.advanceTimersByTimeAsync(1);
      expect(auftrag).toHaveBeenCalledTimes(i + 2);
    }
    expect(auftrag).toHaveBeenLastCalledWith({ schritt: 'stand', ablauf: 'lesen', kuerzel: '0123456789ab' });
    expect(ablauf.phase).toBe('wartet');
  });

  it('fertig → einmal abholen, danach Ruhe', async () => {
    const { ablauf, auftrag } = lage([{ stand: 'fertig' }]);
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(staende(auftrag)).toEqual(['stand', 'abholen']);
    expect(auftrag).toHaveBeenLastCalledWith({ schritt: 'abholen', ablauf: 'lesen' });
    expect(ablauf.phase).toBe('abgeholt');
    expect(ablauf.ergebnis).toBe('fertig');
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(auftrag).toHaveBeenCalledTimes(2);
  });

  it('ein gescheiterter Auftrag wird ebenso abgeholt (der Ablauf sagt, wie es weitergeht)', async () => {
    const { ablauf, auftrag } = lage([{ stand: 'fehler' }]);
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(staende(auftrag)).toEqual(['stand', 'abholen']);
    expect(ablauf.ergebnis).toBe('fehler');
  });

  it('während eines Zugs wird nicht abgeholt — erst, wenn die Shell frei ist (nach erneuter Frage)', async () => {
    const { ablauf, auftrag, zustand } = lage([{ stand: 'fertig' }, { stand: 'fertig' }]);
    zustand.beschaeftigt = true;
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(staende(auftrag)).toEqual(['stand']);
    expect(ablauf.phase).toBe('fertig');
    zustand.beschaeftigt = false;
    ablauf.frei();
    await vi.advanceTimersByTimeAsync(0);
    expect(staende(auftrag)).toEqual(['stand', 'stand', 'abholen']);
  });

  it('nicht gesendet (Fehlerblase) → „Ergebnis abholen“ wird angeboten', async () => {
    const { ablauf, auftrag } = lage([{ stand: 'fertig' }]);
    auftrag.mockImplementation(async (s: { schritt: string }) =>
      s.schritt === 'abholen' ? { gesendet: false } : { stand: 'fertig' });
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ablauf.phase).toBe('fertig');
    expect(ablauf.abholenAngeboten()).toBe(true);
  });

  it('409 (kein wartender Auftrag, alter Block im Verlauf) → abgeschlossen, keine weitere Frage', async () => {
    const { ablauf, auftrag } = lage([fehler(409)]);
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ablauf.phase).toBe('abgeschlossen');
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(auftrag).toHaveBeenCalledTimes(1);
  });

  it('401/403 → Halt (nur angemeldet)', async () => {
    const { ablauf, auftrag } = lage([fehler(403)]);
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ablauf.phase).toBe('halt');
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(auftrag).toHaveBeenCalledTimes(1);
  });

  it('503 oder Netz → Störung, weiter mit dem nächsten Abstand', async () => {
    const { ablauf, auftrag } = lage([fehler(503), new Error('netz')]);
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ablauf.phase).toBe('wartet');
    expect(ablauf.stoerung).toBe(true);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(auftrag).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(auftrag).toHaveBeenCalledTimes(3);
    expect(ablauf.stoerung).toBe(false);
  });

  it('verborgen: keine Frage — sobald sichtbar, sofort', async () => {
    const { ablauf, auftrag, zustand } = lage();
    zustand.sichtbar = false;
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(auftrag).not.toHaveBeenCalled();
    zustand.sichtbar = true;
    ablauf.sichtbarGeworden();
    await vi.advanceTimersByTimeAsync(0);
    expect(auftrag).toHaveBeenCalledTimes(1);
  });

  it('nach 30 Minuten nur noch per Knopf', async () => {
    const { ablauf, auftrag } = lage();
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(AUTOMATISCH_MS + 60_000);
    const bis = auftrag.mock.calls.length;
    expect(ablauf.phase).toBe('manuell');
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(auftrag).toHaveBeenCalledTimes(bis);
    await ablauf.pruefen();
    expect(auftrag).toHaveBeenCalledTimes(bis + 1);
    expect(ablauf.phase).toBe('manuell');
  });

  it('„Jetzt prüfen“ fragt sofort und setzt den Abstand fort', async () => {
    const { ablauf, auftrag } = lage();
    ablauf.verbinden();
    await ablauf.pruefen();
    expect(auftrag).toHaveBeenCalledTimes(1);
    expect(ablauf.zuletzt).not.toBeNull();
    await vi.advanceTimersByTimeAsync(9_999);
    expect(auftrag).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(auftrag).toHaveBeenCalledTimes(2);
  });

  it('während einer Frage geht keine zweite hin', async () => {
    const { ablauf, auftrag } = lage();
    let loesen: (v: unknown) => void = () => undefined;
    auftrag.mockImplementationOnce(() => new Promise((r) => { loesen = r as (v: unknown) => void; }));
    ablauf.verbinden();
    const erste = ablauf.pruefen();
    void ablauf.pruefen();
    expect(auftrag).toHaveBeenCalledTimes(1);
    loesen({ stand: 'laeuft' });
    await erste;
  });

  it('getrennt (Widget geschlossen): keine Frage mehr, eine späte Antwort ändert nichts', async () => {
    const { ablauf, auftrag } = lage();
    let loesen: (v: unknown) => void = () => undefined;
    auftrag.mockImplementationOnce(() => new Promise((r) => { loesen = r as (v: unknown) => void; }));
    ablauf.verbinden();
    const frage = ablauf.pruefen();
    ablauf.trennen();
    loesen({ stand: 'fertig' });
    await frage;
    expect(staende(auftrag)).toEqual(['stand']);
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(auftrag).toHaveBeenCalledTimes(1);
  });

  it('ein AbortError (Widget entfernt) beendet still', async () => {
    const { ablauf } = lage([new DOMException('weg', 'AbortError') as unknown as Error]);
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ablauf.stoerung).toBe(false);
  });

  // ── Review K1b ───────────────────────────────────────────────────────────────────────

  it('Befund 1: wurde der Auftrag im laufenden Zug schon abgeholt, sendet „frei“ nichts (erst neu fragen)', async () => {
    const { ablauf, auftrag, zustand } = lage([{ stand: 'fertig' }, new Error('409') as Error]);
    auftrag.mockImplementation(async (s: { schritt: string }) => {
      if (s.schritt === 'abholen') return { gesendet: true };
      const zahl = auftrag.mock.calls.filter(([x]) => (x as { schritt: string }).schritt === 'stand').length;
      if (zahl === 1) return { stand: 'fertig' };
      throw Object.assign(new Error('x'), { status: 409 });
    });
    zustand.beschaeftigt = true;          // die Person tippte „Stand prüfen“ — der Zug holt ab
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    zustand.beschaeftigt = false;
    ablauf.frei();
    await vi.advanceTimersByTimeAsync(0);
    expect(staende(auftrag)).toEqual(['stand', 'stand']);
    expect(ablauf.phase).toBe('abgeschlossen');
  });

  it('Befund 1: „Ergebnis abholen“ fragt erst neu und holt dann ab', async () => {
    const { ablauf, auftrag } = lage();
    let erstesAbholen = true;
    auftrag.mockImplementation(async (s: { schritt: string }) => {
      if (s.schritt === 'abholen') {
        const r = { gesendet: !erstesAbholen };
        erstesAbholen = false;
        return r;
      }
      return { stand: 'fertig' };
    });
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ablauf.abholenAngeboten()).toBe(true);
    await ablauf.nachpruefen();
    expect(staende(auftrag)).toEqual(['stand', 'abholen', 'stand', 'abholen']);
    expect(ablauf.phase).toBe('abgeholt');
  });

  it('Befund 8: wieder eingehängt mitten in einer Frage — es fragt danach weiter', async () => {
    const { ablauf, auftrag } = lage();
    auftrag.mockImplementationOnce(() => new Promise(() => undefined));
    ablauf.verbinden();
    void ablauf.pruefen();
    ablauf.trennen();
    expect(ablauf.phase).toBe('wartet');
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(auftrag).toHaveBeenCalledTimes(2);
  });

  it('ohne gültige Daten fragt es nie', async () => {
    const auftrag = vi.fn();
    const ablauf = new FortschrittAblauf({
      host: () => ({ auftrag }) as never, daten: () => null, beschaeftigt: () => false,
      sichtbar: () => true, zeichne: () => undefined,
    });
    ablauf.verbinden();
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(auftrag).not.toHaveBeenCalled();
    expect(ablauf.phase).toBe('abgeschlossen');
  });
});
