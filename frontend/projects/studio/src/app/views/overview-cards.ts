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
import type { Translate } from '../i18n/studio-language.service';
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

/**
 * Ein Text auf einer Karte, samt den Zählungen, die er benennt.
 *
 * Seit C1-d4a ein Schlüssel statt eines fertigen Satzes. Die Zahl steckte
 * vorher in einer Zeichenketten-Verkettung (`${counts.patterns} Patterns`) —
 * also in deutscher Wortstellung, fest verdrahtet; jetzt steht sie als
 * benannter Platzhalter im Katalog, wo die Sprache über ihre Stellung
 * entscheidet.
 *
 * `counts` ist nicht abzuleiten, sondern angemeldet: nur so lässt sich prüfen,
 * dass Text und Datenbedarf zusammenpassen (`overview-cards.spec.ts`).
 */
export interface CardFigure {
  readonly key: string;
  /** Leer = braucht keine Messung und steht immer da. */
  readonly counts: readonly (keyof ElementCounts)[];
}

export interface LayerCard extends OverviewCard {
  /** 1…6 — the prompt layer this configures, in assembly order. */
  readonly num: number;
  /** The question this layer answers, in the editor's words. */
  readonly headlineKey: string;
  /** The figure line; '' when it needs counts that have not arrived. */
  readonly primary: CardFigure;
  /** Chips under the headline; the numeric ones drop out without counts. */
  readonly tags: readonly CardFigure[];
}

const size = (list: readonly unknown[] | undefined): number => list?.length ?? 0;

/** Der fertige Text — `''`, solange eine benötigte Messung fehlt. */
export function figureText(
  figure: CardFigure, counts: ElementCounts | null, t: Translate,
): string {
  if (figure.counts.length === 0) return t(figure.key);
  if (!counts) return '';
  const params: Record<string, number> = {};
  for (const name of figure.counts) params[name] = counts[name];
  return t(figure.key, params);
}

/** Die Chips, die etwas zu sagen haben — ohne Messungen bleiben die reinen
 *  Beschriftungen übrig, nicht leere Kästchen. */
export function visibleTags(
  card: LayerCard, counts: ElementCounts | null, t: Translate,
): readonly string[] {
  return card.tags.map((tag) => figureText(tag, counts, t)).filter((text) => text !== '');
}

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

/** Kurzform für einen Text ohne Messung. */
const flat = (key: string): CardFigure => ({ key, counts: [] });

export const LAYER_CARDS: readonly LayerCard[] = [
  {
    num: 1, slug: 'identitaet', icon: '🛡️',
    headlineKey: 'overview.layer.identitaet.headline',
    primary: flat('overview.layer.identitaet.primary'),
    tags: [
      flat('overview.layer.identitaet.tag.persona'),
      flat('overview.layer.identitaet.tag.guardrails'),
      flat('overview.layer.identitaet.tag.safety'),
      flat('overview.layer.identitaet.tag.policy'),
    ],
  },
  {
    num: 2, slug: 'domain-wissen', icon: '🌐',
    headlineKey: 'overview.layer.domain.headline',
    primary: flat('overview.layer.domain.primary'),
    tags: [
      flat('overview.layer.domain.tag.rules'),
      flat('overview.layer.domain.tag.wlo'),
      flat('overview.layer.domain.tag.tour'),
    ],
  },
  {
    num: 3, slug: 'patterns', icon: '🧩',
    headlineKey: 'overview.layer.patterns.headline',
    primary: { key: 'overview.layer.patterns.primary', counts: ['patterns'] },
    tags: [
      flat('overview.layer.patterns.tag.retrieve'),
      flat('overview.layer.patterns.tag.create'),
      flat('overview.layer.patterns.tag.research'),
      flat('overview.layer.patterns.tag.safety'),
    ],
  },
  {
    num: 4, slug: 'dimensionen', icon: '🎭',
    headlineKey: 'overview.layer.dimensionen.headline',
    primary: { key: 'overview.layer.dimensionen.primary', counts: ['personas', 'intents'] },
    tags: [
      { key: 'overview.layer.dimensionen.tag.states', counts: ['states'] },
      { key: 'overview.layer.dimensionen.tag.entities', counts: ['entities'] },
      { key: 'overview.layer.dimensionen.tag.signals', counts: ['signals'] },
      flat('overview.layer.dimensionen.tag.turnCount'),
      flat('overview.layer.dimensionen.tag.tone'),
    ],
  },
  {
    num: 5, slug: 'material-formate', icon: '🎨',
    headlineKey: 'overview.layer.material.headline',
    // Counted in `05-canvas/material-types.yaml`: 19 entries, of which `auto` is
    // the "pick one for me" selector rather than a type ⇒ 18 types, 13
    // didaktisch + 5 analytisch. No endpoint reports this, so it cannot be live.
    primary: flat('overview.layer.material.primary'),
    tags: [
      flat('overview.layer.material.tag.didactic'),
      flat('overview.layer.material.tag.analytic'),
      flat('overview.layer.material.tag.aliases'),
      flat('overview.layer.material.tag.triggers'),
    ],
  },
  {
    num: 6, slug: 'wissen', icon: '📚',
    headlineKey: 'overview.layer.wissen.headline',
    primary: flat('overview.layer.wissen.primary'),
    tags: [
      flat('overview.layer.wissen.tag.alwaysOn'),
      flat('overview.layer.wissen.tag.onDemand'),
      flat('overview.layer.wissen.tag.mcp'),
      flat('overview.layer.wissen.tag.topics'),
    ],
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
