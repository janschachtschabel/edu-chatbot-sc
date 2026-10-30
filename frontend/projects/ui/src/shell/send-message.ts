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
 *
 * Paket 9 (Review Paket 7, NIT): die Wege nach einem gescheiterten Strom —
 * Verlauf, POST-Rückfall, Hinweis — stehen in eigenen Funktionen; bis dahin lagen
 * sie verschachtelt in `runSendMessage`.
 */
import { ChatResponse, UiInfo } from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';
import { sitzungsWache } from '../session/session-id';
import { drosselHinweis } from '../stream/http-fehler';
import { ChatStreamEvent } from '../stream/stream-client';

/** Was die Nachfrage im Verlauf braucht (Paket 7, P2; Review C-3/C-4). */
export interface VerlaufNachfrage {
  /** Höchste Nachrichten-ID vor diesem Zug (`connected.after_id`); `null` = unbekannt. */
  nachId: number | null;
  /** `true`, sobald der Zug nicht mehr zählt — die Sitzung wurde neu gestartet. */
  abgebrochen: () => boolean;
}

/** Live-Zustand/Seiteneffekte der Shell, die der Orchestrator braucht — als
 *  deferred Arrows (Muster `CollectionActionsContext`). */
export interface SendMessageContext {
  /** `this.userInput` — Rohtext des Eingabefelds. */
  currentInput: () => string;
  /** `this.userInput = ''`. */
  clearInput: () => void;
  /** Die Frage zurück ins Eingabefeld legen (Review Paket 7, C-6). */
  setInput: (text: string) => void;
  /** LIVE-Sitzungs-ID. Ein Zug gehört der Sitzung, in der er begann. */
  sessionId: () => string;
  /** Globales `isLoading`-Flag (Turn-Serialisierung). */
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  addUserMessage: (content: string) => void;
  /** Der 11-Positionen-Seam des State-Core (8-4S-b). */
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: ChatResponse['cards'],
    quickReplies?: string[], ui?: UiInfo,
    pagination?: ChatResponse['pagination'], queryMetas?: ChatResponse['query_metas'],
    webLinks?: ChatResponse['web_links'], inlineDocuments?: ChatResponse['inline_documents'],
    displayRules?: Record<string, any>, topicPage?: ChatResponse['topic_page'],
  ) => string;
  removeMessage: (id: string) => void;
  updateLoadingPhase: (loadingId: string, label: string) => void;
  /** Token-Streaming: ein `text_delta`-Stück an die Ladeblase (MessageStore). */
  appendStreamText: (loadingId: string, text: string, pos: number) => void;
  /** Den vorläufigen Text verwerfen (vor dem Rückfall auf POST). */
  clearStreamText: (loadingId: string) => void;
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
  /** Übersetzer für Stale- und Fehler-Bubble (C1-b4). */
  t: TranslateFn;
  /** Paket 7 (P2): die Antwort auf `msg` aus dem gespeicherten Verlauf — `null`,
   *  wenn sie in der Wartezeit nicht kommt (`antwort-aus-verlauf`). */
  answerFromHistory: (msg: string, nachfrage: VerlaufNachfrage) => Promise<ChatResponse | null>;
}

/** Ein laufender Zug — was die Wege nach einem gescheiterten Strom brauchen. */
interface Zug {
  readonly ctx: SendMessageContext;
  readonly msg: string;
  readonly env: unknown;
  readonly action?: string;
  readonly actionParams?: Record<string, any>;
  readonly loadingId: string;
  /** Die Frage, wenn sie aus dem Eingabefeld kam — sonst `''` (Chip, Aktion,
   *  Auftrag der Gastseite). Nur sie kehrt bei einem Hinweis ins Feld zurück. */
  readonly getippt: string;
  /** `true`, sobald der Zug nicht mehr zählt (`sitzungsWache`). */
  readonly veraltet: () => boolean;
}

/** Paket 7 (P1): läuft noch ein Zug derselben Sitzung? Im Strom als Kennung im
 *  `error`-Rahmen, auf dem POST-Weg als HTTP 409. */
function istBeschaeftigt(err: unknown): boolean {
  const e = err as { code?: unknown; status?: unknown } | null;
  return e?.code === 'session_busy' || e?.status === 409;
}

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

  // Der Zug gehört der Sitzung, in der er begann (`sitzungsWache`, Paket 3 T6):
  // nach einem Neustart keine Blase, kein `onResult`, kein Laden/Fokus — und vor
  // allem kein POST-Rückfall, der die alte Frage unter der neuen Sitzungs-ID
  // noch einmal stellte. Der Stream läuft im Hintergrund aus; ihn abzubrechen
  // liefe in genau diesen Rückfall.
  const veraltet = sitzungsWache(() => ctx.sessionId());

  // Loading-Bubble + Scroll dorthin.
  const loadingId = ctx.addBotMessage('', true);
  ctx.setScrollTarget(loadingId);

  try {
    const zug: Zug = {
      ctx, msg, env: ctx.pageContextEnv(), action, actionParams, loadingId, veraltet,
      getippt: !text && !action ? msg : '',
    };
    const resp = await antwortHolen(zug);
    if (!resp || veraltet()) return;
    // Loading entfernen, echte Antwort anhängen.
    ctx.removeMessage(loadingId);
    const botMsgId = ctx.addBotMessage(
      resp.content, false, resp.cards, resp.quick_replies, resp.ui,
      resp.pagination, resp.query_metas, resp.web_links, resp.inline_documents,
      resp.display_rules, resp.topic_page,
    );
    ctx.setScrollTarget(botMsgId);

    // Erfolgs-Seiteneffekte (Tour/latestDebug/query-meta/page-action/Guides/
    // autoSpeak) — Shell-verdrahtet.
    ctx.onResult(resp, msg);
  } catch (err) {
    if (veraltet()) return;
    ctx.removeMessage(loadingId);
    // Paket 18C/D: meldet der Strom eine Fehlernummer, nennt die Blase sie — dieselbe
    // steht in der gespeicherten Blase und führt im Studio zum Zug.
    const nummer = (err as { nummer?: unknown } | null)?.nummer;
    const errId = ctx.addBotMessage(typeof nummer === 'string' && nummer
      ? ctx.t('error.genericNumber', { nummer })
      : ctx.t('error.generic'));
    ctx.setScrollTarget(errId);
  }

  ctx.setLoading(false);
  ctx.focusInput();
}

/** Die Antwort des Zugs: aus dem Strom, sonst aus dem Verlauf oder vom
 *  POST-Rückfall. `null` = ohne Antwort zu Ende (ein Hinweis steht da, oder die
 *  Sitzung wechselte); ein Wurf wird zur Fehlerblase. */
async function antwortHolen(zug: Zug): Promise<ChatResponse | null> {
  const { ctx, loadingId, veraltet } = zug;
  // Phase-1-Streaming: SSE-`phase`-Events aktualisieren live das Lade-Label,
  // statt eines statischen Spinners. `text_delta` füllt die Ladeblase mit dem
  // vorläufigen Antworttext (Token-Streaming, Plan 2026-10-01); die fertige
  // Antwort ersetzt sie wie bisher. Eine Nutzlast ohne Text oder ohne Position
  // (`pos`) wird verworfen.
  // Paket 7 (P2): legt der Server die Antwort im Verlauf ab, rechnet er die
  // Frage bei einem Abbruch zu Ende — ein zweiter Versand wäre ein doppelter
  // Zug. Ohne diese Zusage (Datenschutz-Schalter `messages`, älteres Backend)
  // bleibt der POST-Rückfall (Review A-7). `after_id` grenzt die Antwort von
  // einer früheren auf dieselbe Frage ab (Review C-4).
  let angenommen = false;
  let nachId: number | null = null;
  const onEvent = (evt: ChatStreamEvent) => {
    if (evt.event === 'connected') {
      angenommen = evt.data?.history === true;
      nachId = typeof evt.data?.after_id === 'number' ? evt.data.after_id : null;
    }
    if (veraltet()) return;
    if (evt.event === 'text_delta') {
      const text = evt.data?.text;
      const pos = evt.data?.pos;
      if (typeof text === 'string' && typeof pos === 'number') {
        ctx.appendStreamText(loadingId, text, pos);
      }
      return;
    }
    const label = ctx.formatPhaseLabel(evt);
    if (label) ctx.updateLoadingPhase(loadingId, label);
  };

  try {
    return await ctx.stream(zug.msg, onEvent, zug.env, zug.action, zug.actionParams);
  } catch (streamErr) {
    if (veraltet()) return null;
    return nachStromFehler(zug, streamErr, angenommen, nachId);
  }
}

/** Der Strom scheiterte — was der Fehler für diesen Zug bedeutet. */
async function nachStromFehler(
  zug: Zug, streamErr: unknown, angenommen: boolean, nachId: number | null,
): Promise<ChatResponse | null> {
  // B10: Server lebt, wird aber nicht fertig → KEIN Fallback-POST (würde
  // den hängenden Turn erneut anstoßen); ehrliche Meldung, Antwort wird
  // serverseitig fertig gespeichert und steht im Verlauf.
  const t = zug.ctx.t;
  if ((streamErr as Error)?.name === 'StreamStaleError') return hinweis(zug, t('error.stale'));
  if (istBeschaeftigt(streamErr)) return hinweis(zug, t('error.busy'));
  // Paket 18F: zu viele Anfragen (429) — ein zweiter Versand liefe in dieselbe Grenze.
  const gedrosselt = drosselHinweis(t, streamErr);
  if (gedrosselt) return hinweis(zug, gedrosselt);
  // Review C-1: jeder `error`-Rahmen ist ein Bescheid des Servers — der Zug
  // ist dort gescheitert, im Verlauf kommt keine Antwort an, und ein zweiter
  // Versand stieße ihn nur noch einmal an.
  if ((streamErr as Error)?.name === 'StreamServerError') {
    console.warn('chat stream: the server reported an error:', streamErr);
    throw streamErr;
  }
  if (abgelehnt(streamErr)) {
    console.warn('chat stream rejected, no POST fallback:', streamErr);
    throw streamErr;
  }
  return angenommen ? ausDemVerlauf(zug, streamErr, nachId) : perPost(zug, streamErr);
}

/** Hat der Server die Anfrage VERSTANDEN und abgelehnt (4xx), bringt ein zweiter
 *  Versuch nichts: derselbe Rumpf wird auf `/chat` genauso abgelehnt. Gemeldet
 *  2026-08-19 aus der Einbettung — eine ueberlange `host_instruction` erzeugte
 *  zwei identische 422 in der Konsole und am Ende doch nur die Fehlerblase.
 *  Ausgenommen 404/405: das ist der Fall, fuer den der Rueckfall gebaut wurde
 *  (aelteres Backend ohne die Route). */
function abgelehnt(err: unknown): boolean {
  const status = (err as { status?: number })?.status;
  return typeof status === 'number' && status >= 400 && status < 500
    && status !== 404 && status !== 405;
}

/** Paket 7 (P2): der Server hat die Frage und rechnet sie zu Ende — die Antwort
 *  kommt aus dem Verlauf, statt die Frage ein zweites Mal zu stellen. */
async function ausDemVerlauf(
  zug: Zug, streamErr: unknown, nachId: number | null,
): Promise<ChatResponse | null> {
  const { ctx, loadingId, veraltet } = zug;
  console.warn('chat stream broke after the server accepted the turn — '
    + 'reading the answer from the history:', streamErr);
  // Review C-6: sonst stünde der Teiltext bis zu 100 s ohne Hinweis da.
  ctx.clearStreamText(loadingId);
  ctx.updateLoadingPhase(loadingId, ctx.t('phase.fromHistory'));
  const antwort = await ctx.answerFromHistory(zug.msg, { nachId, abgebrochen: veraltet });
  if (veraltet()) return null;
  return antwort ?? hinweis(zug, ctx.t('error.stale'));
}

/** Stream-Transport gescheitert, bevor der Server die Frage hatte (Netz/Proxy)
 *  → stiller Fallback auf den non-stream Endpoint (deckt auch ältere Backends
 *  ohne /stream-Route ab). */
async function perPost(zug: Zug, streamErr: unknown): Promise<ChatResponse | null> {
  const { ctx, loadingId, veraltet } = zug;
  console.warn('chat stream failed, falling back to POST /chat:', streamErr);
  // Der zweite Weg beantwortet die Frage neu — ein Teiltext des ersten
  // stünde sonst bis dahin als Antwort da.
  ctx.clearStreamText(loadingId);
  try {
    return await ctx.post(zug.msg, zug.env, zug.action, zug.actionParams);
  } catch (postErr) {
    if (veraltet()) return null;
    const gedrosselt = drosselHinweis(ctx.t, postErr);
    if (gedrosselt) return hinweis(zug, gedrosselt);
    if (!istBeschaeftigt(postErr)) throw postErr;
    return hinweis(zug, ctx.t('error.busy'));
  }
}

/** Ein Hinweis statt einer Antwort („beschäftigt“, „veraltet“). Beide bitten ums
 *  erneute Senden — dafür liegt eine getippte Frage wieder im Eingabefeld
 *  (Review C-6; seit Paket 9 auch bei „veraltet“). Nicht über das hinweg, was die
 *  Person inzwischen getippt hat, und nur, was sie getippt hat: eine Aktion
 *  (Karten-Knopf) liefe als Text allein ohne die Aktion, ein Chip oder ein Auftrag
 *  der Gastseite stünde als Satz da, den sie nie geschrieben hat. */
function hinweis(zug: Zug, text: string): null {
  const { ctx, loadingId } = zug;
  if (zug.getippt && !ctx.currentInput().trim()) ctx.setInput(zug.getippt);
  ctx.removeMessage(loadingId);
  const id = ctx.addBotMessage(text);
  ctx.setScrollTarget(id);
  ctx.setLoading(false);
  ctx.focusInput();
  return null;
}
