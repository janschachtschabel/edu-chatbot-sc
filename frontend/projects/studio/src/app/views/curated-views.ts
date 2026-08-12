/**
 * What each curated config view puts on one page (9-4b).
 *
 * ALT built one hand-written React component per view — ~6 300 TSX lines that
 * mostly re-implemented "load an area, show its fields, save it". 9-3 already
 * renders any area from its schema, so what is left is genuinely editorial:
 * WHICH areas belong to one job, in what order, and what each is for. That is
 * data, so it lives here as data.
 *
 * Two rules this file must keep:
 *   - a FILE key addresses one document and gets a plain form section;
 *     `03-patterns` and `04-personas` address a folder and must be marked
 *     `kind: 'group'`, which renders a picker plus the form of one document.
 *   - the section order is the reading order of the page. The first section is
 *     open on arrival; the rest load when they are opened.
 *
 * Areas no view lists stay reachable through „Alle Bereiche" (9-3) — that
 * escape hatch is why this list may stay editorial instead of exhaustive.
 *
 * Since C1-d3d this file holds STRUCTURE only. The 70 sentences that used to
 * stand here live in `i18n/catalogue/curated.ts`; what remains are catalogue
 * KEYS. Finished text on module level freezes in whichever language was active
 * when the module loaded — the same defect as `CONFIRM_LEAVE` (C1-d3a) and
 * `PREVIEW_CONTEXT_KINDS` (C1-d3b), twenty times over. The keys are written out
 * rather than composed from the slug: one built at runtime would render itself
 * as a heading the moment a name drifts, and no test could see it.
 */

export interface CuratedAreaSection {
  /** Config area key, exactly as the registry spells it. */
  readonly area: string;
  /** `group` = the key is a folder of documents (`03-patterns`). */
  readonly kind?: 'file' | 'group';
  /** Heading for the section — what the editor is changing, not the filename. */
  readonly labelKey: string;
  /** One line on what this area decides. */
  readonly hintKey: string;
  /**
   * Something the generated form alone cannot do for this area. Every value
   * gets its own branch in the section template rather than a plugin mechanism
   * nobody asked for:
   *  - `safety-level` — the picker §5.6 names, shown above the form.
   *  - `pattern-tabs` — ALT's five field tabs (A7). A pattern document carries
   *    21 head fields plus the instruction text; in one fieldset that is a
   *    wall. The cut itself lives in `pattern-field-tabs.ts`.
   */
  readonly feature?: 'safety-level' | 'pattern-tabs';
}

/**
 * A panel that is NOT a config document (9-4e). "Wissen" needs three: the
 * knowledge areas live in the database, ingesting a document is an upload, and
 * the MCP registry has endpoints of its own that add live tool descriptions and
 * an SSRF check on write. None of the three can be a schema form, and all three
 * belong on the same page as the config that describes them.
 */
export interface CuratedPanelSection {
  readonly panel: 'rag-areas' | 'rag-ingest' | 'mcp-registry';
  readonly labelKey: string;
  readonly hintKey: string;
}

export type CuratedSection = CuratedAreaSection | CuratedPanelSection;

/** Narrows the union — a panel has no area key and no schema. */
export function isAreaSection(section: CuratedSection): section is CuratedAreaSection {
  return 'area' in section;
}

export interface CuratedView {
  /** Route slug — must be a `paket: '9-4'` entry in STUDIO_VIEWS. */
  readonly slug: string;
  /** Lead paragraph: what this page is for, in the editor's language. */
  readonly introKey: string;
  readonly sections: readonly CuratedSection[];
}

export const CURATED_VIEWS: readonly CuratedView[] = [
  {
    slug: 'begruessung',
    introKey: 'curated.begruessung.intro',
    sections: [
      {
        area: '01-base/welcome-config',
        labelKey: 'curated.begruessung.welcome.label',
        hintKey: 'curated.begruessung.welcome.hint',
      },
    ],
  },
  {
    slug: 'kontext-aktionen',
    introKey: 'curated.kontextAktionen.intro',
    sections: [
      {
        area: '01-base/context-actions',
        labelKey: 'curated.kontextAktionen.actions.label',
        hintKey: 'curated.kontextAktionen.actions.hint',
      },
    ],
  },
  {
    slug: 'identitaet',
    introKey: 'curated.identitaet.intro',
    sections: [
      {
        area: '01-base/safety-config',
        labelKey: 'curated.identitaet.safety.label',
        hintKey: 'curated.identitaet.safety.hint',
        feature: 'safety-level',
      },
      {
        area: '01-base/base-persona',
        labelKey: 'curated.identitaet.persona.label',
        hintKey: 'curated.identitaet.persona.hint',
      },
      {
        area: '01-base/guardrails',
        labelKey: 'curated.identitaet.guardrails.label',
        hintKey: 'curated.identitaet.guardrails.hint',
      },
      {
        area: '01-base/policy',
        labelKey: 'curated.identitaet.policy.label',
        hintKey: 'curated.identitaet.policy.hint',
      },
    ],
  },
  {
    slug: 'domain-wissen',
    introKey: 'curated.domainWissen.intro',
    sections: [
      {
        area: '02-domain/domain-rules',
        labelKey: 'curated.domainWissen.rules.label',
        hintKey: 'curated.domainWissen.rules.hint',
      },
      {
        area: '02-domain/wlo-plattform-wissen',
        labelKey: 'curated.domainWissen.platform.label',
        hintKey: 'curated.domainWissen.platform.hint',
      },
      {
        area: '01-base/website-tour',
        labelKey: 'curated.domainWissen.tour.label',
        hintKey: 'curated.domainWissen.tour.hint',
      },
    ],
  },
  {
    slug: 'material-formate',
    introKey: 'curated.materialFormate.intro',
    sections: [
      {
        area: '05-canvas/material-types',
        labelKey: 'curated.materialFormate.types.label',
        hintKey: 'curated.materialFormate.types.hint',
      },
      {
        area: '05-canvas/type-aliases',
        labelKey: 'curated.materialFormate.aliases.label',
        hintKey: 'curated.materialFormate.aliases.hint',
      },
      {
        area: '05-canvas/create-triggers',
        labelKey: 'curated.materialFormate.create.label',
        hintKey: 'curated.materialFormate.create.hint',
      },
      {
        area: '05-canvas/edit-triggers',
        labelKey: 'curated.materialFormate.edit.label',
        hintKey: 'curated.materialFormate.edit.hint',
      },
      {
        area: '05-canvas/persona-priorities',
        labelKey: 'curated.materialFormate.priorities.label',
        hintKey: 'curated.materialFormate.priorities.hint',
      },
    ],
  },
  {
    slug: 'patterns',
    introKey: 'curated.patterns.intro',
    sections: [
      {
        area: '03-patterns',
        kind: 'group',
        labelKey: 'curated.patterns.patterns.label',
        hintKey: 'curated.patterns.patterns.hint',
        feature: 'pattern-tabs',
      },
    ],
  },
  {
    slug: 'dimensionen',
    introKey: 'curated.dimensionen.intro',
    sections: [
      {
        area: '04-personas',
        kind: 'group',
        labelKey: 'curated.dimensionen.personas.label',
        hintKey: 'curated.dimensionen.personas.hint',
      },
      {
        area: '04-intents/intents',
        labelKey: 'curated.dimensionen.intents.label',
        hintKey: 'curated.dimensionen.intents.hint',
      },
      {
        area: '04-states/states',
        labelKey: 'curated.dimensionen.states.label',
        hintKey: 'curated.dimensionen.states.hint',
      },
      {
        area: '04-entities/entities',
        labelKey: 'curated.dimensionen.entities.label',
        hintKey: 'curated.dimensionen.entities.hint',
      },
      {
        area: '04-signals/signal-modulations',
        labelKey: 'curated.dimensionen.signals.label',
        hintKey: 'curated.dimensionen.signals.hint',
      },
      {
        area: '01-base/tone-modifiers',
        labelKey: 'curated.dimensionen.tone.label',
        hintKey: 'curated.dimensionen.tone.hint',
      },
    ],
  },
  {
    slug: 'anzeige',
    introKey: 'curated.anzeige.intro',
    sections: [
      {
        area: '01-base/display-rules',
        labelKey: 'curated.anzeige.display.label',
        hintKey: 'curated.anzeige.display.hint',
      },
      {
        area: '01-base/header-nav',
        labelKey: 'curated.anzeige.header.label',
        hintKey: 'curated.anzeige.header.hint',
      },
      {
        area: '01-base/device-config',
        labelKey: 'curated.anzeige.devices.label',
        hintKey: 'curated.anzeige.devices.hint',
      },
    ],
  },
  {
    slug: 'datenschutz',
    introKey: 'curated.datenschutz.intro',
    sections: [
      {
        area: '01-base/privacy-config',
        labelKey: 'curated.datenschutz.privacy.label',
        hintKey: 'curated.datenschutz.privacy.hint',
      },
      {
        area: '01-base/quality-log-config',
        labelKey: 'curated.datenschutz.qualityLog.label',
        hintKey: 'curated.datenschutz.qualityLog.hint',
      },
    ],
  },
  {
    slug: 'wissen',
    introKey: 'curated.wissen.intro',
    sections: [
      {
        panel: 'rag-areas',
        labelKey: 'curated.wissen.areas.label',
        hintKey: 'curated.wissen.areas.hint',
      },
      {
        panel: 'rag-ingest',
        labelKey: 'curated.wissen.ingest.label',
        hintKey: 'curated.wissen.ingest.hint',
      },
      {
        // Describes the areas the panel above lists — only useful together,
        // which is why this config sits between them and not on its own page.
        area: '05-knowledge/rag-config',
        labelKey: 'curated.wissen.ragConfig.label',
        hintKey: 'curated.wissen.ragConfig.hint',
      },
      {
        panel: 'mcp-registry',
        labelKey: 'curated.wissen.mcp.label',
        hintKey: 'curated.wissen.mcp.hint',
      },
    ],
  },
];

export function curatedView(slug: string): CuratedView | undefined {
  return CURATED_VIEWS.find((view) => view.slug === slug);
}
