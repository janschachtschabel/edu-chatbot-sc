// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { wiederkehrKennung, wiederkehrLesen } from '../stream/offene-vorgaenge';
import { ChatShellComponent } from './chat-shell.component';

/**
 * AS-4c (Plan 2026-11-09 §5f, R3): Wiederkehr mit Vorgang- oder Auftragskennung. Die Gastseite
 * (Benachrichtigung, Link) nennt den Vorgang oder den Auftrag; das Backend gibt das Gespräch nur
 * der angemeldeten Besitzerin (`POST /api/ui/vorgaenge/wiederkehr`). Das Widget wechselt dann wie
 * „Gespräch fortsetzen“ (K2a) und fragt bei einem Auftrag „Stand prüfen“.
 */

const DORT = 'bb-fedcba9876543210fedcba9876543210';
const RESP = { content: 'Stand.', session_id: DORT, cards: [], quick_replies: [] } as unknown as ChatResponse;

function make(): ChatShellComponent {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  return f.componentInstance;
}

function fakeApi(antwort: unknown) {
  return {
    stream: vi.fn(async (..._args: unknown[]) => RESP),
    post: vi.fn(async () => RESP),
    wiederkehr: vi.fn(async (..._args: unknown[]) => antwort),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false),
    loadHistory: vi.fn(async () => []), warteAufAnmeldung: vi.fn(),
  };
}

const VORGANG = {
  titel: 'Lesen', ablauf: 'lesen', status: 'wartet_auftrag', session_id: DORT,
  geaendert: '2026-11-07T09:30:00Z',
};

describe('Wiederkehr (AS-4c)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('genau eine wohlgeformte Kennung', () => {
    expect(wiederkehrKennung({ vorgang: '0a1b2c3d-0000-4000-8000-000000000009' }))
      .toEqual({ vorgang: '0a1b2c3d-0000-4000-8000-000000000009' });
    expect(wiederkehrKennung({ auftrag: 'job-42' })).toEqual({ auftrag: 'job-42' });
    expect(wiederkehrKennung({})).toBeNull();
    expect(wiederkehrKennung({ vorgang: '0a1b2c3d', auftrag: 'x' })).toBeNull();
    expect(wiederkehrKennung({ auftrag: 'job/../42' })).toBeNull();
    expect(wiederkehrKennung('job-42' as never)).toBeNull();
  });

  it('nur eine wohlgeformte Antwort wird ein Wechsel', () => {
    expect(wiederkehrLesen(VORGANG)).toEqual(VORGANG);
    expect(wiederkehrLesen({ ...VORGANG, session_id: 'kurz' })).toBeNull();
    expect(wiederkehrLesen({ ...VORGANG, status: 'Böse Sache' })).toBeNull();
    expect(wiederkehrLesen(null)).toBeNull();
  });

  it('wechselt auf das Gespräch und fragt bei einem Auftrag nach dem Stand', async () => {
    const c = make();
    c.sessionId = 'bb-0123456789abcdef0123456789abcdef';
    const api = fakeApi(VORGANG);
    (c as any)._api = api;
    const wechseln = vi.spyOn((c as any)._lifecycle, 'wechseln').mockImplementation(async (id) => {
      c.sessionId = id as string;
      return true;
    });

    await c.vorgangFortsetzen({ auftrag: 'job-42' });

    expect(api.wiederkehr.mock.calls[0].slice(0, 2)).toEqual(['bb-0123456789abcdef0123456789abcdef', { auftrag: 'job-42' }]);
    expect(wechseln).toHaveBeenCalledWith(DORT);
    const [, , , , aktion, params] = api.stream.mock.calls[0] as unknown[];
    expect(aktion).toBe('ablauf_auftrag_pruefen');
    expect(params).toEqual({ ablauf: 'lesen' });
  });

  it('wartet der Lauf auf die Person, nur der Wechsel', async () => {
    const c = make();
    const api = fakeApi({ ...VORGANG, status: 'wartet_person' });
    (c as any)._api = api;
    vi.spyOn((c as any)._lifecycle, 'wechseln').mockResolvedValue(true);
    await c.vorgangFortsetzen({ vorgang: '0a1b2c3d-0000-4000-8000-000000000009' });
    expect(api.stream).not.toHaveBeenCalled();
  });

  it('nichts gefunden: kein Wechsel, eine neutrale Zeile im Chat, die Konsole ohne Kennung', async () => {
    const c = make();
    const api = fakeApi(null);
    api.wiederkehr.mockRejectedValue(new Error('404'));
    (c as any)._api = api;
    (c as any)._hatBlock = () => true;
    const wechseln = vi.spyOn((c as any)._lifecycle, 'wechseln');
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    await c.vorgangFortsetzen({ auftrag: 'job-geheim' });
    expect(wechseln).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0])).not.toContain('job-geheim');
    const zeile = c.messages().at(-1)!;
    expect(zeile.sender).toBe('bot');
    expect(zeile.content).not.toContain('job-geheim');
    expect(zeile.quickReplies ?? []).toEqual([]);
  });

  it('ohne Anmeldung: der Anmelde-Chip, und nach der Anmeldung ein neuer Versuch (Review AS-4c, 5)', async () => {
    const c = make();
    const api = fakeApi(null);
    api.wiederkehr.mockRejectedValueOnce(new Error('403'));
    (c as any)._api = api;
    (c as any)._hatBlock = () => false;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    await c.vorgangFortsetzen({ auftrag: 'job-42' });
    expect(c.messages().at(-1)!.quickReplies).toEqual(['__auth__']);

    api.wiederkehr.mockResolvedValue({ ...VORGANG, status: 'wartet_person' });
    vi.spyOn((c as any)._lifecycle, 'wechseln').mockResolvedValue(true);
    await (c as any)._wiederkehrNachDerAnmeldung();
    expect(api.wiederkehr).toHaveBeenCalledTimes(2);
    expect(api.wiederkehr.mock.calls[1][1]).toEqual({ auftrag: 'job-42' });
  });

  it('die Abfrage hält das Laden; ein Auftrag danach geht auch ohne Treffer ab (Befund 2)', async () => {
    const c = make();
    let antworten!: (v: unknown) => void;
    const api = fakeApi(null);
    api.wiederkehr.mockImplementation(() => new Promise((r) => { antworten = r; }));
    (c as any)._api = api;
    (c as any)._hatBlock = () => true;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    const wiederkehr = c.vorgangFortsetzen({ auftrag: 'job-42' });
    expect(c.isLoading()).toBe(true);               // Eingabe und Warteschlange gesperrt
    const auftrag = c.startTask('Danach.');
    expect(api.stream).not.toHaveBeenCalled();

    antworten(null);                                // nichts gefunden — kein Zug
    await wiederkehr;
    TestBed.tick();
    await auftrag;
    expect(api.stream).toHaveBeenCalledTimes(1);
    expect(api.stream.mock.calls[0][1]).toBe('Danach.');
  });

  it('dasselbe Gespräch: kein Wechsel, aber „Stand prüfen“', async () => {
    const c = make();
    c.sessionId = DORT;
    const api = fakeApi(VORGANG);
    (c as any)._api = api;
    const wechseln = vi.spyOn((c as any)._lifecycle, 'wechseln');
    await c.vorgangFortsetzen({ vorgang: '0a1b2c3d-0000-4000-8000-000000000009' });
    expect(wechseln).not.toHaveBeenCalled();
    expect(api.stream.mock.calls[0][4]).toBe('ablauf_auftrag_pruefen');
  });

  it('scheitert der Wechsel, kein „Stand prüfen“', async () => {
    const c = make();
    const api = fakeApi(VORGANG);
    (c as any)._api = api;
    vi.spyOn((c as any)._lifecycle, 'wechseln').mockResolvedValue(false);
    await c.vorgangFortsetzen({ vorgang: '0a1b2c3d-0000-4000-8000-000000000009' });
    expect(api.stream).not.toHaveBeenCalled();
  });

  it('ein Angebot zu einem anderen Gespräch bleibt (Befund 6)', async () => {
    const c = make();
    c.sessionId = DORT;
    const api = fakeApi({ ...VORGANG, status: 'wartet_person' });
    (c as any)._api = api;
    const anderes = { ...VORGANG, session_id: 'bb-0123456789abcdef0123456789abcdef' };
    c.fortsetzen.angebot.set(anderes as never);
    await c.vorgangFortsetzen({ vorgang: '0a1b2c3d-0000-4000-8000-000000000009' });
    expect(c.fortsetzen.angebot()).toEqual(anderes);
  });

  it('eine kaputte Kennung fragt gar nicht erst', async () => {
    const c = make();
    const api = fakeApi(VORGANG);
    (c as any)._api = api;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    await c.vorgangFortsetzen({ auftrag: 'a b' });
    expect(api.wiederkehr).not.toHaveBeenCalled();
  });

  // ── Querschnitts-Review AS-4 ──────────────────────────────────────────
  it('ein Auftrag, der vor dem Wechsel kam, läuft nicht im Zielgespräch (Befund 2)', async () => {
    const c = make();
    c.sessionId = 'bb-0123456789abcdef0123456789abcdef';
    let antworten!: (v: unknown) => void;
    const api = fakeApi(VORGANG);
    api.wiederkehr.mockImplementation(() => new Promise((r) => { antworten = r; }));
    (c as any)._api = api;
    vi.spyOn((c as any)._lifecycle, 'wechseln').mockImplementation(async (id) => {
      c.sessionId = id as string;
      return true;
    });
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    const wiederkehr = c.vorgangFortsetzen({ auftrag: 'job-42' });
    const ablauf = c.startAblauf('baum');        // eingereiht im alten Gespräch
    antworten(VORGANG);
    await wiederkehr;
    TestBed.tick();
    await ablauf;
    expect(api.stream.mock.calls.map((z) => z[4])).toEqual(['ablauf_auftrag_pruefen']);
    expect(warn.mock.calls.map(String).some((z) => z.includes('verfällt'))).toBe(true);
  });

  it('wechselt das Gespräch während der Abfrage, gilt die Antwort nicht (Befund 4)', async () => {
    const c = make();
    c.sessionId = 'bb-0123456789abcdef0123456789abcdef';
    let antworten!: (v: unknown) => void;
    const api = fakeApi(VORGANG);
    api.wiederkehr.mockImplementation(() => new Promise((r) => { antworten = r; }));
    (c as any)._api = api;
    const wechseln = vi.spyOn((c as any)._lifecycle, 'wechseln');
    const wiederkehr = c.vorgangFortsetzen({ auftrag: 'job-42' });
    c.sessionId = 'bb-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';   // „Neues Gespräch“
    antworten(VORGANG);
    expect(await wiederkehr).toBe('verworfen');
    expect(wechseln).not.toHaveBeenCalled();
  });

  it('nach dem Wechsel ist die Eingabe frei (Befund 5)', async () => {
    const c = make();
    const api = fakeApi({ ...VORGANG, status: 'wartet_person' });
    (c as any)._api = api;
    vi.spyOn((c as any)._lifecycle, 'wechseln').mockResolvedValue(true);
    c.eingabeGesperrt.set(true);
    expect(await c.vorgangFortsetzen({ auftrag: 'job-42' })).toBe('gefunden');
    expect(c.eingabeGesperrt()).toBe(false);
  });

  it('ein Server- oder Netzfehler heißt „später“, nicht „nichts mehr“ (Befund 6)', async () => {
    const c = make();
    const api = fakeApi(null);
    api.wiederkehr.mockRejectedValue(Object.assign(new Error('503'), { status: 503 }));
    (c as any)._api = api;
    (c as any)._hatBlock = () => true;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    expect(await c.vorgangFortsetzen({ auftrag: 'job-42' })).toBe('fehler');
    expect(c.messages().at(-1)!.content).toContain('gerade nicht');
  });

  it('eine 403 trotz Block bittet um die Anmeldung (Befund 6)', async () => {
    const c = make();
    const api = fakeApi(null);
    api.wiederkehr.mockRejectedValue(Object.assign(new Error('403'), { status: 403 }));
    (c as any)._api = api;
    (c as any)._hatBlock = () => true;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    expect(await c.vorgangFortsetzen({ auftrag: 'job-42' })).toBe('anmeldung');
    expect(c.messages().at(-1)!.quickReplies).toEqual(['__auth__']);
  });
});

