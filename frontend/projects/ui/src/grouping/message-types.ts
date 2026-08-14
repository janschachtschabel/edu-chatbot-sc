/**
 * ChatMessage-Familie (Frontend-Modell) — portiert aus ALT
 * `services/api.service.ts`.
 *
 * `QueryMetaEntry` und `WebLink` sind vollständig verbatim portiert
 * (selbst-enthaltene Model-Typen ohne weitere Referenzen). `ChatMessage`
 * war bis 8-2g **absichtlich schmal** (nur die Grouping-Felder). Mit der
 * Chat-Shell (8-4S-a) ist es jetzt auf das **volle ALT-Modell**
 * konsolidiert: `id`/`sender`/`timestamp` required, plus `quickReplies`/
 * `loadingPhase`/`inlineDocuments`/`topicPage`. Einzige bewusste
 * Fidelity-Abweichung: `debug` bleibt `unknown` (siehe Feld-Kommentar).
 */
import { WloCard } from '../cards/card-types';

/** Eine MCP-Such-Metadaten-Zeile (aus `debug._query_metas`). Grouping liest
 *  `tool_name`/`search_url`/`search_term`/`repository_url` für die
 *  Search-CTA. */
export interface QueryMetaEntry {
  tool_name: string;
  query_type: string;
  search_term: string;
  criteria: Array<{ property: string; values: string[]; label?: string }>;
  pagination: { maxItems: number; skipCount: number; totalResults: number };
  repository_url: string;
  search_url: string;
}

/** Strukturierter Web-Link aus dem Bot-Antwort-Text (RAG-Quellen), vom
 *  Backend via `_extract_web_links_from_text` extrahiert. */
export interface WebLink {
  title: string;
  url: string;
}

/** Eine Schwimmlinie EINER Themenseite (Pattern M16). Box-Titel im Chat =
 *  `heading` + „(Auszug)"; max. 3 Karten. Verbatim aus ALT api.service.ts. */
export interface SwimlaneBox {
  heading: string;
  type?: string;
  cards: WloCard[];
  has_more?: boolean;
}

/** Inhalte EINER Themenseite, nach Schwimmlinien gruppiert (Pattern M16).
 *  Wird ANSTELLE der normalen Boxen gerendert; `topic_page_url` ist der
 *  Absprung-Button auf die vollständige Themenseite. Verbatim aus ALT. */
export interface TopicPageView {
  variant_title: string;
  topic_page_url: string;
  swimlanes: SwimlaneBox[];
}

/** Lernpfad (M09) / KI-Material (M10) / Edit (M11) als gerahmte Box im Chat
 *  (Welle E). `content` = Markdown-Body (via MarkdownRenderer gerendert).
 *  Verbatim aus ALT api.service.ts. */
export interface InlineDocument {
  /** "lernpfad" | "ki_material" | "edit" | "bericht" | "remix" */
  kind: string;
  title: string;
  content: string;
  meta?: Record<string, unknown>;
}

/** Ein Tool-Aufruf-Ergebnis (Triple-Schema v2). Verbatim aus ALT api.service.ts. */
export interface ToolOutcome {
  tool: string;
  status: string; // success | empty | error | timeout
  item_count: number;
  error: string;
  latency_ms: number;
}

/** Safety-Entscheidung des Turns (Regex-Gate/Moderation/Legal). Verbatim aus ALT. */
export interface SafetyDecision {
  risk_level: string; // low | medium | high
  blocked_tools: string[];
  enforced_pattern: string;
  reasons: string[];
  stages_run?: string[];
  categories?: Record<string, number>;
  flagged_categories?: string[];
  legal_flags?: string[];
  escalated?: boolean;
}

/** Policy-Entscheidung (erlaubte Tools / Disclaimer / gematchte Regeln).
 *  Verbatim aus ALT api.service.ts. */
export interface PolicyDecision {
  allowed: boolean;
  blocked_tools: string[];
  required_disclaimers: string[];
  matched_rules: string[];
}

/** Kontext-Snapshot des Turns (Seite / Gerät / Session-Historie). Verbatim aus ALT. */
export interface ContextSnapshot {
  page: string;
  device: string;
  locale: string;
  session_duration: number;
  turn_count: number;
  entities: Record<string, any>;
  recent_signals: string[];
  memory_keys: string[];
  last_intent: string;
  last_state: string;
}

/** Ein Trace-Eintrag (Phase/Label/Dauer + optionale Parallel-Gruppen-Daten in
 *  `data`). Verbatim aus ALT api.service.ts. */
export interface TraceEntry {
  step: string;
  label: string;
  duration_ms: number;
  data: Record<string, any>;
}

/** Debug-/Telemetrie-Block einer Bot-Antwort — **volles ALT-`DebugInfo`**
 *  (verbatim aus ALT api.service.ts, portiert im Debug-Panel-Slice 8-4). Das
 *  ist der Vertrag für `ChatResponse.debug` und die `latestDebug`-Anzeige des
 *  Debug-Panel-Renderers. `ChatMessage.debug` bleibt bewusst `unknown` — das
 *  Grouping castet nur `as any` auf `pattern`/`_web_links`/`_type_focus` und
 *  braucht diese Form nicht. */
export interface DebugInfo {
  persona: string;
  intent: string;
  state: string;
  turn_type: string;
  signals: string[];
  pattern: string;
  entities: Record<string, any>;
  tools_called: string[];
  phase1_eliminated: string[];
  phase2_scores: Record<string, number>;
  phase3_modulations: Record<string, any>;
  // Triple-Schema v2
  outcomes?: ToolOutcome[];
  safety?: SafetyDecision | null;
  confidence?: number;
  policy?: PolicyDecision | null;
  context?: ContextSnapshot | null;
  trace?: TraceEntry[];
  // Phase-1 Pattern-Hint (Shadow-Mode-Telemetrie des LLM-Classifiers)
  pattern_id_hint?: string | null;
  pattern_reasoning?: string | null;
  llm_engine_match?: boolean | null;
  // Phase A2 Token-Cost-Tracking (Per-Turn-Aggregator über alle LLM-Calls);
  // `per_phase`-Keys: classify, tool_loop, response, quick_replies, …
  // `cached_tokens`/`reasoning_tokens` sind „davon"-Zahlen — enthalten in
  // prompt_tokens bzw. completion_tokens, nicht zusätzlich dazu.
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    cached_tokens?: number;
    reasoning_tokens?: number;
    calls?: number;
    models?: Record<string, { prompt: number; completion: number; cached: number; reasoning?: number; calls: number; hit_rate?: number }>;
    per_phase?: Record<string, { prompt: number; completion: number; cached: number; reasoning?: number; calls: number; hit_rate?: number }>;
  };
  // Welle C Sprint 6 — Conversation-State-Plausibilität (Telemetrie-only,
  // `plausible=false` = vom Classifier gewählter Übergang außerhalb der
  // next_likely-Liste; State wird NICHT automatisch korrigiert).
  state_transition?: {
    prev: string;
    next: string;
    plausible: boolean | null;
    reason: string;
    expected_next_likely: string[];
  } | null;
}

/** Paginierungs-Info für Sammlungs-/Browse-Antworten. Verbatim aus ALT. */
export interface PaginationInfo {
  total_count: number;
  skip_count: number;
  page_size: number;
  has_more: boolean;
  collection_id: string;
  collection_title: string;
}

/** Eine Änderung, die der MCP-Server **beschreibt** statt sie auszuführen (E3),
 *  damit die Repository-Seite sie mit der Anmeldung absetzt, die dort schon
 *  besteht — so trägt sie den Namen einer Person und nicht den eines
 *  Sammelkontos. Gegenstück zu `api/schemas.PreparedWriteOut` des Backends.
 *
 *  Hier steht nur die **Form**; ob diese eine Anfrage abgesetzt werden darf,
 *  entscheidet die Erlaubnisliste in `session/prepared-write.ts`. */
export interface PreparedWriteOut {
  method: string;
  /** Pfad ab der Herkunft — nie eine absolute Adresse (E4 setzt ihn relativ ab). */
  path: string;
  /** Serialisierter JSON-Rumpf, oder nichts wo der Endpunkt keinen nimmt. */
  body?: string | null;
  /** Der Satz für hinterher; er gehört zum Werkzeug, das die Änderung kennt. */
  done_message?: string;
}

/** Volle Bot-Antwort aus POST /api/chat[/stream] (das `result`-Event des
 *  Streams bzw. der JSON-Body des Fallback-POST). Verbatim aus ALT
 *  api.service.ts — das Modell, das die Chat-Shell (8-4) zu `ChatMessage`
 *  reduziert. */
export interface ChatResponse {
  session_id: string;
  content: string;
  cards: WloCard[];
  follow_up: string;
  quick_replies: string[];
  debug: DebugInfo;
  page_action: { action: string; payload: any } | null;
  pagination: PaginationInfo | null;
  query_metas?: QueryMetaEntry[];
  web_links?: WebLink[];
  inline_documents?: InlineDocument[];
  topic_page?: TopicPageView | null;
  display_rules?: Record<string, any>;
  tour?: { active: boolean; step: string; group: string } | null;
  /** Eingebetteter Betrieb (E3/E4): die eine Änderung, die dieser Zug ausliefern
   *  darf. Höchstens eine je Zug — das Backend gibt bei zweien keine heraus. */
  prepared_write?: PreparedWriteOut | null;
  /** Das maschinenlesbare Ergebnis des Zuges (2026-08-14), wenn der Gastgeber
   *  ein `result_schema` erklärt hat. `null`, wenn dieser Zug keins hergab —
   *  „Hallo" ergibt kein Ergebnis, und das ist kein Fehler. */
  result?: Record<string, any> | null;
  /** Warum der Lauf endete (`submit`, `text`, `deadline`, …). Gehört ZUM
   *  Ergebnis: ein an der Frist abgeschnittener Lauf sähe sonst aus wie einer,
   *  der nichts zu sagen hatte. */
  result_stop_reason?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'bot' | 'user';
  content: string;
  cards?: WloCard[];
  quickReplies?: string[];
  /** ALT: `debug?: DebugInfo`. Bewusste Fidelity-Abweichung → `unknown`:
   *  das Grouping castet nur `as any` auf dynamische Keys
   *  (`_web_links`/`_type_focus`/`pattern`), die NICHT in `DebugInfo`
   *  deklariert sind; die typisierte Debug-Anzeige läuft über das separate
   *  `latestDebug`-Signal, nicht über `msg.debug`. `unknown` ist hier
   *  ehrlicher (ALT castet den Wert ohnehin sofort `as any`) und hält die
   *  Grouping-Charakterisierungs-Specs frei von Voll-`DebugInfo`-Literalen.
   *  `addBotMessage` nimmt `debug?: DebugInfo` und weitet beim Zuweisen.
   *  simplify: `unknown` statt `DebugInfo`; Upgrade-Pfad =
   *  `DebugInfo & Record<string, unknown>`, falls je typisierter Zugriff nötig. */
  debug?: unknown;
  isLoading?: boolean;
  /** Der Satz kam vom GASTGEBER, nicht von der Person am Chat (`startTask()`,
   *  Nutzer-Entscheid 2026-08-14). `sender` bleibt `'user'`: Grouping, Verlauf
   *  und Backend kennen zwei Seiten, eine dritte einzuführen kostete jede
   *  Consumer-Regel. Diese Markierung sagt nur, WER den Satz beigesteuert hat,
   *  und die Blase wird danach anders dargestellt — ein untergeschobener Satz
   *  im Verlauf wäre eine Behauptung über die Person. */
  fromHost?: boolean;
  /** Live-Status aus POST /api/chat/stream während `isLoading`. Von der Shell
   *  pro Tracer-`phase`-Event gesetzt (updateLoadingPhase). */
  loadingPhase?: string;
  /** Paginierung + client-seitiges Karten-Fenster — von den Cards-Aktionen
   *  (loadMore/showMoreCards) gelesen und fortgeschrieben. */
  pagination?: PaginationInfo | null;
  visibleCardCount?: number;
  queryMetas?: QueryMetaEntry[];
  webLinks?: WebLink[];
  /** Lernpfade / KI-Materialien / Edits als gerahmte Box im Chat (Welle E). */
  inlineDocuments?: InlineDocument[];
  /** M16 — Themenseiten-Inhalte (Schwimmlinien-Boxen) statt normaler Boxen. */
  topicPage?: TopicPageView | null;
  /** Echo der aktiven Display-Regeln (`01-base/display-rules.yaml`), per
   *  Message übertragen, damit die Bubble ihre Render-Settings behält. */
  displayRules?: Record<string, any>;
  timestamp: Date;
}
