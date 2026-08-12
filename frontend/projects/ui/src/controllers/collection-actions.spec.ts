import { afterEach, describe, expect, it, vi } from 'vitest';

import { WloCard } from '../cards/card-types';
import { ChatMessage, ChatResponse, DebugInfo, PaginationInfo } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import {
  CollectionActionsContext,
  browseCollection,
  generateLearningPath,
  loadMore,
  showContentText,
  showMoreCards,
} from './collection-actions';

/**
 * Charakterisierung der Cards-/Pagination-Aktionen — Verbatim-Port aus ALT
 * (dort nur integrativ über chat.component.spec gedeckt). Gepinnt: Loading-
 * Guard + Loading-Bubble-Lebenszyklus, sendMessage-Arg-Verdrahtung
 * (message/env/action/actionParams), Render-Arg-Reihenfolge (queryMetas=undefined
 * an Position 7), Fehler-Bubble-Texte, showMoreCards +5-Fenster + Scroll-Ziel,
 * loadMore-Guards + Card-Merge.
 */
interface Calls {
  bot: Array<{ id: string; content: string; loading?: boolean; rest: unknown[] }>;
  removed: string[];
  scroll: string[];
  debug: unknown[];
  loading: boolean[];
  page: unknown[];
  sent: Array<{ message: string; env: any; action?: string; actionParams?: any }>;
}

interface CtxOpts {
  respond?: (message: string, env: any, action?: string, actionParams?: any) => ChatResponse | Promise<ChatResponse>;
  isLoading?: () => boolean;
  initialMessages?: ChatMessage[];
  messagesContainer?: () => HTMLElement | undefined;
  t?: CollectionActionsContext['t'];
}

function makeCtx(opts: CtxOpts = {}): { ctx: CollectionActionsContext; calls: Calls; getMessages: () => ChatMessage[] } {
  const calls: Calls = { bot: [], removed: [], scroll: [], debug: [], loading: [], page: [], sent: [] };
  let loading = false;
  let n = 0;
  let messages: ChatMessage[] = opts.initialMessages ?? [];
  const ctx: CollectionActionsContext = {
    sendMessage: async (message, env, action, actionParams) => {
      calls.sent.push({ message, env, action, actionParams });
      return opts.respond ? opts.respond(message, env, action, actionParams) : makeResp();
    },
    isLoading: opts.isLoading ?? (() => loading),
    setLoading: (v) => {
      loading = v;
      calls.loading.push(v);
    },
    messages: () => messages,
    updateMessages: (updater) => {
      messages = updater(messages);
    },
    addBotMessage: (content, isLoading, ...rest) => {
      const id = 'b' + ++n;
      calls.bot.push({ id, content, loading: isLoading, rest });
      return id;
    },
    removeMessage: (id) => calls.removed.push(id),
    setScrollTarget: (id) => calls.scroll.push(id),
    setLatestDebug: (d) => calls.debug.push(d),
    dispatchPageAction: (pa) => calls.page.push(pa),
    messagesContainer: opts.messagesContainer ?? (() => undefined),
    t: opts.t ?? createTranslator(DE, DE),
  };
  return { ctx, calls, getMessages: () => messages };
}

function makeResp(fields: Partial<ChatResponse> = {}): ChatResponse {
  return {
    session_id: 's', content: 'geladen', cards: [], follow_up: '', quick_replies: [],
    debug: { pattern: 'M06' } as DebugInfo, page_action: null, pagination: null, ...fields,
  } as ChatResponse;
}

function makeMsg(fields: Partial<ChatMessage> = {}): ChatMessage {
  return { id: 'm1', sender: 'bot', content: 'x', timestamp: new Date(), ...fields };
}

describe('browseCollection', () => {
  it('Loading-Bubble → sendMessage(browse_collection) → Render (Arg-Reihenfolge) → Scroll/Debug/PageAction/Loading', async () => {
    const pagination: PaginationInfo = {
      total_count: 20, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
    };
    const { ctx, calls } = makeCtx({
      respond: () => makeResp({
        content: 'Inhalte da', cards: [{ id: 'k' }] as unknown as WloCard[], quick_replies: ['q'],
        pagination, web_links: [{ title: 't', url: 'u' }], inline_documents: [{ kind: 'lernpfad', title: 'L', content: 'c' }],
        display_rules: { fontSize: 90 }, page_action: { action: 'open', payload: 1 },
      }),
    });

    await browseCollection('c1', 'Mathe', ctx);

    // Loading-Bubble zuerst (leer, loading=true), danach entfernt
    expect(calls.bot[0]).toMatchObject({ content: '', loading: true });
    expect(calls.removed).toEqual([calls.bot[0].id]);
    // sendMessage-Argumente
    expect(calls.sent).toEqual([{
      message: 'Inhalte der Sammlung "Mathe"', env: undefined, action: 'browse_collection',
      actionParams: { collection_id: 'c1', title: 'Mathe' },
    }]);
    // Render mit exakter Arg-Reihenfolge (queryMetas=undefined an Position 7)
    const real = calls.bot.find((b) => b.content === 'Inhalte da')!;
    expect(real.loading).toBe(false);
    expect(real.rest).toEqual([
      [{ id: 'k' }], ['q'], { pattern: 'M06' }, pagination, undefined,
      [{ title: 't', url: 'u' }], [{ kind: 'lernpfad', title: 'L', content: 'c' }], { fontSize: 90 },
    ]);
    expect(calls.scroll).toEqual([real.id]);
    expect(calls.debug).toEqual([{ pattern: 'M06' }]);
    expect(calls.page).toEqual([{ action: 'open', payload: 1 }]);
    expect(calls.loading).toEqual([true, false]);
  });

  it('isLoading → No-Op (kein sendMessage, keine Bubble)', async () => {
    const { ctx, calls } = makeCtx({ isLoading: () => true });
    await browseCollection('c1', 'Mathe', ctx);
    expect(calls.sent).toEqual([]);
    expect(calls.bot).toEqual([]);
  });

  it('Fehler → Loading-Bubble weg + Fehler-Bubble + Scroll + Loading false, kein PageAction', async () => {
    const { ctx, calls } = makeCtx({ respond: () => { throw new Error('x'); } });
    await browseCollection('c1', 'Mathe', ctx);
    expect(calls.removed).toEqual([calls.bot[0].id]);
    const err = calls.bot.find((b) => b.content.includes('Inhalte von "Mathe" leider nicht laden'))!;
    expect(err).toBeTruthy();
    expect(calls.scroll).toEqual([err.id]);
    expect(calls.page).toEqual([]);
    expect(calls.loading).toEqual([true, false]);
  });
});

describe('Fehler-Bubbles kommen aus dem Übersetzer (C1-b4)', () => {
  const EN = {
    'error.browseCollection': 'Could not load the contents of "{title}".',
    'error.contentText': 'Could not load the content of "{title}".',
    'error.learningPath': 'Could not build a learning path for "{title}".',
  };

  it('alle drei Aktionen übersetzen ihre Fehlermeldung', async () => {
    const boom = () => { throw new Error('x'); };
    for (const [lauf, erwartet] of [
      [browseCollection, 'Could not load the contents of "Mathe".'],
      [showContentText, 'Could not load the content of "Mathe".'],
      [generateLearningPath, 'Could not build a learning path for "Mathe".'],
    ] as const) {
      const { ctx, calls } = makeCtx({ respond: boom, t: createTranslator(EN, DE) });
      await lauf('c1', 'Mathe', ctx);
      expect(calls.bot.some((b) => b.content === erwartet)).toBe(true);
    }
  });

  it('der GESENDETE Text bleibt deutsch — er ist die Anweisung ans Backend, kein Oberflächentext', async () => {
    const { ctx, calls } = makeCtx({ t: createTranslator(EN, DE) });
    await browseCollection('c1', 'Mathe', ctx);
    expect(calls.sent[0].message).toBe('Inhalte der Sammlung "Mathe"');
  });
});

describe('showContentText (M17)', () => {
  it('Loading-Bubble → sendMessage(show_content_text) → Dokument-Box im Bot-Turn', async () => {
    const doc = { kind: 'volltext', title: 'Arbeitsblatt', content: '# Aufgabe 1' };
    const { ctx, calls } = makeCtx({
      respond: () => makeResp({
        content: 'Hier ist der Inhalt.', quick_replies: ['Daran weiterarbeiten'],
        inline_documents: [doc],
      }),
    });

    await showContentText('n7', 'Arbeitsblatt', ctx);

    expect(calls.bot[0]).toMatchObject({ content: '', loading: true });
    expect(calls.removed).toEqual([calls.bot[0].id]);
    // Die Aktion trägt die node_id — sie ist das, was der Server braucht.
    expect(calls.sent).toEqual([{
      message: 'Inhalt von "Arbeitsblatt"', env: undefined, action: 'show_content_text',
      actionParams: { node_id: 'n7', title: 'Arbeitsblatt' },
    }]);
    // Die Volltext-Box muss an derselben Stelle der Render-Argumente stehen
    // wie bei den Geschwister-Aktionen (`inline_documents` = rest[6]) — sonst
    // landet der Text nicht in der Dokument-Box, sondern nirgends.
    const real = calls.bot.find((b) => b.content === 'Hier ist der Inhalt.')!;
    expect(real.rest[6]).toEqual([doc]);
    expect(calls.scroll).toEqual([real.id]);
    expect(calls.loading).toEqual([true, false]);
  });

  it('isLoading → No-Op (kein sendMessage, keine Bubble)', async () => {
    const { ctx, calls } = makeCtx({ isLoading: () => true });
    await showContentText('n7', 'Arbeitsblatt', ctx);
    expect(calls.sent).toEqual([]);
    expect(calls.bot).toEqual([]);
  });

  it('Fehler → Loading-Bubble weg + Fehler-Bubble + Loading false', async () => {
    const { ctx, calls } = makeCtx({ respond: () => { throw new Error('x'); } });
    await showContentText('n7', 'Arbeitsblatt', ctx);
    expect(calls.removed).toEqual([calls.bot[0].id]);
    const err = calls.bot.find((b) => b.content.includes('Arbeitsblatt'))!;
    expect(err).toBeTruthy();
    expect(calls.scroll).toEqual([err.id]);
    expect(calls.loading).toEqual([true, false]);
  });
});

describe('generateLearningPath', () => {
  it('sendMessage(generate_learning_path) mit Lernpfad-Message + Render', async () => {
    const { ctx, calls } = makeCtx({ respond: () => makeResp({ content: 'Dein Lernpfad' }) });
    await generateLearningPath('c1', 'Mathe', ctx);
    expect(calls.sent[0]).toEqual({
      message: 'Lernpfad für "Mathe"', env: undefined, action: 'generate_learning_path',
      actionParams: { collection_id: 'c1', title: 'Mathe' },
    });
    expect(calls.bot.some((b) => b.content === 'Dein Lernpfad')).toBe(true);
    expect(calls.loading).toEqual([true, false]);
  });

  it('Fehler → Lernpfad-Fehler-Bubble', async () => {
    const { ctx, calls } = makeCtx({ respond: () => { throw new Error('x'); } });
    await generateLearningPath('c1', 'Mathe', ctx);
    expect(calls.bot.some((b) => b.content.includes('Lernpfad für "Mathe" konnte ich leider nicht erstellen'))).toBe(true);
    expect(calls.loading).toEqual([true, false]);
  });
});

describe('showMoreCards', () => {
  afterEach(() => vi.useRealTimers());

  it('Default-Fenster 5 → 10, nur die passende Message mit Cards; andere unberührt', () => {
    vi.useFakeTimers();
    const { ctx, getMessages } = makeCtx({
      initialMessages: [
        makeMsg({ id: 'm1', cards: [{}, {}, {}, {}, {}, {}] as unknown as WloCard[] }),
        makeMsg({ id: 'm2', cards: [{}] as unknown as WloCard[], visibleCardCount: 3 }),
      ],
    });
    showMoreCards('m1', ctx);
    const msgs = getMessages();
    expect(msgs.find((m) => m.id === 'm1')!.visibleCardCount).toBe(10);
    expect(msgs.find((m) => m.id === 'm2')!.visibleCardCount).toBe(3); // unberührt
  });

  it('bestehendes visibleCardCount respektiert (+5)', () => {
    vi.useFakeTimers();
    const { ctx, getMessages } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', cards: [{}] as unknown as WloCard[], visibleCardCount: 8 })],
    });
    showMoreCards('m1', ctx);
    expect(getMessages()[0].visibleCardCount).toBe(13);
  });

  it('Message ohne Cards bleibt unverändert', () => {
    vi.useFakeTimers();
    const { ctx, getMessages } = makeCtx({ initialMessages: [makeMsg({ id: 'm1' })] });
    showMoreCards('m1', ctx);
    expect(getMessages()[0].visibleCardCount).toBeUndefined();
  });

  it('scrollt die erste neu enthüllte Card (Index = previousCount) mittig ein', () => {
    vi.useFakeTimers();
    const target = { scrollIntoView: vi.fn() };
    const cards = [{}, {}, {}, {}, {}, target];
    const msgEl = { querySelectorAll: () => cards };
    const container = { querySelector: () => msgEl } as unknown as HTMLElement;
    const { ctx } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', cards: [{}] as unknown as WloCard[] })],
      messagesContainer: () => container,
    });
    showMoreCards('m1', ctx);
    vi.runAllTimers();
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });
  });

  it('kein Container → kein Wurf (Click-Handler bleibt heil)', () => {
    vi.useFakeTimers();
    const { ctx } = makeCtx({ initialMessages: [makeMsg({ id: 'm1', cards: [{}] as unknown as WloCard[] })] });
    showMoreCards('m1', ctx);
    expect(() => vi.runAllTimers()).not.toThrow();
  });
});

describe('loadMore', () => {
  const basePagination: PaginationInfo = {
    total_count: 12, skip_count: 5, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
  };

  it('ohne pagination → No-Op', async () => {
    const { ctx, calls } = makeCtx({ initialMessages: [makeMsg({ id: 'm1' })] });
    await loadMore('m1', ctx);
    expect(calls.sent).toEqual([]);
  });

  it('has_more=false → No-Op', async () => {
    const { ctx, calls } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', pagination: { ...basePagination, has_more: false } })],
    });
    await loadMore('m1', ctx);
    expect(calls.sent).toEqual([]);
  });

  it('isLoading → No-Op', async () => {
    const { ctx, calls } = makeCtx({
      isLoading: () => true,
      initialMessages: [makeMsg({ id: 'm1', pagination: basePagination })],
    });
    await loadMore('m1', ctx);
    expect(calls.sent).toEqual([]);
  });

  it('newSkip = skip+page_size, browse_collection-Args, Card-Merge + visibleCardCount + pagination + content', async () => {
    const newPagination: PaginationInfo = { ...basePagination, skip_count: 10, has_more: false };
    const { ctx, calls, getMessages } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', content: 'alt', cards: [{ id: 'a' }] as unknown as WloCard[], pagination: basePagination })],
      respond: () => makeResp({ content: 'neu', cards: [{ id: 'b' }, { id: 'c' }] as unknown as WloCard[], pagination: newPagination }),
    });

    await loadMore('m1', ctx);

    expect(calls.sent).toEqual([{
      message: 'Weitere Inhalte von "Mathe"', env: undefined, action: 'browse_collection',
      actionParams: { collection_id: 'c1', title: 'Mathe', skip_count: 10 },
    }]);
    const msg = getMessages()[0];
    expect(msg.cards).toEqual([{ id: 'a' }, { id: 'b' }, { id: 'c' }]);
    expect(msg.visibleCardCount).toBe(3);
    expect(msg.pagination).toEqual(newPagination);
    expect(msg.content).toBe('neu');
    expect(calls.loading).toEqual([true, false]);
  });

  it('Fehler → console.error, Loading false, Message unverändert', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { ctx, calls, getMessages } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', cards: [{ id: 'a' }] as unknown as WloCard[], pagination: basePagination })],
      respond: () => { throw new Error('boom'); },
    });
    await loadMore('m1', ctx);
    expect(spy).toHaveBeenCalled();
    expect(calls.loading).toEqual([true, false]);
    expect(getMessages()[0].cards).toEqual([{ id: 'a' }]); // unverändert
    spy.mockRestore();
  });
});
