/**
 * Die beiden Start-Panels der Evaluation (C1-d4c) — Gold-Lauf und generativer
 * Lauf.
 *
 * **Ein Teil für beide und nicht je einer.** Sie stehen im selben Reiter
 * übereinander, und vier Texte standen bis hierher WÖRTLICH doppelt da:
 * „Nichts ausgewählt = alle.", „Es läuft schon ein Lauf …", „Startet …" und die
 * Wortgruppe für die Judge-Aufrufe. Zwei Teile hiessen, diese vier Einträge
 * zweimal zu pflegen — eine Doppelung, die `en.spec.ts` bauartbedingt nicht
 * fände: der Test vergleicht Deutsch gegen Englisch je Schlüssel, nie Schlüssel
 * gegeneinander.
 *
 * **Jede Anzahl bekommt ihre eigene Wortgruppe.** Die Kostenzeile des
 * generativen Laufs trägt VIER Anzahlen in einem Satz, jede mit eigener
 * Mehrzahl; eine Schlüssel-Matrix aus 2⁴ Sätzen wäre die falsche Antwort. Die
 * Wortgruppen entstehen einzeln über `plural()` und werden eingesetzt —
 * dieselbe Bauart wie `evalPattern.combos` (C1-d4b3). Im Gold-Panel ersetzt das
 * ausserdem ein `{{ … }} Flow(s)`: die Klammer-Mehrzahl ist die Ausrede dafür,
 * dass eine Sprache hier eine Form wählen müsste.
 *
 * Die Kostenzeile UND die Rückfrage lesen dieselben Wortgruppen. Sie stehen
 * jeweils als zwei ganze Sätze da (mit und ohne Judge) statt als ein Satz mit
 * eingebautem `@if` — ein Nebensatz, den das Template ein- und ausblendet, ist
 * kein Satz, den man übersetzen kann.
 *
 * „Chat-Anfragen" (Gold) und „Chat-Aufrufe" (generativ) bleiben zwei Einträge:
 * das sind zwei verschiedene Texte des Bestands, kein Versehen.
 *
 * NICHT hier: „Abbrechen" (`action.cancel` aus `shared.ts`) und die Namen der
 * Ansichten — beide Panels tragen ihren Titel doppelt, als Überschrift und auf
 * dem Knopf, und lesen dafür EINEN Eintrag.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_START: CataloguePart = {
  de: {
    // ── Was sich beide Panels teilen ────────────────────────────────
    'evalStart.nothingChosen': 'Nichts ausgewählt = alle.',
    'evalStart.busy':
      'Es läuft schon ein Lauf — es kann immer nur einer gleichzeitig laufen.',
    /** Der Ja-Knopf, während er startet. */
    'evalStart.starting': 'Startet …',
    'evalStart.judgeCalls.one': '{count} Judge-Aufruf',
    'evalStart.judgeCalls.other': '{count} Judge-Aufrufe',

    // ── Gold-Lauf ───────────────────────────────────────────────────
    /** Überschrift UND Beschriftung des Knopfs darunter. */
    'evalStart.gold.title': 'Gold-Lauf starten',
    'evalStart.gold.intro':
      'Geprüfte Abläufe aus `eval/gold-flows.yaml` gegen die echte '
      + 'Chat-Pipeline, mit harten Soll-Ist-Checks je Turn. Deterministisch und '
      + 'A/B-vergleichbar — dieselben Flows, dieselbe Scorecard.',
    'evalStart.gold.list': 'Gold-Flows',
    'evalStart.gold.empty':
      'Diese Config enthält keine Gold-Flows (eval/gold-flows.yaml fehlt oder '
      + 'ist leer). Ohne Flows gibt es nichts abzuspielen.',
    'evalStart.gold.legend': 'Flows',
    'evalStart.gold.turns.one': '{count} Turn',
    'evalStart.gold.turns.other': '{count} Turns',
    'evalStart.gold.judge.legend': 'Weiche Bewertung',
    'evalStart.gold.judge.label': 'LLM-Judge mitlaufen lassen',
    'evalStart.gold.judge.hint':
      'bewertet zusätzlich Intent-Treffer, Tonalität und Informationsqualität '
      + '— ein weiterer LLM-Aufruf je beantwortetem Turn. Die harte Quote '
      + 'bleibt davon unberührt.',
    'evalStart.gold.calls.one': '{count} Chat-Anfrage',
    'evalStart.gold.calls.other': '{count} Chat-Anfragen',
    'evalStart.gold.flows.one': '{count} Flow',
    'evalStart.gold.flows.other': '{count} Flows',
    'evalStart.gold.cost.plain':
      'Dieser Lauf feuert *{calls}* durch die echte Pipeline — {flows}. '
      + 'Keine Schätzung: die Turns stehen in der Flow-Datei.',
    'evalStart.gold.cost.judge':
      'Dieser Lauf feuert *{calls}* durch die echte Pipeline und '
      + '*{judgeCalls}* — {flows}. Keine Schätzung: die Turns stehen in der '
      + 'Flow-Datei.',
    'evalStart.gold.confirm.plain':
      '{calls} durch die echte Pipeline starten? Es läuft dann kein zweiter '
      + 'Lauf, bis dieser fertig ist.',
    'evalStart.gold.confirm.judge':
      '{calls} plus {judgeCalls} starten? Es läuft dann kein zweiter Lauf, bis '
      + 'dieser fertig ist.',
    'evalStart.gold.go': 'Ja, starten',
    'evalStart.gold.started': 'Gold-Lauf {id} gestartet.',

    // ── Generativer Lauf ────────────────────────────────────────────
    'evalStart.gen.title': 'Generativen Lauf starten',
    'evalStart.gen.intro':
      'Ein LLM erfindet Szenarien je Persona × Intent, spielt sie durch die '
      + 'echte Chat-Pipeline und bewertet jede Antwort. Das kostet Geld — die '
      + 'Schätzung steht vor dem Start.',
    'evalStart.gen.list': 'Personas und Intents',
    'evalStart.gen.empty':
      'Diese Chatbot-Config hat keine Personas oder keine Intents — ohne beide '
      + 'gibt es keine Kombination, die ein Lauf durchspielen könnte. Erst '
      + 'unter „Personas" bzw. „Intents" anlegen.',
    'evalStart.gen.scope': 'Umfang',
    'evalStart.gen.personas': 'Personas',
    'evalStart.gen.intents': 'Intents',
    'evalStart.gen.combos.one': 'Auswahl ergibt *{count} Kombination*.',
    'evalStart.gen.combos.other': 'Auswahl ergibt *{count} Kombinationen*.',
    'evalStart.gen.mode.legend': 'Art des Laufs',
    'evalStart.gen.mode.both': 'Szenarien und Gespräche',
    'evalStart.gen.mode.scenarios': 'nur Szenarien (ein Turn je Szenario)',
    'evalStart.gen.mode.conversations': 'nur Gespräche (mehrere Turns)',
    'evalStart.gen.amount.legend': 'Menge je Kombination',
    'evalStart.gen.scenariosLabel': 'Szenarien je Kombination',
    'evalStart.gen.turnsLabel': 'Turns je Gespräch',
    'evalStart.gen.bounds': 'Je {min} bis {max} — außerhalb lehnt das Backend ab.',
    'evalStart.gen.check': 'Kosten prüfen',
    'evalStart.gen.checking': 'Wird geschätzt …',
    'evalStart.gen.chatCalls.one': '{count} Chat-Aufruf',
    'evalStart.gen.chatCalls.other': '{count} Chat-Aufrufe',
    'evalStart.gen.simCalls.one': '{count} Simulator-Aufruf',
    'evalStart.gen.simCalls.other': '{count} Simulator-Aufrufe',
    'evalStart.gen.ratedTurns.one': '{count} bewerteter Turn',
    'evalStart.gen.ratedTurns.other': '{count} bewertete Turns',
    'evalStart.gen.cost':
      'Dieser Lauf feuert *{chat}* durch die echte Pipeline, *{judge}* und '
      + '{sim} — {turns}.',
    'evalStart.gen.band': 'Geschätzte Kosten *{min} bis {max}*, erwartet {expected}.',
    'evalStart.gen.bandHint':
      'Schätzung mit festen Preisannahmen je Aufruf — die echte Rechnung hängt '
      + 'an Prompt-Länge, Antwort-Länge und Tool-Ergebnissen.',
    /** Der Fehlersatz des Backends kommt als `{error}` herein — geteilt wird
     *  der Katalog-Text, eingesetzt wird danach, er kann also keine
     *  Auszeichnung erzeugen (C1-d4b2). */
    'evalStart.gen.blind.one':
      'Start *ohne Kostenschätzung*: {error} Der Lauf kostet trotzdem Geld — '
      + '{count} Kombination.',
    'evalStart.gen.blind.other':
      'Start *ohne Kostenschätzung*: {error} Der Lauf kostet trotzdem Geld — '
      + '{count} Kombinationen.',
    'evalStart.gen.go': 'Ja, Lauf starten',
    'evalStart.gen.started': 'Lauf {id} gestartet.',
  },

  en: {
    'evalStart.nothingChosen': 'Nothing selected = all.',
    'evalStart.busy': 'A run is already in flight — only one can run at a time.',
    'evalStart.starting': 'Starting …',
    'evalStart.judgeCalls.one': '{count} judge call',
    'evalStart.judgeCalls.other': '{count} judge calls',

    'evalStart.gold.title': 'Start gold run',
    'evalStart.gold.intro':
      'Checked conversations from `eval/gold-flows.yaml` against the real chat '
      + 'pipeline, with hard expected-versus-actual checks per turn. '
      + 'Deterministic and comparable — same flows, same scorecard.',
    'evalStart.gold.list': 'Gold flows',
    'evalStart.gold.empty':
      'This config holds no gold flows (eval/gold-flows.yaml is missing or '
      + 'empty). Without flows there is nothing to replay.',
    'evalStart.gold.legend': 'Flows',
    'evalStart.gold.turns.one': '{count} turn',
    'evalStart.gold.turns.other': '{count} turns',
    'evalStart.gold.judge.legend': 'Soft scoring',
    'evalStart.gold.judge.label': 'Run the LLM judge along',
    'evalStart.gold.judge.hint':
      'additionally scores intent hit, tone and information quality — one more '
      + 'LLM call per answered turn. The hard rate stays untouched by it.',
    'evalStart.gold.calls.one': '{count} chat request',
    'evalStart.gold.calls.other': '{count} chat requests',
    'evalStart.gold.flows.one': '{count} flow',
    'evalStart.gold.flows.other': '{count} flows',
    'evalStart.gold.cost.plain':
      'This run fires *{calls}* through the real pipeline — {flows}. No '
      + 'estimate: the turns are in the flow file.',
    'evalStart.gold.cost.judge':
      'This run fires *{calls}* through the real pipeline and *{judgeCalls}* — '
      + '{flows}. No estimate: the turns are in the flow file.',
    'evalStart.gold.confirm.plain':
      'Start {calls} through the real pipeline? No second run will go until '
      + 'this one is done.',
    'evalStart.gold.confirm.judge':
      'Start {calls} plus {judgeCalls}? No second run will go until this one '
      + 'is done.',
    'evalStart.gold.go': 'Yes, start',
    'evalStart.gold.started': 'Gold run {id} started.',

    'evalStart.gen.title': 'Start generative run',
    'evalStart.gen.intro':
      'An LLM invents scenarios per persona × intent, plays them through the '
      + 'real chat pipeline and scores every answer. That costs money — the '
      + 'estimate comes before the start.',
    'evalStart.gen.list': 'Personas and intents',
    'evalStart.gen.empty':
      'This chatbot config has no personas or no intents — without both there '
      + 'is no combination a run could play through. Create them under '
      + '“Personas” and “Intents” first.',
    'evalStart.gen.scope': 'Scope',
    'evalStart.gen.personas': 'Personas',
    'evalStart.gen.intents': 'Intents',
    'evalStart.gen.combos.one': 'The selection makes *{count} combination*.',
    'evalStart.gen.combos.other': 'The selection makes *{count} combinations*.',
    'evalStart.gen.mode.legend': 'Kind of run',
    'evalStart.gen.mode.both': 'scenarios and conversations',
    'evalStart.gen.mode.scenarios': 'scenarios only (one turn each)',
    'evalStart.gen.mode.conversations': 'conversations only (several turns)',
    'evalStart.gen.amount.legend': 'Amount per combination',
    'evalStart.gen.scenariosLabel': 'Scenarios per combination',
    'evalStart.gen.turnsLabel': 'Turns per conversation',
    'evalStart.gen.bounds': '{min} to {max} each — outside that the backend refuses.',
    'evalStart.gen.check': 'Check cost',
    'evalStart.gen.checking': 'Estimating …',
    'evalStart.gen.chatCalls.one': '{count} chat call',
    'evalStart.gen.chatCalls.other': '{count} chat calls',
    'evalStart.gen.simCalls.one': '{count} simulator call',
    'evalStart.gen.simCalls.other': '{count} simulator calls',
    'evalStart.gen.ratedTurns.one': '{count} scored turn',
    'evalStart.gen.ratedTurns.other': '{count} scored turns',
    'evalStart.gen.cost':
      'This run fires *{chat}* through the real pipeline, *{judge}* and {sim} '
      + '— {turns}.',
    'evalStart.gen.band': 'Estimated cost *{min} to {max}*, expected {expected}.',
    'evalStart.gen.bandHint':
      'An estimate with fixed price assumptions per call — the real bill hangs '
      + 'on prompt length, answer length and tool results.',
    'evalStart.gen.blind.one':
      'Starting *without a cost estimate*: {error} The run costs money all the '
      + 'same — {count} combination.',
    'evalStart.gen.blind.other':
      'Starting *without a cost estimate*: {error} The run costs money all the '
      + 'same — {count} combinations.',
    'evalStart.gen.go': 'Yes, start the run',
    'evalStart.gen.started': 'Run {id} started.',
  },
};
