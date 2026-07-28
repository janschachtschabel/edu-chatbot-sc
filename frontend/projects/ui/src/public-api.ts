/**
 * Public surface of the shared `@boerdi/ui` source library (consumed by the
 * widget and — from P9 — the studio app via tsconfig path mapping; never
 * published, so no ng-packagr build step).
 *
 * P8: 8-1 seeded the theme layer; 8-2 adds `session/` (session-id + trusted
 * host, V5-unified), then markdown, chips, cards, inline-doc, swimlanes and the
 * page-context detector.
 */
export { applyPrimaryColor, isValidCssColor } from './theme/primary-color';

export {
  deleteSessionCookie,
  generateSessionId,
  isValidSessionId,
  readSessionCookie,
  resolvePersistedSessionId,
  writeSessionCookie,
  writeSessionEverywhere,
} from './session/session-id';
export type { ResolvedSessionId, SessionCookieConfig } from './session/session-id';

export {
  buildTrustedDomains,
  CORE_TRUSTED_DOMAINS,
  externalLinkWarning,
  isTrustedHost,
  mergeTrustedDomains,
  normalizeTrustedDomain,
  withBsid,
} from './session/trusted-host';
export { maybeRewriteOutgoingLink, resolveGuideNavUrl } from './session/link-handoff';
export type { LinkHandoffContext, OutgoingLinkContext } from './session/link-handoff';

export { ICONS } from './icons/icons';
export type { IconName } from './icons/icons';
export { SafeSvgPipe } from './icons/safe-svg.pipe';

export { stripLatex } from './markdown/latex';
export { MarkdownRenderer } from './markdown/markdown-renderer';
export type { MarkdownRenderContext } from './markdown/markdown-renderer';

export {
  ACTION_QR_PREFIX,
  actionQuickReplyLabel,
  isActionQuickReply,
  parseActionQuickReply,
} from './chips/action-qr';
export type { ParsedActionQr } from './chips/action-qr';
export {
  GUIDE_QR_PREFIX,
  guideQuickReplyLabel,
  guideQuickReplyUrl,
  isGuideQuickReply,
  shouldHideGuideQuickReply,
} from './chips/guide-qr';
export { QuickRepliesComponent } from './chips/quick-replies.component';

export { detectPageContext } from './page-context/page-context-detector';
export type { DetectedContext } from './page-context/page-context-detector';

export {
  getCardIcon,
  getCardPrimaryUrl,
  getContentTypeLabel,
  isInhalt,
  isSammlung,
  isThemenseite,
} from './cards/card-utils';
export { getLicenseShort } from './cards/license';
export type { WloCard } from './cards/card-types';
export { WloCardTileComponent } from './cards/wlo-card-tile.component';
export { CardListComponent } from './cards/card-list.component';
export type { CardAction } from './cards/card-list.component';

export {
  cardTooltip,
  displayContent,
  groupedCollectionCards,
  groupedContentCards,
  groupedContentCardsCount,
  groupedSearchTerm,
  groupedSearchUrl,
  groupedTopicCards,
  groupedWebLinks,
  hasGroupedResults,
  isTourMessage,
  itemTooltip,
  searchCtaTooltip,
} from './grouping/result-grouping';
export type { GroupingContext } from './grouping/result-grouping';
export type {
  ChatMessage,
  ChatResponse,
  ContextSnapshot,
  DebugInfo,
  InlineDocument,
  PaginationInfo,
  PolicyDecision,
  QueryMetaEntry,
  SafetyDecision,
  SwimlaneBox,
  ToolOutcome,
  TopicPageView,
  TraceEntry,
  WebLink,
} from './grouping/message-types';
export { DebugPanelComponent } from './debug/debug-panel.component';
export { ResultGroupsComponent } from './grouping/result-groups.component';
export type { ResultGroupsContext } from './grouping/result-groups.component';
export { SwimlanesComponent } from './grouping/swimlanes.component';

export {
  inlineDocFallbackLabel,
  inlineDocFontSize,
  inlineDocIcon,
} from './inline-doc/inline-doc';
export { InlineDocumentsComponent } from './inline-doc/inline-documents.component';

export {
  parseSseBlock,
  postChat,
  streamChat,
  StreamStaleError,
} from './stream/stream-client';
export type { ChatStreamEvent, PostChatOptions, StreamChatOptions } from './stream/stream-client';

export { BOERDI_LOGO_DATA_URL, BOERDI_LOGO_SVG, boerdiLogoUrl } from './branding/boerdi-logo';
export {
  PRINTABLE_CANVAS_RE,
  printCanvasMaterial,
  printLearningPath,
  printMarkdownDocument,
  printMdToHtml,
  safePrintHref,
} from './print/print-utils';

export { TourController, TOUR_START_LABEL } from './controllers/tour.controller';
export type { TourContext } from './controllers/tour.controller';
export { ContextGreetingController } from './controllers/context-greeting.controller';
export type { ContextGreetingContext } from './controllers/context-greeting.controller';
export {
  browseCollection,
  generateLearningPath,
  loadMore,
  showMoreCards,
} from './controllers/collection-actions';
export type { CollectionActionsContext } from './controllers/collection-actions';
export { SpeechService } from './speech/speech.service';
export type { SpeechContext } from './speech/speech.service';

export { _attrIsTrue } from './element/attr';
export {
  maybeDispatchGuideNavigate,
  maybeDispatchGuideSuggestion,
  maybeDispatchRoutingDebug,
} from './host-events/host-events';
export type { GuideSuggestionPayload, HostEventsContext, RoutingDebugPayload } from './host-events/host-events';

// ── Widget-Hülle (8-5): Chat-Shell + die Bausteine, die die Hülle verdrahtet ──
export { ChatShellComponent } from './shell/chat-shell.component';
export { computeInitialExpanded, resolveMergedPageContext } from './widget/widget-init';
export {
  headerNavHrefWithBsid,
  headerNavIconSvg,
  parseGuideModeConfig,
} from './widget/guide-mode-config';
export type { HeaderNavButton, ParsedGuideModeConfig } from './widget/guide-mode-config';
export { PanelState } from './widget/panel-state';
export type { PanelStateContext } from './widget/panel-state';
export { GuideBoot } from './widget/guide-boot';
export type { GuideBootContext } from './widget/guide-boot';
export { GuideNav } from './widget/guide-nav';
export type { GuideNavContext } from './widget/guide-nav';
export { HostBridges } from './widget/host-bridges';
export type { HostBridgesContext } from './widget/host-bridges';
