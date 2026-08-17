/**
 * History-Restore (8-4S-e3) — der Resume-Render aus ALT `restoreHistory`
 * (chat.component.ts:347-399) als kontext-getriebene Funktion, damit `ngOnInit`
 * schlank bleibt. Lädt die persistierte History und rendert sie in die Message-
 * Liste: die hardcodierte Begrüßung IMMER voranstellen (Backend persistiert sie
 * nicht → würde nach Reopen/Cross-TLD-Handoff verschwinden), deren Quick-Reply-
 * Pillen strippen (nur der ganz frische Chat-Anfang bleibt klickbar), dann jede
 * user-/assistant-Zeile mit Cards/WebLinks/QueryMetas/Debug mitrestoren, zuletzt
 * ans Ende scrollen. KEINE Logik-Änderung — Bodies verbatim aus ALT.
 */
import { WloCard } from '../cards/card-types';
import { ChatMessage, DebugInfo, PaginationInfo, QueryMetaEntry, WebLink } from '../grouping/message-types';
import { HistoryMessage } from '../stream/chat-api';

/** Live-Zustand/Reducer der Shell, die der Restore braucht (deferred Arrows +
 *  die öffentliche Message-API; Signaturen wie `ChatShellComponent`). */
export interface HistoryRestoreContext {
  loadHistory: (sessionId: string, limit: number) => Promise<HistoryMessage[]>;
  sessionId: () => string;
  showGreeting: () => void;
  updateMessages: (updater: (msgs: ChatMessage[]) => ChatMessage[]) => void;
  addUserMessage: (content: string) => void;
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[], quickReplies?: string[],
    debug?: DebugInfo, pagination?: PaginationInfo | null,
    queryMetas?: QueryMetaEntry[], webLinks?: WebLink[],
  ) => string;
  scrollToLatest: () => void;
}

/** Kennzeichen der persistierten Kontext-Begrüßung im ``debug.pattern`` —
 *  Gegenstück zu ``CONTEXT_GREETING_MARKER`` im Backend
 *  (``domain/quick_reply_policy.py``). Lokal wie ``'TOUR:'`` in
 *  ``grouping/result-grouping.ts``: beide Seiten teilen die Zeichenkette, nicht
 *  den Code. */
const CONTEXT_GREETING_MARKER = 'CTX:';

/** Hat die Kontext-Begrüßung dieses Gespräch eröffnet?
 *
 *  Dann gab es nie eine statische Startnachricht: ``_greetOnFirstLoad`` lässt
 *  sie in genau diesem Fall bewusst aus (Ansatz C — die Person soll EINE
 *  Eröffnung sehen, nicht zwei). Nur der erste Eintrag zählt; eine
 *  Kontext-Begrüßung mitten im Verlauf gehört zu einem späteren Seitenwechsel
 *  und sagt nichts darüber, womit das Gespräch begann.
 *
 *  **Grenze:** geladen werden die letzten 20 Nachrichten. In einem längeren
 *  Gespräch ist der erste Eintrag deshalb nicht zwingend der echte Anfang —
 *  beginnt das Fenster zufällig mit einer Kontext-Begrüßung, bleibt die
 *  Startnachricht aus, obwohl es sie gab. Der Preis ist eine fehlende
 *  Begrüßungsblase über einem langen Verlauf; der umgekehrte Fehler (eine
 *  Startnachricht, die bei jedem Seitenwechsel nachwächst) war der teurere. */
function openerIsContextGreeting(history: HistoryMessage[]): boolean {
  const first = history[0];
  const pattern = first?.debug?.['pattern'];
  return first?.role === 'assistant' && typeof pattern === 'string'
    && pattern.startsWith(CONTEXT_GREETING_MARKER);
}

/** History der Session laden und render-fertig einspielen. Verbatim aus ALT
 *  chat.component.ts:347-399, plus das Kontext-Tor von 2026-08-17. */
export async function restoreHistory(ctx: HistoryRestoreContext): Promise<void> {
  const history = await ctx.loadHistory(ctx.sessionId(), 20);
  if (!history || history.length === 0) {
    // Leere Session — Begrüßung wie ein frischer Chat.
    ctx.showGreeting();
    return;
  }
  // Hardcodierte Anfangs-Begrüßung voranstellen (Backend persistiert sie nicht
  // → würde nach Reopen/Cross-TLD-Handoff verschwinden) — es sei denn, sie gab
  // es nie, weil die Kontext-Begrüßung eröffnet hat. Befund 2026-08-17: ein
  // Browser-Plugin ohne Sidebar-API hängt das Widget bei jedem Seitenwechsel neu
  // ein; ohne dieses Tor wuchs bei jedem Wechsel eine Startnachricht nach.
  if (!openerIsContextGreeting(history)) {
    ctx.showGreeting();
    // Greeting-QRs nur am ganz frischen Chat-Anfang klickbar lassen — sobald echte
    // Konversation folgt, die QRs der prepended Greeting-Bubble strippen.
    ctx.updateMessages(msgs => {
      if (!msgs.length) return msgs;
      const head = msgs[0];
      return [{ ...head, quickReplies: undefined }, ...msgs.slice(1)];
    });
  }
  for (const m of history) {
    const content = (m.content || '').trim();
    if (!content) continue;
    if (m.role === 'user') {
      ctx.addUserMessage(content);
    } else if (m.role === 'assistant') {
      // Cards / Web-Links / Query-Metas aus dem persistierten Backend-State
      // mitrestoren, damit Bot-Antworten nach Refresh nicht als nackter Text
      // ohne Kacheln/Webseiten-Inhalte-Box/Such-CTA dastehen.
      const cards = Array.isArray(m.cards) ? m.cards : undefined;
      const webLinks = Array.isArray(m.webLinks) ? m.webLinks : undefined;
      const queryMetas = Array.isArray(m.queryMetas) ? m.queryMetas : undefined;
      // debug mitgeben (pattern="TOUR:…" + _type_focus): so werden auch
      // wiederhergestellte Tour-Nachrichten erkannt und Result-Boxen unterdrückt.
      ctx.addBotMessage(content, false, cards, undefined, m.debug as DebugInfo | undefined, undefined, queryMetas, webLinks);
    }
  }
  // Ans Ende scrollen — der Auto-Follow-Tail hält jede spätere Mutation am Boden.
  ctx.scrollToLatest();
}
