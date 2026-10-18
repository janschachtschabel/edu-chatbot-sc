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
    'fassungen.alleAufEinmal': 'Alle Bereiche auf einmal',
    'fassungen.mehr': 'Was bedeutet das?',
    'backup.reiter.werk': 'Werksfassung',
    'backup.reiter.sichern': 'Sichern',
    'backup.intro':
      'Oben, welche Bereiche der Werksfassung folgen und welche angepasst sind; darunter die '
      + 'Sicherungen. Alle sichern dasselbe: die Konfigurationsbereiche des Chatbots. '
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
      '„{name}“ einspielen? Jeder Bereich aus der ZIP überschreibt seinen aktuellen Stand.',
    'backup.confirmRestoreYes': 'Ja, einspielen',
    'backup.downloaded': 'Backup heruntergeladen.',
    // ST-9: die Kopfzeile. Einspielen führt zur Sicherungs-Seite — daher „…".
    'backupTools.restore': 'Backup einspielen …',
    'backupTools.toSnapshots': 'Zu den Snapshots',
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
    // Paket 12: selbst angelegt oder vom Server vor einem Überschreiben.
    'snapshots.art.hand': 'von Hand',
    'snapshots.art.auto': 'automatisch',
    'snapshots.delete': 'Löschen',
    'snapshots.confirmRestore':
      '„{name}“ einspielen? Die Konfigurationsbereiche aus diesem Snapshot überschreiben '
      + 'den aktuellen Stand.',
    'snapshots.confirmRestoreYes': 'Ja, wiederherstellen',
    'snapshots.confirmDelete':
      '„{name}“ endgültig löschen? Der gesicherte Stand ist danach nur noch über eine '
      + 'heruntergeladene ZIP verfügbar.',
    'snapshots.created': 'Snapshot „{name}“ angelegt.',
    'snapshots.deleted': 'Snapshot „{name}“ gelöscht.',
    'snapshots.downloaded': '„{name}“ heruntergeladen.',

    // ── Werksstand ──────────────────────────────────────────────────
    'factory.title': 'Eigener Grundstand',
    'factory.lead':
      'Ein selbst gesicherter Stand der gelebten Konfiguration, auf den du jederzeit '
      + 'zurücksetzen kannst. Er kommt nicht aus dem Repository — die Werksfassung steht in '
      + 'der Karte „Werk und eigene Fassung“.',
    'factory.checking': 'Grundstand wird geprüft …',
    'factory.savedAt': 'Gesichert am {date}',
    'factory.none':
      'Kein Grundstand gesichert. Sichere den aktuellen Stand, wenn du einen Punkt zum '
      + 'Zurücksetzen brauchst.',
    'factory.save': 'Aus Live-Stand sichern',
    'factory.saving': 'Wird gesichert …',
    'factory.reset': 'Zurücksetzen',
    'factory.resetting': 'Wird eingespielt …',
    'factory.confirmSave':
      'Den aktuellen Live-Stand als Grundstand sichern? Der bisher gesicherte Grundstand '
      + 'wird dabei überschrieben.',
    'factory.confirmSaveYes': 'Ja, Grundstand ersetzen',
    'factory.confirmReset':
      'Auf den Grundstand zurücksetzen? Die Konfigurationsbereiche aus dem gesicherten '
      + 'Stand überschreiben den aktuellen — laufende Gespräche und Auswertungen bleiben '
      + 'unberührt.',
    'factory.confirmResetYes': 'Ja, zurücksetzen',
    'factory.uploadLabel': 'Grundstand aus einer ZIP übernehmen',
    'factory.upload': 'Hochladen',
    'factory.uploading': 'Wird übernommen …',
    'factory.confirmUpload':
      '„{name}“ als neuen Grundstand übernehmen? Der bisher gesicherte Grundstand wird '
      + 'überschrieben.',
    'factory.confirmUploadYes': 'Ja, übernehmen',
    'factory.saved': 'Grundstand aus dem aktuellen Live-Stand gesichert.',
    'factory.wasReset.one': '{count} Konfigurationsbereich auf den Grundstand zurückgesetzt.',
    'factory.wasReset.other': '{count} Konfigurationsbereiche auf den Grundstand zurückgesetzt.',
    'factory.downloaded': 'Grundstand heruntergeladen.',
    'factory.uploaded': '„{name}“ als Grundstand übernommen.',

    // ── Werksfassung aus dem Repository (S4; bis Paket 12 „Auslieferungsstand“) ──
    // Der Unterschied zum Grundstand darüber muss im Text stehen, sonst
    // stehen zwei Karten mit fast gleichem Wort nebeneinander und niemand
    // weiss, welche was tut.
    'seed.title': 'Werksfassung aus dem Repository',
    'seed.lead':
      'Die Werksfassung, mit der dieses Abbild gebaut wurde — sie liegt im Abbild selbst, '
      + 'nachgeladen wird nichts. Unberührte Bereiche folgen ihr beim Start von selbst; '
      + 'hier lässt sich zählen und im Ganzen herstellen. Je Bereich umschalten geht in der '
      + 'Karte „Werk und eigene Fassung“.',
    'seed.checking': 'Werksfassung wird gelesen …',
    'seed.unavailable':
      'Dieses Abbild bringt keine Werksfassung mit. Nichts zu tun.',
    /** Beschriftung vor der Zahl, nicht dahinter: „1 fehlen in der Datenbank"
     *  wäre falsch, und für fünf Zeilen sechs Pluralschlüssel anzulegen, nur
     *  damit die Verben stimmen, wäre teurer als die Umstellung. So ist jede
     *  Zeile bei jeder Zahl richtig. */
    'seed.areaCount': 'Bereiche im Abbild: {count}',
    'seed.same': 'unverändert: {count}',
    'seed.new': 'fehlend: {count}',
    'seed.differing': 'abweichend: {count}',
    'seed.onlyInDb': 'nur in der Datenbank: {count}',
    'seed.names': 'Bereiche im Einzelnen',
    'seed.fill': 'Fehlende nachziehen',
    'seed.filling': 'Wird nachgezogen …',
    'seed.exact': 'Alles auf die Werksfassung',
    'seed.exacting': 'Wird hergestellt …',
    /** Der scharfe Knopf. Der Satz nennt beide Folgen — Überschreiben *und*
     *  Löschen — weil die zweite die ist, die niemand erwartet. */
    'seed.confirmExact':
      'Alles auf die Werksfassung bringen? Abweichende Bereiche werden '
      + 'überschrieben und Bereiche, die es nur in der Datenbank gibt, gelöscht. '
      + 'Vorher wird automatisch ein Schnappschuss angelegt — das ist der Rückweg.',
    'seed.confirmExactYes': 'Ja, herstellen',
    'seed.filled.one': '{count} Bereich nachgezogen.',
    'seed.filled.other': '{count} Bereiche nachgezogen.',
    'seed.nothingToFill': 'Nichts nachzuziehen — es fehlt kein Bereich.',
    /** Zwei Zahlen in einem Satz — dieselbe Umstellung wie bei den Zählungen
     *  oben, statt vier Pluralformen für eine Meldung. */
    'seed.applied':
      'Geschrieben: {written}, gelöscht: {deleted}. Der Stand davor liegt als '
      + 'Schnappschuss „vor Werksfassung“ oben in der Liste.',
  },

  en: {
    'fassungen.alleAufEinmal': 'All areas at once',
    'fassungen.mehr': 'What does this mean?',
    'backup.reiter.werk': 'Factory version',
    'backup.reiter.sichern': 'Back up',
    'backup.intro':
      'At the top, which areas follow the factory version and which are customized; below, '
      + 'the backups. They all back up the same thing: the chatbot’s configuration areas. '
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
      'Restore “{name}”? Every area in the ZIP overwrites its current state.',
    'backup.confirmRestoreYes': 'Yes, restore',
    'backup.downloaded': 'Backup downloaded.',
    'backupTools.restore': 'Restore backup …',
    'backupTools.toSnapshots': 'Go to snapshots',
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
    'snapshots.art.hand': 'manual',
    'snapshots.art.auto': 'automatic',
    'snapshots.delete': 'Delete',
    'snapshots.confirmRestore':
      'Restore “{name}”? The configuration areas from this snapshot overwrite the current '
      + 'state.',
    'snapshots.confirmRestoreYes': 'Yes, restore',
    'snapshots.confirmDelete':
      'Delete “{name}” for good? The preserved state is then only available through a '
      + 'downloaded ZIP.',
    'snapshots.created': 'Snapshot “{name}” created.',
    'snapshots.deleted': 'Snapshot “{name}” deleted.',
    'snapshots.downloaded': '“{name}” downloaded.',

    'factory.title': 'Own baseline',
    'factory.lead':
      'A state of the live configuration you saved yourself and can reset to at any time. It '
      + 'does not come from the repository — the factory version is in the card “Factory and '
      + 'own version”.',
    'factory.checking': 'Checking the baseline …',
    'factory.savedAt': 'Saved on {date}',
    'factory.none':
      'No baseline saved. Save the current state once the configuration is ready to '
      + 'ship.',
    'factory.save': 'Save from live state',
    'factory.saving': 'Saving …',
    'factory.reset': 'Reset',
    'factory.resetting': 'Restoring …',
    'factory.confirmSave':
      'Save the current live state as the baseline? The baseline saved so far '
      + 'will be overwritten.',
    'factory.confirmSaveYes': 'Yes, replace the baseline',
    'factory.confirmReset':
      'Reset to the baseline? The configuration areas from the saved state overwrite '
      + 'the current ones — ongoing conversations and monitoring data stay untouched.',
    'factory.confirmResetYes': 'Yes, reset',
    'factory.uploadLabel': 'Take a baseline from a ZIP',
    'factory.upload': 'Upload',
    'factory.uploading': 'Applying …',
    'factory.confirmUpload':
      'Take “{name}” as the new baseline? The baseline saved so far will be '
      + 'overwritten.',
    'factory.confirmUploadYes': 'Yes, take it',
    'factory.saved': 'Baseline saved from the current live state.',
    'factory.wasReset.one': 'Reset {count} configuration area to the baseline.',
    'factory.wasReset.other': 'Reset {count} configuration areas to the baseline.',
    'factory.downloaded': 'Baseline downloaded.',
    'factory.uploaded': 'Took “{name}” as the baseline.',

    'seed.title': 'Factory version from the repository',
    'seed.lead':
      'The factory version this image was built from — it travels inside the image, nothing '
      + 'is fetched. Untouched areas follow it on every start; here you can count and apply '
      + 'it as a whole. Switching per area is in the card “Factory and own version”.',
    'seed.checking': 'Reading the factory version …',
    'seed.unavailable': 'This image ships no factory version. Nothing to do.',
    'seed.areaCount': 'Areas in the image: {count}',
    'seed.same': 'unchanged: {count}',
    'seed.new': 'missing: {count}',
    'seed.differing': 'differing: {count}',
    'seed.onlyInDb': 'only in the database: {count}',
    'seed.names': 'Areas in detail',
    'seed.fill': 'Add what is missing',
    'seed.filling': 'Adding …',
    'seed.exact': 'Match the factory version exactly',
    'seed.exacting': 'Applying …',
    'seed.confirmExact':
      'Match the factory version exactly? Differing areas are overwritten and areas that '
      + 'exist only in the database are deleted. A snapshot is taken first — that is the '
      + 'way back.',
    'seed.confirmExactYes': 'Yes, apply it',
    'seed.filled.one': 'Added {count} area.',
    'seed.filled.other': 'Added {count} areas.',
    'seed.nothingToFill': 'Nothing to add — no area is missing.',
    'seed.applied':
      'Written: {written}, deleted: {deleted}. The previous state is at the top of the '
      + 'snapshot list as “before factory version”.',
  },
};
