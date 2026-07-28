/**
 * What the front page offers to open, and which figures it puts on the cards
 * (9-5f / A5, port of ALT `HomeOverview.tsx:135-234`).
 *
 * Data, not markup, for two reasons: the nav targets can then be checked against
 * the view registry in a unit test (a card pointing at a slug nobody serves is a
 * dead end on the studio's front page), and labels are *read* from that registry
 * instead of copied — ALT kept its own `label` per card, which is how its
 * "Quality" card came to open a page titled "Analyse".
 *
 * Figures come in two kinds, deliberately handled differently:
 *
 *  - **measurable** (patterns, personas, intents, states, entities, signals):
 *    from `GET /api/config/elements`. Missing ⇒ the card shows no figure. ALT
 *    substituted `?? 16`, `?? 6`, `?? 8`, `?? 3`, `?? 5`, `?? 17`, so the first
 *    paint asserted six counts nobody had measured, and a failed request left
 *    them standing.
 *  - **not measurable here** (the 18 material types): no endpoint exposes them,
 *    so the number is checked in with its source named below and can be
 *    re-counted by hand.
 */
import { STUDIO_VIEWS, type StudioView } from '../studio-views';

/** The six element lists an editor can grow, as counts. */
export interface ElementCounts {
  readonly patterns: number;
  readonly personas: number;
  readonly intents: number;
  readonly states: number;
  readonly entities: number;
  readonly signals: number;
}

/** The shape `GET /config/elements` answers with, narrowed to what is counted. */
export interface ElementsPayload {
  readonly patterns?: readonly unknown[];
  readonly personas?: readonly unknown[];
  readonly intents?: readonly unknown[];
  readonly states?: readonly unknown[];
  readonly entities?: readonly unknown[];
  readonly signals?: readonly unknown[];
}

export interface OverviewCard {
  /** Which view this card opens; must exist in STUDIO_VIEWS. */
  readonly slug: string;
  readonly icon: string;
}

export interface LayerCard extends OverviewCard {
  /** 1…6 — the prompt layer this configures, in assembly order. */
  readonly num: number;
  /** The question this layer answers, in the editor's words. */
  readonly headline: string;
  /** The figure line; '' when it needs counts that have not arrived. */
  primary(counts: ElementCounts | null): string;
  /** Chips under the headline; the numeric ones drop out without counts. */
  tags(counts: ElementCounts | null): readonly string[];
}

const size = (list: readonly unknown[] | undefined): number => list?.length ?? 0;

/**
 * Six counts, or null when there is no payload at all — the caller then renders
 * no figures rather than zeros.
 */
export function elementCounts(payload: ElementsPayload | null | undefined): ElementCounts | null {
  if (!payload) return null;
  return {
    patterns: size(payload.patterns), personas: size(payload.personas),
    intents: size(payload.intents), states: size(payload.states),
    entities: size(payload.entities), signals: size(payload.signals),
  };
}

/** The registry entry for a slug — label, description and group in one place. */
export function viewOf(slug: string): StudioView {
  const view = STUDIO_VIEWS.find((v) => v.slug === slug);
  if (!view) throw new Error(`Unbekannter View-Slug: ${slug}`);
  return view;
}

export const LAYER_CARDS: readonly LayerCard[] = [
  {
    num: 1, slug: 'identitaet', icon: '🛡️',
    headline: 'Wer ist der Chatbot? Was darf er nie tun?',
    primary: () => 'Persona · Guardrails · Safety · Policy',
    tags: () => ['Basis-Persona', 'Guardrails', 'Safety-Preset', 'Policy-Regeln'],
  },
  {
    num: 2, slug: 'domain-wissen', icon: '🌐',
    headline: 'Was weiß der Chatbot über WLO und seine Umgebung?',
    primary: () => 'Plattform-Wissen · Domain-Regeln',
    tags: () => ['Domain-Rules', 'WLO-Fachwissen', 'Web-Tour'],
  },
  {
    num: 3, slug: 'patterns', icon: '🧩',
    headline: 'Der LLM-Hint wählt das passende Pattern.',
    primary: (counts) => (counts ? `${counts.patterns} Patterns` : ''),
    tags: () => ['Inhalte abrufen', 'Material-Erstellung', 'Recherche', 'Safety-Pattern'],
  },
  {
    num: 4, slug: 'dimensionen', icon: '🎭',
    headline: 'Wie wird jeder Nutzer-Input klassifiziert?',
    primary: (counts) =>
      counts ? `${counts.personas} Personas · ${counts.intents} Intents` : '',
    tags: (counts) => [
      ...(counts
        ? [`${counts.states} States`, `${counts.entities} Entities`, `${counts.signals} Signale`]
        : []),
      'Turn-Count', 'Tonalitäts-Modifier',
    ],
  },
  {
    num: 5, slug: 'material-formate', icon: '🎨',
    headline: 'Wie sieht KI-generierter Inhalt im Chat aus?',
    // Counted in `05-canvas/material-types.yaml`: 19 entries, of which `auto` is
    // the "pick one for me" selector rather than a type ⇒ 18 types, 13
    // didaktisch + 5 analytisch. No endpoint reports this, so it cannot be live.
    primary: () => '18 Material-Typen',
    tags: () => ['13 didaktisch', '5 analytisch', 'Typ-Aliase', 'Edit-/Create-Trigger'],
  },
  {
    num: 6, slug: 'wissen', icon: '📚',
    headline: 'Welche Quellen liefern Faktenwissen zur Laufzeit?',
    primary: () => 'RAG + MCP-Tools',
    tags: () => ['Always-on RAG', 'On-Demand RAG', 'MCP-Server', 'Themenseiten-Resolver'],
  },
];

/**
 * Operations, in ALT's order. Label and description come from the registry, so
 * only the icon lives here.
 */
export const OPS_CARDS: readonly OverviewCard[] = [
  { slug: 'sessions', icon: '💬' },
  { slug: 'analyse', icon: '📊' },
  { slug: 'evaluation', icon: '🎯' },
  { slug: 'safety-logs', icon: '🛡️' },
  { slug: 'datenschutz', icon: '🔒' },
  // ALT's third quick-access button opened the snapshots modal. It is a view
  // since 9-6, so it belongs with the other operations rather than in a second
  // button row that duplicates cards on this very page.
  { slug: 'sicherung', icon: '📦' },
];
