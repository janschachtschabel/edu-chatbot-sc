/**
 * The tables of the architecture reference (9-5f / A5, from ALT `InfoView.tsx`).
 *
 * Data rather than markup so the long rows stay readable and so the widget table
 * can be counted in a test. Every figure and every identifier below was checked
 * against NEU before it shipped; where ALT's text was wrong or described ALT-only
 * mechanics, the correction is noted at the row.
 *
 * **Seit C1-d5a2 stehen hier nur noch Struktur und Bezeichner.** Jede Zelle mit
 * Prosa trägt einen Katalog-Schlüssel (`i18n/catalogue/reference-rows.ts`), den
 * die Vorlage über `t()` auflöst — dasselbe Muster wie `labelKey` in der
 * Ansichts-Registry seit C1-d2. Was ein Bezeichner ist, entscheidet nicht der
 * Geschmack, sondern die Darstellung: was im `<code>` steht, bleibt Daten.
 * Einzige Ausnahme ist `sourceKey` — zwei der vier Zellen jener Spalte sind
 * Prosa, die ALT ins `<code>` gesetzt hat, und eine Spalte mit zwei Wegen wäre
 * schwerer zu lesen als eine mit einem.
 */

export interface PipelinePhase {
  readonly step: number;
  readonly labelKey: string;
  readonly descKey: string;
}

/** ALT InfoView:132-139. Names match the graph nodes in `graph/build.py`. */
export const PIPELINE: readonly PipelinePhase[] = [
  { step: 1, labelKey: 'arch.row.pipe.1.label', descKey: 'arch.row.pipe.1.desc' },
  { step: 2, labelKey: 'arch.row.pipe.2.label', descKey: 'arch.row.pipe.2.desc' },
  { step: 3, labelKey: 'arch.row.pipe.3.label', descKey: 'arch.row.pipe.3.desc' },
  { step: 4, labelKey: 'arch.row.pipe.4.label', descKey: 'arch.row.pipe.4.desc' },
  { step: 5, labelKey: 'arch.row.pipe.5.label', descKey: 'arch.row.pipe.5.desc' },
  { step: 6, labelKey: 'arch.row.pipe.6.label', descKey: 'arch.row.pipe.6.desc' },
  { step: 7, labelKey: 'arch.row.pipe.7.label', descKey: 'arch.row.pipe.7.desc' },
];

export interface InputDimension {
  readonly elementKey: string;
  readonly descKey: string;
  readonly effectKey: string;
}

/**
 * ALT InfoView:171-206, without its "Anzahl" column: four of those six figures
 * are measured live on the Übersicht tab and the other two are already spelled
 * out in the description, so the column could only ever go stale.
 */
export const INPUT_DIMENSIONS: readonly InputDimension[] = [
  {
    elementKey: 'arch.row.dim.persona.name', descKey: 'arch.row.dim.persona.desc',
    effectKey: 'arch.row.dim.persona.effect',
  },
  {
    elementKey: 'arch.row.dim.intent.name', descKey: 'arch.row.dim.intent.desc',
    effectKey: 'arch.row.dim.intent.effect',
  },
  {
    elementKey: 'arch.row.dim.signals.name', descKey: 'arch.row.dim.signals.desc',
    effectKey: 'arch.row.dim.signals.effect',
  },
  {
    elementKey: 'arch.row.dim.entities.name', descKey: 'arch.row.dim.entities.desc',
    effectKey: 'arch.row.dim.entities.effect',
  },
  {
    elementKey: 'arch.row.dim.state.name', descKey: 'arch.row.dim.state.desc',
    effectKey: 'arch.row.dim.state.effect',
  },
  {
    elementKey: 'arch.row.dim.turnType.name', descKey: 'arch.row.dim.turnType.desc',
    effectKey: 'arch.row.dim.turnType.effect',
  },
];

export interface FieldDoc {
  /** Feldname aus dem Code — steht im `<code>` und bleibt deshalb hier. */
  readonly field: string;
  readonly descKey: string;
}

/** ALT InfoView:247-262 — the modulation output, style half. */
export const MODULATION_STYLE: readonly FieldDoc[] = [
  { field: 'tone', descKey: 'arch.row.style.tone' },
  { field: 'formality', descKey: 'arch.row.style.formality' },
  { field: 'length', descKey: 'arch.row.style.length' },
  { field: 'detail_level', descKey: 'arch.row.style.detailLevel' },
  { field: 'response_type', descKey: 'arch.row.style.responseType' },
  { field: 'format_primary', descKey: 'arch.row.style.formatPrimary' },
  { field: 'format_follow_up', descKey: 'arch.row.style.formatFollowUp' },
  { field: 'sources', descKey: 'arch.row.style.sources' },
];

/** ALT InfoView:269-281 — the modulation output, control half. */
export const MODULATION_CONTROL: readonly FieldDoc[] = [
  { field: 'max_items', descKey: 'arch.row.ctl.maxItems' },
  { field: 'card_text_mode', descKey: 'arch.row.ctl.cardTextMode' },
  { field: 'tools', descKey: 'arch.row.ctl.tools' },
  { field: 'rag_areas', descKey: 'arch.row.ctl.ragAreas' },
  { field: 'core_rule', descKey: 'arch.row.ctl.coreRule' },
  { field: 'skip_intro', descKey: 'arch.row.ctl.skipIntro' },
  { field: 'one_option', descKey: 'arch.row.ctl.oneOption' },
  { field: 'add_sources', descKey: 'arch.row.ctl.addSources' },
  { field: 'degradation', descKey: 'arch.row.ctl.degradation' },
  { field: 'missing_slots', descKey: 'arch.row.ctl.missingSlots' },
  { field: 'blocked_patterns', descKey: 'arch.row.ctl.blockedPatterns' },
];

export interface SelectionStep {
  readonly stepKey: string;
  readonly sourceKey: string;
  readonly effectKey: string;
}

/** ALT InfoView:334-353. */
export const SELECTION_STEPS: readonly SelectionStep[] = [
  {
    stepKey: 'arch.row.sel.1.step', sourceKey: 'arch.row.sel.1.source',
    effectKey: 'arch.row.sel.1.effect',
  },
  {
    stepKey: 'arch.row.sel.2.step', sourceKey: 'arch.row.sel.2.source',
    effectKey: 'arch.row.sel.2.effect',
  },
  {
    stepKey: 'arch.row.sel.3.step', sourceKey: 'arch.row.sel.3.source',
    effectKey: 'arch.row.sel.3.effect',
  },
  {
    stepKey: 'arch.row.sel.4.step', sourceKey: 'arch.row.sel.4.source',
    effectKey: 'arch.row.sel.4.effect',
  },
];

export interface PromptLayer {
  readonly layerKey: string;
  /** Zahl oder Spanne — in jeder Sprache dieselbe. */
  readonly priority: string;
  readonly contentKey: string;
  readonly tokensKey: string;
}

/** ALT InfoView:419-455. */
export const PROMPT_LAYERS: readonly PromptLayer[] = [
  {
    layerKey: 'arch.row.layer.1.name', priority: '1000',
    contentKey: 'arch.row.layer.1.content', tokensKey: 'arch.row.layer.1.tokens',
  },
  {
    layerKey: 'arch.row.layer.2.name', priority: '900',
    contentKey: 'arch.row.layer.2.content', tokensKey: 'arch.row.layer.2.tokens',
  },
  {
    layerKey: 'arch.row.layer.3.name', priority: '500–800',
    contentKey: 'arch.row.layer.3.content', tokensKey: 'arch.row.layer.3.tokens',
  },
  {
    layerKey: 'arch.row.layer.4.name', priority: '300–600',
    contentKey: 'arch.row.layer.4.content', tokensKey: 'arch.row.layer.4.tokens',
  },
  {
    layerKey: 'arch.row.layer.5.name', priority: '200–400',
    contentKey: 'arch.row.layer.5.content', tokensKey: 'arch.row.layer.5.tokens',
  },
  {
    layerKey: 'arch.row.layer.6.name', priority: '100–200',
    contentKey: 'arch.row.layer.6.content', tokensKey: 'arch.row.layer.6.tokens',
  },
];
