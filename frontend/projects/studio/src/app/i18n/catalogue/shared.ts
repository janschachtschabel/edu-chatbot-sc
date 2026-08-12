/**
 * Was sich JEDE Ansicht teilt (C1-d3a): der Zustands-Streifen, die Fehlertexte
 * der Konfigurations-Aufrufe, die Speichern-/Verwerfen-Knöpfe und die
 * Verlassen-Rückfrage.
 *
 * Beim Aufteilen des Katalogs (C1-d3b) von `area-editor` getrennt: diese Texte
 * kamen mit dem Bereichs-Editor herein, gehören ihm aber nicht — der
 * Zustands-Streifen steht an 22 Stellen. Sie hier zu suchen ist richtig,
 * sie dort zu suchen wäre Zufall.
 */
import type { CataloguePart } from './catalogue-part';

export const SHARED: CataloguePart = {
  de: {
    // ── Zustands-Streifen ───────────────────────────────────────────
    /** Der GANZE Satz, nicht Verb-ohne-Subjekt: bis C1-d3a stand hier
     *  `{{ label() }} werden geladen …` und das Substantiv kam samt Artikel
     *  aus der Aufrufstelle. Das war schon einsprachig falsch (sechs Aufrufe
     *  übergeben einen Singular) und in zwei Sprachen gar nicht zu machen —
     *  die Wortstellung gehört zur Übersetzung. `{label}` ist jetzt ein
     *  blosses Substantiv. */
    'async.loading': 'Lade {label} …',
    'async.retry': 'Erneut versuchen',
    /** Zugänglicher Name desselben Knopfs. Mehrere Streifen auf einer Seite
     *  tragen denselben sichtbaren Text; ohne das Ziel sind ihre Knöpfe für
     *  einen Screenreader nicht unterscheidbar. Beginnt mit dem sichtbaren
     *  Text (WCAG 2.5.3 „Label in Name"). */
    'async.retryFor': 'Erneut versuchen — {label}',
    'async.empty': 'Hier ist noch nichts.',

    // ── Fehlertexte der Konfigurations-Aufrufe ──────────────────────
    'error.offline': 'Backend nicht erreichbar.',
    'error.unexpected': 'Unerwarteter Fehler.',
    /** Antwort mit einem Fehler-Status, aber ohne eigenen Satz darin. */
    'error.unknown': 'Unbekannter Fehler.',
    'error.badAreaKey': 'Der Bereichsschlüssel ist ungültig.',
    'error.noSuchArea': 'Diesen Konfigurationsbereich gibt es nicht.',
    'error.schemaMismatch': 'Die Eingabe passt nicht zum Bereichsmodell: {detail}',
    'error.status': 'Fehler {status}: {detail}',

    // ── Bearbeiten: Speichern/Verwerfen ─────────────────────────────
    'editor.save': 'Speichern',
    'editor.saving': 'Wird gespeichert …',
    'editor.discard': 'Verwerfen',
    'editor.saved': 'Gespeichert.',
    'editor.discarded': 'Änderungen verworfen.',
    'editor.unsaved': 'Ungespeicherte Änderungen',
    /** Kurzform auf dem zugeklappten Abschnitt, wo kein Platz für den Satz
     *  ist. */
    'editor.unsavedShort': 'Ungespeichert',
    'editor.loading': 'Wird geladen …',
    'editor.blocked': 'Nicht speicherbar: {fields} enthält kein gültiges JSON.',
    'editor.notSaved': 'Nicht gespeichert: {fields} enthält kein gültiges JSON.',
    'guard.confirmLeave':
      'Es gibt ungespeicherte Änderungen. Diese Seite trotzdem verlassen und die '
      + 'Änderungen verwerfen?',

    // ── Wiederkehrende Beschriftungen ───────────────────────────────
    // Gezählt, nicht vermutet: „Abbrechen" steht an 17 Stellen, „Aktualisieren"
    // an 13. Sie gehören keiner Ansicht. Verbraucht werden sie ab C1-d3b nach
    // und nach — die übrigen Stellen ziehen mit ihrer eigenen Scheibe nach.
    'action.cancel': 'Abbrechen',
    'action.refresh': 'Aktualisieren',
    /** Derselbe Knopf, während er liest. */
    'action.refreshing': 'Wird geladen …',
    /** Die Ja-Antwort einer Löschen-Rückfrage. Stand bis C1-d4b zweimal
     *  gleichlautend im Katalog (`snapshots.confirmDeleteYes`,
     *  `rag.confirmYes`); die Lauf-Liste wäre die dritte Kopie geworden. */
    'action.confirmDelete': 'Ja, löschen',
    'action.download': 'Herunterladen',
    /** Kurzform am Knopf selbst, wo „Wird heruntergeladen …" die Breite
     *  sprengt. */
    'action.downloading': 'Lädt …',
    /** Ein leerer Bezeichner ist ein unklassifizierter Turn; eine leere Zelle
     *  läse sich als Anzeigefehler. Stand bis C1-d4b3 zweimal wörtlich da —
     *  in `quality-bars.component.ts` und in der Pattern-Nutzung. */
    'label.unclassified': '(ohne)',

    // ── Balken-Tabelle (C1-d4b3) ────────────────────────────────────
    // `QualityBarsComponent` steht in drei Ansichten an sieben Stellen und
    // übersetzt ihre eigenen drei Texte selbst. Was sie ZÄHLT weiss nur die
    // Aufrufstelle; Beschriftung und abweichende Einheit kommen von dort.
    /** Spaltenkopf, nur für Screenreader — am Bildschirm sagen die zwei
     *  Spalten selbst, was sie sind. */
    'bars.key': 'Kennung',
    /** Voreingestellte Einheit: fünf der sieben Aufrufstellen zählen Turns,
     *  die zwei übrigen (Fluss-Ansicht) geben „Übergänge" mit. */
    'bars.unit': 'Turns',
  },

  en: {
    'async.loading': 'Loading {label} …',
    'async.retry': 'Try again',
    'async.retryFor': 'Try again — {label}',
    'async.empty': 'Nothing here yet.',

    'error.offline': 'Backend unreachable.',
    'error.unexpected': 'Unexpected error.',
    'error.unknown': 'Unknown error.',
    'error.badAreaKey': 'The area key is invalid.',
    'error.noSuchArea': 'There is no such configuration area.',
    'error.schemaMismatch': 'The input does not match the area model: {detail}',
    'error.status': 'Error {status}: {detail}',

    'editor.save': 'Save',
    'editor.saving': 'Saving …',
    'editor.discard': 'Discard',
    'editor.saved': 'Saved.',
    'editor.discarded': 'Changes discarded.',
    'editor.unsaved': 'Unsaved changes',
    'editor.unsavedShort': 'Unsaved',
    'editor.loading': 'Loading …',
    'editor.blocked': 'Cannot save: {fields} does not hold valid JSON.',
    'editor.notSaved': 'Not saved: {fields} does not hold valid JSON.',
    'guard.confirmLeave':
      'There are unsaved changes. Leave this page anyway and discard them?',

    'action.cancel': 'Cancel',
    'action.refresh': 'Refresh',
    'action.refreshing': 'Loading …',
    'action.confirmDelete': 'Yes, delete',
    'action.download': 'Download',
    'action.downloading': 'Downloading …',
    'label.unclassified': '(none)',

    'bars.key': 'Id',
    'bars.unit': 'Turns',
  },
};
