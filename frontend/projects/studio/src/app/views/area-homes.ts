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
import type { Engine } from '../core/effects-api.service';
import { navGroups } from '../studio-views';
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
  // Paket 15: die Schalter der Seite „Werkzeuge“ schreiben `werkzeuge_aus` derselben Liste.
  'agent-tools': '05-knowledge/mcp-servers',
  // Paket 14/15: nur Name und Anrede je Persona (Seite „Zielgruppen“).
  anrede: '04-personas',
  // Paket 14 (D3): die Materialtypen als Liste mit Vorschau.
  'material-typen': '05-canvas/material-types',
};

/** Paket 15: the fields a panel writes, when it edits only part of its area — the home guard
 *  needs them, because „Zielgruppen“ and „Dimensionen“ both edit the persona documents. */
export const PANEL_FELDER: Readonly<Partial<Record<CuratedPanelSection['panel'], readonly string[]>>> = {
  anrede: ['frontmatter.formality'],
  // Review-Runde 2: zwei Panels, eine Server-Liste — je Server die Angaben hier, die Schalter dort.
  'mcp-registry': ['id', 'name', 'url', 'description', 'enabled', 'tools', 'tool_schemas'],
  'agent-tools': ['werkzeuge_aus'],
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

/**
 * Paket 15: die Seite, auf der ein Bereich im Arbeitsbereich zu Hause ist — Ziel von „Zurück“
 * im Bereichs-Editor. Ein Dokument einer Gruppe (`03-patterns/m01-…`) gehört zur Gruppe.
 * `null`, wenn der Bereich dort keine Seite hat (dann bleibt „Alle Bereiche“).
 */
export function heimatSeite(area: string, ansicht: Engine): string | null {
  const sichtbar = new Set(navGroups(ansicht).flatMap((g) => g.views.map((v) => v.slug)));
  const passt = (heim: string | undefined) =>
    !!heim && (area === heim || area.startsWith(`${heim}/`));
  for (const view of CURATED_VIEWS) {
    if (!sichtbar.has(view.slug)) continue;
    if (view.sections.some((s) => passt(isAreaSection(s) ? s.area : PANEL_AREAS[s.panel]))) {
      return view.slug;
    }
  }
  const dashboard = Object.entries(DASHBOARD_SECTIONS)
    .find(([slug, sections]) => sichtbar.has(slug) && sections.some((s) => passt(s.area)));
  return dashboard?.[0] ?? null;
}
