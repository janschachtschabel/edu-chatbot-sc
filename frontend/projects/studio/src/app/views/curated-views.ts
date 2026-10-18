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

import type { FeldGruppe } from '../schema-form/form-sections';
import { AGENT_SEITEN } from './curated-pages-agent';
import { BETRIEB_SEITEN } from './curated-pages-betrieb';
import { GEMEINSAME_SEITEN } from './curated-pages-gemeinsam';
import { INHALT_SEITEN } from './curated-pages-inhalt';

/** Ein Hinweis am Abschnitt: ein Text-Schlüssel, mit Parametern (Rundgang 3). */
export type Hinweis = string | { readonly key: string; readonly params: Readonly<Record<string, string | number>> };

/** Rundgang 3: benannte Feldgruppen eines Abschnitts (siehe `schema-form/form-sections.ts`). */
export type { FeldGruppe };

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
  /** Which element list counts this section in a tabbed page (ST-4c): the
   *  number comes from `GET /config/elements`, one request for all tabs. */
  readonly count?: 'personas' | 'intents' | 'states' | 'entities' | 'signals';
  /** Paket 14: nur diese Felder zeigen (Wurzel-Schlüssel oder `gruppe.feld`, siehe
   *  `pickFields`). `01-base/engine` trägt Felder beider Arbeitsbereiche; jede Seite zeigt
   *  ihren Ausschnitt — gespeichert wird weiter das ganze Dokument. */
  readonly felder?: readonly string[];
  /** Paket 15: das Gegenstück zu `felder` — alle Felder außer diesen. Die Personas unter
   *  „Dimensionen“ zeigen die Anrede nicht mehr; sie steht auf „Zielgruppen“. */
  readonly ohneFelder?: readonly string[];
  /** Paket 16, C8: in diesem Arbeitsbereich steht der Abschnitt zuerst (und ist offen) — die
   *  Skill-Brücke wirkt nur im Muster-Modus, auf der gemeinsamen Seite „Skills“ stand sie
   *  dort als dritte und zugeklappt. */
  readonly zuerstIn?: 'agent' | 'pattern';
  /** Paket 14, nur `kind: 'group'`: nur diese Dokumente der Gruppe wählbar (die beiden
   *  Schutzantworten im Agent-Arbeitsbereich); Anlegen und Löschen sind dort aus. */
  readonly dokumente?: readonly string[];
  /** Paket 15: Einstellungen, die einander aushebeln — Katalog-Schlüssel der Hinweise, aus dem
   *  aktuellen Entwurf berechnet (fehlende Schlüssel zählen mit ihrer Vorgabe). */
  readonly hinweise?: (doc: Readonly<Record<string, unknown>>) => readonly Hinweis[];
  /** Rundgang 3: das Formular in benannte Gruppen gliedern — ein Editor, ein Speichern. */
  readonly gruppen?: readonly FeldGruppe[];
  /** Rundgang 3: ein Sprung zu einer Seite, auf der man prüft, was hier eingestellt wird. */
  readonly sprung?: { readonly labelKey: string; readonly slug: string };
  /** Paket 15: der Reiter der Seite, in dem der Abschnitt steht (`CuratedView.reiter`). */
  readonly reiter?: string;
}

/**
 * A panel that is NOT a config document (9-4e). "Wissen" needs three: the
 * knowledge areas live in the database, ingesting a document is an upload, and
 * the MCP registry has endpoints of its own that add live tool descriptions and
 * an SSRF check on write. None of the three can be a schema form, and all three
 * belong on the same page as the config that describes them. The same holds
 * for `privacy-purge` (ST-6): deleting across all sessions is an action on the
 * database, next to the settings that decide what gets stored — and so for
 * `retention` (Paket 8): what the retention periods mean in rows right now.
 */
export interface CuratedPanelSection {
  readonly panel:
    | 'rag-areas' | 'rag-ingest' | 'mcp-registry' | 'agent-tester' | 'master-skill'
    | 'privacy-purge' | 'retention' | 'agent-tools' | 'agent-skills' | 'agent-prompt'
    | 'agent-probe' | 'anrede' | 'material-typen';
  readonly labelKey: string;
  readonly hintKey: string;
  /** Paket 15: der Reiter der Seite, in dem das Panel steht (`CuratedView.reiter`). */
  readonly reiter?: string;
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
  /** `tabs`: one tab per section plus a head card with the counts (ST-4c,
   *  ALT's dimensions page); otherwise the sections stack as disclosures. */
  readonly layout?: 'tabs';
  /** Paket 15: Reiter über den Abschnitten (Panels wie Bereiche) — jeder Abschnitt nennt
   *  seinen. Anders als `layout: 'tabs'` bleiben alle Abschnitte eingehängt: ein Wechsel
   *  verliert keine ungespeicherte Änderung. */
  readonly reiter?: readonly { readonly id: string; readonly labelKey: string }[];
}

/** Alle kuratierten Seiten in der Reihenfolge der Navigation — die Daten
 *  stehen nach Seitengruppen in `curated-pages-*.ts` (Paket 6). */
export const CURATED_VIEWS: readonly CuratedView[] = [
  ...AGENT_SEITEN, ...INHALT_SEITEN, ...GEMEINSAME_SEITEN, ...BETRIEB_SEITEN,
];

export function curatedView(slug: string): CuratedView | undefined {
  return CURATED_VIEWS.find((view) => view.slug === slug);
}
