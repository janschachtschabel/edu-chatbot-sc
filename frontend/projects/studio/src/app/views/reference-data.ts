/**
 * The tables of the architecture reference (9-5f / A5, from ALT `InfoView.tsx`).
 *
 * Data rather than markup so the long rows stay readable and so the widget table
 * can be counted in a test. Every figure and every identifier below was checked
 * against NEU before it shipped; where ALT's text was wrong or described ALT-only
 * mechanics, the correction is noted at the row.
 */

export interface PipelinePhase {
  readonly step: number;
  readonly label: string;
  readonly desc: string;
}

/** ALT InfoView:132-139. Names match the graph nodes in `graph/build.py`. */
export const PIPELINE: readonly PipelinePhase[] = [
  {
    step: 1, label: 'Safety-Check',
    desc: 'Regex, Moderation und Legal-Klassifikator prüfen die Nachricht; '
      + 'Crisis-/Threat-Marker erzwingen M01 bzw. M02.',
  },
  {
    step: 2, label: 'Klassifikation (LLM)',
    desc: 'Persona, Intent, Pattern-Hint, Signale, Entities, State und Turn-Type '
      + 'erkennen — classify-overrides.yaml liefert die Hard-Override-Anker.',
  },
  {
    step: 3, label: 'Policy-Prüfung',
    desc: 'Tool-Blockaden und Disclaimer anhand von Persona und Intent.',
  },
  {
    step: 4, label: 'Pattern-Wahl',
    desc: 'Safety vor LLM-Hint vor Fallback (M15). Eine Quelle, keine Rule-Engine.',
  },
  {
    step: 5, label: 'Prompt-Zusammensetzung',
    desc: 'Die Schichten werden zum System-Prompt kombiniert.',
  },
  {
    step: 6, label: 'LLM-Aufruf + MCP-Tools',
    desc: 'Das LLM antwortet und ruft bei Bedarf externe Tools auf.',
  },
  {
    step: 7, label: 'Nachbereitung',
    desc: 'Karten extrahieren, Quality-Log schreiben, State speichern.',
  },
];

export interface InputDimension {
  readonly element: string;
  readonly desc: string;
  readonly effect: string;
}

/**
 * ALT InfoView:171-206, without its "Anzahl" column: four of those six figures
 * are measured live on the Übersicht tab and the other two are already spelled
 * out in the description, so the column could only ever go stale.
 */
export const INPUT_DIMENSIONS: readonly InputDimension[] = [
  {
    element: 'Persona', desc: 'Wer spricht? (Lehrkraft, Lernende, Eltern, Presse …)',
    effect: 'Anrede, Tonalität, Policy-Regeln, Tool-Zugang',
  },
  {
    element: 'Intent', desc: 'Was will die Person? (Inhalte abrufen, Fakten, Material erstellen oder bearbeiten, Feedback …)',
    effect: 'Pattern-Wahl, MCP-Tool-Präferenz, spekulative Vorab-Abfragen',
  },
  {
    element: 'Signale', desc: 'Emotionale und situative Hinweise in vier Dimensionen',
    effect: 'Modulieren Ton, Länge und skip_intro — überschreiben Pattern-Defaults',
  },
  {
    element: 'Entities', desc: 'Extrahierte Parameter: Fach, Stufe, Thema, Medientyp, Lizenz',
    effect: 'MCP-Suchparameter, Pattern-Preconditions, Entity-Memory über Turns',
  },
  {
    element: 'State', desc: 'Gesprächszustand: Orientierung → Suche → Kuratierung',
    effect: 'Pattern-Wahl, zustandsabhängiges Verhalten',
  },
  {
    element: 'Turn-Type', desc: 'initial, follow_up, clarification, correction, topic_switch',
    effect: 'Entity-Akkumulation (behalten, ergänzen, überschreiben, zurücksetzen)',
  },
];

export interface FieldDoc {
  readonly field: string;
  readonly desc: string;
}

/** ALT InfoView:247-262 — the modulation output, style half. */
export const MODULATION_STYLE: readonly FieldDoc[] = [
  { field: 'tone', desc: 'Ton der Antwort (sachlich, empathisch, spielerisch …)' },
  { field: 'formality', desc: 'Formalitätsgrad' },
  { field: 'length', desc: 'Antwortlänge (kurz, mittel, lang)' },
  { field: 'detail_level', desc: 'Detailgrad (standard, ausführlich)' },
  { field: 'response_type', desc: 'Antworttyp (answer, question, redirect …)' },
  { field: 'format_primary', desc: 'Primärformat (text, list, cards …)' },
  { field: 'format_follow_up', desc: 'Follow-up-Format' },
  { field: 'sources', desc: 'Wissensquellen (mcp, rag oder leer)' },
];

/** ALT InfoView:269-281 — the modulation output, control half. */
export const MODULATION_CONTROL: readonly FieldDoc[] = [
  { field: 'max_items', desc: 'Höchstzahl der Ergebniskarten' },
  { field: 'card_text_mode', desc: 'Kartentext (minimal, detailed)' },
  { field: 'tools', desc: 'Erzwungene MCP-Tools' },
  { field: 'rag_areas', desc: 'RAG-Wissensbereiche' },
  { field: 'core_rule', desc: 'Kern-Anweisung für das LLM' },
  { field: 'skip_intro', desc: 'Einleitung weglassen' },
  { field: 'one_option', desc: 'Nur einen Vorschlag zeigen' },
  { field: 'add_sources', desc: 'Quellenangaben erzwingen' },
  { field: 'degradation', desc: 'Degradation aktiv?' },
  { field: 'missing_slots', desc: 'Fehlende Precondition-Slots' },
  { field: 'blocked_patterns', desc: 'Eliminierte Pattern-IDs' },
];

export interface SelectionStep {
  readonly step: string;
  readonly source: string;
  readonly effect: string;
}

/** ALT InfoView:334-353. */
export const SELECTION_STEPS: readonly SelectionStep[] = [
  {
    step: '1. Safety-Override', source: 'safety.enforced_pattern',
    effect: 'M01 bei Selbstgefährdung, M02 bei Drohungen — gewinnt immer.',
  },
  {
    step: '2. LLM-Hint', source: 'classification.pattern_id_hint',
    effect: 'Der primäre Pfad in praktisch jedem Turn, geleitet von den '
      + 'Hint-Ankern aus 01-base/classify-overrides.yaml.',
  },
  {
    step: '3. Fallback', source: 'defensiv hartkodiert',
    effect: 'M15 (Orientierung), wenn weder Safety noch Hint ein gültiges Pattern liefern.',
  },
  {
    step: '4. Modulation', source: 'Persona-Modifier + Pattern-Defaults + Signale',
    effect: 'Stil, Tonalität, Tool-Liste, Slot-Degradation. Die Persona greift '
      + 'hier — nicht bei der Pattern-Wahl.',
  },
];

export interface PromptLayer {
  readonly layer: string;
  readonly priority: string;
  readonly content: string;
  readonly tokens: string;
}

/** ALT InfoView:419-455. */
export const PROMPT_LAYERS: readonly PromptLayer[] = [
  {
    layer: '1 — Identität & Schutz', priority: '1000',
    content: 'Persona-Definition, Guardrails, Safety-Config, Policy-Regeln',
    tokens: 'Wird nie entladen. Guardrails stehen immer am Ende.',
  },
  {
    layer: '2 — Domain & Regeln', priority: '900',
    content: 'Plattform-Regeln, WLO-Fachwissen', tokens: 'Wird nie entladen.',
  },
  {
    layer: '3 — Patterns', priority: '500–800',
    content: 'Das gewählte Gesprächsmuster (genau eines)',
    tokens: 'Kann auf M12 (Degradation) zurückfallen.',
  },
  {
    layer: '4 — Dimensionen', priority: '300–600',
    content: 'Nur erkannte Persona, aktiver Intent und aktive Signale',
    tokens: 'Kann teilweise entladen werden.',
  },
  {
    layer: '5 — Material-Formate', priority: '200–400',
    content: 'Struktur-Vorgabe des Material-Typs, Alias-Mapping, Trigger',
    tokens: 'Nur bei I05/I06 geladen, sonst nicht im Prompt.',
  },
  {
    layer: '6 — Wissen', priority: '100–200',
    content: 'RAG-Kontext (always-on + on-demand), MCP-Tools',
    tokens: 'Wird als erstes entladen.',
  },
];
