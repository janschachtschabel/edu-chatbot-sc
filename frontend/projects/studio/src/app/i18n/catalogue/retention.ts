/**
 * Aufbewahrung der Protokolle (Paket 8, A), Panel der Datenschutz-Seite.
 *
 * Die Sätze sagen, was der Code tut: der Lauf geht alle sechs Stunden
 * (`services/aufbewahrung.TAKT_S`) und löscht endgültig; 0 Tage heißt
 * unbegrenzt; Gesprächsverläufe (Nachrichten, Gedächtnis) haben seit dem
 * Nutzer-Entscheid vom 2026-10-09 eine Frist, die Sitzungen selbst bleiben —
 * nur ihr Gesprächsstand wird nach derselben Frist geleert (Paket 9, V7). Samt
 * Verbrauch löschen sie zwei Wege: einzeln in „Sessions“, gesammelt über
 * „Gespräche löschen“ (Paket 9, MINOR 13).
 */
import type { CataloguePart } from './catalogue-part';

export const RETENTION: CataloguePart = {
  de: {
    'retention.lead':
      'Was älter ist als seine Frist, löscht das Backend alle sechs Stunden endgültig; '
      + '0 Tage heißt unbegrenzt. Die Frist der Gesprächsverläufe steht oben unter '
      + '„Datenschutz“, die des Qualitäts-Protokolls unter „Qualitäts-Logging“, die des '
      + 'Sicherheitsprotokolls auf der Seite „Identität & Schutz“. Sitzungen und ihre '
      + 'Verbrauchszahlen bleiben — ruht eine Sitzung länger als die Frist der '
      + 'Gesprächsverläufe, wird nur ihr Gesprächsstand (Thema, Seitentitel, Suchbegriffe, '
      + 'Tour) geleert; ebenso der Text im Qualitäts-Protokoll (Nachricht, Thema, Begründungen) — '
      + 'die Kennzahlen bleiben bis zu dessen Frist. Samt Verbrauch löschen lassen sich Sitzungen einzeln in der Ansicht '
      + '„Sessions“ oder gesammelt über „Gespräche löschen“.',
    'retention.caption': 'Gezählt beim Öffnen, vor jeder Rückfrage und nach jedem Bereinigen.',
    'retention.col.log': 'Daten',
    'retention.col.period': 'Frist',
    'retention.col.due': 'Jetzt fällig',
    'retention.col.oldest': 'Ältester Eintrag',
    'retention.log.messages': 'Chatnachrichten',
    'retention.log.memory': 'Sitzungsgedächtnis',
    'retention.log.session_state': 'Gesprächsstand ruhender Sitzungen',
    'retention.log.safety_logs': 'Sicherheitsprotokoll',
    'retention.log.quality_logs': 'Qualitäts-Protokoll',
    'retention.log.quality_text': 'Text im Qualitäts-Protokoll',
    'retention.days.one': '{count} Tag',
    'retention.days.other': '{count} Tage',
    'retention.unlimited': 'unbegrenzt',
    'retention.due.one': '{count} Eintrag',
    'retention.due.other': '{count} Einträge',
    'retention.neverDue': 'nie',
    'retention.empty': 'keiner',
    'retention.loading': 'Fristen werden gelesen …',
    'retention.start': 'Bereinigen …',
    'retention.counting': 'Fällige Einträge werden gezählt …',
    'retention.confirm':
      'Löscht jetzt endgültig {list} — alles, was älter ist als seine Frist; dasselbe, was das '
      + 'Backend alle sechs Stunden ohnehin tut.',
    'retention.confirmUncounted':
      'Löscht jetzt endgültig alle Einträge, die älter sind als ihre Frist — dasselbe, was das '
      + 'Backend alle sechs Stunden ohnehin tut.',
    'retention.confirmNothing': 'Gerade ist nichts fällig — der Lauf würde nichts löschen.',
    'retention.go': 'Jetzt bereinigen',
    'retention.busy': 'Wird bereinigt …',
    'retention.done': 'Bereinigt: {list}.',
    'retention.nothing': 'Es war nichts fällig.',
    'retention.count.messages.one': '{count} Nachricht',
    'retention.count.messages.other': '{count} Nachrichten',
    'retention.count.memory.one': '{count} Gedächtnis-Eintrag',
    'retention.count.memory.other': '{count} Gedächtnis-Einträge',
    'retention.count.session_state.one': '{count} Gesprächsstand',
    'retention.count.session_state.other': '{count} Gesprächsstände',
    'retention.count.safety_logs.one': '{count} Sicherheits-Eintrag',
    'retention.count.safety_logs.other': '{count} Sicherheits-Einträge',
    'retention.count.quality_logs.one': '{count} Qualitäts-Eintrag',
    'retention.count.quality_logs.other': '{count} Qualitäts-Einträge',
    'retention.count.quality_text.one': '{count} Text im Qualitäts-Protokoll',
    'retention.count.quality_text.other': '{count} Texte im Qualitäts-Protokoll',
  },

  en: {
    'retention.lead':
      'Whatever is older than its period, the backend deletes for good every six hours; 0 days '
      + 'means unlimited. The period for conversations is set above under “Privacy”, the quality '
      + 'log\'s under “Quality logging”, the safety log\'s on the “Identity & safeguards” page. '
      + 'Sessions and their usage figures stay — once a session has been idle longer than the '
      + 'conversation period, only its conversation state (topic, page title, search terms, '
      + 'tour) is cleared; so is the text in the quality log (message, topic, reasoning) — its '
      + 'figures stay until the quality log\'s own period. Sessions are deleted together with their usage one by one in the '
      + '“Sessions” view or all at once via “Delete conversations”.',
    'retention.caption':
      'Counted when the panel opens, before every confirmation and after every cleanup.',
    'retention.col.log': 'Data',
    'retention.col.period': 'Period',
    'retention.col.due': 'Due now',
    'retention.col.oldest': 'Oldest entry',
    'retention.log.messages': 'Chat messages',
    'retention.log.memory': 'Session memory',
    'retention.log.session_state': 'State of idle sessions',
    'retention.log.safety_logs': 'Safety log',
    'retention.log.quality_logs': 'Quality log',
    'retention.log.quality_text': 'Text in the quality log',
    'retention.days.one': '{count} day',
    'retention.days.other': '{count} days',
    'retention.unlimited': 'unlimited',
    'retention.due.one': '{count} entry',
    'retention.due.other': '{count} entries',
    'retention.neverDue': 'never',
    'retention.empty': 'none',
    'retention.loading': 'Reading the periods …',
    'retention.start': 'Clean up …',
    'retention.counting': 'Counting what is due …',
    'retention.confirm':
      'Deletes {list} now, for good — everything older than its period; the same the backend '
      + 'does every six hours anyway.',
    'retention.confirmUncounted':
      'Deletes every entry older than its period now, for good — the same the backend does '
      + 'every six hours anyway.',
    'retention.confirmNothing': 'Nothing is due right now — the run would delete nothing.',
    'retention.go': 'Clean up now',
    'retention.busy': 'Cleaning up …',
    'retention.done': 'Cleaned up: {list}.',
    'retention.nothing': 'Nothing was due.',
    'retention.count.messages.one': '{count} message',
    'retention.count.messages.other': '{count} messages',
    'retention.count.memory.one': '{count} memory entry',
    'retention.count.memory.other': '{count} memory entries',
    'retention.count.session_state.one': '{count} conversation state',
    'retention.count.session_state.other': '{count} conversation states',
    'retention.count.safety_logs.one': '{count} safety log entry',
    'retention.count.safety_logs.other': '{count} safety log entries',
    'retention.count.quality_logs.one': '{count} quality log entry',
    'retention.count.quality_logs.other': '{count} quality log entries',
    'retention.count.quality_text.one': '{count} text in the quality log',
    'retention.count.quality_text.other': '{count} texts in the quality log',
  },
};
