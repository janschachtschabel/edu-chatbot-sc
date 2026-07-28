/**
 * sendMessage-**Orchestrator** (8-4S-c) — der Turn-Lifecycle der Chat-Shell,
 * Port von ALT `ChatComponent.sendMessage` (chat.component.ts:448-569).
 *
 * RE-ARCHITEKTUR (kein Verbatim — ALT-Monolith): die Lifecycle-Mechanik
 * (Guard → Input leeren → User-Bubble → Loading-Bubble → Stream/Stale/Fallback
 * → Ergebnis-Bubble → Fehler-Bubble → isLoading/Fokus) ist hier eine reine
 * Funktion hinter der `SendMessageContext`-Seam (Muster `CollectionActions-
 * Context`: deferred Arrows lesen/schreiben LIVE-Shell-State). Die
 * ERFOLGS-Seiteneffekte von ALT (Tour-State, latestDebug, query-meta-Event,
 * page-action, Guide-Dispatch, autoSpeak) sind zu EINEM `onResult(resp, msg)`-
 * Hook zusammengefasst — die Shell verdrahtet ihn in 8-4S-d/e/g und hält dort
 * ALTs Sequenz + Gates (`query_metas?.length`, `autoSpeak && content`). Die
 * URL-/Body-Formung des Transports bleibt ebenfalls Shell-Sache (8-4S-d):
 * `stream`/`post` sind Arrows, die intern `streamChat`/`postChat` (8-3) mit der
 * LIVE-`sessionId` rufen.
 */
import { ChatResponse } from '../grouping/message-types';
import { ChatStreamEvent } from '../stream/stream-client';

/** Live-Zustand/Seiteneffekte der Shell, die der Orchestrator braucht — als
 *  deferred Arrows (Muster `CollectionActionsContext`). */
export interface SendMessageContext {
  /** `this.userInput` — Rohtext des Eingabefelds. */
  currentInput: () => string;
  /** `this.userInput = ''`. */
  clearInput: () => void;
  /** Globales `isLoading`-Flag (Turn-Serialisierung). */
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  addUserMessage: (content: string) => void;
  /** Der 11-Positionen-Seam des State-Core (8-4S-b). */
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: ChatResponse['cards'],
    quickReplies?: string[], debug?: ChatResponse['debug'],
    pagination?: ChatResponse['pagination'], queryMetas?: ChatResponse['query_metas'],
    webLinks?: ChatResponse['web_links'], inlineDocuments?: ChatResponse['inline_documents'],
    displayRules?: Record<string, any>, topicPage?: ChatResponse['topic_page'],
  ) => string;
  removeMessage: (id: string) => void;
  updateLoadingPhase: (loadingId: string, label: string) => void;
  /** Setzt `scrollTargetId` (in `ngAfterViewChecked` konsumiert, 8-4S-e). */
  setScrollTarget: (id: string) => void;
  /** `setTimeout(() => inputField.focus(), 100)` — Shell-seitig. */
  focusInput: () => void;
  /** envOverride aus `parsedPageContext` (undefined, wenn leer). */
  pageContextEnv: () => unknown;
  /** `streamChat` (8-3) mit LIVE-`sessionId` gebunden; wirft `StreamStaleError`
   *  bei B10-Stale, sonst Netz-/Parser-Fehler (→ POST-Fallback). */
  stream: (
    msg: string, onEvent: (evt: ChatStreamEvent) => void, env: unknown,
    action?: string, actionParams?: Record<string, any>,
  ) => Promise<ChatResponse>;
  /** `postChat` (8-3) Fallback mit LIVE-`sessionId` gebunden. */
  post: (msg: string, env: unknown, action?: string, actionParams?: Record<string, any>) => Promise<ChatResponse>;
  /** Tracer-`phase` → Lade-Label (pure); `null` = kein Label. */
  formatPhaseLabel: (evt: ChatStreamEvent) => string | null;
  /** Erfolgs-Seiteneffekte (Tour/latestDebug/query-meta/page-action/Guides/
   *  autoSpeak) — Shell-verdrahtet in 8-4S-d/e/g, ALT-Sequenz + Gates dort. */
  onResult: (resp: ChatResponse, userMessage: string) => void;
}

/** Stale-Meldung, wenn der Stream 100 s lang nicht fertig wird (B10). */
const STALE_MESSAGE =
  'Das dauert gerade ungewöhnlich lange — bitte stell deine Frage '
  + 'gleich noch einmal. Falls meine Antwort doch noch fertig '
  + 'geworden ist, findest du sie beim nächsten Öffnen im Verlauf.';

/**
 * Einen Chat-Turn abwickeln. `text` leer → Rückgriff aufs Eingabefeld
 * (`text || currentInput().trim()`, ALT-verbatim); Guard gegen leere Message
 * und laufenden Turn. Lifecycle + Fehler-/Stale-/Fallback-Verhalten wie ALT
 * `sendMessage`; Erfolgs-Seiteneffekte über `ctx.onResult`.
 */
export async function runSendMessage(
  text: string | undefined,
  action: string | undefined,
  actionParams: Record<string, any> | undefined,
  ctx: SendMessageContext,
): Promise<void> {
  const msg = text || ctx.currentInput().trim();
  if (!msg || ctx.isLoading()) return;

  ctx.clearInput();
  ctx.addUserMessage(msg);
  ctx.setLoading(true);

  // Loading-Bubble + Scroll dorthin.
  const loadingId = ctx.addBotMessage('', true);
  ctx.setScrollTarget(loadingId);

  try {
    const env = ctx.pageContextEnv();

    // Phase-1-Streaming: SSE-`phase`-Events aktualisieren live das Lade-Label,
    // statt eines statischen Spinners. `text_delta` ist ein bewusster No-Op
    // (Phase-2-Token-Streaming zurückgerollt — flackerte).
    const onEvent = (evt: ChatStreamEvent) => {
      if (evt.event === 'text_delta') return;
      const label = ctx.formatPhaseLabel(evt);
      if (!label) return;
      ctx.updateLoadingPhase(loadingId, label);
    };

    let resp: ChatResponse;
    try {
      resp = await ctx.stream(msg, onEvent, env, action, actionParams);
    } catch (streamErr) {
      // B10: Server lebt, wird aber nicht fertig → KEIN Fallback-POST (würde
      // den hängenden Turn erneut anstoßen); ehrliche Meldung, Antwort wird
      // serverseitig fertig gespeichert und steht im Verlauf.
      if ((streamErr as Error)?.name === 'StreamStaleError') {
        ctx.removeMessage(loadingId);
        const staleId = ctx.addBotMessage(STALE_MESSAGE);
        ctx.setScrollTarget(staleId);
        ctx.setLoading(false);
        ctx.focusInput();
        return;
      }
      // Stream-Transport gescheitert (Netz/Proxy/Parser) → stiller Fallback
      // auf den non-stream Endpoint, damit der User trotzdem eine Antwort
      // bekommt (deckt auch ältere Backends ohne /stream-Route ab).
      console.warn('chat stream failed, falling back to POST /chat:', streamErr);
      resp = await ctx.post(msg, env, action, actionParams);
    }

    // Loading entfernen, echte Antwort anhängen.
    ctx.removeMessage(loadingId);
    const botMsgId = ctx.addBotMessage(
      resp.content, false, resp.cards, resp.quick_replies, resp.debug,
      resp.pagination, resp.query_metas, resp.web_links, resp.inline_documents,
      resp.display_rules, resp.topic_page,
    );
    ctx.setScrollTarget(botMsgId);

    // Erfolgs-Seiteneffekte (Tour/latestDebug/query-meta/page-action/Guides/
    // autoSpeak) — Shell-verdrahtet.
    ctx.onResult(resp, msg);
  } catch {
    ctx.removeMessage(loadingId);
    const errId = ctx.addBotMessage('Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.');
    ctx.setScrollTarget(errId);
  }

  ctx.setLoading(false);
  ctx.focusInput();
}
