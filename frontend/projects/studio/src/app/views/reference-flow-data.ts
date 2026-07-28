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
 */

export interface InfluenceCard {
  /** The element whose value ripples outward. */
  readonly from: string;
  readonly effects: readonly string[];
}

export const INFLUENCES: readonly InfluenceCard[] = [
  {
    from: 'Persona',
    effects: [
      'Pattern-Wahl über den LLM-Hint',
      'Policy: Disclaimer und Tool-Sperren',
      'Anrede (Sie / du / neutral) über die Formality-Regeln',
      'eigener Persona-Abschnitt im Prompt',
    ],
  },
  {
    from: 'Intent',
    effects: [
      'Pattern-Wahl über den LLM-Hint',
      'spekulative MCP-Vorab-Abfrage noch während der Klassifikation',
      'Tool-Vorliebe: Sammlungen oder einzelne Inhalte',
      'welche Entity-Slots überhaupt erwartet werden',
    ],
  },
  {
    from: 'Signale',
    effects: [
      'Pattern-Hint des Klassifikators',
      'Modulation: überschreibt Ton und Länge des Patterns',
      'Flags wie „ohne Einleitung", „nur ein Vorschlag", „mit Quellen"',
      'reduce_items_signals deckelt max_items auf 3',
    ],
  },
  {
    from: 'Entities',
    effects: [
      'Parameter der MCP-Suche (Thema, Fach, Stufe …)',
      'Slot-Prüfung: fehlt einer, wird nachgefragt statt geraten',
      'Entity-Gedächtnis über mehrere Turns',
      'der Turn-Type entscheidet, ob angesammelt oder ersetzt wird',
    ],
  },
  {
    from: 'State',
    effects: [
      'Pattern-Wahl über den LLM-Hint',
      'wird pro Turn neu vom Modell gesetzt',
      'der State-Machine-Prüfer verwirft unplausible Sprünge',
    ],
  },
  {
    from: 'Pattern',
    effects: [
      'Antwortstruktur: Ton, Länge, Detailgrad',
      'Zugang zu Quellen und Tools (sources + tools)',
      'wird anschließend von den Signalen moduliert',
      'seine Core-Rule steht als Anweisung im Prompt',
    ],
  },
];

export interface FlowStep {
  readonly stage: string;
  readonly result: string;
}

/** „Mathe Klasse 7 Videos", getippt von einer Lehrkraft auf der Startseite. */
export const EXAMPLE_FLOW: readonly FlowStep[] = [
  { stage: 'Safety', result: 'Risiko niedrig, keine Blockade.' },
  {
    stage: 'Klassifikation',
    result: 'Persona P-LEH (Lehrkraft) · Intent I03 (Inhalte abrufen) · '
      + 'Entities fach=Mathematik, stufe=Klasse 7, medientyp=Video · '
      + 'Signale zielgerichtet, erfahren · State S3.',
  },
  { stage: 'Policy', result: 'Für Lehrkraft + Material-Suche keine Sperre.' },
  {
    stage: 'Pattern-Wahl',
    result: 'Hint des Klassifikators: M05 (Material-Suche gefiltert) — die Slots '
      + 'sind gefüllt, also greift keine Degradation.',
  },
  {
    stage: 'Modulation',
    result: 'Ton kollegial (Persona-Modifier), Länge kurz und ohne Einleitung '
      + '(Signal „zielgerichtet"), Quellen an (Signal „erfahren" setzt keine).',
  },
  {
    stage: 'Prompt',
    result: 'Basis-Persona + Domain-Regeln + P-LEH + M05 + Signal-Overrides + '
      + 'Guardrails — Guardrails immer zuletzt.',
  },
  {
    stage: 'LLM + MCP',
    result: 'search_wlo_content(…) liefert Treffer; die Karten-Pipeline '
      + 'normalisiert, sortiert und begrenzt sie.',
  },
  {
    stage: 'Antwort',
    result: 'Knappe Auflistung ohne Einleitung, dazu die Materialkarten.',
  },
];
