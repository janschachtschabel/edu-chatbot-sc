import { describe, expect, it, vi } from 'vitest';

import { type EigenerVorgang, eigeneVorgaengeLesen } from '../stream/offene-vorgaenge';
import { MeineVorgaengeController } from './meine-vorgaenge';

/**
 * AS-Ud (Plan 2026-11-09 §5j): „Meine Vorgänge“ — nur wohlgeformte Einträge, Laden mit Lade- und
 * Fehlerzustand, Löschen erst nach der Rückfrage, eine veraltete Antwort (anderes Gespräch, andere
 * Anmeldung) gilt nicht, und nach dem Abmelden ist alles vergessen.
 */

const HIER = 'bb-12345678-1234-4123-8123-123456789abc';
const DORT = 'bb-87654321-4321-4321-8321-cba987654321';
const V1: EigenerVorgang = {
  id: '0a1b2c3d-0000-4000-8000-000000000001', titel: 'Lesen', ablauf: 'lesen',
  status: 'wartet_auftrag', session_id: DORT, geaendert: '2026-11-07T09:30:00Z',
};
const V2: EigenerVorgang = { ...V1, id: '0a1b2c3d-0000-4000-8000-000000000002', titel: 'Optik', ablauf: null, status: 'aktiv' };

describe('eigeneVorgaengeLesen', () => {
  it('lässt nur wohlgeformte Einträge durch', () => {
    const liste = eigeneVorgaengeLesen({ vorgaenge: [
      V1, V2,
      { ...V1, id: 'x' },
      { ...V1, id: undefined },
      { ...V1, session_id: 'evil' },
      { ...V1, status: 'Fertig!' },
      { ...V1, geaendert: 'gestern' },
      null,
    ] });
    expect(liste).toEqual([V1, V2]);
  });

  it('wirft ohne Liste', () => {
    expect(() => eigeneVorgaengeLesen({})).toThrow();
  });
});

function make(antwort: EigenerVorgang[] | Error = [V1, V2]) {
  let sid = HIER;
  let block: string | null = 'block-p';
  const abrufen = vi.fn(async (_s: string) => {
    if (antwort instanceof Error) throw antwort;
    return antwort;
  });
  const loeschen = vi.fn(async (_s: string, _id: string) => undefined as void);
  const c = new MeineVorgaengeController({ abrufen, loeschen, sessionId: () => sid, block: () => block });
  return { c, abrufen, loeschen, setSid: (s: string) => { sid = s; }, setBlock: (b: string | null) => { block = b; } };
}

describe('MeineVorgaengeController', () => {
  it('öffnen lädt: erst „lädt“, dann die Liste', async () => {
    const { c, abrufen } = make();
    const laden = c.umschalten();
    expect([c.offen(), c.stand()]).toEqual([true, 'laedt']);
    await laden;
    expect(abrufen).toHaveBeenCalledWith(HIER);
    expect([c.stand(), c.liste()]).toEqual(['bereit', [V1, V2]]);
    await c.umschalten();
    expect(c.offen()).toBe(false);
  });

  it('ein Fehler zeigt „fehler“; erneut laden geht', async () => {
    const t = make(new Error('netz'));
    await t.c.umschalten();
    expect(t.c.stand()).toBe('fehler');
    t.abrufen.mockResolvedValueOnce([V2]);
    await t.c.laden();
    expect([t.c.stand(), t.c.liste()]).toEqual(['bereit', [V2]]);
  });

  it('nie das aktuelle Gespräch, auch wenn der Server es schickte', async () => {
    const { c } = make([V1, { ...V2, session_id: HIER }]);
    await c.umschalten();
    expect(c.liste()).toEqual([V1]);
  });

  it('eine Antwort für ein anderes Gespräch oder eine andere Anmeldung gilt nicht', async () => {
    const t = make();
    const laden = t.c.umschalten();
    t.setBlock('block-q');
    await laden;
    expect(t.c.liste()).toEqual([]);
    expect(t.c.stand()).toBe('laedt');
  });

  it('löschen erst nach der Rückfrage; danach fehlt der Eintrag und die Meldung nennt ihn', async () => {
    const { c, loeschen } = make();
    await c.umschalten();
    c.fragen(V1.id);
    expect(c.frage()).toBe(V1.id);
    c.nichtLoeschen();
    expect(c.frage()).toBeNull();
    expect(loeschen).not.toHaveBeenCalled();
    c.fragen(V1.id);
    expect(await c.loeschen(V1.id)).toBe(true);
    expect(loeschen).toHaveBeenCalledWith(HIER, V1.id);
    expect(c.liste()).toEqual([V2]);
    expect(c.meldung()).toEqual({ schluessel: 'vorgaenge.geloescht', titel: 'Lesen' });
    expect(c.frage()).toBeNull();
  });

  it('scheitert das Löschen, sagt die Meldung es und die Liste wird neu geladen', async () => {
    const { c, loeschen, abrufen } = make();
    await c.umschalten();
    loeschen.mockRejectedValueOnce(new Error('404'));
    abrufen.mockResolvedValueOnce([V2]);
    expect(await c.loeschen(V1.id)).toBe(false);
    expect(c.meldung()).toEqual({ schluessel: 'vorgaenge.loeschFehler', titel: 'Lesen' });
    expect(c.liste()).toEqual([V2]);
  });

  it('zweimal löschen läuft nur einmal', async () => {
    const { c, loeschen } = make();
    await c.umschalten();
    await Promise.all([c.loeschen(V1.id), c.loeschen(V1.id)]);
    expect(loeschen).toHaveBeenCalledTimes(1);
  });

  it('vergessen (Abmelden, neuer Block): zu, leer, eine laufende Antwort gilt nicht mehr', async () => {
    const { c } = make();
    const laden = c.umschalten();
    c.vergessen();
    await laden;
    expect([c.offen(), c.liste(), c.frage(), c.meldung()]).toEqual([false, [], null, null]);
  });
});

describe('Querschnitts-Review AS-U/BU', () => {
  it('Q-6: läuft der Auftrag bei der b-api weiter, sagt es die Meldung', async () => {
    const { c, loeschen } = make();
    loeschen.mockResolvedValueOnce({ laeuftWeiter: true } as never);
    await c.umschalten();
    expect(await c.loeschen(V1.id)).toBe(true);
    expect(c.meldung()).toEqual({ schluessel: 'vorgaenge.geloeschtAuftragWeiter', titel: 'Lesen' });
  });

  it('Q-7: der Laufstatus bleibt beim Lesen erhalten', () => {
    const [v] = eigeneVorgaengeLesen({ vorgaenge: [{ ...V1, lauf_status: 'wartet_freigabe' }] });
    expect(v.lauf_status).toBe('wartet_freigabe');
    const [ohne] = eigeneVorgaengeLesen({ vorgaenge: [{ ...V1, lauf_status: 3 }] });
    expect(ohne.lauf_status).toBeUndefined();
  });
});
