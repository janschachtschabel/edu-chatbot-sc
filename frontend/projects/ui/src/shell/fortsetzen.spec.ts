import { describe, expect, it, vi } from 'vitest';

import { offeneVorgaengeLesen } from '../stream/offene-vorgaenge';
import { FortsetzenController, type OffenerVorgang, fortsetzenDatum } from './fortsetzen';

/**
 * „Gespräch fortsetzen“ (Paket K2a): nur wohlgeformte Angebote, einmal je Gespräch gefragt, nie das
 * aktuelle Gespräch, still bei Fehlern, und nach dem Abmelden vergessen.
 */

const HIER = 'bb-12345678-1234-4123-8123-123456789abc';
const DORT = 'bb-87654321-4321-4321-8321-cba987654321';
const VORGANG: OffenerVorgang = {
  titel: 'Lesen', ablauf: 'lesen', status: 'wartet_auftrag', session_id: DORT,
  geaendert: '2026-11-07T09:30:00Z',
};

describe('offeneVorgaengeLesen', () => {
  it('lässt nur wohlgeformte Einträge durch', () => {
    const liste = offeneVorgaengeLesen({ vorgaenge: [
      VORGANG,
      { ...VORGANG, session_id: 'evil-tracking-id' },
      { ...VORGANG, status: 'fertig' },
      { ...VORGANG, geaendert: 'gestern' },
      { ...VORGANG, ablauf: 3 },
      null,
    ] });
    expect(liste).toEqual([VORGANG]);
  });

  it('wirft ohne Liste', () => {
    expect(() => offeneVorgaengeLesen({})).toThrow();
    expect(() => offeneVorgaengeLesen(null)).toThrow();
  });
});

describe('fortsetzenDatum', () => {
  it('formatiert in der Sprache des Widgets, ein kaputtes Datum bleibt leer', () => {
    expect(fortsetzenDatum('2026-11-07T09:30:00Z', 'de')).toMatch(/7\. Nov/);
    expect(fortsetzenDatum('kaputt', 'de')).toBe('');
  });
});

describe('FortsetzenController', () => {
  function make(liste: OffenerVorgang[] | Error = [VORGANG]) {
    let sid = HIER;
    let block: string | null = 'block-p';
    const abrufen = vi.fn(async () => {
      if (liste instanceof Error) throw liste;
      return liste;
    });
    const c = new FortsetzenController({ abrufen, sessionId: () => sid, block: () => block });
    return { c, abrufen, setSid: (s: string) => { sid = s; }, setBlock: (b: string | null) => { block = b; } };
  }

  it('fragt einmal je Gespräch und bietet den Vorgang an', async () => {
    const { c, abrufen } = make();
    await c.pruefen();
    await c.pruefen();
    expect(abrufen).toHaveBeenCalledTimes(1);
    expect(abrufen).toHaveBeenCalledWith(HIER);
    expect(c.angebot()).toEqual(VORGANG);
  });

  it('bietet nie das aktuelle Gespräch an', async () => {
    const { c } = make([{ ...VORGANG, session_id: HIER }]);
    await c.pruefen();
    expect(c.angebot()).toBeNull();
  });

  it('verwirft eine Antwort, die nach einem Gesprächswechsel kommt', async () => {
    const { c, setSid } = make();
    const laeuft = c.pruefen();
    setSid(DORT);
    await laeuft;
    expect(c.angebot()).toBeNull();
  });

  it('bleibt bei einem Fehler still', async () => {
    const { c } = make(new Error('503'));
    await expect(c.pruefen()).resolves.toBeUndefined();
    expect(c.angebot()).toBeNull();
  });

  it('verwerfen schließt, vergessen fragt beim nächsten Mal neu', async () => {
    const { c, abrufen } = make();
    await c.pruefen();
    c.verwerfen();
    expect(c.angebot()).toBeNull();
    await c.pruefen();
    expect(abrufen).toHaveBeenCalledTimes(1);
    c.vergessen();
    await c.pruefen();
    expect(abrufen).toHaveBeenCalledTimes(2);
    expect(c.angebot()).toEqual(VORGANG);
  });

  // Review K2a, Befund 2: meldet die Gastseite eine andere Person an, gilt das Angebot nicht mehr.
  it('ein Angebot gilt nur für den Block, mit dem gefragt wurde', async () => {
    const { c, setBlock } = make();
    await c.pruefen();
    expect(c.gueltiges()).toEqual(VORGANG);
    setBlock('block-q');
    expect(c.gueltiges()).toBeNull();
    expect(c.angebot()).toBeNull();
  });

  it('verwirft eine Antwort, die nach einem Blockwechsel kommt', async () => {
    const { c, setBlock } = make();
    const laeuft = c.pruefen();
    setBlock('block-q');
    await laeuft;
    expect(c.angebot()).toBeNull();
  });
});
