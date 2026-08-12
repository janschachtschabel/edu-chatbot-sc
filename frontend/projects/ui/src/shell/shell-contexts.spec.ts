import { describe, expect, it } from 'vitest';

import { ChatApiClient } from '../stream/chat-api';
import { ChatMessage } from '../grouping/message-types';
import { ShellHost, buildControllerContexts } from './shell-contexts';

/**
 * Charakterisierung des Controller-Context-Factory (8-4S-d1). Pinnt, dass die
 * 5 Contexts ihre deferred Arrows an den `ShellHost` durchreichen — vor allem
 * die LIVE-Bindung von `sessionId`/`api` in beide `sendMessage`-Varianten
 * (das Kern-Contract der Seams: der Turn liest sessionId frisch, nicht beim
 * Bau eingefroren). Kein TestBed nötig — reiner Fake-Host.
 */

interface Rec { post: any[][]; transcribe: any[][]; synthesize: any[][]; [k: string]: any[][]; }

function fakeHost(): {
  host: ShellHost; calls: Rec; setSid: (s: string) => void; setSprache: (s: string) => void;
} {
  const calls: Rec = { post: [], transcribe: [], synthesize: [] };
  const rec = (k: string) => (...args: any[]) => { (calls[k] ??= []).push(args); return undefined; };
  const api = {
    post: (...a: any[]) => { calls.post.push(a); return Promise.resolve({ content: 'ok' }); },
    transcribe: (...a: any[]) => { calls.transcribe.push(a); return Promise.resolve('txt'); },
    synthesize: (...a: any[]) => { calls.synthesize.push(a); return Promise.resolve(new Blob()); },
  } as unknown as ChatApiClient;
  let sid = 'sess-1';
  let sprache = 'de';
  const msgs: ChatMessage[] = [{ id: 'm', sender: 'bot', content: 'x', timestamp: new Date() }];
  const host: ShellHost = {
    api: () => api,
    sessionId: () => sid,
    pageContext: () => ({ node_id: 'n1' }),
    isLoading: () => false,
    setLoading: rec('setLoading'),
    messages: () => msgs,
    updateMessages: rec('updateMessages'),
    addUserMessage: rec('addUserMessage'),
    addBotMessage: (...a: any[]) => { calls['addBotMessage'] = (calls['addBotMessage'] || []); calls['addBotMessage'].push(a); return 'bot-id'; },
    removeMessage: rec('removeMessage'),
    setScrollTarget: rec('setScrollTarget'),
    setLatestDebug: rec('setLatestDebug'),
    dispatchPageAction: rec('dispatchPageAction'),
    messagesContainer: () => undefined,
    emitGuideSuggestion: () => 'true',
    emitRoutingDebug: () => false,
    emitGuideSuggestionOutput: rec('emitGuideSuggestionOutput'),
    emitRoutingDebugOutput: rec('emitRoutingDebugOutput'),
    runInZone: (fn: any) => fn(),
    onTranscript: rec('onTranscript'),
    t: (key: string) => `${sprache}:${key}`,
  };
  return {
    host, calls,
    setSid: (s) => { sid = s; },
    setSprache: (s) => { sprache = s; },
  };
}

describe('buildControllerContexts', () => {
  it('tour.sendMessage bindet LIVE sessionId+api (post), tour.pageContext liest host', () => {
    const { host, calls, setSid } = fakeHost();
    const { tour } = buildControllerContexts(host);

    tour.sendMessage('hallo', { tour_action: 'start' });
    expect(calls.post[0]).toEqual(['sess-1', 'hallo', { tour_action: 'start' }]);

    // deferred: nach sessionId-Wechsel nutzt derselbe Context die neue ID.
    setSid('sess-2');
    tour.sendMessage('zwei', undefined);
    expect(calls.post[1]).toEqual(['sess-2', 'zwei', undefined]);

    expect(tour.pageContext()).toEqual({ node_id: 'n1' });
  });

  it('tour Reducer/Setter delegieren an host', () => {
    const { host, calls } = fakeHost();
    const { tour } = buildControllerContexts(host);
    tour.addUserMessage('u');
    tour.setLoading(true);
    tour.setScrollTarget('sid');
    tour.removeMessage('r');
    expect(calls['addUserMessage'][0]).toEqual(['u']);
    expect(calls['setLoading'][0]).toEqual([true]);
    expect(calls['setScrollTarget'][0]).toEqual(['sid']);
    expect(calls['removeMessage'][0]).toEqual(['r']);
  });

  it('contextGreeting nutzt dieselbe sendMessage-Seam (post) + keine addUserMessage', () => {
    const { host, calls } = fakeHost();
    const { contextGreeting } = buildControllerContexts(host);
    contextGreeting.sendMessage('[context-open]', { page_event: 'context_open' });
    expect(calls.post[0]).toEqual(['sess-1', '[context-open]', { page_event: 'context_open' }]);
    expect((contextGreeting as any).addUserMessage).toBeUndefined();
  });

  it('collectionActions.sendMessage reicht action+actionParams durch (5-arg post)', () => {
    const { host, calls } = fakeHost();
    const { collectionActions } = buildControllerContexts(host);
    collectionActions.sendMessage('Inhalte', undefined, 'browse_collection', { collection_id: 'c1' });
    expect(calls.post[0]).toEqual(['sess-1', 'Inhalte', undefined, 'browse_collection', { collection_id: 'c1' }]);
  });

  it('collectionActions.messages/updateMessages/messagesContainer/dispatchPageAction delegieren', () => {
    const { host, calls } = fakeHost();
    const { collectionActions } = buildControllerContexts(host);
    expect(collectionActions.messages()[0].id).toBe('m');
    const updater = (m: ChatMessage[]) => m;
    collectionActions.updateMessages(updater);
    expect(calls['updateMessages'][0]).toEqual([updater]);
    expect(collectionActions.messagesContainer()).toBeUndefined();
    collectionActions.dispatchPageAction({ action: 'canvas', payload: 1 });
    expect(calls['dispatchPageAction'][0]).toEqual([{ action: 'canvas', payload: 1 }]);
  });

  it('speech.transcribe/synthesize gehen an host.api(); addBotMessage(single) + runInZone delegieren', () => {
    const { host, calls } = fakeHost();
    const { speech } = buildControllerContexts(host);
    const blob = new Blob(['a']);
    speech.transcribe(blob);
    expect(calls.transcribe[0]).toEqual([blob]);
    const sig = new AbortController().signal;
    speech.synthesize('text', sig);
    expect(calls.synthesize[0]).toEqual(['text', sig]);
    speech.addBotMessage('err');
    expect(calls['addBotMessage'][0]).toEqual(['err']);
    expect(speech.runInZone(() => 42)).toBe(42);
  });

  it('hostEvents liest LIVE emit-Flags + emittet über host-Outputs', () => {
    const { host, calls } = fakeHost();
    const { hostEvents } = buildControllerContexts(host);
    expect(hostEvents.emitGuideSuggestion()).toBe('true');
    expect(hostEvents.emitRoutingDebug()).toBe(false);
    const gp = { url: 'u', title: 't', node_id: '', node_type: '', query: 'q', alternatives: [] };
    hostEvents.emitGuideSuggestionOutput(gp);
    expect(calls['emitGuideSuggestionOutput'][0]).toEqual([gp]);
  });

  it('tour/speech/collectionActions bekommen `t` LIVE vom Host (C1-b4)', () => {
    const { host, setSprache } = fakeHost();
    const { tour, speech, collectionActions } = buildControllerContexts(host);
    expect(tour.t('error.tourStart')).toBe('de:error.tourStart');

    // Deferred wie `sessionId`: nach einem Sprachwechsel liefern DIESELBEN
    // Contexts den neuen Text — sie halten keine eingefrorene Funktion.
    setSprache('en');
    expect(tour.t('error.tourStart')).toBe('en:error.tourStart');
    expect(speech.t('error.transcription')).toBe('en:error.transcription');
    expect(collectionActions.t('error.browseCollection')).toBe('en:error.browseCollection');
  });
});
