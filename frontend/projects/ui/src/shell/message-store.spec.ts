import { describe, expect, it } from 'vitest';

import { WloCard } from '../cards/card-types';
import { InlineDocument, PaginationInfo, TopicPageView } from '../grouping/message-types';
import { MessageStore } from './message-store';

/**
 * Charakterisierung des State-Core der Chat-Shell (8-4S-b, hierher verlagert in
 * 8-4S-f0).
 *
 * RE-ARCHITEKTUR, kein Verbatim: ALT `ChatComponent` ist ein 1480-Z.-Monolith
 * und verletzt die ≤300-Z.-Invariante. Die in ALT PRIVATEN Message-Reducer
 * (chat.component.ts:1273-1321) leben hier in einem eigenen Zustands-Container,
 * den Orchestrator/Controller-Wiring/Lifecycle (8-4S-c…e) über die Shell-Seams
 * konsumieren. Die REDUCER-BODIES + alle ALT-Gates bleiben verbatim; gepinnt:
 * Default-State, addUserMessage/addBotMessage-Feldmapping inkl. pageSize-
 * Default, `pagination||undefined`, inlineDocuments-Length-Gate,
 * topicPage-swimlanes-Gate, id-Rückgabe/-Eindeutigkeit, removeMessage,
 * updateLoadingPhase (nur die ladende Bubble mit passender id).
 *
 * Kein TestBed nötig: der Store ist ein reiner Signal-Container ohne Angular-
 * Abhängigkeit (Verlagerungs-Gewinn ggü. der Component-Spec vorher).
 */

describe('MessageStore — State-Core', () => {
  it('Default-State: leere messages', () => {
    expect(new MessageStore().messages()).toEqual([]);
  });

  it('addUserMessage: hängt user-Bubble mit id/sender/content/timestamp an', () => {
    const s = new MessageStore();
    s.addUserMessage('Hallo');
    const msgs = s.messages();
    expect(msgs.length).toBe(1);
    expect(msgs[0].sender).toBe('user');
    expect(msgs[0].content).toBe('Hallo');
    expect(typeof msgs[0].id).toBe('string');
    expect(msgs[0].id.length).toBeGreaterThan(0);
    expect(msgs[0].timestamp).toBeInstanceOf(Date);
  });

  it('addBotMessage: minimal → bot-Bubble, gibt id zurück, isLoading default false, visibleCardCount 5', () => {
    const s = new MessageStore();
    const id = s.addBotMessage('Antwort');
    const m = s.messages()[0];
    expect(m.id).toBe(id);
    expect(m.sender).toBe('bot');
    expect(m.content).toBe('Antwort');
    expect(m.isLoading).toBe(false);
    expect(m.visibleCardCount).toBe(5);
    expect(m.timestamp).toBeInstanceOf(Date);
  });

  it('addBotMessage: id ist pro Aufruf eindeutig und landet in der Message', () => {
    const s = new MessageStore();
    const a = s.addBotMessage('a');
    const b = s.addBotMessage('b');
    expect(a).not.toBe(b);
    expect(s.messages().map(m => m.id)).toEqual([a, b]);
  });

  it('addBotMessage: volles Arg-Mapping (11 Positionen wie collection-actions es ruft)', () => {
    const s = new MessageStore();
    const cards = [{ id: 'k' }] as unknown as WloCard[];
    const pagination: PaginationInfo = {
      total_count: 20, skip_count: 0, page_size: 10, has_more: true, collection_id: 'c', collection_title: 'T',
    };
    const inlineDocs: InlineDocument[] = [{ kind: 'lernpfad', title: 'L', content: 'c' }];
    const topic: TopicPageView = {
      variant_title: 'V', topic_page_url: 'https://t', swimlanes: [{ heading: 'H', cards: [] }],
    };
    const id = s.addBotMessage(
      'X', false, cards, ['q'], { pattern: 'M06' }, pagination,
      undefined, [{ title: 'w', url: 'u' }], inlineDocs, { fontSize: 90 }, topic,
    );
    const m = s.messages()[0];
    expect(m.id).toBe(id);
    expect(m.cards).toBe(cards);
    expect(m.quickReplies).toEqual(['q']);
    expect(m.ui).toEqual({ pattern: 'M06' });
    expect(m.pagination).toBe(pagination);
    expect(m.visibleCardCount).toBe(10); // = pagination.page_size
    expect(m.queryMetas).toBeUndefined();
    expect(m.webLinks).toEqual([{ title: 'w', url: 'u' }]);
    expect(m.inlineDocuments).toBe(inlineDocs);
    expect(m.displayRules).toEqual({ fontSize: 90 });
    expect(m.topicPage).toBe(topic);
  });

  it('addBotMessage-Gates: leere inlineDocuments/topicPage-ohne-swimlanes/pagination-null → undefined', () => {
    const s = new MessageStore();
    const topicNoLanes: TopicPageView = { variant_title: 'V', topic_page_url: 'https://t', swimlanes: [] };
    s.addBotMessage('X', false, undefined, undefined, undefined, null, undefined, undefined, [], undefined, topicNoLanes);
    const m = s.messages()[0];
    expect(m.inlineDocuments).toBeUndefined();
    expect(m.topicPage).toBeUndefined();
    expect(m.pagination).toBeUndefined();
    expect(m.visibleCardCount).toBe(5); // Default-pageSize bei pagination null
  });

  it('removeMessage: entfernt per id', () => {
    const s = new MessageStore();
    const a = s.addBotMessage('a');
    const b = s.addBotMessage('b');
    s.removeMessage(a);
    expect(s.messages().map(m => m.id)).toEqual([b]);
  });

  it('updateLoadingPhase: setzt loadingPhase NUR auf der ladenden Bubble mit passender id', () => {
    const s = new MessageStore();
    const loadingId = s.addBotMessage('', true);
    const doneId = s.addBotMessage('fertig', false);
    const byId = (id: string) => s.messages().find(m => m.id === id)!;

    s.updateLoadingPhase(loadingId, 'sucht…');
    expect(byId(loadingId).loadingPhase).toBe('sucht…');
    expect(byId(doneId).loadingPhase).toBeUndefined();

    // Nicht-ladende Bubble mit passender id bleibt unberührt (`&& m.isLoading`).
    s.updateLoadingPhase(doneId, 'x');
    expect(byId(doneId).loadingPhase).toBeUndefined();
  });

  // Token-Streaming (Plan 2026-10-01, T14): `pos` ist die Länge des bisher
  // gesendeten Texts. Passt er nicht, fehlt ein Stück — dann wird nichts mehr
  // angehängt, und `result` bringt am Ende den ganzen Text.
  it('appendStreamText: hängt an, solange pos zur bisherigen Länge passt', () => {
    const s = new MessageStore();
    const loadingId = s.addBotMessage('', true);
    const byId = (id: string) => s.messages().find(m => m.id === id)!;

    s.appendStreamText(loadingId, 'Hal', 0);
    s.appendStreamText(loadingId, 'lo', 3);
    expect(byId(loadingId).streamText).toBe('Hallo');

    s.appendStreamText(loadingId, ' Welt', 9);   // Lücke: pos 9 statt 5
    s.appendStreamText(loadingId, '!', 5);        // danach bleibt der Strom stehen
    expect(byId(loadingId).streamText).toBe('Hallo');
  });

  // Review Token-Streaming, M1: `pos` zählt Unicode-Zeichen (Python `len`),
  // JavaScript-`length` dagegen UTF-16-Einheiten — ein Emoji zählt dort doppelt.
  it('appendStreamText: Emoji im Strom zählt als ein Zeichen wie beim Server', () => {
    const s = new MessageStore();
    const loadingId = s.addBotMessage('', true);
    const emoji = String.fromCodePoint(0x1F600);
    s.appendStreamText(loadingId, 'Grüße ' + emoji, 0);
    s.appendStreamText(loadingId, ' und mehr', 7);
    expect(s.messages()[0].streamText).toBe('Grüße ' + emoji + ' und mehr');
  });

  it('appendStreamText: nur auf der ladenden Bubble mit passender id', () => {
    const s = new MessageStore();
    const doneId = s.addBotMessage('fertig', false);
    s.appendStreamText(doneId, 'x', 0);
    expect(s.messages()[0].streamText).toBeUndefined();
  });

  it('clearStreamText: leert den vorläufigen Text und hebt die Sperre nach einer Lücke auf', () => {
    const s = new MessageStore();
    const loadingId = s.addBotMessage('', true);
    const byId = (id: string) => s.messages().find(m => m.id === id)!;
    s.appendStreamText(loadingId, 'Hal', 0);
    s.appendStreamText(loadingId, 'x', 7);        // Lücke
    s.clearStreamText(loadingId);
    expect(byId(loadingId).streamText).toBeUndefined();
    s.appendStreamText(loadingId, 'Neu', 0);
    expect(byId(loadingId).streamText).toBe('Neu');
  });

  it('set/update: ersetzt bzw. transformiert den Verlauf (Lifecycle-/History-Pfade)', () => {
    const s = new MessageStore();
    s.addBotMessage('a');
    s.set([]);
    expect(s.messages()).toEqual([]);
    s.addUserMessage('u');
    s.update(msgs => msgs.map(m => ({ ...m, content: m.content + '!' })));
    expect(s.messages()[0].content).toBe('u!');
  });
});
