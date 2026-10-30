/**
 * Die Ansicht „Sessions" (C1-d4e2) — Liste, zwei zerstörende Aktionen und der
 * Gesprächsverlauf.
 *
 * **Ein Teil, weil es EIN Panel ist:** der Verlauf wird in die rechte Spalte
 * der Sessions-Ansicht hinein gerendert. Er teilt sich deshalb auch
 * `sv.transcript` — die Überschrift der Spalte IST die Beschriftung seines
 * Zustands-Streifens.
 *
 * **Zwei zerstörende Aktionen nebeneinander**, die sich hörbar unterscheiden
 * müssen: „Verlauf leeren" behält Session, Gedächtnis und Auswertungsdaten,
 * „Löschen" nimmt alles. Beide tragen darum einen eigenen zugänglichen Namen
 * mit der Sitzungs-Kennung (WCAG 2.5.3), und die zwei Rückfragen sind zwei
 * ganze Sätze — nicht ein Satz mit eingesetztem Verb.
 *
 * **Was NICHT hier steht:** Brotkrume (`nav.group.auswertung`), Titel und die
 * Beschriftung des Listen-Zustands (`view.sessions.label`, in beiden Sprachen
 * „Sessions"), `action.cancel`, `action.confirmDelete`, `action.refresh*`.
 *
 * **`sv.unknown` steht EINMAL und wird an zwei Stellen gelesen:** die Zeile
 * ohne Persona und die Nachricht ohne Rolle. Beides ist derselbe Satz „das Feld
 * ist leer", und zwei Einträge wären zwei Orte für dieselbe Übersetzung.
 */
import type { CataloguePart } from './catalogue-part';

export const SESSIONS: CataloguePart = {
  de: {
    'sv.intro':
      'Die zuletzt aktiven Gespräche, neueste zuerst (die Liste zeigt höchstens 100). Eine '
      + 'Session wählen, um ihren Verlauf mit den Routing-Entscheidungen zu sehen.',
    'sv.empty':
      'Noch keine Sessions. Sobald jemand mit dem Widget spricht, steht das Gespräch hier.',

    /** Bis C1-d4e2 stand die deutsche Regel handgeschrieben in der Vorlage
     *  (`turn_count === 1 ? 'Turn' : 'Turns'`) — richtig, aber fest verdrahtet.
     *  Damit ist es der letzte Handgriff dieser Art im Studio. */
    'sv.turns.one': '{count} Turn',
    'sv.turns.other': '{count} Turns',
    /** Leeres Feld — gelesen für die Zeile ohne Persona UND für die Nachricht
     *  ohne Rolle. */
    'sv.unknown': 'unbekannt',

    'sv.clear': 'Verlauf leeren',
    'sv.clearFor': 'Verlauf leeren — Session {id}',
    'sv.clearing': 'Wird geleert …',
    'sv.clearYes': 'Ja, Verlauf leeren',
    'sv.confirmClear':
      'Wirklich den Gesprächsverlauf leeren? Die Session, ihr Gedächtnis und die '
      + 'Auswertungsdaten bleiben erhalten.',
    'sv.cleared': 'Gesprächsverlauf geleert.',

    'sv.delete': 'Löschen',
    'sv.deleteFor': 'Löschen — Session {id}',
    'sv.deleting': 'Wird gelöscht …',
    'sv.confirmDelete':
      'Wirklich löschen? Verlauf, Gedächtnis und alle Auswertungsdaten dieser Session '
      + 'gehen mit — das lässt sich nicht rückgängig machen.',
    'sv.deleted': 'Session gelöscht.',

    'sv.transcript': 'Gesprächsverlauf',
    'sv.pick': 'Links eine Session wählen.',

    // ── Gesprächsverlauf ────────────────────────────────────────────
    'st.empty':
      'In dieser Session sind keine Nachrichten gespeichert — sie wurde angelegt, aber nie '
      + 'benutzt, oder der Verlauf wurde geleert.',
    'st.role.user': 'Nutzerin/Nutzer',
    /** Produktname, in beiden Sprachen derselbe. */
    'st.role.assistant': 'BOERDi',
    'st.fact.pattern': 'Muster',
    'st.fact.intent': 'Intent',
    'st.fact.persona': 'Persona',
    'st.fact.state': 'Zustand',
    'st.fact.tools': 'Werkzeuge',
    'st.fact.signals': 'Signale',
    /** Paket 18C/D: der Anfang der Trace-ID — derselbe wie in der Fehlerblase. */
    'st.fact.errorNumber': 'Fehlernummer',

    // ── Zugakte (Paket 18C/D) ───────────────────────────────────────
    'st.za.tools.one': '{count} Werkzeugaufruf',
    'st.za.tools.other': '{count} Werkzeugaufrufe',
    'st.za.skipped.one': 'Dazu 1 weiterer Aufruf, nur gezählt (höchstens 50 je Zug).',
    'st.za.skipped.other': 'Dazu {count} weitere Aufrufe, nur gezählt (höchstens 50 je Zug).',
    'st.za.chars': '{count} Zeichen',
    'st.za.noAnswer': 'keine Antwort',
    'st.za.cached': 'aus dem Zwischenspeicher',
    'st.za.args': 'Argumente',
    'st.za.args.in': 'Eingegangen',
    'st.za.args.sent': 'Gesendet (nach Auflösung)',
    'st.za.error': 'Fehler',
    'st.za.status.tool': 'Fehler des Werkzeugs',
    'st.za.status.transport': 'Verbindungsfehler',
    'st.za.status.timeout': 'Zeitüberschreitung',
    'st.za.status.auth': 'Anmeldung abgewiesen',
    'st.za.rewrites.one': '{count} Umschreibung',
    'st.za.rewrites.other': '{count} Umschreibungen',
    'st.za.rewrite.typ_fokus': 'Typ-Fokus',
    'st.za.rewrite.waechter': 'Wächter',
    'st.za.before': 'Vorher',
    'st.za.after': 'Nachher',
    'st.za.reason': 'Grund',
    'st.za.shortcut': 'Schnellweg',
    'st.za.shortcut.canvas': 'Material (Canvas)',
    'st.za.shortcut.lernpfad': 'Lernpfad',

    // ── Suche nach Fehlernummer (Paket 18C/D) ───────────────────────
    'sv.search.label': 'Fehlernummer',
    'sv.search.hint':
      'Die Nummer aus einer Fehlerblase („Fehlernummer: …“). Ab 8 Zeichen genügt der Anfang.',
    'sv.search.submit': 'Zug suchen',
    'sv.search.searching': 'Sucht …',
    'sv.search.invalid':
      'Eine Fehlernummer besteht aus Buchstaben, Ziffern und den Zeichen . _ : - '
      + '(höchstens 128).',
    'sv.search.none':
      'Keine Antwort mit der Fehlernummer {nummer} gefunden. Vielleicht ist der Verlauf schon '
      + 'gelöscht (Aufbewahrung) oder die Nummer stammt aus einer anderen Anlage.',
    'sv.search.opened': 'Gefunden: der Verlauf von {id} ist geöffnet.',
    'sv.search.many': '{count} Treffer — bitte einen wählen.',
    'sv.search.results': 'Treffer',
  },

  en: {
    'sv.intro':
      'The most recently active conversations, newest first (the list shows at most 100). '
      + 'Pick a session to see its transcript with the routing decisions.',
    'sv.empty':
      'No sessions yet. As soon as someone talks to the widget, the conversation shows up '
      + 'here.',

    'sv.turns.one': '{count} turn',
    'sv.turns.other': '{count} turns',
    'sv.unknown': 'unknown',

    'sv.clear': 'Clear transcript',
    'sv.clearFor': 'Clear transcript — session {id}',
    'sv.clearing': 'Clearing …',
    'sv.clearYes': 'Yes, clear the transcript',
    'sv.confirmClear':
      'Really clear the transcript? The session, its memory and the analytics are kept.',
    'sv.cleared': 'Transcript cleared.',

    'sv.delete': 'Delete',
    'sv.deleteFor': 'Delete — session {id}',
    'sv.deleting': 'Deleting …',
    'sv.confirmDelete':
      'Really delete? The transcript, the memory and all analytics of this session go with '
      + 'it — this cannot be undone.',
    'sv.deleted': 'Session deleted.',

    'sv.transcript': 'Transcript',
    'sv.pick': 'Pick a session on the left.',

    'st.empty':
      'No messages are stored for this session — it was created but never used, or the '
      + 'transcript was cleared.',
    'st.role.user': 'User',
    'st.role.assistant': 'BOERDi',
    'st.fact.pattern': 'Pattern',
    'st.fact.intent': 'Intent',
    'st.fact.persona': 'Persona',
    'st.fact.state': 'State',
    'st.fact.tools': 'Tools',
    'st.fact.signals': 'Signals',
    'st.fact.errorNumber': 'Error number',

    'st.za.tools.one': '{count} tool call',
    'st.za.tools.other': '{count} tool calls',
    'st.za.skipped.one': 'Plus 1 more call, only counted (at most 50 per turn).',
    'st.za.skipped.other': 'Plus {count} more calls, only counted (at most 50 per turn).',
    'st.za.chars': '{count} characters',
    'st.za.noAnswer': 'no answer',
    'st.za.cached': 'from the cache',
    'st.za.args': 'Arguments',
    'st.za.args.in': 'As received',
    'st.za.args.sent': 'As sent (after resolving)',
    'st.za.error': 'Error',
    'st.za.status.tool': 'tool error',
    'st.za.status.transport': 'connection error',
    'st.za.status.timeout': 'timeout',
    'st.za.status.auth': 'sign-in rejected',
    'st.za.rewrites.one': '{count} rewrite',
    'st.za.rewrites.other': '{count} rewrites',
    'st.za.rewrite.typ_fokus': 'Type focus',
    'st.za.rewrite.waechter': 'Guard',
    'st.za.before': 'Before',
    'st.za.after': 'After',
    'st.za.reason': 'Reason',
    'st.za.shortcut': 'Shortcut',
    'st.za.shortcut.canvas': 'Material (canvas)',
    'st.za.shortcut.lernpfad': 'Learning path',

    'sv.search.label': 'Error number',
    'sv.search.hint':
      'The number from an error bubble (“Error number: …”). From 8 characters on, the '
      + 'beginning is enough.',
    'sv.search.submit': 'Find turn',
    'sv.search.searching': 'Searching …',
    'sv.search.invalid':
      'An error number consists of letters, digits and the characters . _ : - (at most 128).',
    'sv.search.none':
      'No answer with error number {nummer} found. The transcript may already be deleted '
      + '(retention), or the number comes from another installation.',
    'sv.search.opened': 'Found: the transcript of {id} is open.',
    'sv.search.many': '{count} hits — please pick one.',
    'sv.search.results': 'Hits',
  },
};
