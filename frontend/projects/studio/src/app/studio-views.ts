/**
 * The studio's view registry — ONE list that produces both the route table and
 * the sidebar navigation (P9-2, spec §5.6).
 *
 * ALT kept these apart: a `NAV_SECTIONS` array (page.tsx:238-270) and a separate
 * `switch (layer)` render block, so a view could exist in one and not the other —
 * and one did: `Layer` declared `'info'`, which no nav entry and no render branch
 * ever used. Deriving both sides from this array makes that class of drift
 * impossible, and studio-views.spec.ts pins the invariant.
 *
 * ALT had NO routes at all: all 17 views were `useState<Layer>` inside a single
 * page, so there is no URL contract to port. Slugs are therefore new and German,
 * matching the German content convention.
 *
 * Since C1-d2 the registry carries catalogue KEYS rather than the German words:
 * the studio speaks two languages, and a label sitting here would be the one
 * place the switch cannot reach. The slug stays German and stable — it is a URL,
 * not a text, and translating it would break every bookmark on every switch.
 * `i18n/de.ts` holds the words; `studio-views.spec.ts` pins the key convention
 * and `i18n/views-i18n.spec.ts` pins that every key is in both catalogues.
 *
 * Paket 14: the studio has two WORKSPACES, one per engine. Each workspace shows its
 * own block (`agent` or `muster`) and the groups both share. The lists are curated
 * on purpose — deriving them from the effect levels (Paket 13) left every page in
 * place, because nearly every page carries some area that works "partly".
 */
import type { Engine } from './core/effects-api.service';

/** Sidebar grouping. `agent`/`muster` belong to one workspace, the rest to both. */
export type StudioGroup = 'agent' | 'muster' | 'gemeinsam' | 'auswertung' | 'system';

export interface StudioView {
  /** URL segment under /studio/ — also the route path. */
  readonly slug: string;
  /** Catalogue key of the nav label and page heading (`view.<slug>.label`).
   *  ALT had two views where nav label and heading disagreed. */
  readonly labelKey: string;
  /** Catalogue key of the one-line hint under the nav label (ALT `desc`). */
  readonly descKey: string;
  readonly group: StudioGroup;
  /** The slice that replaces the placeholder with the real view — a P9 one for
   *  everything ported from ALT, or the package that invented it (K5, P14). */
  readonly paket: string;
}

function view(slug: string, group: StudioGroup, paket: string): StudioView {
  return { slug, labelKey: `view.${slug}.label`, descKey: `view.${slug}.desc`, group, paket };
}

export const STUDIO_VIEWS: readonly StudioView[] = [
  // ── Agent-Arbeitsbereich (Paket 14) ──
  view('agent-uebersicht', 'agent', 'P14'),
  view('agent-rolle', 'agent', 'P14'),
  view('agent-prompt', 'agent', 'P14'),
  // ── Muster-Arbeitsbereich ──
  view('uebersicht', 'muster', '9-5'),
  view('identitaet', 'muster', '9-4'),
  view('domain-wissen', 'muster', '9-4'),
  view('patterns', 'muster', '9-4'),
  view('dimensionen', 'muster', '9-4'),
  view('material-formate', 'muster', '9-4'),
  // ── Gemeinsam ──
  view('begruessung', 'gemeinsam', '9-4'),
  view('kontext-aktionen', 'gemeinsam', '9-4'),
  view('fuehrung', 'gemeinsam', 'P14'),
  // Paket 15: gelten in beiden Modi (Nutzer-Rundgang 2026-10-17).
  view('zielgruppen', 'gemeinsam', 'P15'),
  view('wissen', 'gemeinsam', '9-4'),
  view('werkzeuge', 'gemeinsam', 'P15'),
  view('skills', 'gemeinsam', 'P15'),
  view('anzeige', 'gemeinsam', '9-4'),
  view('datenschutz', 'gemeinsam', '9-4'),
  // ── Auswertung ──
  // Paket 16 (D3): Besuch und Tageszeit aus dem Qualitätsprotokoll — vor den einzelnen Sessions.
  view('nutzung', 'auswertung', 'P16'),
  view('sessions', 'auswertung', '9-5'),
  view('analyse', 'auswertung', '9-5'),
  view('evaluation', 'auswertung', '9-5'),
  view('lasttest', 'auswertung', '9-5'),
  view('safety-logs', 'auswertung', '9-5'),
  // Kein ALT-Gegenstück: ALT rechnete überhaupt nicht ab. Die Ansicht kommt
  // mit der Kostenüberwachung (K5), nicht aus dem P9-Port.
  view('kosten', 'auswertung', 'K5'),
  // ── System ──
  view('betrieb', 'system', 'P14'),
  view('bereiche', 'system', '9-3'),
  // ALT reached this through three header buttons and a modal; 9-2 recorded it
  // as "header chrome" and left it out of the view count. 9-6 makes it a view —
  // see backup.component.ts for why the modal was not rebuilt.
  view('sicherung', 'system', '9-6'),
  // Verbesserung V8, kein ALT-Gegenstück: dort ließ sich eine Änderung nur
  // auf einer echten Host-Seite ansehen.
  view('vorschau', 'system', '9-6'),
];

/** Die Startseite eines Arbeitsbereichs — Ziel von `/` und des Umschalters. */
export function startView(ansicht: Engine): string {
  return ansicht === 'agent' ? 'agent-uebersicht' : 'uebersicht';
}

/** Der Arbeitsbereich, zu dem eine Seite gehört; `null` = beiden gemeinsam. */
export function workspaceOf(slug: string): Engine | null {
  const group = STUDIO_VIEWS.find((v) => v.slug === slug)?.group;
  return group === 'agent' ? 'agent' : group === 'muster' ? 'pattern' : null;
}

const GROUP_TITLE_KEYS: Record<StudioGroup, string> = {
  agent: 'nav.group.agent',
  muster: 'nav.group.muster',
  gemeinsam: 'nav.group.gemeinsam',
  auswertung: 'nav.group.auswertung',
  system: 'nav.group.system',
};

export interface NavGroup {
  /** Catalogue key of the group heading. */
  readonly titleKey: string;
  readonly views: readonly StudioView[];
}

/** Sidebar structure of one workspace: its own block first, then the shared groups. */
export function navGroups(ansicht: Engine): readonly NavGroup[] {
  const eigen: StudioGroup = ansicht === 'agent' ? 'agent' : 'muster';
  return ([eigen, 'gemeinsam', 'auswertung', 'system'] as const).map((group) => ({
    titleKey: GROUP_TITLE_KEYS[group],
    views: STUDIO_VIEWS.filter((v) => v.group === group),
  }));
}
