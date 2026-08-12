/**
 * Controller-Context-Factory (8-4S-d1) — baut die fünf `*Context`-Objekte, mit
 * denen die Chat-Shell ihre Cluster verdrahtet (tour/context-greeting/speech/
 * collection-actions/host-events).
 *
 * RE-ARCHITEKTUR ggü. ALT: In ALT `ChatComponent` sind diese Contexts
 * Feld-Initializer, deren deferred Arrows direkt `this.api`/`this.sessionId`/…
 * lesen. Hier sind es dieselben Arrows, aber über einen `ShellHost` (dem
 * Live-Accessor-Seam der Shell) parametrisiert — herausgezogen, damit (1) die
 * Shell-Komponente unter der ≤300-Z.-Invariante bleibt, wenn Lifecycle (8-4S-e)
 * dazukommt, und (2) die Verdrahtung ohne TestBed unit-testbar ist (Fake-Host).
 * Das Wiring ist verhaltensgleich zu ALT chat.component.ts:656-680/782-792/
 * 1123-1129/1162-1175 — die eine echte Konsolidierung ist der geteilte `post`-
 * Helfer, der ALTs dreifach wiederholtes `api.sendMessage(sessionId, …)` bündelt
 * (die LIVE-`sessionId`-Bindung liegt damit an genau einer Stelle).
 */
import { WloCard } from '../cards/card-types';
import {
  ChatMessage, DebugInfo, InlineDocument, PaginationInfo,
  QueryMetaEntry, TopicPageView, WebLink,
} from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';
import { ChatApiClient } from '../stream/chat-api';
import { TourContext } from '../controllers/tour.controller';
import { ContextGreetingContext } from '../controllers/context-greeting.controller';
import { CollectionActionsContext } from '../controllers/collection-actions';
import { SpeechContext } from '../speech/speech.service';
import {
  GuideSuggestionPayload, HostEventsContext, RoutingDebugPayload,
} from '../host-events/host-events';

/**
 * Live-Accessor-Seam der Chat-Shell — die minimale Fläche, aus der alle fünf
 * Controller-Contexts gebaut werden. Die Shell (8-4S-d2) stellt sie als
 * Objekt-Literal deferred Arrows bereit (Muster ALT `_collectionActionsCtx`),
 * sodass jeder Zugriff LIVE gegen den aktuellen Shell-Zustand geht.
 */
export interface ShellHost {
  /** Der Chat-API-Client (post/stream/transcribe/synthesize). */
  api: () => ChatApiClient;
  /** Aktuelle Session-ID (in `post` gebunden — der Turn liest sie frisch). */
  sessionId: () => string;
  /** `parsedPageContext` — Seiten-Kontext für Tour-/Ping-Envs. */
  pageContext: () => Record<string, any>;
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  messages: () => ChatMessage[];
  updateMessages: (updater: (msgs: ChatMessage[]) => ChatMessage[]) => void;
  addUserMessage: (content: string) => void;
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[],
    quickReplies?: string[], debug?: DebugInfo,
    pagination?: PaginationInfo | null, queryMetas?: QueryMetaEntry[],
    webLinks?: WebLink[], inlineDocuments?: InlineDocument[],
    displayRules?: Record<string, any>, topicPage?: TopicPageView | null,
  ) => string;
  removeMessage: (id: string) => void;
  setScrollTarget: (id: string) => void;
  setLatestDebug: (debug: DebugInfo) => void;
  dispatchPageAction: (pa: { action: string; payload: any } | null | undefined) => void;
  messagesContainer: () => HTMLElement | undefined;
  /** `@Input() emitGuideSuggestion` — LIVE (kann nach Konstruktion gesetzt werden). */
  emitGuideSuggestion: () => boolean | string;
  emitRoutingDebug: () => boolean | string;
  emitGuideSuggestionOutput: (payload: GuideSuggestionPayload) => void;
  emitRoutingDebugOutput: (payload: RoutingDebugPayload) => void;
  /** Zoneless-Äquivalent zu `NgZone.run` (Shell: `markForCheck` nach `fn`). */
  runInZone: <T>(fn: () => T) => T;
  /** STT-Erfolg: Transkript ins Eingabefeld + senden. */
  onTranscript: (text: string) => void;
  /** Übersetzer der Shell (C1-b4) — LIVE gelesen wie alles andere, damit die
   *  Controller nach einem Sprachwechsel den neuen Text nehmen. */
  t: TranslateFn;
}

/** Die fünf Controller-Contexts, die die Shell aus einem `ShellHost` baut. */
export interface ControllerContexts {
  tour: TourContext;
  contextGreeting: ContextGreetingContext;
  speech: SpeechContext;
  collectionActions: CollectionActionsContext;
  hostEvents: HostEventsContext;
}

/** Baut die fünf Controller-Contexts über die `ShellHost`-Arrows. */
export function buildControllerContexts(host: ShellHost): ControllerContexts {
  // Geteilte POST-Turns: bündeln ALTs mehrfaches `api.sendMessage(sessionId,…)`.
  // `sessionId`/`api` werden pro Aufruf frisch gelesen (deferred). Die Arität
  // spiegelt ALT: Tour/Context-Ping ohne action (2 Args), Collection-Aktionen
  // mit action/actionParams (4 Args).
  const send = (message: string, env: any) =>
    host.api().post(host.sessionId(), message, env);
  const post = (message: string, env: any, action?: string, actionParams?: Record<string, any>) =>
    host.api().post(host.sessionId(), message, env, action, actionParams);

  const tour: TourContext = {
    sendMessage: send,
    pageContext: () => host.pageContext(),
    isLoading: () => host.isLoading(),
    setLoading: (v) => host.setLoading(v),
    addUserMessage: (content) => host.addUserMessage(content),
    addBotMessage: (...args) => host.addBotMessage(...args),
    removeMessage: (id) => host.removeMessage(id),
    setScrollTarget: (id) => host.setScrollTarget(id),
    setLatestDebug: (debug) => host.setLatestDebug(debug),
    t: (key, params) => host.t(key, params),
  };

  const contextGreeting: ContextGreetingContext = {
    sendMessage: send,
    pageContext: () => host.pageContext(),
    isLoading: () => host.isLoading(),
    setLoading: (v) => host.setLoading(v),
    addBotMessage: (...args) => host.addBotMessage(...args),
    removeMessage: (id) => host.removeMessage(id),
    setScrollTarget: (id) => host.setScrollTarget(id),
    setLatestDebug: (debug) => host.setLatestDebug(debug),
  };

  const collectionActions: CollectionActionsContext = {
    sendMessage: post,
    isLoading: () => host.isLoading(),
    setLoading: (v) => host.setLoading(v),
    messages: () => host.messages(),
    updateMessages: (updater) => host.updateMessages(updater),
    addBotMessage: (...args) => host.addBotMessage(...args),
    removeMessage: (id) => host.removeMessage(id),
    setScrollTarget: (id) => host.setScrollTarget(id),
    setLatestDebug: (debug) => host.setLatestDebug(debug),
    dispatchPageAction: (pa) => host.dispatchPageAction(pa),
    messagesContainer: () => host.messagesContainer(),
    t: (key, params) => host.t(key, params),
  };

  const speech: SpeechContext = {
    transcribe: (blob) => host.api().transcribe(blob),
    synthesize: (text, signal) => host.api().synthesize(text, signal),
    runInZone: (fn) => host.runInZone(fn),
    onTranscript: (text) => host.onTranscript(text),
    addBotMessage: (content) => { host.addBotMessage(content); },
    messages: () => host.messages(),
    t: (key, params) => host.t(key, params),
  };

  const hostEvents: HostEventsContext = {
    emitGuideSuggestion: () => host.emitGuideSuggestion(),
    emitRoutingDebug: () => host.emitRoutingDebug(),
    dispatchPageAction: (pa) => host.dispatchPageAction(pa),
    emitGuideSuggestionOutput: (payload) => host.emitGuideSuggestionOutput(payload),
    emitRoutingDebugOutput: (payload) => host.emitRoutingDebugOutput(payload),
  };

  return { tour, contextGreeting, speech, collectionActions, hostEvents };
}
