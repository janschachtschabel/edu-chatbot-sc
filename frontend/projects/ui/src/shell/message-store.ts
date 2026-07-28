/**
 * Message-Store (8-4S-b, als eigenes Modul herausgelöst in 8-4S-f0) — der
 * State-Core des Chat-Verlaufs: das `messages`-Signal plus die Reducer, die es
 * fortschreiben.
 *
 * RE-ARCHITEKTUR, kein Verbatim-Modul: in ALT sind das PRIVATE Methoden des
 * 1480-Z.-`ChatComponent`-Monolithen. Die REDUCER-BODIES + alle Gates sind
 * verbatim aus ALT chat.component.ts:1273-1321 + 1455 übernommen. Herausgelöst,
 * weil „Verlauf fortschreiben" eine andere Verantwortung ist als „Module an den
 * Live-Zustand verdrahten" (die der Shell-Integrator hat) — und weil der Store
 * so ohne TestBed prüfbar ist.
 *
 * Kein Modul-Global-State: jede Instanz hält ihr eigenes Signal.
 */
import { signal } from '@angular/core';

import { WloCard } from '../cards/card-types';
import {
  ChatMessage, DebugInfo, InlineDocument, PaginationInfo, QueryMetaEntry, TopicPageView, WebLink,
} from '../grouping/message-types';

export class MessageStore {
  /** Nachrichten-Verlauf (bot/user Bubbles) — Single Source of Truth. */
  readonly messages = signal<ChatMessage[]>([]);

  /** Verlauf ersetzen (Restart/Reset/History-Restore). */
  set(msgs: ChatMessage[]): void {
    this.messages.set(msgs);
  }

  /** Verlauf transformieren (History-Restore, Card-Pagination, Loading-Tausch). */
  update(updater: (msgs: ChatMessage[]) => ChatMessage[]): void {
    this.messages.update(updater);
  }

  /** Kurze, zufällige Message-ID. Verbatim aus ALT chat.component.ts:1455. */
  private uid(): string {
    return Math.random().toString(36).slice(2, 10);
  }

  /** User-Bubble anhängen. Verbatim aus ALT chat.component.ts:1273-1278. */
  addUserMessage(content: string): void {
    const msg: ChatMessage = {
      id: this.uid(), sender: 'user', content, timestamp: new Date(),
    };
    this.messages.update(msgs => [...msgs, msg]);
  }

  /** Bot-Bubble anhängen; gibt die neue Message-ID zurück (Scroll-Ziel /
   *  Loading-Handle). Body + Gates verbatim aus ALT chat.component.ts:1292-1317
   *  — die 11-Positionen-Seam, exakt wie collection-actions sie ruft. */
  addBotMessage(
    content: string, isLoading = false,
    cards?: WloCard[], quickReplies?: string[], debug?: DebugInfo,
    pagination?: PaginationInfo | null,
    queryMetas?: QueryMetaEntry[],
    webLinks?: WebLink[],
    inlineDocuments?: InlineDocument[],
    displayRules?: Record<string, any>,
    topicPage?: TopicPageView | null,
  ): string {
    const id = this.uid();
    const pageSize = pagination?.page_size || 5;
    const msg: ChatMessage = {
      id, sender: 'bot', content, isLoading, cards, quickReplies, debug,
      pagination: pagination || undefined,
      visibleCardCount: pageSize,
      queryMetas: queryMetas || undefined,
      webLinks: webLinks || undefined,
      inlineDocuments: inlineDocuments && inlineDocuments.length ? inlineDocuments : undefined,
      topicPage: (topicPage && topicPage.swimlanes && topicPage.swimlanes.length) ? topicPage : undefined,
      displayRules: displayRules || undefined,
      timestamp: new Date(),
    };
    this.messages.update(msgs => [...msgs, msg]);
    return id;
  }

  /** Message per id entfernen. Verbatim aus ALT chat.component.ts:1319-1321. */
  removeMessage(id: string): void {
    this.messages.update(msgs => msgs.filter(m => m.id !== id));
  }

  /** Lade-Phasen-Label einer laufenden Bubble per id setzen (nur solange
   *  `isLoading`). Verbatim aus ALT chat.component.ts:1286-1289. */
  updateLoadingPhase(loadingId: string, label: string): void {
    this.messages.update(msgs => msgs.map(m =>
      m.id === loadingId && m.isLoading ? { ...m, loadingPhase: label } : m,
    ));
  }
}
