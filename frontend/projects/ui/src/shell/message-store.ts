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
  ChatMessage, InlineDocument, PaginationInfo, QueryMetaEntry, TopicPageView, UiInfo, WebLink,
} from '../grouping/message-types';

/** Plant einen Rückruf für den nächsten Bildschirm-Rahmen. */
export type RahmenPlaner = (cb: () => void) => void;

/** `requestAnimationFrame`, wo es das gibt — sonst ein Rahmen von ~16 ms. In einem
 *  verborgenen Tab feuert rAF nicht; dann wartet der Text, bis der Tab wieder
 *  sichtbar ist oder die fertige Antwort die Ladeblase ersetzt. */
const naechsterRahmen: RahmenPlaner = (cb) => {
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => cb());
  else setTimeout(cb, 16);
};

/** Was ein laufender Strom schon geliefert, aber noch nicht geschrieben hat. */
interface StromPuffer {
  /** Zeichen (Unicode-Codepunkte wie Python `len`) seit Beginn des Stroms —
   *  geschrieben UND ausstehend. Gegen sie prüft `pos`. */
  zeichen: number;
  /** Stücke, die auf ihren Rahmen warten. */
  ausstehend: string;
  /** Ist für diesen Strom schon ein Rahmen geplant? */
  geplant: boolean;
}

export class MessageStore {
  /** Nachrichten-Verlauf (bot/user Bubbles) — Single Source of Truth. */
  readonly messages = signal<ChatMessage[]>([]);

  /** `planen`: wann gesammelte Strom-Stücke geschrieben werden (Paket 19, N-40).
   *  Vorgabe: einmal je Bildschirm-Rahmen; Tests geben einen eigenen Planer. */
  constructor(private readonly planen: RahmenPlaner = naechsterRahmen) {}

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

  /** User-Bubble anhängen. Rumpf aus ALT chat.component.ts:1273-1278; neu ist
   *  allein `fromHost` — der Satz kam vom Gastgeber (`startTask`), nicht von
   *  der Person. Das Feld wird nur GESETZT, wenn es zutrifft: eine
   *  `fromHost: false`-Eigenschaft an jeder Nachricht wäre Rauschen im
   *  gespeicherten Verlauf. */
  addUserMessage(content: string, fromHost = false): void {
    const msg: ChatMessage = {
      id: this.uid(), sender: 'user', content, timestamp: new Date(),
      ...(fromHost ? { fromHost: true } : {}),
    };
    this.messages.update(msgs => [...msgs, msg]);
  }

  /** Bot-Bubble anhängen; gibt die neue Message-ID zurück (Scroll-Ziel /
   *  Loading-Handle). Body + Gates verbatim aus ALT chat.component.ts:1292-1317
   *  — die 11-Positionen-Seam, exakt wie collection-actions sie ruft. */
  addBotMessage(
    content: string, isLoading = false,
    cards?: WloCard[], quickReplies?: string[], ui?: UiInfo,
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
      id, sender: 'bot', content, isLoading, cards, quickReplies, ui,
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
    // Ein noch geplanter Strom-Rahmen findet dann nichts mehr (Paket 19, N-40).
    this._strom.delete(id);
    this._stromLuecke.delete(id);
  }

  /** Lade-Phasen-Label einer laufenden Bubble per id setzen (nur solange
   *  `isLoading`). Verbatim aus ALT chat.component.ts:1286-1289. */
  updateLoadingPhase(loadingId: string, label: string): void {
    this.messages.update(msgs => msgs.map(m =>
      m.id === loadingId && m.isLoading ? { ...m, loadingPhase: label } : m,
    ));
  }

  /** Bubbles, deren Strom eine Lücke hatte — dort wird nichts mehr angehängt. */
  private readonly _stromLuecke = new Set<string>();

  /** Laufende Ströme je Ladeblase (Paket 19, N-40). */
  private readonly _strom = new Map<string, StromPuffer>();

  /** Token-Streaming (Plan 2026-10-01): ein Stück Antworttext an die ladende
   *  Bubble hängen. `pos` ist die Länge des bisher gesendeten Texts; passt er
   *  nicht, fehlt ein Stück — dann bleibt der Strom stehen, und `result`
   *  bringt den ganzen Text.
   *
   *  Paket 19 (Audit 2026-10-31 N-40): geschrieben wird einmal je Rahmen, nicht je
   *  Stück. Jeder Schreibvorgang schickt den ganzen Teiltext durch marked und
   *  DOMPurify — je Stück wurde das quadratisch und machte das Streaming auf
   *  schwachen Geräten hakelig. Die Zeichenzahl läuft mit, statt den Text je
   *  Stück neu zu zählen. Der Endstand ist derselbe Text. */
  appendStreamText(loadingId: string, text: string, pos: number): void {
    if (this._stromLuecke.has(loadingId)) return;
    const msg = this.messages().find(m => m.id === loadingId);
    if (!msg || !msg.isLoading) return;
    let puffer = this._strom.get(loadingId);
    if (!puffer) {
      // `pos` zählt Unicode-Zeichen wie der Server (Python `len`), nicht
      // UTF-16-Einheiten: ein Emoji ist ein Zeichen, `length` zählte zwei.
      puffer = { zeichen: Array.from(msg.streamText ?? '').length, ausstehend: '', geplant: false };
      this._strom.set(loadingId, puffer);
    }
    if (pos !== puffer.zeichen) {
      this._stromLuecke.add(loadingId);
      return;
    }
    puffer.zeichen += Array.from(text).length;
    puffer.ausstehend += text;
    if (puffer.geplant) return;
    puffer.geplant = true;
    this.planen(() => this._schreibeStrom(loadingId));
  }

  /** **Sofort** alle ausstehenden Strom-Stücke schreiben — für Tests und für
   *  Aufrufer, die den aktuellen Stand brauchen, bevor der Rahmen kommt. */
  streamTextSchreiben(): void {
    for (const id of [...this._strom.keys()]) this._schreibeStrom(id);
  }

  /** Die gesammelten Stücke einer Ladeblase in EINEM Schreibvorgang anhängen. */
  private _schreibeStrom(loadingId: string): void {
    const puffer = this._strom.get(loadingId);
    if (!puffer) return;
    puffer.geplant = false;
    const stueck = puffer.ausstehend;
    puffer.ausstehend = '';
    const msg = this.messages().find(m => m.id === loadingId);
    // Ladeblase schon ersetzt (fertige Antwort, Neustart): nichts zurückschreiben.
    if (!msg || !msg.isLoading) {
      this._strom.delete(loadingId);
      return;
    }
    if (!stueck) return;
    this.messages.update(msgs => msgs.map(m =>
      m.id === loadingId ? { ...m, streamText: (m.streamText ?? '') + stueck } : m,
    ));
  }

  /** Den vorläufigen Text verwerfen (Rückfall auf POST) — samt einer Lücke. */
  clearStreamText(loadingId: string): void {
    this._stromLuecke.delete(loadingId);
    // Auch was noch auf seinen Rahmen wartet; ein schon geplanter Rahmen findet
    // dann keinen Puffer mehr bzw. einen neuen, der bei 0 beginnt.
    this._strom.delete(loadingId);
    this.messages.update(msgs => msgs.map(m => {
      if (m.id !== loadingId || m.streamText === undefined) return m;
      const { streamText: _verworfen, ...rest } = m;
      return rest;
    }));
  }
}
