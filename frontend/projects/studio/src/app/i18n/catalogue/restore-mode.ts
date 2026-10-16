/**
 * Die Wahl beim Wiederherstellen (Paket 7, P5-5) — eine Gruppe für die drei
 * Rückfragen der Ansicht „Sicherung" (Voll-Backup, Snapshot, Werksstand).
 *
 * Die Folge von „Exakt" steht im Etikett selbst: wer wählt, soll sie vorher
 * gelesen haben. Die Kennung im Löschsatz ist die des Snapshots, den das
 * Backend davor anlegt — die Liste zeigt sie neben dem Datum.
 */
import type { CataloguePart } from './catalogue-part';

export const RESTORE_MODE: CataloguePart = {
  de: {
    'restoreMode.legend': 'Bereiche, die nicht in der Sicherung liegen',
    'restoreMode.merge': 'Ergänzend (Vorgabe)',
    'restoreMode.mergeHint': 'bleiben, wie sie sind.',
    'restoreMode.exact': 'Exakt',
    'restoreMode.exactHint':
      'werden gelöscht, etwa ein seitdem angelegtes Muster. Vorher sichert ein Snapshot '
      + 'den jetzigen Stand; ist dafür kein Platz mehr, bleibt alles unverändert.',
    'restoreMode.deleted.one':
      '{count} Bereich gelöscht, der nicht in der Sicherung lag; der Stand davor liegt im '
      + 'Snapshot {id}.',
    'restoreMode.deleted.other':
      '{count} Bereiche gelöscht, die nicht in der Sicherung lagen; der Stand davor liegt '
      + 'im Snapshot {id}.',
  },
  en: {
    'restoreMode.legend': 'Areas the backup does not contain',
    'restoreMode.merge': 'Additive (default)',
    'restoreMode.mergeHint': 'stay as they are.',
    'restoreMode.exact': 'Exact',
    'restoreMode.exactHint':
      'are deleted, such as a pattern created since. A snapshot preserves the current '
      + 'state first; if there is no room for it, nothing changes.',
    'restoreMode.deleted.one':
      'Deleted {count} area the backup did not contain; the state before is in snapshot {id}.',
    'restoreMode.deleted.other':
      'Deleted {count} areas the backup did not contain; the state before is in snapshot {id}.',
  },
};
