/**
 * Die Ansicht „Sicherung" (C1-d3b): Voll-Backup, Snapshots, Werksstand.
 *
 * Drei Namensräume für die drei Bausteine der Ansicht — die Hülle (`backup.`)
 * und die beiden Panels (`snapshots.`, `factory.`). Was in einem Snapshot
 * steckt, entscheidet, was diese Texte versprechen dürfen: NEU sichert
 * ausschliesslich Konfigurationsbereiche, und jeder Satz hier sagt das.
 */
import type { CataloguePart } from './catalogue-part';

export const BACKUP: CataloguePart = {
  de: {
    // ── Hülle und Voll-Backup ───────────────────────────────────────
    // Die Überschrift ist `view.sicherung.label` — dieselbe Ansicht, derselbe
    // Name.
    'backup.intro':
      'Alle drei Wege sichern dasselbe: die Konfigurationsbereiche des Chatbots. '
      + 'Gespräche, Auswertungen und RAG-Inhalte gehören nicht dazu — ein eingespieltes '
      + 'Backup lässt sie unberührt.',
    'backup.full.title': 'Voll-Backup',
    'backup.full.lead':
      'Der aktuelle Stand als ZIP für das eigene Archiv — und der Weg zurück, wenn er '
      + 'woanders liegt. Enthält keine Sessions, keine Logs, keine RAG-Dokumente.',
    'backup.download': 'Backup herunterladen',
    'backup.packing': 'Wird gepackt …',
    'backup.uploadLabel': 'Backup-ZIP einspielen',
    'backup.restore': 'Backup einspielen',
    'backup.restoring': 'Wird eingespielt …',
    /** Der ganze Satz, mit dem Dateinamen als Platzhalter: im Englischen steht
     *  das Objekt hinter dem Verb, im Deutschen davor — aus Bruchstücken ist
     *  das nicht zusammenzusetzen. */
    'backup.confirmRestore':
      '„{name}“ einspielen? Jeder Bereich aus der ZIP überschreibt seinen aktuellen '
      + 'Stand. Bereiche, die nicht darin liegen, bleiben, wie sie sind.',
    'backup.confirmRestoreYes': 'Ja, einspielen',
    'backup.downloaded': 'Backup heruntergeladen.',
    /** Einer für zwei: Voll-Backup und Snapshot melden denselben Satz, weil
     *  beide dasselbe tun — Bereiche aus einer ZIP schreiben. */
    'backup.areasRestored.one': '{count} Konfigurationsbereich aus „{name}“ eingespielt.',
    'backup.areasRestored.other': '{count} Konfigurationsbereiche aus „{name}“ eingespielt.',

    // ── Snapshots ───────────────────────────────────────────────────
    'snapshots.title': 'Snapshots',
    'snapshots.lead':
      'Ein Snapshot friert alle Konfigurationsbereiche auf dem Server ein und lässt sich '
      + 'ohne Download zurückspielen.',
    // Im Deutschen beugt sich das Verb, im Englischen auch — deshalb der ganze
    // Satz je Form und nicht nur ein Wort.
    'snapshots.count.one': 'Gespeichert ist {count} von {limit} möglichen.',
    'snapshots.count.other': 'Gespeichert sind {count} von {limit} möglichen.',
    'snapshots.labelField': 'Bezeichnung (optional)',
    'snapshots.labelExample': 'z. B. vor dem Persona-Umbau',
    'snapshots.create': 'Snapshot anlegen',
    'snapshots.creating': 'Wird angelegt …',
    'snapshots.empty':
      'Noch keine Snapshots. Ein Snapshot sichert die Konfiguration in ihrem jetzigen '
      + 'Stand — sinnvoll, bevor größere Änderungen anstehen.',
    'snapshots.restore': 'Wiederherstellen',
    'snapshots.delete': 'Löschen',
    'snapshots.confirmRestore':
      '„{name}“ einspielen? Die Konfigurationsbereiche aus diesem Snapshot überschreiben '
      + 'den aktuellen Stand. Bereiche, die er nicht enthält, bleiben unverändert.',
    'snapshots.confirmRestoreYes': 'Ja, wiederherstellen',
    'snapshots.confirmDelete':
      '„{name}“ endgültig löschen? Der gesicherte Stand ist danach nur noch über eine '
      + 'heruntergeladene ZIP verfügbar.',
    'snapshots.created': 'Snapshot „{name}“ angelegt.',
    'snapshots.deleted': 'Snapshot „{name}“ gelöscht.',
    'snapshots.downloaded': '„{name}“ heruntergeladen.',

    // ── Werksstand ──────────────────────────────────────────────────
    'factory.title': 'Werkseinstellungen',
    'factory.lead':
      'Der Werksstand ist die Konfiguration, mit der eine frisch aufgesetzte Installation '
      + 'startet. Er liegt als eigener Stand auf dem Server und lässt sich jederzeit '
      + 'wieder einspielen.',
    'factory.checking': 'Werksstand wird geprüft …',
    'factory.savedAt': 'Gesichert am {date}',
    'factory.none':
      'Kein Werksstand gesichert. Sichere den aktuellen Stand, sobald die Konfiguration '
      + 'ausgeliefert werden soll.',
    'factory.save': 'Aus Live-Stand sichern',
    'factory.saving': 'Wird gesichert …',
    'factory.reset': 'Zurücksetzen',
    'factory.resetting': 'Wird eingespielt …',
    'factory.confirmSave':
      'Den aktuellen Live-Stand als Werksstand sichern? Der bisher gesicherte Werksstand '
      + 'wird dabei überschrieben.',
    'factory.confirmSaveYes': 'Ja, Werksstand ersetzen',
    'factory.confirmReset':
      'Auf den Werksstand zurücksetzen? Die Konfigurationsbereiche aus dem gesicherten '
      + 'Stand überschreiben den aktuellen — laufende Gespräche und Auswertungen bleiben '
      + 'unberührt.',
    'factory.confirmResetYes': 'Ja, zurücksetzen',
    'factory.uploadLabel': 'Werksstand aus einer ZIP übernehmen',
    'factory.upload': 'Hochladen',
    'factory.uploading': 'Wird übernommen …',
    'factory.confirmUpload':
      '„{name}“ als neuen Werksstand übernehmen? Der bisher gesicherte Werksstand wird '
      + 'überschrieben.',
    'factory.confirmUploadYes': 'Ja, übernehmen',
    'factory.saved': 'Werksstand aus dem aktuellen Live-Stand gesichert.',
    'factory.wasReset.one': '{count} Konfigurationsbereich auf den Werksstand zurückgesetzt.',
    'factory.wasReset.other': '{count} Konfigurationsbereiche auf den Werksstand zurückgesetzt.',
    'factory.downloaded': 'Werksstand heruntergeladen.',
    'factory.uploaded': '„{name}“ als Werksstand übernommen.',
  },

  en: {
    'backup.intro':
      'All three routes back up the same thing: the chatbot’s configuration areas. '
      + 'Conversations, monitoring data and RAG content are not included — restoring a '
      + 'backup leaves them untouched.',
    'backup.full.title': 'Full backup',
    'backup.full.lead':
      'The current state as a ZIP for your own archive — and the way back when it lives '
      + 'elsewhere. Contains no sessions, no logs, no RAG documents.',
    'backup.download': 'Download backup',
    'backup.packing': 'Packing …',
    'backup.uploadLabel': 'Restore a backup ZIP',
    'backup.restore': 'Restore backup',
    'backup.restoring': 'Restoring …',
    'backup.confirmRestore':
      'Restore “{name}”? Every area in the ZIP overwrites its current state. Areas the '
      + 'ZIP does not contain stay as they are.',
    'backup.confirmRestoreYes': 'Yes, restore',
    'backup.downloaded': 'Backup downloaded.',
    'backup.areasRestored.one': 'Restored {count} configuration area from “{name}”.',
    'backup.areasRestored.other': 'Restored {count} configuration areas from “{name}”.',

    'snapshots.title': 'Snapshots',
    'snapshots.lead':
      'A snapshot freezes every configuration area on the server and can be restored '
      + 'without a download.',
    'snapshots.count.one': '{count} of {limit} possible snapshots is saved.',
    'snapshots.count.other': '{count} of {limit} possible snapshots are saved.',
    'snapshots.labelField': 'Label (optional)',
    'snapshots.labelExample': 'e.g. before the persona rework',
    'snapshots.create': 'Create snapshot',
    'snapshots.creating': 'Creating …',
    'snapshots.empty':
      'No snapshots yet. A snapshot preserves the configuration as it stands right now — '
      + 'worth doing before larger changes.',
    'snapshots.restore': 'Restore',
    'snapshots.delete': 'Delete',
    'snapshots.confirmRestore':
      'Restore “{name}”? The configuration areas from this snapshot overwrite the current '
      + 'state. Areas it does not contain stay unchanged.',
    'snapshots.confirmRestoreYes': 'Yes, restore',
    'snapshots.confirmDelete':
      'Delete “{name}” for good? The preserved state is then only available through a '
      + 'downloaded ZIP.',
    'snapshots.created': 'Snapshot “{name}” created.',
    'snapshots.deleted': 'Snapshot “{name}” deleted.',
    'snapshots.downloaded': '“{name}” downloaded.',

    'factory.title': 'Factory settings',
    'factory.lead':
      'The factory state is the configuration a freshly installed system starts from. It '
      + 'lives as its own state on the server and can be restored at any time.',
    'factory.checking': 'Checking the factory state …',
    'factory.savedAt': 'Saved on {date}',
    'factory.none':
      'No factory state saved. Save the current state once the configuration is ready to '
      + 'ship.',
    'factory.save': 'Save from live state',
    'factory.saving': 'Saving …',
    'factory.reset': 'Reset',
    'factory.resetting': 'Restoring …',
    'factory.confirmSave':
      'Save the current live state as the factory state? The factory state saved so far '
      + 'will be overwritten.',
    'factory.confirmSaveYes': 'Yes, replace the factory state',
    'factory.confirmReset':
      'Reset to the factory state? The configuration areas from the saved state overwrite '
      + 'the current ones — ongoing conversations and monitoring data stay untouched.',
    'factory.confirmResetYes': 'Yes, reset',
    'factory.uploadLabel': 'Take a factory state from a ZIP',
    'factory.upload': 'Upload',
    'factory.uploading': 'Applying …',
    'factory.confirmUpload':
      'Take “{name}” as the new factory state? The factory state saved so far will be '
      + 'overwritten.',
    'factory.confirmUploadYes': 'Yes, take it',
    'factory.saved': 'Factory state saved from the current live state.',
    'factory.wasReset.one': 'Reset {count} configuration area to the factory state.',
    'factory.wasReset.other': 'Reset {count} configuration areas to the factory state.',
    'factory.downloaded': 'Factory state downloaded.',
    'factory.uploaded': 'Took “{name}” as the factory state.',
  },
};
