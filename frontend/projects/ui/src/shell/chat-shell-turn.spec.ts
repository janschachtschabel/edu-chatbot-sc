import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Turn-Maschinerie der Chat-Shell (8-4S-d2a): das Wiring, mit dem die Shell den
 * `SendMessageContext` (8-4S-c) baut + die Erfolgs-Seiteneffekte (`onResult`)
 * verdrahtet. Gepinnt: sendMessage produziert User+Bot-Bubble über das LIVE
 * `_api` (mit `sessionId` gebunden), Stale-freier POST-Fallback, und onResult
 * setzt latestDebug + feuert das query-meta-Event + dispatcht die page_action.
 * NICHT erneut getestet: der runSendMessage-Lebenszyklus selbst (8-4S-c-Spec)
 * und die Context-Delegation (8-4S-d1-Spec).
 */

const RESP = {
  content: 'Antwort', session_id: 's1', debug: { pattern: 'M06' },
  query_metas: [{ query: 'mathe', total_count: 3 }], page_action: { action: 'canvas', payload: { n: 1 } },
  cards: [], quick_replies: [],
} as unknown as ChatResponse;

function make(): ChatShellComponent {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  return TestBed.createComponent(ChatShellComponent).componentInstance;
}

/** Fake-API, das stream/post aufzeichnet und RESP liefert. `streamRejects`
 *  erzwingt den POST-Fallback-Pfad. */
function fakeApi(opts: { streamRejects?: Error; resp?: ChatResponse } = {}) {
  const antwort = opts.resp ?? RESP;
  return {
    stream: vi.fn(async (_sid: string, _msg: string, onEvent: (e: any) => void) => {
      if (opts.streamRejects) throw opts.streamRejects;
      onEvent({ event: 'phase', data: { step: 'wlo_search' } });
      return antwort;
    }),
    post: vi.fn(async () => antwort),
    setResultSchema: vi.fn(),
    // Vom Lebenszyklus gerufen. Die meisten Tests hier rendern nie, ein
    // wartender Test schon — ohne diese Attrappen stürbe er an einem Fehler
    // aus `ngOnInit` statt an seiner eigenen Aussage.
    setUiLocale: vi.fn(),
    setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(),
    getSpeechEnabled: vi.fn(async () => false),
    loadHistory: vi.fn(async () => []),
  };
}

describe('ChatShellComponent — Turn-Maschinerie (8-4S-d2a)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sendMessage: User+Bot-Bubble, _api.stream mit LIVE sessionId, isLoading am Ende false', async () => {
    const c = make();
    c.sessionId = 'sess-x';
    const api = fakeApi();
    (c as any)._api = api;

    await c.sendMessage('hallo');

    const msgs = c.messages();
    expect(msgs.map(m => [m.sender, m.content])).toEqual([['user', 'hallo'], ['bot', 'Antwort']]);
    expect(c.isLoading()).toBe(false);
    expect(api.stream.mock.calls[0][0]).toBe('sess-x'); // sessionId gebunden
    expect(api.stream.mock.calls[0][1]).toBe('hallo');
  });

  // ── Auftrag von außen (Nutzer-Entscheid 2026-08-14) ────────────────────
  // Ein Gastgeber (Browser-Plugin, Repo-Seite) soll den Chat auf ein Thema
  // starten können: „hier ist die Sammlung, hier der Seitentext, leg los".
  // Der Satz erscheint im Verlauf, aber als EIGENE Auftrags-Blase — er wurde
  // nicht von der Person gesagt, und ein untergeschobener Satz im Verlauf wäre
  // eine Behauptung über sie.

  it('startTask: Auftrags-Blase statt Nutzernachricht, Zug geht ab', async () => {
    const c = make();
    c.sessionId = 'sess-a';
    const api = fakeApi();
    (c as any)._api = api;

    await c.startTask('Bestimme das Schulfach dieser Seite.');

    const msgs = c.messages();
    // `sender` bleibt 'user': Grouping und Verlauf kennen zwei Seiten, eine
    // dritte einzuführen kostete jede Consumer-Regel. Die Markierung sagt,
    // WER den Satz beigesteuert hat.
    expect(msgs[0].sender).toBe('user');
    expect(msgs[0].fromHost).toBe(true);
    expect(msgs[0].content).toBe('Bestimme das Schulfach dieser Seite.');
    expect(api.stream.mock.calls[0][1]).toBe('Bestimme das Schulfach dieser Seite.');
    expect(msgs[1].sender).toBe('bot');
  });

  it('eine getippte Nachricht bleibt ohne die Auftrags-Markierung', async () => {
    const c = make();
    (c as any)._api = fakeApi();
    await c.sendMessage('hallo');
    expect(c.messages()[0].fromHost).toBeFalsy();
  });

  it('die Markierung gilt nur für den einen Zug', async () => {
    // Sonst trüge jede spätere Nutzereingabe das Etikett des Gastgebers.
    const c = make();
    (c as any)._api = fakeApi();
    await c.startTask('Auftrag');
    await c.sendMessage('und jetzt ich');
    expect(c.messages()[0].fromHost).toBe(true);
    expect(c.messages()[2].fromHost).toBeFalsy();
  });

  it('ein leerer Auftrag löst keinen Zug aus', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    await c.startTask('   ');
    expect(api.stream).not.toHaveBeenCalled();
    expect(c.messages()).toEqual([]);
  });

  it('onResult: latestDebug gesetzt, query-meta-Event gefeuert, page_action dispatcht', async () => {
    const c = make();
    (c as any)._api = fakeApi();
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    const onPageAction = vi.fn();
    c.onPageAction = onPageAction;

    await c.sendMessage('frag');

    expect(c.latestDebug()).toEqual({ pattern: 'M06' });
    const qm = dispatchSpy.mock.calls.find(([e]) => (e as CustomEvent).type === 'boerdi:query-meta');
    expect(qm).toBeTruthy();
    expect((qm![0] as CustomEvent).detail).toEqual({ queries: RESP.query_metas });
    expect(onPageAction).toHaveBeenCalledWith({ action: 'canvas', payload: { n: 1 } });
  });

  // ── Das maschinenlesbare Ergebnis (Nutzer-Entscheid 2026-08-14) ──────
  // Der Gastgeber erklärt ein Schema; kommt ein Ergebnis, muss es ihn
  // erreichen. Ohne diesen Weg produzierte das Backend ein `result`, das
  // niemand lesen kann.

  it('setResultSchema wird an den Client durchgereicht', () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    c.setResultSchema({ type: 'object' });
    expect(api.setResultSchema).toHaveBeenCalledWith({ type: 'object' });
  });

  it('ein Ergebnis im Zug feuert boerdi:agent-result und den Angular-Ausgang', async () => {
    const c = make();
    (c as any)._api = fakeApi({ resp: {
      ...RESP, result: { taxon_id: '…/460' }, result_stop_reason: 'submit',
    } as unknown as ChatResponse });
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    const gesehen: unknown[] = [];
    c.agentResult.subscribe((v: unknown) => gesehen.push(v));

    await c.sendMessage('welches Fach?');

    const evt = dispatchSpy.mock.calls
      .find(([e]) => (e as CustomEvent).type === 'boerdi:agent-result');
    expect(evt).toBeTruthy();
    expect((evt![0] as CustomEvent).detail)
      .toEqual({ result: { taxon_id: '…/460' }, stop_reason: 'submit' });
    expect(gesehen).toEqual([{ result: { taxon_id: '…/460' }, stop_reason: 'submit' }]);
  });

  it('ein Zug OHNE Ergebnis, aber mit Ende-Grund, meldet den Grund', async () => {
    // „Hallo" bei erklärtem Schema: kein Ergebnis. Der Gastgeber soll den
    // Unterschied zwischen „nichts dabei" und „abgeschnitten" sehen können.
    const c = make();
    (c as any)._api = fakeApi({ resp: {
      ...RESP, result: null, result_stop_reason: 'text',
    } as unknown as ChatResponse });
    const gesehen: unknown[] = [];
    c.agentResult.subscribe((v: unknown) => gesehen.push(v));

    await c.sendMessage('hallo');

    expect(gesehen).toEqual([{ result: null, stop_reason: 'text' }]);
  });

  it('ein gewöhnlicher Zug ohne Schema schweigt', async () => {
    // Die Gegenprobe: kein Ereignis bei jeder normalen Antwort — sonst hörte
    // eine Gastseite auf ein Signal, das nichts bedeutet.
    const c = make();
    (c as any)._api = fakeApi();
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    const gesehen: unknown[] = [];
    c.agentResult.subscribe((v: unknown) => gesehen.push(v));

    await c.sendMessage('hallo');

    expect(dispatchSpy.mock.calls
      .find(([e]) => (e as CustomEvent).type === 'boerdi:agent-result')).toBeFalsy();
    expect(gesehen).toEqual([]);
  });

  it('Stream-Fehler (non-stale) → stiller POST-Fallback, Bot-Bubble erscheint', async () => {
    const c = make();
    const api = fakeApi({ streamRejects: new Error('proxy down') });
    (c as any)._api = api;
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    await c.sendMessage('hallo');

    expect(api.post).toHaveBeenCalledTimes(1);
    expect(c.messages().map(m => m.sender)).toEqual(['user', 'bot']);
    expect(c.messages()[1].content).toBe('Antwort');
  });

  it('leere Eingabe / laufender Turn → no-op (Guard)', async () => {
    const c = make();
    (c as any)._api = fakeApi();
    await c.sendMessage('');            // leer
    expect(c.messages()).toEqual([]);
    c.isLoading.set(true);
    await c.sendMessage('x');           // Turn läuft
    expect(c.messages()).toEqual([]);
  });
});

/**
 * E4 — die vorbereitete Änderung erreicht den Ausführer.
 *
 * Hier hängt nur die NAHT: dass die Shell das Feld bemerkt, den Vorgang startet
 * und dessen Ergebnis in den Verlauf schreibt. Riegel, Erlaubnisliste und die
 * fünf Ausgänge sind in `session/prepared-write.spec.ts` gepinnt und werden
 * nicht ein zweites Mal geprüft.
 */
describe('ChatShellComponent — vorbereitete Änderung (E4)', () => {
  afterEach(() => vi.restoreAllMocks());

  /** Wie oben, aber mit gesetztem Übersetzer — der Vorgang übersetzt seinen
   *  Ausgang, und ohne den Pflicht-Input wirft die Shell (NG0950). */
  function makeUebersetzt(): ChatShellComponent {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
    const f = TestBed.createComponent(ChatShellComponent);
    f.componentRef.setInput('translate', createTranslator(DE, DE));
    return f.componentInstance;
  }

  const WRITE = {
    method: 'PUT',
    path: '/edu-sharing/rest/collection/v1/collections/-home-/aaa/references/bbb',
    body: null,
    done_message: '',
  };

  /** Antwortet als Gast — dann schreibt der Ausführer NICHTS und sagt es. */
  function fetchAlsGast() {
    return vi.fn(async () => ({
      ok: true,
      json: async () => ({ person: { authorityName: 'esguest' } }),
    })) as unknown as typeof fetch;
  }

  it('startet den Vorgang und schreibt sein Ergebnis in den Verlauf', async () => {
    const c = makeUebersetzt();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(fetchAlsGast());
    (c as any)._api = {
      ...fakeApi(),
      stream: vi.fn(async () => ({ ...RESP, prepared_write: WRITE })),
    };

    await c.sendMessage('leg das bitte ab');

    // `toContain` und nicht „letzte Blase": das Warten lässt hier auch den
    // Lebenszyklus anlaufen, der die Begrüßung nachschiebt. Im Betrieb steht
    // die längst da; die Reihenfolge ist ein Artefakt dieses Aufbaus.
    await vi.waitFor(() => {
      expect(c.messages().map(m => m.content)).toContain(DE['prepared.signedOut']);
    });
    expect(fetchSpy).toHaveBeenCalledTimes(1);   // nur die Frage nach der Person
  });

  it('rührt ohne vorbereitete Änderung nichts an', async () => {
    const c = makeUebersetzt();
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    (c as any)._api = fakeApi();

    await c.sendMessage('nur eine Frage');

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(c.messages().map(m => m.sender)).toEqual(['user', 'bot']);
  });
});

/**
 * Ticket-Anmeldung — die Naht zwischen Attribut und Tausch.
 *
 * Hier hängt nur: dass der Effect anspringt, sobald BEIDE Zutaten da sind
 * (Ticket sofort, `mcpAuthBase` erst nach dem Config-Abruf), dass derselbe
 * Wert nur einmal getauscht wird, und dass der Knopf danach „Abmelden" zeigt.
 * Der Tausch selbst ist in `session/ticket-login.spec.ts` gepinnt.
 */
describe('ChatShellComponent — Ticket-Anmeldung', () => {
  const TICKET = 'TICKET_c001d00dfeedface0123456789abcdef01234567';
  const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';

  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  function makeFixture() {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
    const f = TestBed.createComponent(ChatShellComponent);
    f.componentRef.setInput('translate', createTranslator(DE, DE));
    (f.componentInstance as any)._api = fakeApi();
    return f;
  }

  it('tauscht, sobald die Anmelde-Adresse nachkommt — und je Ticket nur einmal', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((async () => new Response(
      JSON.stringify({ ok: true, block: BLOCK, authority: 'lehrerin' }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    )) as typeof fetch);

    const f = makeFixture();
    f.componentRef.setInput('ticket', TICKET);
    f.detectChanges();
    expect(fetchSpy).not.toHaveBeenCalled(); // die Adresse fehlt noch — wie im Betrieb beim Boot

    f.componentRef.setInput('mcpAuthBase', 'https://mcp.example.org');
    f.detectChanges();

    await vi.waitFor(() => {
      expect(sessionStorage.getItem('boerdi.mcp-access')).toBe(BLOCK);
      expect(f.componentInstance.authButton()).toBe('signOut');
    });

    // Weitere Signal-Läufe stoßen KEINEN zweiten Tausch an.
    f.detectChanges();
    expect(fetchSpy.mock.calls.filter(([url]) => String(url).endsWith('/auth/ticket'))).toHaveLength(1);
  });

  it('lässt bei abgelehntem Ticket die Handanmeldung stehen und warnt die Betreiberseite', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((async () => new Response(
      JSON.stringify({ error: 'abgelaufen' }),
      { status: 400, headers: { 'content-type': 'application/json' } },
    )) as typeof fetch);
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const f = makeFixture();
    f.componentRef.setInput('ticket', TICKET);
    f.componentRef.setInput('mcpAuthBase', 'https://mcp.example.org');
    f.detectChanges();

    await vi.waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(
        'WLO-Anmeldung über das Seiten-Ticket nicht gelungen:', 'rejected',
      );
    });
    expect(sessionStorage.getItem('boerdi.mcp-access')).toBeNull();
    expect(f.componentInstance.authButton()).toBe('signIn'); // Rückfall: Knopf bietet die Anmeldung an
  });
});
