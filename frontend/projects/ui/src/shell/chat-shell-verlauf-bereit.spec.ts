// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { generateSessionId } from '../session/session-id';
import { HistoryMessage } from '../stream/chat-api';
import { ChatApiClient } from '../stream/chat-api';
import { ChatShellComponent } from './chat-shell.component';
import { VERLAUF_FRIST_MS } from './lifecycle';

/**
 * Paket RB-3 (Review AS-4b, Befunde 4/5):
 * - In einer fortgesetzten Sitzung wartet ein Auftrag der Gastseite, bis der Verlauf
 *   wiederhergestellt ist. Sonst stünde seine Blase vor dem alten Gespräch.
 * - Ein Zug der Gastseite trägt `from_host`. Der Verlauf gibt es als `ui.from_host` zurück, und
 *   die Blase bleibt nach dem Neuladen eine Auftrags-Blase.
 */

const RESP = { content: 'Los.', session_id: 's1', cards: [], quick_replies: [] } as unknown as ChatResponse;
const SCHLUESSEL = 'boerdi_r3_test';

function fakeApi(verlauf: Promise<HistoryMessage[]>) {
  return {
    stream: vi.fn(async (..._args: unknown[]) => RESP),
    post: vi.fn(async (..._args: unknown[]) => RESP),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false),
    loadHistory: vi.fn(() => verlauf), warteAufAnmeldung: vi.fn(),
    offeneVorgaenge: vi.fn(async () => []),
  };
}

function starten(api: ReturnType<typeof fakeApi>, fortgesetzt: boolean): ChatShellComponent {
  localStorage.removeItem(SCHLUESSEL);
  if (fortgesetzt) localStorage.setItem(SCHLUESSEL, generateSessionId());
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ imports: [ChatShellComponent], providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('sessionKey', SCHLUESSEL);
  f.componentRef.setInput('persistSession', true);
  (f.componentInstance as any)._api = api;
  f.detectChanges();  // ngOnInit
  return f.componentInstance;
}

const ruhe = () => new Promise((r) => setTimeout(r, 0));

describe('ChatShellComponent — Verlauf zuerst, Merker der Gastseite (RB-3)', () => {
  afterEach(() => { vi.restoreAllMocks(); localStorage.removeItem(SCHLUESSEL); });

  it('ein Auftrag wartet in einer fortgesetzten Sitzung, bis der Verlauf da ist', async () => {
    let liefern!: (v: HistoryMessage[]) => void;
    const api = fakeApi(new Promise((r) => { liefern = r; }));
    const c = starten(api, true);

    const auftrag = c.startTask('Leg los');
    await ruhe();
    expect(api.stream).not.toHaveBeenCalled();

    liefern([{ role: 'user', content: 'Alte Frage' }, { role: 'assistant', content: 'Alte Antwort' }]);
    await auftrag;
    expect(api.stream).toHaveBeenCalledTimes(1);
    const texte = c.messages().map((m) => m.content).filter(Boolean);
    expect(texte.indexOf('Alte Frage')).toBeLessThan(texte.indexOf('Leg los'));
  });

  it('in einer frischen Sitzung geht der Auftrag gleich', async () => {
    const api = fakeApi(Promise.resolve([]));
    const c = starten(api, false);
    await c.startTask('Leg los');
    expect(api.stream).toHaveBeenCalledTimes(1);
  });

  it('scheitert das Laden des Verlaufs, wartet der Auftrag nicht für immer', async () => {
    const api = fakeApi(Promise.reject(new Error('weg')));
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const c = starten(api, true);
    await c.startTask('Leg los');
    expect(api.stream).toHaveBeenCalledTimes(1);
  });

  it('ein Zug der Gastseite trägt from_host, ein getippter nicht', async () => {
    const api = fakeApi(Promise.resolve([]));
    const c = starten(api, false);
    await c.startTask('Leg los');
    expect(api.stream.mock.calls[0].at(-1)).toBe(true);
    await c.sendMessage('Hallo');
    expect(api.stream.mock.calls[1].at(-1)).not.toBe(true);
  });

  it('der Merker reist auch mit startAblauf und im POST-Rückfall (Review RB-3, Befund 3)', async () => {
    const api = fakeApi(Promise.resolve([]));
    api.stream.mockRejectedValue(new TypeError('Failed to fetch'));
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const c = starten(api, false);
    await c.startAblauf('baum');
    expect(api.stream.mock.calls[0].at(-1)).toBe(true);
    expect(api.post.mock.calls[0].at(-1)).toBe(true);
  });

  it('hängt der Verlauf, geht der Auftrag nach der Frist (Review RB-3, Befund 1)', async () => {
    vi.useFakeTimers();
    try {
      const api = fakeApi(new Promise(() => undefined));   // kommt nie
      const c = starten(api, true);
      const auftrag = c.startTask('Leg los');
      await vi.advanceTimersByTimeAsync(VERLAUF_FRIST_MS - 1);
      expect(api.stream).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(2);
      await auftrag;
      expect(api.stream).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('ein Neustart während des Ladens gibt die Warteschlange frei (Review RB-3, Befund 1)', async () => {
    const api = fakeApi(new Promise(() => undefined));
    const c = starten(api, true);
    c.resetSession();
    await c.startTask('Leg los');
    expect(api.stream).toHaveBeenCalledTimes(1);
  });

  it('wartet ein Auftrag, entfällt nach dem Verlauf der Kontext-Gruß (Review RB-3, Befund 2)', async () => {
    let liefern!: (v: HistoryMessage[]) => void;
    const api = fakeApi(new Promise((r) => { liefern = r; }));
    const c = starten(api, true);
    const ping = vi.spyOn((c as any)._contextGreeting, 'sendContextPing');
    c.updateContext({ collection_id: 'abc' });
    const auftrag = c.startTask('Leg los');
    liefern([{ role: 'user', content: 'Alte Frage' }]);
    await auftrag;
    await ruhe();
    expect(ping).not.toHaveBeenCalled();
    expect(api.stream).toHaveBeenCalledTimes(1);
  });
});

describe('ChatShellComponent — Ablauf-Leiste nach dem Neuladen (AS-Ub)', () => {
  it('der Stand an der letzten Antwort des Verlaufs zeigt die Leiste wieder', async () => {
    const stand = { id: 'probe', titel: 'Probe', nr: 2, von: 3, status: 'wartet_wahl', teile: [] };
    const api = fakeApi(Promise.resolve([
      { role: 'user', content: 'Los' },
      { role: 'assistant', content: 'Weiter?', ui: { ablauf: stand, fester_text: true } },
    ] as HistoryMessage[]));
    const c = starten(api, true);
    await ruhe();
    expect(c.ablaufStand()).toEqual(stand);
  });
});

describe('ChatApiClient.buildBody — from_host (RB-3)', () => {
  it('nur bei true im Rumpf', () => {
    const api = new ChatApiClient() as any;
    expect(api.buildBody('bb-1', 'x', undefined, undefined, undefined, undefined, true).from_host).toBe(true);
    expect('from_host' in api.buildBody('bb-1', 'x')).toBe(false);
    expect('from_host' in api.buildBody('bb-1', 'x', undefined, undefined, undefined, undefined, false)).toBe(false);
  });

  it('nach dem Neuladen bleibt die Blase der Gastseite eine Auftrags-Blase', async () => {
    const api = fakeApi(Promise.resolve([
      { role: 'user', content: 'Leg los', ui: { from_host: true } },
      { role: 'assistant', content: 'Los.' },
      { role: 'user', content: 'Danke' },
    ] as HistoryMessage[]));
    const c = starten(api, true);
    await ruhe();
    const nutzer = c.messages().filter((m) => m.sender === 'user');
    expect(nutzer.map((m) => [m.content, m.fromHost === true])).toEqual([['Leg los', true], ['Danke', false]]);
  });
});

describe('Wiederkehr vor dem Verlauf (Review PR #51, Widget-Befund 2)', () => {
  afterEach(() => { vi.restoreAllMocks(); localStorage.removeItem(SCHLUESSEL); });

  it('in einer fortgesetzten Sitzung wartet die Wiederkehr auf den Verlauf — „Stand prüfen“ dahinter', async () => {
    let liefern!: (v: HistoryMessage[]) => void;
    const api = fakeApi(new Promise((r) => { liefern = r; }));
    const c = starten(api, true);
    const wiederkehr = vi.fn(async () => ({
      titel: 'Lesen', ablauf: 'lesen', status: 'wartet_auftrag', session_id: c.sessionId,
      geaendert: '2026-11-07T09:30:00Z' }));
    (api as any).wiederkehr = wiederkehr;

    const fertig = c.vorgangFortsetzen({ auftrag: 'job-42' });
    await ruhe();
    expect(wiederkehr).not.toHaveBeenCalled();
    expect(api.stream).not.toHaveBeenCalled();

    liefern([{ role: 'user', content: 'Alte Frage' }, { role: 'assistant', content: 'Alte Antwort' }]);
    expect(await fertig).toBe('gefunden');
    expect(wiederkehr).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(api.stream).toHaveBeenCalledTimes(1));
    expect(api.stream.mock.calls[0][4]).toBe('ablauf_auftrag_pruefen');
    const texte = c.messages().map((m) => m.content).filter(Boolean);
    expect(texte).toContain('Alte Frage');
  });
});
