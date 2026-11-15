// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { clearAccessBlock, holdAccessBlock, readAccessBlock, writeAccessBlock } from './mcp-access';
import {
  SitzungsWache, TAUSCH_PAUSE_MS, WACHE_FRISCH_MS, WACHE_TAUSCH_MS, type SitzungsWacheWege,
} from './sitzungs-wache';

/**
 * Die Wache vor jedem Abruf mit Block (Plan 2026-11-15, SA-13). Gepinnt wird jede Richtung, in
 * der die Seite jemand anderen zeigen kann als den, für den der Block gilt — und dass die Wache
 * dabei nie selbst zum Hindernis wird (keine Antwort, hängender Tausch, Wurf).
 */

const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';
const NEU = 'wlo2.bmV1.aXY.Y3Q';
const LEA = { authority: 'lehrerin', displayName: 'Lea Lehrerin' };
const BEN = { authority: 'redakteur', displayName: 'Ben Redakteur' };

/** Die Wege als Attrappen; `seite` ist, wen das Repository gerade meldet. */
function aufbau(over: Partial<SitzungsWacheWege> = {}) {
  const stand = { seite: 'lehrerin' as string | null, uhr: 1_000_000, aktiv: true, tauschGelingt: true };
  const attrappen = {
    aktiv: vi.fn(() => stand.aktiv),
    fragen: vi.fn(async (): Promise<string | null> => stand.seite),
    verworfen: vi.fn(),
    tauschen: vi.fn(async (): Promise<boolean> => {
      if (stand.tauschGelingt) holdAccessBlock(NEU, stand.seite === 'redakteur' ? BEN : LEA);
      return stand.tauschGelingt;
    }),
    sagen: vi.fn(),
  };
  const wege: SitzungsWacheWege = {
    ...attrappen,
    jetzt: () => stand.uhr,
    warten: () => new Promise<void>(() => undefined),   // die Frist läuft im Test nie ab
    ...over,
  };
  return { stand, wege: attrappen, wache: new SitzungsWache(wege) };
}

beforeEach(() => {
  sessionStorage.clear();
  clearAccessBlock();
});

describe('SitzungsWache', () => {
  it('dieselbe Person: nichts geschieht', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { wege, wache } = aufbau();
    await wache.pruefen();
    expect(readAccessBlock()).toBe(BLOCK);
    expect(wege.verworfen).not.toHaveBeenCalled();
    expect(wege.tauschen).not.toHaveBeenCalled();
    expect(wege.sagen).not.toHaveBeenCalled();
  });

  it('Gast: der Block fällt weg, ein Satz sagt es, getauscht wird nicht', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    stand.seite = 'esguest';
    await wache.pruefen();
    expect(readAccessBlock()).toBeNull();
    expect(wege.verworfen).toHaveBeenCalledTimes(1);
    expect(wege.sagen).toHaveBeenCalledTimes(1);
    expect(wege.tauschen).not.toHaveBeenCalled();
  });

  it('jemand anderes: der alte Block ist weg, BEVOR getauscht wird', async () => {
    holdAccessBlock(BLOCK, LEA);
    const beimTausch: (string | null)[] = [];
    const { stand, wege, wache } = aufbau();
    stand.seite = 'redakteur';
    wege.tauschen.mockImplementationOnce(async () => {
      beimTausch.push(readAccessBlock());
      holdAccessBlock(NEU, BEN);
      return true;
    });
    await wache.pruefen();
    expect(beimTausch, 'kein Abruf trägt mehr den Block der alten Person').toEqual([null]);
    expect(readAccessBlock()).toBe(NEU);
    expect(wege.sagen, 'der Wechsel gelang: kein Satz').not.toHaveBeenCalled();
  });

  it('vorher Gast, jetzt eine Person: es wird getauscht — ohne Satz, ohne „verworfen“', async () => {
    const { wege, wache } = aufbau();
    await wache.pruefen();
    expect(wege.tauschen).toHaveBeenCalledTimes(1);
    expect(readAccessBlock()).toBe(NEU);
    expect(wege.verworfen).not.toHaveBeenCalled();
    expect(wege.sagen).not.toHaveBeenCalled();
  });

  it('Gast ohne Block: eine Frage, sonst nichts', async () => {
    const { stand, wege, wache } = aufbau();
    stand.seite = 'esguest';
    await wache.pruefen();
    expect(wege.fragen).toHaveBeenCalledTimes(1);
    expect(wege.tauschen).not.toHaveBeenCalled();
    expect(wege.sagen).not.toHaveBeenCalled();
  });

  it('keine Antwort ist kein Urteil — und gilt nicht als frisch', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    stand.seite = null;
    await wache.pruefen();
    expect(readAccessBlock()).toBe(BLOCK);
    await wache.pruefen();
    expect(wege.fragen, 'beim nächsten Abruf wird wieder gefragt').toHaveBeenCalledTimes(2);
  });

  it('nicht aktiv (im Chat abgemeldet, Widget entfernt, Weg gilt nicht): keine Frage', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    stand.aktiv = false;
    await wache.pruefen();
    expect(wege.fragen).not.toHaveBeenCalled();
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('ein Block von Hand ist nicht ihr Fall — auch wenn er während der Frage entsteht', async () => {
    writeAccessBlock(BLOCK);
    const erste = aufbau();
    erste.stand.seite = 'esguest';
    await erste.wache.pruefen();
    expect(erste.wege.fragen).not.toHaveBeenCalled();
    expect(readAccessBlock()).toBe(BLOCK);

    clearAccessBlock();
    const zweite = aufbau();
    zweite.wege.fragen.mockImplementationOnce(async () => {
      writeAccessBlock(BLOCK);   // die Person meldet sich von Hand an, während die Frage läuft
      return 'redakteur';
    });
    await zweite.wache.pruefen();
    expect(zweite.wege.tauschen).not.toHaveBeenCalled();
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('wird während der Frage abgemeldet, geschieht danach nichts mehr', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    wege.fragen.mockImplementationOnce(async () => {
      stand.aktiv = false;   // „Abmelden“ im Chat oder das Widget geht
      return 'redakteur';
    });
    await wache.pruefen();
    expect(wege.verworfen).not.toHaveBeenCalled();
    expect(wege.tauschen).not.toHaveBeenCalled();
  });

  it('eine Folge von Abrufen fragt einmal; nach der Frist wieder', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    await wache.pruefen();
    await wache.pruefen();
    stand.uhr += WACHE_FRISCH_MS - 1;
    await wache.pruefen();
    expect(wege.fragen).toHaveBeenCalledTimes(1);

    stand.uhr += 2;
    await wache.pruefen();
    expect(wege.fragen).toHaveBeenCalledTimes(2);
  });

  it('gleichzeitige Abrufe teilen sich einen Lauf — keiner geht hinaus, während getauscht wird', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    stand.seite = 'redakteur';
    let tauschFertig!: (ok: boolean) => void;
    wege.tauschen.mockImplementationOnce(() => new Promise<boolean>((r) => { tauschFertig = r; }));

    let ersterFertig = false;
    let zweiterFertig = false;
    void wache.pruefen().then(() => { ersterFertig = true; });
    void wache.pruefen().then(() => { zweiterFertig = true; });
    await vi.waitFor(() => expect(tauschFertig).toBeTypeOf('function'));
    expect([ersterFertig, zweiterFertig]).toEqual([false, false]);
    expect(wege.fragen).toHaveBeenCalledTimes(1);

    holdAccessBlock(NEU, BEN);
    tauschFertig(true);
    await vi.waitFor(() => expect([ersterFertig, zweiterFertig]).toEqual([true, true]));
  });

  it('ein hängender Tausch hält den Abruf nur bis zur Frist auf; der Satz kommt, wenn er scheitert', async () => {
    holdAccessBlock(BLOCK, LEA);
    let fristAb!: () => void;
    let tauschFertig!: (ok: boolean) => void;
    const gewartet: number[] = [];
    const { stand, wege, wache } = aufbau({
      warten: (ms) => new Promise<void>((r) => { gewartet.push(ms); fristAb = r; }),
    });
    stand.seite = 'redakteur';
    wege.tauschen.mockImplementationOnce(() => new Promise<boolean>((r) => { tauschFertig = r; }));

    let fertig = false;
    void wache.pruefen().then(() => { fertig = true; });
    await vi.waitFor(() => expect(fristAb).toBeTypeOf('function'));
    expect(gewartet).toEqual([WACHE_TAUSCH_MS]);
    fristAb();
    await vi.waitFor(() => expect(fertig).toBe(true));
    expect(readAccessBlock(), 'der Abruf geht ohne Anmeldung hinaus, nicht mit dem alten Block').toBeNull();
    expect(wege.sagen).not.toHaveBeenCalled();

    tauschFertig(false);
    await vi.waitFor(() => expect(wege.sagen).toHaveBeenCalledTimes(1));
  });

  it('nach einem gescheiterten Tausch versucht sie es eine Weile nicht von selbst', async () => {
    // Die Shell meldet den Ausgang jedes Tauschs (`getauscht`) — gleich, wer ihn anstieß.
    const { stand, wege, wache } = aufbau();
    wache.getauscht('rejected');         // etwa der Tausch beim Laden: 5xx am MCP-Server
    await wache.pruefen();
    expect(wege.fragen).toHaveBeenCalledTimes(1);
    expect(wege.tauschen, 'kein Tausch je Abruf').not.toHaveBeenCalled();
    expect(wege.sagen, 'ohne vorherigen Block kein Satz').not.toHaveBeenCalled();

    stand.uhr += TAUSCH_PAUSE_MS + 1;
    await wache.pruefen();
    expect(wege.tauschen, 'nach der Pause wieder').toHaveBeenCalledTimes(1);
  });

  it('ein Ausgang, den nur der Betrieb ändern kann, pausiert bis zum Klick', async () => {
    for (const ausgang of ['unavailable', 'not-allowed', 'mismatch']) {
      clearAccessBlock();
      const { stand, wege, wache } = aufbau();
      wache.getauscht(ausgang);
      stand.uhr += 100 * TAUSCH_PAUSE_MS;
      await wache.pruefen();
      expect(wege.tauschen, ausgang).not.toHaveBeenCalled();

      // Ein gelungener Tausch (der Klick auf „Anmelden“) hebt die Pause auf.
      wache.getauscht('done');
      stand.uhr += WACHE_FRISCH_MS + 1;
      await wache.pruefen();
      expect(wege.tauschen, `${ausgang}: nach dem Klick wieder`).toHaveBeenCalledTimes(1);
    }
  });

  it('in der Pause fällt der Block einer anderen Person trotzdem weg — mit Satz, ohne Tausch', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { stand, wege, wache } = aufbau();
    wache.getauscht('rejected');
    stand.seite = 'redakteur';
    await wache.pruefen();
    expect(readAccessBlock()).toBeNull();
    expect(wege.sagen).toHaveBeenCalledTimes(1);
    expect(wege.tauschen).not.toHaveBeenCalled();
  });

  it('ein gelungener Tausch und ein Gast gelten als frische Antwort der Seite', async () => {
    for (const ausgang of ['done', 'no-session']) {
      const { wege, wache } = aufbau();
      wache.getauscht(ausgang);
      await wache.pruefen();
      expect(wege.fragen, ausgang).not.toHaveBeenCalled();
    }
  });

  it('„der Weg gilt hier nicht“ (`off`) setzt keine Pause', async () => {
    const { wege, wache } = aufbau();
    wache.getauscht('off');
    await wache.pruefen();
    expect(wege.tauschen).toHaveBeenCalledTimes(1);
  });

  it('wirft nie — auch wenn ein Weg wirft', async () => {
    holdAccessBlock(BLOCK, LEA);
    const { wege, wache } = aufbau();
    wege.fragen.mockRejectedValueOnce(new Error('kaputt'));
    await expect(wache.pruefen()).resolves.toBeUndefined();

    const zweite = aufbau();
    zweite.stand.seite = 'redakteur';
    zweite.wege.tauschen.mockRejectedValueOnce(new Error('kaputt'));
    await expect(zweite.wache.pruefen()).resolves.toBeUndefined();
  });
});
