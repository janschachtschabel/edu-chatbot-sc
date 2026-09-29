/**
 * Where each config area lives outside "Alle Bereiche" (ST-9).
 *
 * Three kinds of home: a section of a curated page (`CURATED_VIEWS`), a section
 * embedded in a dashboard page (`DASHBOARD_SECTIONS` — the price table beside
 * the costs it prices, the gold flows beside the runs that play them), and a
 * panel that edits an area through endpoints of its own (`PANEL_AREAS`).
 *
 * Data in one place rather than only in the templates, so the guards see all of
 * it: every area has a page (`curated-view.component.spec.ts`), and every field
 * shown as a form has its texts (`i18n/catalogue/fields.spec.ts`).
 */
import {
  CURATED_VIEWS, type CuratedAreaSection, type CuratedPanelSection, isAreaSection,
} from './curated-views';

/** Config areas edited on a dashboard page rather than on a curated one. */
export const DASHBOARD_SECTIONS = {
  kosten: [{
    area: '01-base/pricing',
    labelKey: 'curated.kosten.pricing.label',
    hintKey: 'curated.kosten.pricing.hint',
  }],
  evaluation: [{
    area: 'eval/gold-flows',
    labelKey: 'curated.evaluation.goldFlows.label',
    hintKey: 'curated.evaluation.goldFlows.hint',
  }],
} as const satisfies Readonly<Record<string, readonly CuratedAreaSection[]>>;

/** Areas a panel edits through its own endpoints — no schema form, so no field texts. */
export const PANEL_AREAS: Readonly<Partial<Record<CuratedPanelSection['panel'], string>>> = {
  'mcp-registry': '05-knowledge/mcp-servers',
};

/** Every area shown as a schema form on some page — curated or dashboard. */
export function areasWithForm(): ReadonlySet<string> {
  return new Set([
    ...CURATED_VIEWS.flatMap((view) => view.sections.filter(isAreaSection).map((s) => s.area)),
    ...Object.values(DASHBOARD_SECTIONS).flatMap((sections) => sections.map((s) => s.area)),
  ]);
}

/** Every area reachable from a page other than "Alle Bereiche". */
export function areasWithPage(): ReadonlySet<string> {
  return new Set([...areasWithForm(), ...Object.values(PANEL_AREAS)]);
}
