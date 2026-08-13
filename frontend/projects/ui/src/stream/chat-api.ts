/**
 * ChatApiClient (8-4S-d0) — der Request-/Transport-Layer der Chat-Shell, Port
 * des ALT-`ApiService` (services/api.service.ts:296-470,650-686). Der
 * Stream-Client (8-3) liefert nur die SSE-/POST-Primitive und überließ die
 * REQUEST-Formung (baseUrl, environment, body) bewusst dieser Ebene — hier
 * wird sie mit dem vollen `ChatResponse`-Typ zusammengeführt.
 *
 * RE-ARCHITEKTUR ggü. ALT: (1) `buildEnvironment` entfernt ALTs wortgleiches
 * Duplikat zwischen `sendMessage` und `sendMessageStream` (behavior-preserving
 * DRY). (2) Die reine URL-Logik von `extractPageContext` ist als
 * `_extractPageContextFromUrl(url)` herausgezogen (testbar ohne `window`, Muster
 * `page-context-detector._detectFromUrl`). Alle Bodies + Schwellen + Regexes
 * sind verbatim aus ALT. Kein Modul-Global-State — `baseUrl`/`guideMode`/
 * `guideHost`/`startTime` sind Instanzfelder; `fetchImpl` ist injizierbar.
 */
import { ChatResponse, QueryMetaEntry } from '../grouping/message-types';
import { ChatStreamEvent, postChat, streamChat } from './stream-client';

/** Request-`environment` (Kontext des Turns). Verbatim aus ALT api.service.ts. */
export interface Environment {
  page: string;
  page_context: Record<string, any>;
  device: string;
  locale: string;
  session_duration: number;
  referrer: string;
  /** Lotsen-Modus (immer aktiv; Backend-Echo für `guide_url`-Annotation). */
  guide_mode?: boolean;
  /** Host-Seite des Embeds (Allow-List-Check fürs Annotieren). */
  host?: string;
  /** Web-Tour: "start" | "tick" (nur bei Tour-Requests). */
  tour_action?: string;
  /** Seitenkontext-Ping "context_open" (proaktive Kontext-Begrüßung). */
  page_event?: string;
}

/** UA-freie Geräteklasse aus der Viewport-Breite. Verbatim ALT api.service.ts:650. */
export function detectDevice(): string {
  const w = window.innerWidth;
  if (w < 768) return 'mobile';
  if (w < 1024) return 'tablet';
  return 'desktop';
}

/** URL-abgeleiteter Teil des per-Request `page_context` (pure, testbar).
 *  Verbatim aus ALT `extractPageContext` (nur der `new URL`-Teil). */
export function _extractPageContextFromUrl(url: URL): Record<string, any> {
  // Widget-Flag: das Backend routet Karten-Antworten in die Canvas
  // (canvas_show_cards) statt in den Host-Pfad ``show_results``.
  const ctx: Record<string, any> = { widget: true };
  const params = url.searchParams;

  // Query-Params (höchste Priorität — explizit vom Host gesetzt).
  if (params.get('q')) ctx['search_query'] = params.get('q');
  if (params.get('node')) ctx['node_id'] = params.get('node');
  if (params.get('collection')) ctx['collection_id'] = params.get('collection');

  const path = url.pathname;

  // edu-sharing Render-Pattern: /edu-sharing/components/render/<uuid>.
  const renderMatch = path.match(/\/components\/render\/([a-f0-9-]{8,})/i);
  if (renderMatch && !ctx['node_id']) ctx['node_id'] = renderMatch[1];

  // WLO /sammlung/<id> und /material/<id>.
  const collMatch = path.match(/\/sammlung\/([^/?#]+)/);
  if (collMatch && !ctx['collection_id']) ctx['collection_id'] = collMatch[1];
  const matMatch = path.match(/\/material\/([^/?#]+)/);
  if (matMatch && !ctx['node_id']) ctx['node_id'] = matMatch[1];

  // WLO Themenseiten: /themenseite/<slug> bzw. /fachportal/<fach>[/<slug>].
  const themenMatch = path.match(/\/themenseite\/([^/?#]+)/);
  if (themenMatch) {
    ctx['topic_page_slug'] = themenMatch[1];
    ctx['page_type'] = 'themenseite';
  }
  const fachMatch = path.match(/\/fachportal\/([^/?#]+)(?:\/([^/?#]+))?/);
  if (fachMatch) {
    ctx['subject_slug'] = fachMatch[1];
    if (fachMatch[2]) ctx['topic_page_slug'] = fachMatch[2];
    ctx['page_type'] = ctx['page_type'] || 'fachportal';
  }

  return ctx;
}

/** Per-Request `page_context`: URL-Teil + Dokumenttitel. Verbatim ALT
 *  `extractPageContext`. */
export function extractPageContext(): Record<string, any> {
  const ctx = _extractPageContextFromUrl(new URL(window.location.href));
  if (typeof document !== 'undefined' && document.title) {
    ctx['document_title'] = document.title.slice(0, 200);
  }
  return ctx;
}

export interface ChatApiClientOptions {
  /** Injizierbar für Tests; sonst `globalThis.fetch` (via 8-3). */
  fetchImpl?: typeof fetch;
}

/** Persistierte History-Message (GET /sessions/:id/messages). Das Backend legt
 *  `web_links`/`query_metas` in `debug_json` ab; {@link ChatApiClient.loadHistory}
 *  hebt sie auf die Top-Level, damit die Shell sie ohne zweites Mapping direkt an
 *  `addBotMessage` reichen kann. Verbatim-Shape aus ALT api.service.ts:556-573. */
export interface HistoryMessage {
  role: string;
  content: string;
  cards?: any[];
  debug?: Record<string, any>;
  webLinks?: Array<{ title: string; url: string }>;
  queryMetas?: QueryMetaEntry[];
  [key: string]: any;
}

/**
 * Zustandsbehafteter Chat-Client: hält `baseUrl` (+ Runtime-Override) und den
 * Lotsen-Env-State, formt `environment`/`body` und ruft die 8-3-Transporte.
 */
export class ChatApiClient {
  private baseUrl = '/api';
  private readonly startTime = Date.now();
  private guideMode = false;
  private guideHost = '';
  private uiLocale = '';
  private engine = '';
  private readonly fetchImpl?: typeof fetch;

  constructor(opts: ChatApiClientOptions = {}) {
    this.fetchImpl = opts.fetchImpl;
    // Host darf die Backend-URL zur Laufzeit via ``window.BOERDI_API_URL``
    // überschreiben (ein Bundle → Remote-Backend ohne Dev-Proxy). Verbatim ALT.
    try {
      const w: any = typeof window !== 'undefined' ? window : null;
      if (w && typeof w.BOERDI_API_URL === 'string' && w.BOERDI_API_URL.trim()) {
        this.setBaseUrl(w.BOERDI_API_URL.trim());
      }
    } catch { /* ignore */ }
  }

  /** Backend-Basis überschreiben (trailing slash weg, `/api` anhängen). */
  setBaseUrl(url: string): void {
    if (!url) return;
    let u = url.replace(/\/$/, '');
    if (!u.endsWith('/api')) u = u + '/api';
    this.baseUrl = u;
  }

  /** Lotsen-Env setzen (Widget beim Boot). Host lowercased/getrimmt. */
  /** Sprache der Oberfläche setzen (C1-f1). Die Shell ruft das beim Boot und
   *  bei jeder Umschaltung — deshalb ein Setter und kein Konstruktor-Argument.
   *
   *  Ohne das schickte das Widget `navigator.language`: den Browser, nicht die
   *  Sprache, die es anzeigt. Wer es per Host-Attribut auf Englisch stellt,
   *  bekam eine deutsche Antwort. */
  setUiLocale(locale: string): void {
    this.uiLocale = (locale || '').trim();
  }

  setGuideEnv(guideMode: boolean, host: string): void {
    this.guideMode = !!guideMode;
    this.guideHost = (host || '').trim().toLowerCase();
  }

  /**
   * Welche Maschine diesen Einbau beantwortet — `''` überlässt es dem Backend.
   *
   * Eine Kopfzeile und kein Body-Feld: das Backend liest sie undeklariert aus
   * dem `Request` (`services/engine_choice.ENGINE_HEADER`), damit der
   * eingefrorene OpenAPI-Vertrag unberührt bleibt. Denselben Weg gehen schon
   * `Accept-Language` und `WLO-Access-Block`.
   *
   * Leer heisst hier wirklich leer: das Backend nimmt dann die Vorgabe aus
   * `01-base/engine`. Eine leere Kopfzeile mitzuschicken wäre etwas anderes —
   * sie protokolliert dort einen unbekannten Wert.
   */
  setEngine(mode: string): void {
    this.engine = (mode || '').trim().toLowerCase();
  }

  /** Die Kopfzeilen, die dieser Einbau jedem Zug mitgibt. */
  private turnHeaders(): Record<string, string> {
    return this.engine ? { 'X-Boerdi-Engine': this.engine } : {};
  }

  /** `environment` aus Overrides + Ambient. Verbatim ALT-Literal (dedupliziert
   *  über beide Transport-Varianten). */
  private buildEnvironment(env?: Partial<Environment>): Environment {
    return {
      page: env?.page || window.location.pathname,
      page_context: env?.page_context || extractPageContext(),
      device: env?.device || detectDevice(),
      locale: env?.locale || this.uiLocale || navigator.language || 'de-DE',
      session_duration: Math.floor((Date.now() - this.startTime) / 1000),
      referrer: env?.referrer || document.referrer || 'direkt',
      guide_mode: env?.guide_mode ?? this.guideMode,
      host: env?.host ?? this.guideHost,
      tour_action: env?.tour_action,
      page_event: env?.page_event,
    };
  }

  /** Request-Body (session_id/message/environment + optionale Aktion). */
  private buildBody(
    sessionId: string, message: string, env?: Partial<Environment>,
    action?: string, actionParams?: Record<string, any>,
  ): Record<string, any> {
    const body: Record<string, any> = { session_id: sessionId, message, environment: this.buildEnvironment(env) };
    if (action) body['action'] = action;
    if (actionParams) body['action_params'] = actionParams;
    return body;
  }

  /** SSE-Streaming-Turn (POST /api/chat/stream). `onEvent` bekommt jedes
   *  connected/phase/text_delta-Event; löst mit der `ChatResponse`. */
  stream(
    sessionId: string, message: string, onEvent: (evt: ChatStreamEvent) => void,
    env?: Partial<Environment>, action?: string, actionParams?: Record<string, any>,
  ): Promise<ChatResponse> {
    return streamChat<ChatResponse>({
      url: `${this.baseUrl}/chat/stream`,
      body: this.buildBody(sessionId, message, env, action, actionParams),
      onEvent,
      fetchImpl: this.fetchImpl,
      extraHeaders: this.turnHeaders(),
    });
  }

  /** Non-streaming Fallback-Turn (POST /api/chat). */
  post(
    sessionId: string, message: string, env?: Partial<Environment>,
    action?: string, actionParams?: Record<string, any>,
  ): Promise<ChatResponse> {
    return postChat<ChatResponse>({
      url: `${this.baseUrl}/chat`,
      body: this.buildBody(sessionId, message, env, action, actionParams),
      fetchImpl: this.fetchImpl,
      extraHeaders: this.turnHeaders(),
    });
  }

  // ── Sprach-Transport (STT/TTS) ──────────────────────────────────
  // Verbatim aus ALT api.service.ts:609-648. Provider-Split (#122): bei
  // b-api-academiccloud liefert das Backend `enabled:false` und die Speech-
  // Endpoints sind aus — die Shell gated die Mic/Speaker-Buttons entsprechend.

  /** Sprach-Capability des Backends abfragen. Optimistisch `true` bei
   *  Fehler/nicht-ok; nur explizites `enabled:false` blendet die Buttons aus. */
  async getSpeechEnabled(): Promise<boolean> {
    const doFetch = this.fetchImpl ?? fetch;
    try {
      const resp = await doFetch(`${this.baseUrl}/speech/status`);
      if (!resp.ok) return true;
      const data = await resp.json();
      return data?.enabled !== false;
    } catch {
      return true;
    }
  }

  /** STT: Audio-Blob → Transkript (Whisper, Sprache "de"). */
  async transcribe(audioBlob: Blob): Promise<string> {
    const doFetch = this.fetchImpl ?? fetch;
    const form = new FormData();
    form.append('audio', audioBlob, 'recording.webm');
    form.append('language', 'de');
    const resp = await doFetch(`${this.baseUrl}/speech/transcribe`, { method: 'POST', body: form });
    if (!resp.ok) throw new Error('Transcription failed');
    const data = await resp.json();
    return data.text;
  }

  /** TTS: Text → Audio-Blob (OpenAI TTS, Stimme "nova"). `signal` bricht eine
   *  laufende Synthese ab (Speech-Cluster überlappt Sätze). */
  async synthesize(text: string, signal?: AbortSignal): Promise<Blob> {
    const doFetch = this.fetchImpl ?? fetch;
    const form = new FormData();
    form.append('text', text);
    form.append('voice', 'nova');
    const resp = await doFetch(`${this.baseUrl}/speech/synthesize`, { method: 'POST', body: form, signal });
    if (!resp.ok) throw new Error('Synthesis failed');
    return resp.blob();
  }

  // ── History (Resume-Pfad) ───────────────────────────────────────
  /** History der Session laden und render-fertig aufbereiten: `_web_links`/
   *  `_query_metas` aus `debug` auf die Top-Level heben; ein `_type_focus`-Marker
   *  überstimmt stale `_web_links` mit `[]` (Material-Typ-Antwort → keine
   *  Webseiten-Inhalte-Box). Fehler/nicht-ok/Nicht-Array → `[]` (Resume darf nie
   *  den Boot brechen). Verbatim aus ALT api.service.ts:556-602. */
  async loadHistory(sessionId: string, limit = 20): Promise<HistoryMessage[]> {
    const doFetch = this.fetchImpl ?? fetch;
    try {
      const resp = await doFetch(`${this.baseUrl}/sessions/${encodeURIComponent(sessionId)}/messages?limit=${limit}`);
      if (!resp.ok) return [];
      const data = await resp.json();
      if (!Array.isArray(data)) return [];
      return data.map((m: any) => {
        const dbg = m && typeof m === 'object' ? (m.debug || {}) : {};
        const isTypeFocus = !!dbg._type_focus;
        const wl = isTypeFocus
          ? []
          : (Array.isArray(dbg._web_links) ? dbg._web_links : undefined);
        const qm = Array.isArray(dbg._query_metas) ? dbg._query_metas : undefined;
        return { ...m, webLinks: wl, queryMetas: qm };
      });
    } catch {
      return [];
    }
  }
}
