/**
 * Cards-/Pagination-Aktionen (Sammlung durchstöbern, Lernpfad generieren,
 * Karten-Fenster erweitern, Nachladen) — extrahiert aus
 * ``chat.component.ts`` (Frontend-Split, 2026-07-09).
 *
 * Plain functions — die Aktionen halten keinen eigenen State; alles lebt
 * in der Message-Liste der Komponente. Live-Zustand kommt als
 * :class:`CollectionActionsContext` mit deferred Arrows herein (Muster
 * ``TourContext``): ``api``/``sessionId``/``isLoading``/``messages``
 * werden pro Aufruf frisch gelesen — die Bestands-Spec ersetzt
 * ``comp.api`` NACH Konstruktion durch einen Instanz-Fake, deshalb darf
 * hier nichts eager gebunden werden. Bodies verbatim übernommen —
 * KEINE Logik-Änderung. NEU: Imports umgehängt (``WloCard`` → ``../cards``,
 * Response-/Message-Modell → ``../grouping/message-types``).
 */
import { WloCard } from '../cards/card-types';
import {
  ChatMessage, ChatResponse, DebugInfo, PaginationInfo,
  QueryMetaEntry, WebLink, InlineDocument, TopicPageView,
} from '../grouping/message-types';

/** Live-Zustand/Seiteneffekte der ChatComponent, die die Aktionen
 *  brauchen — als deferred Arrows (Muster: ``TourContext``). */
export interface CollectionActionsContext {
  /** ``ApiService.sendMessage`` mit LIVE-``sessionId`` der Komponente.
   *  Arg-Reihenfolge wie ``ApiService.sendMessage`` ab Position 2
   *  (message, env, action, actionParams). */
  sendMessage: (
    message: string, env: any, action?: string,
    actionParams?: Record<string, any>,
  ) => Promise<ChatResponse>;
  /** Globales ``isLoading``-Flag der Komponente (Turn-Serialisierung). */
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  /** Message-Signal der Komponente: Snapshot-Read + Update-Reducer. */
  messages: () => ChatMessage[];
  updateMessages: (updater: (msgs: ChatMessage[]) => ChatMessage[]) => void;
  /** Message-State-Reducer der Komponente (Signaturen unverändert). */
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[],
    quickReplies?: string[], debug?: DebugInfo,
    pagination?: PaginationInfo | null, queryMetas?: QueryMetaEntry[],
    webLinks?: WebLink[], inlineDocuments?: InlineDocument[],
    displayRules?: Record<string, any>, topicPage?: TopicPageView | null,
  ) => string;
  removeMessage: (id: string) => void;
  /** Setzt ``scrollTargetId`` (konsumiert in ``ngAfterViewChecked``). */
  setScrollTarget: (id: string) => void;
  /** Setzt ``latestDebug`` (Debug-Panel). */
  setLatestDebug: (debug: DebugInfo) => void;
  /** Komponenten-``dispatchPageAction`` (host callback + Output + window-Event). */
  dispatchPageAction: (pa: { action: string; payload: any } | null | undefined) => void;
  /** ``messagesContainer?.nativeElement`` — LIVE (ViewChild füllt sich
   *  erst nach dem ersten Render); ``undefined`` toleriert. */
  messagesContainer: () => HTMLElement | undefined;
}

/** Inhalte einer Sammlung als neuen Bot-Turn laden (Card-Button „Inhalte zeigen"). */
export async function browseCollection(
  nodeId: string, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  if (ctx.isLoading()) return;
  ctx.setLoading(true);
  const loadingId = ctx.addBotMessage('', true);

  try {
    const resp = await ctx.sendMessage(
      `Inhalte der Sammlung "${title}"`,
      undefined,
      'browse_collection',
      { collection_id: nodeId, title },
    );
    ctx.removeMessage(loadingId);
    const botMsgId = ctx.addBotMessage(resp.content, false, resp.cards, resp.quick_replies, resp.debug, resp.pagination, undefined, resp.web_links, resp.inline_documents, resp.display_rules);
    ctx.setScrollTarget(botMsgId);
    ctx.setLatestDebug(resp.debug);
    ctx.dispatchPageAction(resp.page_action);
  } catch {
    ctx.removeMessage(loadingId);
    const errId = ctx.addBotMessage(`Ich konnte die Inhalte von "${title}" leider nicht laden. Versuch es nochmal!`);
    ctx.setScrollTarget(errId);
  }
  ctx.setLoading(false);
}

/** Lernpfad zu einer Sammlung generieren (Card-Button „Lernpfad"). */
export async function generateLearningPath(
  nodeId: string, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  if (ctx.isLoading()) return;
  ctx.setLoading(true);
  const loadingId = ctx.addBotMessage('', true);

  try {
    const resp = await ctx.sendMessage(
      `Lernpfad für "${title}"`,
      undefined,
      'generate_learning_path',
      { collection_id: nodeId, title },
    );
    ctx.removeMessage(loadingId);
    const botMsgId = ctx.addBotMessage(resp.content, false, resp.cards, resp.quick_replies, resp.debug, resp.pagination, undefined, resp.web_links, resp.inline_documents, resp.display_rules);
    ctx.setScrollTarget(botMsgId);
    ctx.setLatestDebug(resp.debug);
    ctx.dispatchPageAction(resp.page_action);
  } catch {
    ctx.removeMessage(loadingId);
    const errId = ctx.addBotMessage(`Den Lernpfad für "${title}" konnte ich leider nicht erstellen. Versuch es nochmal!`);
    ctx.setScrollTarget(errId);
  }
  ctx.setLoading(false);
}

/** „Mehr anzeigen": Karten-Fenster einer Message um 5 erweitern.
 *
 *  Old visibleCardCount merken, damit wir nach dem Render zur ERSTEN
 *  neu enthüllten Card scrollen können — ohne den Scroll-Hint wirken
 *  die zusätzlichen Cards für den User "unsichtbar", weil sie unter
 *  der Scroll-Region des Messages-Containers erscheinen und die
 *  Pagination-Bar (mit aktualisierter "X von Y"-Zahl) den einzigen
 *  sofort sichtbaren Effekt zeigt. */
export function showMoreCards(msgId: string, ctx: CollectionActionsContext): void {
  const msg = ctx.messages().find(m => m.id === msgId);
  const previousCount = msg?.visibleCardCount || 5;
  ctx.updateMessages(all => all.map(m => {
    if (m.id !== msgId || !m.cards) return m;
    const newCount = previousCount + 5;
    return { ...m, visibleCardCount: newCount };
  }));
  // Nach Angular-Re-Render zur ersten neu enthüllten Card scrollen.
  // setTimeout(0) gibt der Change-Detection eine Tick Zeit, das DOM zu
  // aktualisieren. ``block: 'center'`` sorgt dafür, dass die Card
  // mittig in den Viewport rückt — der User sieht eindeutig dass neue
  // Inhalte aufgetaucht sind.
  setTimeout(() => {
    try {
      const container = ctx.messagesContainer();
      if (!container) return;
      // Alle wlo-card-wrapper innerhalb der Message finden (per msg.id-Anchor).
      const msgEl = container.querySelector(`#msg-${msgId}`);
      if (!msgEl) return;
      const cards = msgEl.querySelectorAll('.wlo-card-wrapper');
      // Erste neu enthüllte Card = Index previousCount (0-based).
      const target = cards[previousCount] as HTMLElement | undefined;
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } catch { /* never break a click handler */ }
  }, 0);
}

/** Pagination: weitere Inhalte einer Sammlung nachladen (Load more).
 *  Merged die neuen Cards in die BESTEHENDE Message (kein neuer Turn). */
export async function loadMore(msgId: string, ctx: CollectionActionsContext): Promise<void> {
  const msgs = ctx.messages();
  const msg = msgs.find(m => m.id === msgId);
  if (!msg?.pagination || !msg.pagination.has_more || ctx.isLoading()) return;

  const p = msg.pagination;
  const newSkip = p.skip_count + p.page_size;

  ctx.setLoading(true);

  try {
    const resp = await ctx.sendMessage(
      `Weitere Inhalte von "${p.collection_title}"`,
      undefined,
      'browse_collection',
      { collection_id: p.collection_id, title: p.collection_title, skip_count: newSkip },
    );

    // Append new cards to existing message and reveal them immediately
    ctx.updateMessages(all => all.map(m => {
      if (m.id !== msgId) return m;
      const merged: WloCard[] = [...(m.cards || []), ...(resp.cards || [])];
      return {
        ...m,
        cards: merged,
        visibleCardCount: merged.length,
        pagination: resp.pagination || undefined,
        content: resp.content,
      };
    }));
  } catch (err) {
    console.error('Load more failed:', err);
  }

  ctx.setLoading(false);
}
