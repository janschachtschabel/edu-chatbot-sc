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
  },
};
