/**
 * English catalogue (C1-c). Same keys as `de.ts`, which stays the fallback:
 * a gap here shows German, never emptiness.
 *
 * Built into the bundle, not fetched — measured at the C1-b1 gate there is
 * enough budget headroom (see `docs/plans/2026-08-02-c1-i18n.md`, "Korrektur
 * 2026-08-02"). No second request means no loading state, no error path and no
 * flash of the wrong language.
 *
 * Typography follows the *target* language, not the source: English uses
 * “curly double quotes” where German uses „…" — the German catalogue's comment
 * on `widget.nav.*` reserved exactly that freedom. Placeholders (`{title}`) are
 * identical to the German ones by contract; a spec pins that.
 */
import { Catalogue } from './dictionary';

export const EN: Catalogue = {
  // ── Custom element shell (widget.component.html) ───────────────────
  // EU AI Act Art. 50 — see the German catalogue for the reasoning.
  'chat.aiGenerated': 'AI-generated answer',
  'widget.open': 'Open chat',
  'widget.close': 'Close',
  'widget.restart': 'New chat',

  'widget.size.larger': 'Enlarge chat',
  'widget.size.smaller': 'Shrink chat',

  'widget.tourStart': 'Start web tour',
  'widget.tourHint': 'Click me — I will show you around',

  'widget.status.thinking': 'thinking …',
  'widget.status.speaking': 'speaking …',

  'widget.speech.on': 'Speech output on',
  'widget.speech.off': 'Speech output off',
  'widget.debug.on': 'Debug on',
  'widget.debug.off': 'Debug off',

  /** Accessible name of the language toggle — it names the TARGET language,
   *  because that is what the button does. */
  'widget.language.toDe': 'Switch to German',
  'widget.language.toEn': 'Switch to English',

  'widget.nav.askBefore': 'Shall I take you to “',
  'widget.nav.askAfter': '”?',
  'widget.nav.confirm': 'Take me there',
  'widget.nav.cancel': 'Stay here',

  // ── Chat shell: history, print bars, input footer ──────────────────
  'chat.log': 'Chat history',
  'chat.speak': 'Read aloud',
  'chat.speakStop': 'Stop',
  'chat.record.start': 'Start voice input',
  'chat.record.stop': 'Stop recording',
  'chat.send': 'Send',
  'chat.hostTask': 'Task from the page',

  'chat.input.label': 'Message to BOERDi',
  'chat.input.placeholder': 'Type a message…',
  'chat.input.thinking': 'Boerdi is thinking…',
  'chat.input.recording': 'Recording… click Stop to finish',

  'chat.print.learningPathTitle': 'Print learning path as PDF',
  'chat.print.learningPath': 'Print learning path / save as PDF',
  'chat.print.materialTitle': 'Print material as PDF',
  'chat.print.canvas': 'Print {label} / save as PDF',
  'chat.print.canvasFallback': 'Material',

  // ── Flat card list (card-list.component) ───────────────────────────
  'cards.browse': 'Contents',
  'cards.learningPath': 'Learning path',
  'cards.topicPage': 'Topic page',
  'cards.topicPageMore': 'Show more topic pages',
  'cards.topicTooltip.single': 'Open topic page',
  'cards.topicTooltip.more': 'Topic page ({variant}) — more available',
  'cards.showContent': 'Show content',
  'cards.skills.one': '1 skill approved',
  'cards.skills.many': '{count} skills approved',
  'cards.pagination.count': '{visible} of {total} results',
  'cards.pagination.showMore': 'Show more',
  'cards.pagination.loadMore': 'Load more',
  'cards.pagination.loading': 'Loading…',

  // ── Result boxes (result-groups.component) ─────────────────────────
  'groups.topics': 'Topic pages',
  'groups.collections': 'Collections',
  'groups.materials': 'Selected materials',
  'groups.web': 'Web page contents',
  'groups.showContent': 'Show contents of {title} in the chat',
  'groups.webItem': '{title} (web page)',
  'groups.webItemUntitled': 'Web page',
  'groups.cta.withTerm': 'Results for “{term}”',
  'groups.cta.all': 'All results in search',
  'groups.cta.sub': 'Show all matching materials',
  'groups.ctaTooltip.all': 'Show all results in search',
  'groups.ctaTooltip.withTerm': 'Show all results in search for “{term}”',

  // ── Topic-page swimlanes (swimlanes.component) ─────────────────────
  'swimlanes.heading': '{heading} (excerpt)',
  'swimlanes.headingFallback': 'Contents',
  'swimlanes.cta.title': 'Go to the full topic page: {title}',
  'swimlanes.cta.label': 'Go to the topic page “{title}”',
  'swimlanes.cta.sub': 'View all contents on the topic page',

  // ── Inline document box (inline-documents.component) ───────────────
  'inlineDoc.print': 'Print / save as PDF',

  'inlineDoc.kind.lernpfad': 'Learning path',
  'inlineDoc.kind.ki_material': 'Material',
  'inlineDoc.kind.edit': 'Edited version',
  'inlineDoc.kind.bericht': 'Report',
  'inlineDoc.kind.remix': 'Remix',
  'inlineDoc.kind.fallback': 'Content',

  // ── Content types (C1-b3) ──────────────────────────────────────────
  'contentType.topicPage': 'Topic page',
  'contentType.collection': 'Collection',
  'contentType.video': 'Video',
  'contentType.worksheet': 'Worksheet',
  'contentType.interactive': 'Interactive content',
  'contentType.audio': 'Audio',
  'contentType.quiz': 'Quiz',
  'contentType.presentation': 'Presentation',
  'contentType.exercise': 'Exercise',
  'contentType.course': 'Course',
  'contentType.website': 'Web page',
  'contentType.material': 'Material',
  'contentType.fallback': 'Content',

  // ── Stream loading phases (phase-label) ────────────────────────────
  'phase.connected': 'Connecting …',
  'phase.safety_classify': 'Understanding your request …',
  'phase.context': 'Loading session context …',
  'phase.policy': 'Checking data protection …',
  'phase.pattern': 'Choosing the right answer …',
  'phase.wlo_search': 'Searching WLO contents …',
  'phase.topic_content': 'Loading topic page contents …',
  'phase.response': 'Composing the answer …',
  'phase.query_meta': 'Search results compiled',
  'phase.agent_iteration': 'Working out the next step …',
  'phase.agent_tool': 'Working with WLO contents …',

  // ── Link warning (trusted-host + markdown-renderer) ────────────────
  'link.external': 'Caution! External URL.',

  // ── Quick-reply chips (C1-b4) ──────────────────────────────────────
  'chips.guideFallback': 'Take me there',

  // ── Bot error bubbles (C1-b4) ──────────────────────────────────────
  'error.browseCollection': 'Sorry, I could not load the contents of “{title}”. Please try again!',
  'error.contentText': 'Sorry, I could not load the content of “{title}”. Please try again!',
  'error.learningPath': 'Sorry, I could not create the learning path for “{title}”. Please try again!',
  'error.tourStart': 'Sorry, the tour could not be started just now. Please try again.',
  'error.transcription': 'Voice input could not be processed. Please type your message.',
  'error.generic': 'Sorry, something went wrong. Please try again.',
  'error.stale': 'This is taking unusually long — please ask your question again in '
    + 'a moment. If my answer does finish after all, you will find it '
    + 'in the history the next time you open the chat.',

  // ── Greeting: the FALLBACK only (C1-b4) ────────────────────────────
  /** The regular case is editorial content from `welcome-config.yaml` and stays
   *  German by decision — these six only appear when host and studio config
   *  deliver nothing. */
  'greeting.default': 'Hey, great to have you here! I am Boerdi, the clever owl of '
    + 'WissenLebtOnline.\nI can show you how to bring your knowledge or '
    + 'learning content into the age of AI. Or I can help you find '
    + 'existing content in our database.',
  'greeting.reset': 'Hello! How can I help you?',
  'greeting.reply.aiAge': 'How do I bring my content into the age of AI?',
  'greeting.reply.search': 'I am looking for content on a topic.',
  'greeting.reply.tour': 'Guide me through the website step by step.',
  'greeting.reply.about': 'What is WissenLebtOnline?',

  // ── Print window (print-utils) ─────────────────────────────────────
  'print.button': '🖨 Print / Save as PDF',
  'print.docTitle': '{title} – BadBoerdi',
  'print.learningPath': 'Learning path',
  'print.usedContents': 'Contents used ({count})',
  'print.meta': 'BadBoerdi · {date}',
  'print.footer': 'Created with BadBoerdi · WirLernenOnline.de · {date}',
  'print.popupBlockedMaterial': 'Please allow pop-ups for this page in order to print the material.',
  'print.popupBlockedLearningPath': 'Please allow pop-ups for this page in order to print the learning path.',

  // ── WLO sign-in (C5-c2) ────────────────────────────────────────────
  'auth.signIn': 'Sign in with your WLO account',
  'auth.done': 'You are signed in with your WLO account. From now on I act in your name.',
  'auth.denied': 'Understood, no sign-in. I can still search and show things — I cannot change anything in WLO.',
  'auth.popupBlocked': 'Your browser blocked the sign-in window. Please allow pop-ups for this page, then tap the chip again.',
  'auth.unavailable': 'This installation does not offer WLO sign-in. Searching and showing still work.',
  'auth.timeout': 'Nothing came back from the sign-in. You can try again at any time.',
  'auth.failed': 'The sign-in did not work. Please try again.',
  'auth.signOut': 'Sign out — search anonymously again',
  'auth.signedOut': 'Signed out. I am searching anonymously again — the access is gone from this tab.',

  // ── Prepared change in the repository (E4) ─────────────────────────
  'prepared.done': 'Done — the change is saved in the repository.',
  'prepared.blocked': 'I am not allowed to carry out this change from here. Nothing was changed.',
  'prepared.signedOut': 'You are not signed in to the repository right now, so I changed '
    + 'nothing. Sign in on this tab and tell me again.',
  'prepared.unreachable': 'I could not establish with the repository who you are. '
    + 'Nothing was changed.',
  'prepared.failed': 'The repository refused the change. Nothing was changed.',

  // ── Format values, not texts ───────────────────────────────────────
  /** `lang` marking of the print document (WCAG 3.1.1). */
  'format.htmlLang': 'en',
  /** BCP-47 tag for `toLocaleDateString` in the print window. `en-GB` and not
   *  `en-US`: WLO is a European offering, so "2 August 2026" over "August 2". */
  'format.dateLocale': 'en-GB',
};
