/**
 * Der Reiter „Gesprächs-Flow" der Analyse (C1-d4d2).
 *
 * **Drei unabhängige Anzahlen in EINEM Satz** (Turns, Übergänge, Tage) — drei
 * Wortgruppen über `plural()`, in `qualFlow.total` eingesetzt. Eine
 * Schlüssel-Matrix wären 2³ Sätze; dieselbe Bauart wie `evalStart.gen.cost`.
 *
 * **Der Leer-Text steht als ZWEI ganze Sätze da** und nicht als einer mit
 * eingesetzter Tages-Wortgruppe: die Wortgruppe trägt „letzter/letzte", und im
 * Satz braucht es den Dativ („in den letzten … Tagen"). Ein Platzhalter mitten
 * im Satz kann die Beugung nicht mitbringen — der Satz je Form kann es.
 *
 * **Was NICHT hier steht:** der Name des Panels (`qual.tab.flow` aus der
 * Hülle), `action.refresh*` und `bars.key` (beide `shared.ts`).
 */
import type { CataloguePart } from './catalogue-part';

export const QUALITY_FLOW: CataloguePart = {
  de: {
    'qualFlow.turns.one': '{count} Turn',
    'qualFlow.turns.other': '{count} Turns',
    'qualFlow.transitions.one': '{count} Übergang',
    'qualFlow.transitions.other': '{count} Übergänge',
    /** Der Artikel gehört in die Form: „letzter 1 Tag" gegen „letzte 30 Tage". */
    'qualFlow.days.one': 'letzter {count} Tag',
    'qualFlow.days.other': 'letzte {count} Tage',
    'qualFlow.total': '{turns} mit Phase, {transitions} ({scope}, {days}).',

    'qualFlow.daysLabel': 'Zeitraum in Tagen',
    'qualFlow.minCount': 'Min-Häufigkeit',
    'qualFlow.empty.one':
      'Am letzten Tag wurde kein Turn mit einer Phase aufgezeichnet. Führe ein Gespräch '
      + 'oder vergrößere den Zeitraum.',
    'qualFlow.empty.other':
      'In den letzten {count} Tagen wurde kein Turn mit einer Phase aufgezeichnet. Führe '
      + 'ein Gespräch oder vergrößere den Zeitraum.',

    'qualFlow.chart.states': 'Häufigkeit der Phasen',
    'qualFlow.chart.moves': 'Übergänge zwischen Phasen',
    'qualFlow.chart.repeats': 'Wiederholungen derselben Phase',
    /** Abweichende Einheit der Balken-Tabelle — der Regelfall `bars.unit`
     *  zählt Turns, diese beiden Tabellen zählen Übergänge. */
    'qualFlow.unit': 'Übergänge',
    'qualFlow.noMoves':
      'Keine Übergänge zwischen verschiedenen Phasen im Zeitraum — jede Sitzung blieb in '
      + 'einer Phase.',
    'qualFlow.noRepeats': 'Keine Wiederholungen derselben Phase im Zeitraum.',
    'qualFlow.legend':
      'Phasen sind Verlaufs-Abschnitte: *S1 Orientierung* (kein konkretes Anliegen), '
      + '*S2 Klärung* (ein Pflicht-Slot fehlt, eine Rückfrage) und *S3 Aktion* (der Bot '
      + 'liefert). Häufige Übergänge zeigen den typischen Gesprächsverlauf; „S2 ↻" heißt '
      + 'mehrere Klärungsrunden hintereinander — meist fehlte danach noch ein Slot.',
  },

  en: {
    'qualFlow.turns.one': '{count} turn',
    'qualFlow.turns.other': '{count} turns',
    'qualFlow.transitions.one': '{count} transition',
    'qualFlow.transitions.other': '{count} transitions',
    'qualFlow.days.one': 'past {count} day',
    'qualFlow.days.other': 'past {count} days',
    'qualFlow.total': '{turns} with a phase, {transitions} ({scope}, {days}).',

    'qualFlow.daysLabel': 'Period in days',
    'qualFlow.minCount': 'Min frequency',
    'qualFlow.empty.one':
      'No turn with a phase was recorded on the past day. Have a conversation or widen '
      + 'the period.',
    'qualFlow.empty.other':
      'No turn with a phase was recorded in the past {count} days. Have a conversation '
      + 'or widen the period.',

    'qualFlow.chart.states': 'Frequency of the phases',
    'qualFlow.chart.moves': 'Transitions between phases',
    'qualFlow.chart.repeats': 'Repeats of the same phase',
    'qualFlow.unit': 'Transitions',
    'qualFlow.noMoves':
      'No transitions between different phases in the period — every session stayed in '
      + 'one phase.',
    'qualFlow.noRepeats': 'No repeats of the same phase in the period.',
    'qualFlow.legend':
      'Phases are stages of the conversation: *S1 orientation* (no concrete request), '
      + '*S2 clarification* (a required slot is missing, one follow-up question) and '
      + '*S3 action* (the bot delivers). Frequent transitions show the typical course; '
      + '"S2 ↻" means several rounds of clarification in a row — usually another slot '
      + 'was still missing afterwards.',
  },
};
