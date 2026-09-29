/**
 * Löschen über alle Sitzungen und Aufräumen der Datenbank (ST-6), Panel der
 * Datenschutz-Seite.
 *
 * Die Texte sagen, was wirklich geschieht — gemessen, nicht erinnert: die
 * Sitzungen reißen in der Datenbank ihre Verbrauchszahlen mit (`usage_events`,
 * ON DELETE CASCADE); die Studio-Sicherung umfasst nur die Konfiguration; eine
 * gelöschte Sitzung entsteht beim nächsten Zug neu, aber ohne Verlauf; ein
 * einfaches VACUUM macht die Datei selten kleiner.
 */
import type { CataloguePart } from './catalogue-part';

export const PRIVACY_PURGE: CataloguePart = {
  de: {
    'purge.lead':
      'Jede Karte löscht über ALLE Sitzungen hinweg und lässt sich nicht rückgängig machen. '
      + 'Die Sicherung des Studios umfasst nur die Konfiguration — gelöschte Gespräche kommen '
      + 'von dort nicht zurück.',
    'purge.card.inhalte.title': 'Gesprächsinhalte',
    'purge.card.inhalte.desc':
      'Chatnachrichten, Sitzungsgedächtnis und Qualitäts-Protokolle. Die Sitzungen selbst, '
      + 'ihre Verbrauchszahlen und das Sicherheitsprotokoll bleiben.',
    'purge.card.inhalte.start': 'Gesprächsinhalte löschen …',
    'purge.card.sitzungen.title': 'Gesprächsinhalte und Sitzungen',
    'purge.card.sitzungen.desc':
      'Dazu die Sitzungen selbst — und mit ihnen ihre Verbrauchszahlen: die Kostenübersicht '
      + 'beginnt wieder bei null. Das Sicherheitsprotokoll bleibt.',
    'purge.card.sitzungen.start': 'Inhalte und Sitzungen löschen …',
    'purge.card.alles.title': 'Alles, auch das Sicherheitsprotokoll',
    'purge.card.alles.desc':
      'Dazu das Sicherheitsprotokoll, der Nachweis, was die Schutzstufen erkannt haben. Nur '
      + 'löschen, wenn dieser Nachweis nicht mehr gebraucht wird.',
    'purge.card.alles.start': 'Alles löschen …',
    'purge.step1':
      'Das gilt für alle Sitzungen und ist endgültig. Wer gerade chattet, kann weiterschreiben '
      + '— der Chatbot kennt das bisherige Gespräch dann aber nicht mehr.',
    'purge.next': 'Weiter',
    'purge.step2': 'Letzte Rückfrage: „{title}“ jetzt endgültig löschen?',
    'purge.go': 'Endgültig löschen',
    'purge.busy': 'Wird gelöscht …',
    'purge.done': 'Gelöscht: {list}.',
    'purge.nothing': 'Es gab nichts zu löschen.',
    'purge.count.messages.one': '{count} Nachricht',
    'purge.count.messages.other': '{count} Nachrichten',
    'purge.count.memory.one': '{count} Gedächtnis-Eintrag',
    'purge.count.memory.other': '{count} Gedächtnis-Einträge',
    'purge.count.quality_logs.one': '{count} Qualitäts-Eintrag',
    'purge.count.quality_logs.other': '{count} Qualitäts-Einträge',
    'purge.count.safety_logs.one': '{count} Sicherheits-Eintrag',
    'purge.count.safety_logs.other': '{count} Sicherheits-Einträge',
    'purge.count.sessions.one': '{count} Sitzung',
    'purge.count.sessions.other': '{count} Sitzungen',

    'purge.db.title': 'Datenbank aufräumen',
    'purge.db.desc':
      'Gibt den Platz gelöschter Zeilen zum Wiederverwenden frei und frischt die Statistiken '
      + 'auf (VACUUM ANALYZE). Die Datei wird dabei meist nicht kleiner. PostgreSQL räumt auch '
      + 'von selbst auf; von Hand lohnt es sich direkt nach einem großen Löschen.',
    'purge.db.loading': 'Größe wird gelesen …',
    'purge.db.size': 'Größe der Datenbank: {size}',
    'purge.db.reclaimable': 'davon belegt durch gelöschte Zeilen: etwa {size}',
    'purge.db.reclaimableNone': 'keine gelöschten Zeilen, die Platz belegen',
    'purge.db.start': 'Aufräumen …',
    'purge.db.confirm':
      'Das Aufräumen belastet die Datenbank je nach Größe Sekunden bis Minuten. Der Chat '
      + 'bleibt erreichbar, antwortet aber womöglich langsamer.',
    'purge.db.go': 'Jetzt aufräumen',
    'purge.db.busy': 'Räumt auf …',
    'purge.db.done': 'Aufgeräumt. Größe vorher {before}, nachher {after}.',
  },

  en: {
    'purge.lead':
      'Every card deletes across ALL sessions and cannot be undone. The studio backup covers '
      + 'the configuration only — deleted conversations cannot be restored from it.',
    'purge.card.inhalte.title': 'Conversation content',
    'purge.card.inhalte.desc':
      'Chat messages, session memory and quality logs. The sessions themselves, their usage '
      + 'figures and the safety log stay.',
    'purge.card.inhalte.start': 'Delete conversation content …',
    'purge.card.sitzungen.title': 'Conversation content and sessions',
    'purge.card.sitzungen.desc':
      'Also the sessions themselves — and with them their usage figures: the cost overview '
      + 'starts again at zero. The safety log stays.',
    'purge.card.sitzungen.start': 'Delete content and sessions …',
    'purge.card.alles.title': 'Everything, including the safety log',
    'purge.card.alles.desc':
      'Also the safety log, the record of what the safety levels detected. Delete it only when '
      + 'that record is no longer needed.',
    'purge.card.alles.start': 'Delete everything …',
    'purge.step1':
      'This applies to all sessions and is final. Anyone chatting right now can keep writing — '
      + 'but the chatbot will no longer know the conversation so far.',
    'purge.next': 'Continue',
    'purge.step2': 'Last check: delete “{title}” for good now?',
    'purge.go': 'Delete for good',
    'purge.busy': 'Deleting …',
    'purge.done': 'Deleted: {list}.',
    'purge.nothing': 'There was nothing to delete.',
    'purge.count.messages.one': '{count} message',
    'purge.count.messages.other': '{count} messages',
    'purge.count.memory.one': '{count} memory entry',
    'purge.count.memory.other': '{count} memory entries',
    'purge.count.quality_logs.one': '{count} quality log entry',
    'purge.count.quality_logs.other': '{count} quality log entries',
    'purge.count.safety_logs.one': '{count} safety log entry',
    'purge.count.safety_logs.other': '{count} safety log entries',
    'purge.count.sessions.one': '{count} session',
    'purge.count.sessions.other': '{count} sessions',

    'purge.db.title': 'Tidy up the database',
    'purge.db.desc':
      'Frees the space of deleted rows for reuse and refreshes the statistics (VACUUM '
      + 'ANALYZE). The file usually does not get smaller. PostgreSQL also tidies up on its own; '
      + 'doing it by hand pays off right after a large deletion.',
    'purge.db.loading': 'Reading the size …',
    'purge.db.size': 'Database size: {size}',
    'purge.db.reclaimable': 'of which taken up by deleted rows: about {size}',
    'purge.db.reclaimableNone': 'no deleted rows taking up space',
    'purge.db.start': 'Tidy up …',
    'purge.db.confirm':
      'Tidying up puts load on the database for seconds to minutes, depending on its size. The '
      + 'chat stays available but may answer more slowly.',
    'purge.db.go': 'Tidy up now',
    'purge.db.busy': 'Tidying up …',
    'purge.db.done': 'Tidied up. Size before {before}, after {after}.',
  },
};
