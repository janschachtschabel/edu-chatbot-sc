/**
 * Der Chat-Probelauf der Agent-Seite (ST-8e, AG-4 Teil A): ein Gespräch mit der
 * Agent-Schleife über den echten Chat-Weg.
 *
 * Der Hinweis vor dem Senden nennt die Kosten, wie beim Auftrags-Tester: ein Zug
 * ist ein echter Chat-Zug, keine Vorschau.
 */
import type { CataloguePart } from './catalogue-part';

export const AGENT_PROBE: CataloguePart = {
  de: {
    'curated.agent.probe.label': 'Probelauf im Chat',
    'curated.agent.probe.hint':
      'Ein Gespräch mit der Agent-Schleife über den echten Chat-Weg — mit Master-Skill, Safety '
      + 'und Nutzungsbuchung, wie im Widget.',
    'agentProbe.cost':
      'Jeder Zug läuft wie ein Chat-Zug mit engine=agent und kostet wie einer. Die Sitzung steht '
      + 'danach unter Sessions und zählt nicht als echtes Gespräch.',
    'agentProbe.session': 'Sitzung',
    'agentProbe.transcript': 'Verlauf des Probelaufs',
    'agentProbe.you': 'Du',
    'agentProbe.noAnswer': '(keine Antwort)',
    'agentProbe.duration': 'Dauer',
    'agentProbe.cards': 'Karten',
    'agentProbe.documents': 'Dokument-Boxen',
    'agentProbe.language': 'Widget-Sprache',
    'agentProbe.language.de': 'Deutsch',
    'agentProbe.language.en': 'Englisch',
    'agentProbe.message': 'Nachricht',
    'agentProbe.messageHint': 'Wie im Widget: eine Frage, ein Materialwunsch, eine Aufgabe.',
    'agentProbe.send': 'Senden',
    'agentProbe.running': 'Läuft …',
    'agentProbe.reset': 'Neues Gespräch',
    'agentProbe.error.empty': 'Bitte eine Nachricht eingeben.',
    'agentProbe.done': 'Zug fertig nach {duration}.',
    'agentProbe.started': 'Neues Gespräch begonnen.',
  },
  en: {
    'curated.agent.probe.label': 'Trial run in the chat',
    'curated.agent.probe.hint':
      'A conversation with the agent loop over the real chat path — with master skill, safety '
      + 'and usage accounting, as in the widget.',
    'agentProbe.cost':
      'Each turn runs like a chat turn with engine=agent and costs like one. The session then '
      + 'appears under Sessions and does not count as a real conversation.',
    'agentProbe.session': 'Session',
    'agentProbe.transcript': 'Transcript of the trial run',
    'agentProbe.you': 'You',
    'agentProbe.noAnswer': '(no answer)',
    'agentProbe.duration': 'Duration',
    'agentProbe.cards': 'Cards',
    'agentProbe.documents': 'Document boxes',
    'agentProbe.language': 'Widget language',
    'agentProbe.language.de': 'German',
    'agentProbe.language.en': 'English',
    'agentProbe.message': 'Message',
    'agentProbe.messageHint': 'As in the widget: a question, a request for material, a task.',
    'agentProbe.send': 'Send',
    'agentProbe.running': 'Running …',
    'agentProbe.reset': 'New conversation',
    'agentProbe.error.empty': 'Please enter a message.',
    'agentProbe.done': 'Turn finished after {duration}.',
    'agentProbe.started': 'New conversation started.',
  },
};
