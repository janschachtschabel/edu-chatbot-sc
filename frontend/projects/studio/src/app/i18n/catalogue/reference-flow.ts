/**
 * Der Referenz-Abschnitt „Wechselwirkungen" und der durchgespielte Turn
 * (C1-d5c1).
 *
 * **Bewusste Doppelung:** fünf der sechs Karten-Überschriften (`Persona`,
 * `Intent`, `Signale`, `Entities`, `State`) lauten wie die Namen der
 * Input-Dimensionen in `reference-rows.ts`. Sie hier ein zweites Mal zu führen
 * ist die kleinere Kopplung: es sind zwei Abschnitts-Komponenten mit je eigenem
 * Grund zur Änderung, und die sechste Karte (`Pattern`) hat in jener Tabelle gar
 * keine Entsprechung — fünf geliehene Schlüssel und einer aus dem eigenen
 * Vorrat wäre schwerer zu lesen als sechs aus einem. Abdriften kann dabei nur
 * ein Wort: „Signale" gegen „Signals". Die übrigen vier lauten in beiden
 * Sprachen gleich.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE_FLOW: CataloguePart = {
  de: {
    'rf.influences.title': 'Wechselwirkungen',
    'rf.influences.text':
      'Die Elemente arbeiten nicht für sich — jede erkannte Größe wirkt an '
      + 'mehreren Stellen weiter.',

    'rf.inf.persona.title': 'Persona',
    'rf.inf.persona.1': 'Pattern-Wahl über den LLM-Hint',
    'rf.inf.persona.2': 'Policy: Disclaimer und Tool-Sperren',
    'rf.inf.persona.3': 'Anrede (Sie / du / neutral) über die Formality-Regeln',
    'rf.inf.persona.4': 'eigener Persona-Abschnitt im Prompt',

    'rf.inf.intent.title': 'Intent',
    'rf.inf.intent.1': 'Pattern-Wahl über den LLM-Hint',
    'rf.inf.intent.2': 'spekulative MCP-Vorab-Abfrage noch während der Klassifikation',
    'rf.inf.intent.3': 'Tool-Vorliebe: Sammlungen oder einzelne Inhalte',
    'rf.inf.intent.4': 'welche Entity-Slots überhaupt erwartet werden',

    'rf.inf.signals.title': 'Signale',
    'rf.inf.signals.1': 'Pattern-Hint des Klassifikators',
    'rf.inf.signals.2': 'Modulation: überschreibt Ton und Länge des Patterns',
    'rf.inf.signals.3': 'Flags wie „ohne Einleitung", „nur ein Vorschlag", „mit Quellen"',
    'rf.inf.signals.4': 'reduce_items_signals deckelt max_items auf 3',

    'rf.inf.entities.title': 'Entities',
    'rf.inf.entities.1': 'Parameter der MCP-Suche (Thema, Fach, Stufe …)',
    'rf.inf.entities.2': 'Slot-Prüfung: fehlt einer, wird nachgefragt statt geraten',
    'rf.inf.entities.3': 'Entity-Gedächtnis über mehrere Turns',
    'rf.inf.entities.4': 'der Turn-Type entscheidet, ob angesammelt oder ersetzt wird',

    'rf.inf.state.title': 'State',
    'rf.inf.state.1': 'Pattern-Wahl über den LLM-Hint',
    'rf.inf.state.2': 'wird pro Turn neu vom Modell gesetzt',
    'rf.inf.state.3': 'der State-Machine-Prüfer verwirft unplausible Sprünge',

    'rf.inf.pattern.title': 'Pattern',
    'rf.inf.pattern.1': 'Antwortstruktur: Ton, Länge, Detailgrad',
    'rf.inf.pattern.2': 'Zugang zu Quellen und Tools (sources + tools)',
    'rf.inf.pattern.3': 'wird anschließend von den Signalen moduliert',
    'rf.inf.pattern.4': 'seine Core-Rule steht als Anweisung im Prompt',

    'rf.example.title': 'Beispiel: ein kompletter Turn',
    'rf.example.text':
      'Nachricht: *„Mathe Klasse 7 Videos"* — getippt von einer Lehrkraft auf der '
      + 'Startseite.',

    'rf.step.safety.stage': 'Safety',
    'rf.step.safety.result': 'Risiko niedrig, keine Blockade.',
    'rf.step.classify.stage': 'Klassifikation',
    'rf.step.classify.result':
      'Persona P-LEH (Lehrkraft) · Intent I03 (Inhalte abrufen) · Entities '
      + 'fach=Mathematik, stufe=Klasse 7, medientyp=Video · Signale zielgerichtet, '
      + 'erfahren · State S3.',
    'rf.step.policy.stage': 'Policy',
    'rf.step.policy.result': 'Für Lehrkraft + Material-Suche keine Sperre.',
    'rf.step.pattern.stage': 'Pattern-Wahl',
    'rf.step.pattern.result':
      'Hint des Klassifikators: M05 (Material-Suche gefiltert) — die Slots sind '
      + 'gefüllt, also greift keine Degradation.',
    'rf.step.modulation.stage': 'Modulation',
    'rf.step.modulation.result':
      'Ton kollegial (Persona-Modifier), Länge kurz und ohne Einleitung (Signal '
      + '„zielgerichtet"), Quellen an (Signal „erfahren" setzt keine).',
    'rf.step.prompt.stage': 'Prompt',
    'rf.step.prompt.result':
      'Basis-Persona + Domain-Regeln + P-LEH + M05 + Signal-Overrides + '
      + 'Guardrails — Guardrails immer zuletzt.',
    'rf.step.llm.stage': 'LLM + MCP',
    'rf.step.llm.result':
      'search_wlo_content(…) liefert Treffer; die Karten-Pipeline normalisiert, '
      + 'sortiert und begrenzt sie.',
    'rf.step.answer.stage': 'Antwort',
    'rf.step.answer.result': 'Knappe Auflistung ohne Einleitung, dazu die Materialkarten.',
  },

  en: {
    'rf.influences.title': 'How the pieces influence each other',
    'rf.influences.text':
      'The elements do not work in isolation — every recognised value takes effect '
      + 'in several places.',

    'rf.inf.persona.title': 'Persona',
    'rf.inf.persona.1': 'pattern choice through the LLM hint',
    'rf.inf.persona.2': 'policy: disclaimers and tool blocks',
    'rf.inf.persona.3': 'form of address (formal / informal / neutral) through the formality rules',
    'rf.inf.persona.4': 'a persona section of its own in the prompt',

    'rf.inf.intent.title': 'Intent',
    'rf.inf.intent.1': 'pattern choice through the LLM hint',
    'rf.inf.intent.2': 'a speculative MCP prefetch while the classification still runs',
    'rf.inf.intent.3': 'tool preference: collections or individual content',
    'rf.inf.intent.4': 'which entity slots are expected at all',

    'rf.inf.signals.title': 'Signals',
    'rf.inf.signals.1': 'the classifier’s pattern hint',
    'rf.inf.signals.2': 'modulation: it overrides the pattern’s tone and length',
    'rf.inf.signals.3': 'flags such as “no introduction”, “one suggestion only”, “with sources”',
    'rf.inf.signals.4': 'reduce_items_signals caps max_items at 3',

    'rf.inf.entities.title': 'Entities',
    'rf.inf.entities.1': 'parameters of the MCP search (topic, subject, level …)',
    'rf.inf.entities.2': 'slot check: if one is missing, it is asked for instead of guessed',
    'rf.inf.entities.3': 'entity memory across several turns',
    'rf.inf.entities.4': 'the turn type decides whether values accumulate or are replaced',

    'rf.inf.state.title': 'State',
    'rf.inf.state.1': 'pattern choice through the LLM hint',
    'rf.inf.state.2': 'set anew by the model on every turn',
    'rf.inf.state.3': 'the state-machine check rejects implausible jumps',

    'rf.inf.pattern.title': 'Pattern',
    'rf.inf.pattern.1': 'structure of the answer: tone, length, level of detail',
    'rf.inf.pattern.2': 'access to sources and tools (sources + tools)',
    'rf.inf.pattern.3': 'it is modulated by the signals afterwards',
    'rf.inf.pattern.4': 'its core rule stands as an instruction in the prompt',

    'rf.example.title': 'Example: one complete turn',
    'rf.example.text':
      'Message: *“Mathe Klasse 7 Videos”* — typed by a teacher on the start page.',

    'rf.step.safety.stage': 'Safety',
    'rf.step.safety.result': 'Risk low, no block.',
    'rf.step.classify.stage': 'Classification',
    'rf.step.classify.result':
      'Persona P-LEH (teacher) · intent I03 (retrieve content) · entities '
      + 'fach=Mathematik, stufe=Klasse 7, medientyp=Video · signals zielgerichtet, '
      + 'erfahren · state S3.',
    'rf.step.policy.stage': 'Policy',
    'rf.step.policy.result': 'No block for a teacher plus a material search.',
    'rf.step.pattern.stage': 'Pattern choice',
    'rf.step.pattern.result':
      'The classifier’s hint: M05 (filtered material search) — the slots are '
      + 'filled, so no degradation applies.',
    'rf.step.modulation.stage': 'Modulation',
    'rf.step.modulation.result':
      'Tone collegial (persona modifier), length short and without an introduction '
      + '(signal “zielgerichtet”), sources on (signal “erfahren” sets none).',
    'rf.step.prompt.stage': 'Prompt',
    'rf.step.prompt.result':
      'Base persona + domain rules + P-LEH + M05 + signal overrides + guardrails — '
      + 'guardrails always last.',
    'rf.step.llm.stage': 'LLM + MCP',
    'rf.step.llm.result':
      'search_wlo_content(…) returns hits; the card pipeline normalises, sorts and '
      + 'limits them.',
    'rf.step.answer.stage': 'Answer',
    'rf.step.answer.result': 'A terse list without an introduction, plus the material cards.',
  },
};
