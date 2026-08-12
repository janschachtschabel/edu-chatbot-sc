/**
 * How the pieces influence each other, and one turn walked through end to end
 * (A5-Rest, from ALT `InfoView.tsx:472-550`).
 *
 * Separate from `reference-data.ts` because those are the tables OF the
 * architecture (what a layer holds, which dimensions exist) while these two
 * describe one RUN through it. Every identifier below was checked against NEU:
 * `M05` = `03-patterns/m05-material-suche-gefiltert.md`, `P-LEH` =
 * `04-personas/leh.md`, `I03` and `S3` exist in `intents.yaml` / `states.yaml`,
 * and `search_wlo_content` is one of the twelve MCP tools in
 * `services/mcp/tool_defs.py`.
 *
 * **Seit C1-d5c1 stehen hier nur noch Struktur und Katalog-Schlüssel.** Die
 * geprüften Bezeichner selbst stehen jetzt IN den Texten
 * (`i18n/catalogue/reference-flow.ts`) — sie sind Teil des Satzes, den sie
 * belegen, und kein eigenes Feld.
 */

export interface InfluenceCard {
  /** The element whose value ripples outward. */
  readonly titleKey: string;
  readonly effectKeys: readonly string[];
}

export const INFLUENCES: readonly InfluenceCard[] = [
  {
    titleKey: 'rf.inf.persona.title',
    effectKeys: [
      'rf.inf.persona.1', 'rf.inf.persona.2', 'rf.inf.persona.3', 'rf.inf.persona.4',
    ],
  },
  {
    titleKey: 'rf.inf.intent.title',
    effectKeys: [
      'rf.inf.intent.1', 'rf.inf.intent.2', 'rf.inf.intent.3', 'rf.inf.intent.4',
    ],
  },
  {
    titleKey: 'rf.inf.signals.title',
    effectKeys: [
      'rf.inf.signals.1', 'rf.inf.signals.2', 'rf.inf.signals.3', 'rf.inf.signals.4',
    ],
  },
  {
    titleKey: 'rf.inf.entities.title',
    effectKeys: [
      'rf.inf.entities.1', 'rf.inf.entities.2', 'rf.inf.entities.3', 'rf.inf.entities.4',
    ],
  },
  {
    titleKey: 'rf.inf.state.title',
    effectKeys: ['rf.inf.state.1', 'rf.inf.state.2', 'rf.inf.state.3'],
  },
  {
    titleKey: 'rf.inf.pattern.title',
    effectKeys: [
      'rf.inf.pattern.1', 'rf.inf.pattern.2', 'rf.inf.pattern.3', 'rf.inf.pattern.4',
    ],
  },
];

export interface FlowStep {
  readonly stageKey: string;
  readonly resultKey: string;
}

/** „Mathe Klasse 7 Videos", getippt von einer Lehrkraft auf der Startseite. */
export const EXAMPLE_FLOW: readonly FlowStep[] = [
  { stageKey: 'rf.step.safety.stage', resultKey: 'rf.step.safety.result' },
  { stageKey: 'rf.step.classify.stage', resultKey: 'rf.step.classify.result' },
  { stageKey: 'rf.step.policy.stage', resultKey: 'rf.step.policy.result' },
  { stageKey: 'rf.step.pattern.stage', resultKey: 'rf.step.pattern.result' },
  { stageKey: 'rf.step.modulation.stage', resultKey: 'rf.step.modulation.result' },
  { stageKey: 'rf.step.prompt.stage', resultKey: 'rf.step.prompt.result' },
  { stageKey: 'rf.step.llm.stage', resultKey: 'rf.step.llm.result' },
  { stageKey: 'rf.step.answer.stage', resultKey: 'rf.step.answer.result' },
];
