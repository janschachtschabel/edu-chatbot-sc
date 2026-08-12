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
 */

/** Sidebar grouping, in display order. `null` = the ungrouped first item. */
export type StudioGroup = 'start' | 'konfiguration' | 'auswertung' | 'system';

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
   *  everything ported from ALT, or the package that invented it (K5). */
  readonly paket: string;
}

export const STUDIO_VIEWS: readonly StudioView[] = [
  {
    slug: 'uebersicht', labelKey: 'view.uebersicht.label', descKey: 'view.uebersicht.desc',
    group: 'start', paket: '9-5',
  },
  {
    slug: 'begruessung', labelKey: 'view.begruessung.label', descKey: 'view.begruessung.desc',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'kontext-aktionen', labelKey: 'view.kontext-aktionen.label',
    descKey: 'view.kontext-aktionen.desc', group: 'konfiguration', paket: '9-4',
  },
  {
    // "Geräte" stood in this description until 9-4c: device-config belongs to
    // Anzeige (§5.6), and naming it in two places would send editors astray.
    slug: 'identitaet', labelKey: 'view.identitaet.label', descKey: 'view.identitaet.desc',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'domain-wissen', labelKey: 'view.domain-wissen.label',
    descKey: 'view.domain-wissen.desc', group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'patterns', labelKey: 'view.patterns.label', descKey: 'view.patterns.desc',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'dimensionen', labelKey: 'view.dimensionen.label', descKey: 'view.dimensionen.desc',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'material-formate', labelKey: 'view.material-formate.label',
    descKey: 'view.material-formate.desc', group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'wissen', labelKey: 'view.wissen.label', descKey: 'view.wissen.desc',
    group: 'konfiguration', paket: '9-4',
  },
  {
    slug: 'sessions', labelKey: 'view.sessions.label', descKey: 'view.sessions.desc',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'analyse', labelKey: 'view.analyse.label', descKey: 'view.analyse.desc',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'evaluation', labelKey: 'view.evaluation.label', descKey: 'view.evaluation.desc',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'lasttest', labelKey: 'view.lasttest.label', descKey: 'view.lasttest.desc',
    group: 'auswertung', paket: '9-5',
  },
  {
    slug: 'safety-logs', labelKey: 'view.safety-logs.label', descKey: 'view.safety-logs.desc',
    group: 'auswertung', paket: '9-5',
  },
  {
    // Kein ALT-Gegenstück: ALT rechnete überhaupt nicht ab. Die Ansicht kommt
    // mit der Kostenüberwachung (K5), nicht aus dem P9-Port.
    slug: 'kosten', labelKey: 'view.kosten.label', descKey: 'view.kosten.desc',
    group: 'auswertung', paket: 'K5',
  },
  {
    slug: 'anzeige', labelKey: 'view.anzeige.label', descKey: 'view.anzeige.desc',
    group: 'system', paket: '9-4',
  },
  {
    slug: 'datenschutz', labelKey: 'view.datenschutz.label', descKey: 'view.datenschutz.desc',
    group: 'system', paket: '9-4',
  },
  {
    slug: 'bereiche', labelKey: 'view.bereiche.label', descKey: 'view.bereiche.desc',
    group: 'system', paket: '9-3',
  },
  {
    // ALT reached this through three header buttons and a modal; 9-2 recorded it
    // as "header chrome" and left it out of the view count. 9-6 makes it a view —
    // see backup.component.ts for why the modal was not rebuilt.
    slug: 'sicherung', labelKey: 'view.sicherung.label', descKey: 'view.sicherung.desc',
    group: 'system', paket: '9-6',
  },
  {
    // Verbesserung V8, kein ALT-Gegenstück: dort ließ sich eine Änderung nur
    // auf einer echten Host-Seite ansehen.
    slug: 'vorschau', labelKey: 'view.vorschau.label', descKey: 'view.vorschau.desc',
    group: 'system', paket: '9-6',
  },
];

/** The view the studio opens on. */
export const DEFAULT_VIEW = 'uebersicht';

const GROUP_TITLE_KEYS: Record<StudioGroup, string | null> = {
  start: null, // the single Übersicht entry sits above the first heading
  konfiguration: 'nav.group.konfiguration',
  auswertung: 'nav.group.auswertung',
  system: 'nav.group.system',
};

const GROUP_ORDER: readonly StudioGroup[] = ['start', 'konfiguration', 'auswertung', 'system'];

export interface NavGroup {
  /** Catalogue key of the group heading; `null` = no heading at all. */
  readonly titleKey: string | null;
  readonly views: readonly StudioView[];
}

/** Sidebar structure — grouped, in display order, empty groups dropped. */
export const NAV_GROUPS: readonly NavGroup[] = GROUP_ORDER.map((group) => ({
  titleKey: GROUP_TITLE_KEYS[group],
  views: STUDIO_VIEWS.filter((v) => v.group === group),
})).filter((g) => g.views.length > 0);
