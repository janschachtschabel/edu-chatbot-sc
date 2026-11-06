import { afterEach, describe, expect, it, vi } from 'vitest';

import { WloCard } from '../cards/card-types';
import { ChatMessage, ChatResponse, DebugInfo, PaginationInfo } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import {
  ablageSchritt,
  auftragAbholen,
  auftragStand,
  CollectionActionsContext,
  browseCollection,
  generateLearningPath,
  loadMore,
  showContentText,
  showMoreCards,
  themenbaumZweig,
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
  sent: Array<{ message: string; env: any; action?: string; actionParams?: any; opts?: any }>;
}

interface CtxOpts {
  respond?: (message: string, env: any, action?: string, actionParams?: any) => ChatResponse | Promise<ChatResponse>;
  isLoading?: () => boolean;
  sessionId?: () => string;
  initialMessages?: ChatMessage[];
  messagesContainer?: () => HTMLElement | undefined;
  t?: CollectionActionsContext['t'];
  ladeZweig?: CollectionActionsContext['ladeZweig'];
  ladeDokument?: CollectionActionsContext['ladeDokument'];
  ladeAblage?: CollectionActionsContext['ladeAblage'];
  ladeAuftragStand?: CollectionActionsContext['ladeAuftragStand'];
}

function makeCtx(opts: CtxOpts = {}): { ctx: CollectionActionsContext; calls: Calls; getMessages: () => ChatMessage[] } {
  const calls: Calls = { bot: [], removed: [], scroll: [], debug: [], loading: [], page: [], sent: [] };
  let loading = false;
  let n = 0;
  let messages: ChatMessage[] = opts.initialMessages ?? [];
  const ctx: CollectionActionsContext = {
    sendMessage: async (message, env, action, actionParams, weitere) => {
      calls.sent.push({ message, env, action, actionParams, ...(weitere ? { opts: weitere } : {}) });
      return opts.respond ? opts.respond(message, env, action, actionParams) : makeResp();
    },
    sessionId: opts.sessionId ?? (() => 'bb-1'),
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
    ladeZweig: opts.ladeZweig ?? (async () => ({ knoten: [] })),
    ladeDokument: opts.ladeDokument ?? (async () => ({ upload_id: 'u-1' })),
    ladeAblage: opts.ladeAblage ?? (async () => ({ stand: 'stored' })),
    ladeAuftragStand: opts.ladeAuftragStand ?? (async () => ({ stand: 'laeuft' })),
  };
  return { ctx, calls, getMessages: () => messages };
}

function makeResp(fields: Partial<ChatResponse> = {}): ChatResponse {
  return {
    session_id: 's', content: 'geladen', cards: [], follow_up: '', quick_replies: [],
    debug: { pattern: 'M06', persona: 'P-LK' } as DebugInfo, ui: { pattern: 'M06' },
    page_action: null, pagination: null, ...fields,
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
        pagination, web_links: [{ title: 't', url: 'u' }],
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
      [{ title: 't', url: 'u' }], { fontSize: 90 },
    ]);
    expect(calls.scroll).toEqual([real.id]);
    expect(calls.debug).toEqual([{ pattern: 'M06', persona: 'P-LK' }]);
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

describe('themenbaumZweig (U1-h, Unterthemen im selben Baum)', () => {
  it('lädt den Zweig ohne Zug: keine Blase, kein Laden-Zustand, die Daten gehen zurück', async () => {
    const gefragt: string[] = [];
    const { ctx, calls } = makeCtx({
      ladeZweig: async (nodeId) => { gefragt.push(nodeId); return { knoten: [{ id: 'cccc-3333', titel: 'Gleichungen' }] }; },
    });

    await expect(themenbaumZweig('bbbb-2222', ctx)).resolves.toEqual({ knoten: [{ id: 'cccc-3333', titel: 'Gleichungen' }] });

    expect(gefragt).toEqual(['bbbb-2222']);
    expect(calls.sent).toEqual([]);
    expect(calls.bot).toEqual([]);
    expect(calls.loading).toEqual([]);
  });

  it('geht auch, während ein Zug läuft (kein Zug, keine Sperre)', async () => {
    const { ctx } = makeCtx({ isLoading: () => true });
    await expect(themenbaumZweig('bbbb-2222', ctx)).resolves.toEqual({ knoten: [] });
  });

  it('wechselt die Sitzung während des Ladens, wird abgelehnt (Sitzungs-Wache)', async () => {
    let sitzung = 'bb-1';
    const { ctx } = makeCtx({
      sessionId: () => sitzung,
      ladeZweig: async () => { sitzung = 'bb-2'; return { knoten: [] }; },
    });
    await expect(themenbaumZweig('bbbb-2222', ctx)).rejects.toThrow(/Sitzung/);
  });

  it('ein Fehler des Abrufs geht samt Status an das Modul', async () => {
    const fehler = Object.assign(new Error('Chat error: 502'), { status: 502 });
    const { ctx, calls } = makeCtx({ ladeZweig: async () => { throw fehler; } });
    await expect(themenbaumZweig('bbbb-2222', ctx)).rejects.toBe(fehler);
    expect(calls.bot).toEqual([]);
  });
});

describe('ablageSchritt (U3-3b, Ablage im persönlichen Bereich)', () => {
  const SCHRITT = { schritt: 'abschluss', batchToken: 'tok-1234567890' } as const;

  it('geht ohne Zug an den Client: keine Blase, kein Laden-Zustand', async () => {
    const gefragt: unknown[] = [];
    const { ctx, calls } = makeCtx({ ladeAblage: async (blockId, schritt) => { gefragt.push([blockId, schritt]); return { stand: 'stored' }; } });
    await expect(ablageSchritt('b0000001', SCHRITT, ctx)).resolves.toEqual({ stand: 'stored' });
    expect(gefragt).toEqual([['b0000001', SCHRITT]]);
    expect(calls.sent).toEqual([]);
    expect(calls.bot).toEqual([]);
    expect(calls.loading).toEqual([]);
  });

  it('wechselt die Sitzung währenddessen, wird abgelehnt (Sitzungs-Wache)', async () => {
    let sitzung = 'bb-1';
    const { ctx } = makeCtx({ sessionId: () => sitzung, ladeAblage: async () => { sitzung = 'bb-2'; return {}; } });
    await expect(ablageSchritt('b0000001', SCHRITT, ctx)).rejects.toMatchObject({ code: 'sitzung' });
  });

  it('ein Fehler geht samt Code an das Modul; geloggt ohne Dateinamen', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const fehler = Object.assign(new Error('Transport: 403 nur_angemeldet'), { status: 403, code: 'nur_angemeldet' });
    const { ctx } = makeCtx({ ladeAblage: async () => { throw fehler; } });
    const datei = new File(['x'], 'Zeugnis Mustermann.pdf');
    await expect(ablageSchritt('b0000001', { schritt: 'datei', batchToken: 'tok-1234567890', index: 0, datei }, ctx))
      .rejects.toBe(fehler);
    expect(JSON.stringify(warn.mock.calls)).not.toContain('Mustermann');
    warn.mockRestore();
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
    // Seit U1-b2 reist die Volltext-Box als Inhaltsrahmen-Block an `ui`.
    const ui = {
      ui_bloecke: [{
        block_id: 'b0000001', modul: 'ui_inhaltsrahmen', version: 1, art: 'anzeigen' as const,
        daten: { titel: 'Arbeitsblatt', art: 'volltext', markdown: '# Aufgabe 1' },
        text: '# Aufgabe 1', status: 'nur_anzeige' as const,
      }],
    };
    const { ctx, calls } = makeCtx({
      respond: () => makeResp({
        content: 'Hier ist der Inhalt.', quick_replies: ['Daran weiterarbeiten'], ui,
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
    // Die Volltext-Box reist mit `ui` (rest[2]) — sonst landete der Text nirgends.
    const real = calls.bot.find((b) => b.content === 'Hier ist der Inhalt.')!;
    expect(real.rest[2]).toEqual(ui);
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

// Paket 3, T6 (Review 2026-10-03): eine Karten-Aktion gehört der Sitzung, in der
// sie begann. Ein Lernpfad braucht 10–20 s; kam er nach einem Neustart an,
// landete er im frischen Verlauf und gab die Eingabe mitten im neuen Zug frei.
describe('Karten-Aktionen nach einem Neustart', () => {
  const aktionen: Array<[string, (ctx: CollectionActionsContext) => Promise<void>]> = [
    ['browseCollection', (ctx) => browseCollection('c1', 'Mathe', ctx)],
    ['showContentText', (ctx) => showContentText('n1', 'Mathe', ctx)],
    ['generateLearningPath', (ctx) => generateLearningPath('c1', 'Mathe', ctx)],
  ];

  it.each(aktionen)('%s: kein Rendern, keine Freigabe', async (_name, aktion) => {
    let sitzung = 'bb-1';
    const { ctx, calls } = makeCtx({
      sessionId: () => sitzung,
      respond: () => { sitzung = 'bb-2'; return makeResp({ content: 'Spät' }); },
    });
    await aktion(ctx);
    expect(calls.bot.map((b) => b.content)).toEqual(['']);   // nur die Ladeblase
    expect(calls.loading).toEqual([true]);
  });

  it.each(aktionen)('%s: auch der Fehlerweg bleibt still', async (_name, aktion) => {
    let sitzung = 'bb-1';
    const { ctx, calls } = makeCtx({
      sessionId: () => sitzung,
      respond: () => { sitzung = 'bb-2'; throw new Error('weg'); },
    });
    await aktion(ctx);
    expect(calls.bot.map((b) => b.content)).toEqual(['']);
    expect(calls.loading).toEqual([true]);
  });

  it('loadMore: kein Zusammenführen, keine Freigabe', async () => {
    let sitzung = 'bb-1';
    const pagination: PaginationInfo = {
      total_count: 12, skip_count: 5, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
    };
    const { ctx, calls, getMessages } = makeCtx({
      sessionId: () => sitzung,
      initialMessages: [makeMsg({ id: 'm1', cards: [{ id: 'a' }] as unknown as WloCard[], pagination })],
      respond: () => {
        sitzung = 'bb-2';
        return makeResp({ cards: [{ id: 'b' }] as unknown as WloCard[] });
      },
    });
    await loadMore('m1', ctx);
    expect(calls.loading).toEqual([true]);
    expect(getMessages()[0].cards).toEqual([{ id: 'a' }]);
  });
});

// ── Paket 18E: Spur in der Konsole — die Fehlerart, nie der Text ─────────────
const MARKE = 'KANARIE7Q';
const ausgabe = (spy: { mock: { calls: unknown[][] } }): string =>
  spy.mock.calls.flat().map(String).join(' ');

describe('Paket 18E: gescheiterte Sammlungs-Aktionen hinterlassen eine Spur', () => {
  afterEach(() => vi.restoreAllMocks());

  it('jede Aktion warnt mit der Fehlerart, nie mit dem Text', async () => {
    for (const lauf of [browseCollection, showContentText, generateLearningPath]) {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const { ctx } = makeCtx({ respond: () => { throw new Error(MARKE); } });
      await lauf('c1', 'Mathe', ctx);
      expect(warn).toHaveBeenCalledTimes(1);
      expect(ausgabe(warn)).toContain('Error');
      expect(ausgabe(warn)).not.toContain(MARKE);
      warn.mockRestore();
    }
  });
});

describe('Paket 18F: zu viele Anfragen bei Sammlungs-Aktionen', () => {
  afterEach(() => vi.restoreAllMocks());

  it('429 → der Drossel-Satz statt der Aktions-Fehlermeldung', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const t = createTranslator(DE, DE);
    for (const lauf of [browseCollection, showContentText, generateLearningPath]) {
      const { ctx, calls } = makeCtx({
        respond: () => { throw Object.assign(new Error('Chat error: 429'), { status: 429, retryAfterMs: 12_000 }); },
      });
      await lauf('c1', 'Mathe', ctx);
      expect(calls.bot.at(-1)?.content).toBe(t('error.rateLimitedWait', { sekunden: 12 }));
    }
  });
});

// ── Paket 19, Audit 2026-10-31 N-34 + M-15 ──────────────────────────────────
describe('Paket 19: „Weitere laden“ und Fristen bei Karten-Aktionen', () => {
  afterEach(() => vi.restoreAllMocks());
  const pagination: PaginationInfo = {
    total_count: 12, skip_count: 5, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
  };
  const t = createTranslator(DE, DE);

  // N-34: „Weitere laden“ scheiterte still — nur eine Konsolenzeile.
  it('loadMore-Fehler → Fehlerblase mit dem Sammlungstitel (N-34)', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { ctx, calls } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', pagination })],
      respond: () => { throw new Error('weg'); },
    });
    await loadMore('m1', ctx);
    expect(calls.bot.map((b) => b.content)).toEqual([t('error.browseCollection', { title: 'Mathe' })]);
    expect(calls.scroll).toEqual([calls.bot[0].id]);
    expect(calls.loading).toEqual([true, false]);
  });

  it('loadMore bei 429 → der Drossel-Satz (N-34)', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { ctx, calls } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', pagination })],
      respond: () => { throw Object.assign(new Error('Chat error: 429'), { status: 429, retryAfterMs: 3_000 }); },
    });
    await loadMore('m1', ctx);
    expect(calls.bot.at(-1)?.content).toBe(t('error.rateLimitedWait', { sekunden: 3 }));
  });

  // M-15: läuft der POST in seine Frist, sagt die Blase „dauert ungewöhnlich lange“.
  it('Frist abgelaufen → „veraltet“-Satz bei allen Karten-Aktionen (M-15)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const frist = () => { throw Object.assign(new Error('frist'), { name: 'StreamStaleError' }); };
    for (const lauf of [browseCollection, showContentText, generateLearningPath]) {
      const { ctx, calls } = makeCtx({ respond: frist });
      await lauf('c1', 'Mathe', ctx);
      expect(calls.bot.at(-1)?.content).toBe(t('error.stale'));
      expect(calls.loading.at(-1)).toBe(false);
    }
    const { ctx, calls } = makeCtx({ initialMessages: [makeMsg({ id: 'm1', pagination })], respond: frist });
    await loadMore('m1', ctx);
    expect(calls.bot.at(-1)?.content).toBe(t('error.stale'));
  });
});

describe('loadMore mit Trefferliste (U1-c2b)', () => {
  it('schreibt die neuen Karten und die Seitenangabe auch in den Block', async () => {
    const p: PaginationInfo = {
      total_count: 12, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
    };
    const alt = [{ node_id: 'a', title: 'A' }] as unknown as WloCard[];
    const neu = [{ node_id: 'b', title: 'B' }] as unknown as WloCard[];
    const block = {
      block_id: 'b0000007', modul: 'ui_trefferliste', version: 1, art: 'anzeigen' as const,
      daten: { karten: alt, such_metas: [], seiten: p, typ_fokus: '' }, text: '', status: 'nur_anzeige' as const,
    };
    const neuSeiten: PaginationInfo = { ...p, skip_count: 5, has_more: false };
    const { ctx, getMessages } = makeCtx({
      initialMessages: [makeMsg({ id: 'm1', cards: alt, pagination: p, ui: { ui_bloecke: [block] } })],
      respond: () => makeResp({ content: 'mehr', cards: neu, pagination: neuSeiten }),
    });
    await loadMore('m1', ctx);
    const b = getMessages()[0].ui!.ui_bloecke![0];
    expect((b.daten['karten'] as WloCard[]).map((k) => k.node_id)).toEqual(['a', 'b']);
    expect(b.daten['seiten']).toEqual(neuSeiten);
  });

  it('andere Blöcke und Nachrichten ohne ui bleiben unberührt', async () => {
    const p: PaginationInfo = {
      total_count: 12, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
    };
    const linkbox = {
      block_id: 'b0000010', modul: 'ui_linkbox', version: 1, art: 'anzeigen' as const,
      daten: { links: [] }, text: '', status: 'nur_anzeige' as const,
    };
    const { ctx, getMessages } = makeCtx({
      initialMessages: [
        makeMsg({ id: 'm1', cards: [], pagination: p, ui: { ui_bloecke: [linkbox] } }),
        makeMsg({ id: 'm2', cards: [], pagination: p }),
      ],
      respond: () => makeResp({ content: 'mehr', cards: [], pagination: { ...p, has_more: false } }),
    });
    await loadMore('m1', ctx);
    await loadMore('m2', ctx);
    expect(getMessages()[0].ui!.ui_bloecke![0]).toEqual(linkbox);
    expect(getMessages()[1].ui).toBeUndefined();
  });
});

describe('auftragStand / auftragAbholen (K1b, Fortschritt eines Ablauf-Auftrags)', () => {
  it('der Stand geht ohne Zug an den Client', async () => {
    const gefragt: unknown[] = [];
    const { ctx, calls } = makeCtx({ ladeAuftragStand: async (ablauf, kuerzel) => { gefragt.push([ablauf, kuerzel]); return { stand: 'fertig' }; } });
    await expect(auftragStand('lesen', '0123456789ab', ctx)).resolves.toEqual({ stand: 'fertig' });
    expect(gefragt).toEqual([['lesen', '0123456789ab']]);
    expect(calls.sent).toEqual([]);
    expect(calls.bot).toEqual([]);
  });

  it('ein Stand aus einer inzwischen gewechselten Sitzung gilt nicht', async () => {
    let sitzung = 'bb-1';
    const { ctx } = makeCtx({ sessionId: () => sitzung, ladeAuftragStand: async () => { sitzung = 'bb-2'; return { stand: 'fertig' }; } });
    await expect(auftragStand('lesen', '0123456789ab', ctx)).rejects.toMatchObject({ code: 'sitzung' });
  });

  it('abholen = die Direktaktion „Stand prüfen“ als Zug ohne Nutzerblase', async () => {
    const { ctx, calls } = makeCtx({ respond: () => makeResp({ content: 'Gelesen.' }) });
    await expect(auftragAbholen('lesen', ctx)).resolves.toEqual({ gesendet: true });
    // Querschnitts-Review M1: automatisch, und offene Fragen anderer Module bleiben offen.
    expect(calls.sent).toEqual([{
      message: 'Stand prüfen', env: undefined, action: 'ablauf_auftrag_pruefen',
      actionParams: { ablauf: 'lesen', automatisch: true }, opts: { fragenOffen: true },
    }]);
    expect(calls.bot.map((b) => b.content)).toContain('Gelesen.');
  });

  it('Review Q1, Befund 5: bringt das Abholen eine neue Frage, gilt die alte als veraltet (eine je Sitzung)', async () => {
    const alt = { block_id: 'u1', modul: 'ui_upload', version: 1, art: 'abfragen', status: 'offen', daten: {}, text: 'x', antwort: null };
    const neu = { ...alt, block_id: 'e1', modul: 'ui_entscheidung' };
    const { ctx, getMessages } = makeCtx({
      initialMessages: [{ id: 'm1', sender: 'bot', content: 'Ordner', ui: { ui_bloecke: [alt] } } as unknown as ChatMessage],
      respond: () => makeResp({ content: 'Gelesen.', ui: { ui_bloecke: [neu] } as never }),
    });
    await auftragAbholen('lesen', ctx);
    const status = getMessages().flatMap((m) => m.ui?.ui_bloecke ?? []).map((b) => [b.block_id, b.status]);
    expect(status).toContainEqual(['u1', 'veraltet']);
  });

  it('ohne neue Frage bleibt die alte offen', async () => {
    const alt = { block_id: 'u1', modul: 'ui_upload', version: 1, art: 'abfragen', status: 'offen', daten: {}, text: 'x', antwort: null };
    const { ctx, getMessages } = makeCtx({
      initialMessages: [{ id: 'm1', sender: 'bot', content: 'Ordner', ui: { ui_bloecke: [alt] } } as unknown as ChatMessage],
      respond: () => makeResp({ content: 'Gelesen.' }),
    });
    await auftragAbholen('lesen', ctx);
    const status = getMessages().flatMap((m) => m.ui?.ui_bloecke ?? []).map((b) => [b.block_id, b.status]);
    expect(status).toContainEqual(['u1', 'offen']);
  });

  it('während eines Zugs wird nicht abgeholt (das Modul versucht es danach)', async () => {
    const { ctx, calls } = makeCtx({ isLoading: () => true });
    await expect(auftragAbholen('lesen', ctx)).resolves.toEqual({ gesendet: false });
    expect(calls.sent).toEqual([]);
  });
});
