/**
 * Die Spur eines Zugs (ST-8a): welche Maschine antwortete, was der Zug an Token
 * kostete und — im Agent-Modus — was jede Runde der Schleife tat.
 *
 * Die Ende-Gründe sagen, was geschah, nicht wie der Code heißt: „Frist
 * erreicht" statt `deadline`. Ein unbekannter Grund kommt roh durch
 * (`agent-trace.ts`).
 */
import type { CataloguePart } from './catalogue-part';

export const AGENT_TRACE: CataloguePart = {
  de: {
    'trace.engine': 'Maschine',
    'trace.tokens': 'Token',
    'trace.tokens.value': 'Eingabe {prompt} (davon {cached} gecacht) · Ausgabe {completion}',
    'trace.end': 'Ende',
    'trace.end.value': '{reason} · {rounds} · {duration}',
    'trace.rounds.one': '{count} Runde',
    'trace.rounds.other': '{count} Runden',
    'trace.skill': 'Geholter Skill',
    'trace.detail': 'Runden im Einzelnen ({count})',
    'trace.caption':
      'Runden der Agent-Schleife: Werkzeuge mit ihren Argumenten (nur ihre Namen, die Werte '
      + 'speichert der Server nicht), Dauer und Token je Runde.',
    'trace.col.round': 'Runde',
    'trace.col.tools': 'Werkzeuge',
    'trace.col.duration': 'Dauer',
    'trace.col.prompt': 'Eingabe',
    'trace.col.cached': 'davon gecacht',
    'trace.col.completion': 'Ausgabe',
    'trace.noTool': 'ohne Werkzeug',
    'trace.stop.text': 'Antwort geschrieben',
    'trace.stop.submit': 'Ergebnis abgegeben',
    'trace.stop.deadline': 'Frist erreicht',
    'trace.stop.token_budget': 'Token-Deckel erreicht',
    'trace.stop.max_iterations': 'Runden-Deckel erreicht',
    'trace.stop.no_progress': 'Stillstand: derselbe Aufruf zweimal',
    'trace.stop.empty': 'weder Werkzeug noch Text',
    'trace.stop.error': 'Fehler beim Modellaufruf',
    'trace.stop.safety': 'Schutzantwort ohne Schleife',
    'trace.stop.unknown': 'Grund nicht gespeichert',
  },
  en: {
    'trace.engine': 'Engine',
    'trace.tokens': 'Tokens',
    'trace.tokens.value': 'Input {prompt} ({cached} cached) · Output {completion}',
    'trace.end': 'End',
    'trace.end.value': '{reason} · {rounds} · {duration}',
    'trace.rounds.one': '{count} round',
    'trace.rounds.other': '{count} rounds',
    'trace.skill': 'Fetched skill',
    'trace.detail': 'Rounds in detail ({count})',
    'trace.caption':
      'Rounds of the agent loop: tools with their arguments (names only, the server does not '
      + 'store the values), duration and tokens per round.',
    'trace.col.round': 'Round',
    'trace.col.tools': 'Tools',
    'trace.col.duration': 'Duration',
    'trace.col.prompt': 'Input',
    'trace.col.cached': 'of which cached',
    'trace.col.completion': 'Output',
    'trace.noTool': 'no tool',
    'trace.stop.text': 'Answer written',
    'trace.stop.submit': 'Result submitted',
    'trace.stop.deadline': 'Deadline reached',
    'trace.stop.token_budget': 'Token cap reached',
    'trace.stop.max_iterations': 'Round cap reached',
    'trace.stop.no_progress': 'Stalled: the same call twice',
    'trace.stop.empty': 'neither tool nor text',
    'trace.stop.error': 'Model call failed',
    'trace.stop.safety': 'Safety answer without the loop',
    'trace.stop.unknown': 'reason not recorded',
  },
};
