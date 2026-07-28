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
 * matching the German content convention (labels and slugs stay in sync).
 */

/** Sidebar grouping, in display order. `null` = the ungrouped first item. */
export type StudioGroup = 'start' | 'konfiguration' | 'auswertung' | 'system';

export interface StudioView {
  /** URL segment under /studio/ — also the route path. */
  readonly slug: string;
  /** Nav label and page heading. ALT had two views where these disagreed. */
  readonly label: string;
  /** One-line hint under the nav label (ALT `desc`). */
  readonly desc: string;
  readonly group: StudioGroup;
  /** The P9 slice that replaces the placeholder with the real view. */
  readonly paket: string;
}

export const STUDIO_VIEWS: readonly StudioView[] = [
  {
    slug: 'uebersicht', label: 'Übersicht', desc: 'Start, Architektur & Status',
    group: 'start', paket: '9-5',
  },
  {
    slug: 'begruessung', label: 'Begrüßung', desc: 'Start-Text & Start-Quick-Replies',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'kontext-aktionen', label: 'Kontext-Aktionen',
    desc: 'Proaktive Begrüßung + Pills je Seitentyp', group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'identitaet', label: 'Identität & Schutz',
    // "Geräte" stood here until 9-4c: device-config belongs to Anzeige (§5.6),
    // and naming it in two places would send editors to the wrong page.
    desc: 'Sicherheitslevel, Persona, Leitplanken, Regelwerk',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'domain-wissen', label: 'Domain-Wissen', desc: 'Plattform-Wissen, Web-Tour',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'patterns', label: 'Patterns', desc: 'Gesprächsmuster',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'dimensionen', label: 'Dimensionen', desc: 'Personas, Intents, States, Entities',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'material-formate', label: 'Material-Formate', desc: 'Material-Typen, Aliase, Trigger',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'wissen', label: 'Wissen', desc: 'RAG-Bereiche & MCP-Tools',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'sessions', label: 'Sessions', desc: 'Gesprächsverläufe',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'analyse', label: 'Analyse', desc: 'Pattern-/Intent-Verteilung, Diagnose',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'evaluation', label: 'Evaluation', desc: 'Persona-Dialoge & Gold-Flows',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'lasttest', label: 'Lasttest', desc: 'Skalierbarkeit & Ressourcen',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'safety-logs', label: 'Safety-Logs', desc: 'Risiko-Events & Rate-Limits',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'anzeige', label: 'Anzeige', desc: 'Boxen, Schriftgrößen, Geräte-Limits',
    group: 'system', paket: '9-4',
  },
  {
    slug: 'datenschutz', label: 'Datenschutz', desc: 'Logging & Purge',
    group: 'system', paket: '9-4',
  },
  {
    slug: 'bereiche', label: 'Alle Bereiche', desc: 'Jede Konfigurationsdatei, generisch editierbar',
    group: 'system', paket: '9-3',
  },
  {
    // ALT reached this through three header buttons and a modal; 9-2 recorded it
    // as "header chrome" and left it out of the view count. 9-6 makes it a view —
    // see backup.component.ts for why the modal was not rebuilt.
    slug: 'sicherung', label: 'Sicherung', desc: 'Snapshots, Backup & Werksstand',
    group: 'system', paket: '9-6',
  },
  {
    // Verbesserung V8, kein ALT-Gegenstück: dort ließ sich eine Änderung nur
    // auf einer echten Host-Seite ansehen.
    slug: 'vorschau', label: 'Vorschau', desc: 'Das echte Widget mit dieser Konfiguration',
    group: 'system', paket: '9-6',
  },
];

/** The view the studio opens on. */
export const DEFAULT_VIEW = 'uebersicht';

const GROUP_TITLES: Record<StudioGroup, string | null> = {
  start: null, // the single Übersicht entry sits above the first heading
  konfiguration: 'Konfiguration',
  auswertung: 'Auswertung',
  system: 'System',
};

const GROUP_ORDER: readonly StudioGroup[] = ['start', 'konfiguration', 'auswertung', 'system'];

export interface NavGroup {
  readonly title: string | null;
  readonly views: readonly StudioView[];
}

/** Sidebar structure — grouped, in display order, empty groups dropped. */
export const NAV_GROUPS: readonly NavGroup[] = GROUP_ORDER.map((group) => ({
  title: GROUP_TITLES[group],
  views: STUDIO_VIEWS.filter((v) => v.group === group),
})).filter((g) => g.views.length > 0);
