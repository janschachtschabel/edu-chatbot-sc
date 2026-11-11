/**
 * Texte des Moduls `ui_upload` (Paket U3-1a), Deutsch und Englisch. Zahlen über `Intl.NumberFormat`,
 * Einzahl/Mehrzahl über `Intl.PluralRules` — nie zusammengesetzt. Fremdtext (Ordnernamen) setzt das
 * Element immer als `textContent`.
 */
import type { AntwortWarnung } from './upload-antwort';
import type { Rolle } from './upload-erfassen';

export type Sprache = 'de' | 'en';

const DE = {
  titel: 'Ordner und Dateien',
  hinweisLeer: 'Ziehe einen Ordner hierher oder wähle ihn aus. Dabei wird noch nichts hochgeladen.',
  ablage: 'Ordner oder Dateien hier ablegen',
  ordnerWaehlen: 'Ordner wählen',
  dateienWaehlen: 'Dateien wählen',
  liest: 'Wird gelesen …',
  leseFehler: 'Der Ordner ließ sich nicht lesen. Bitte noch einmal auswählen.',
  nichtsGefunden: 'In der Auswahl sind keine Dateien.',
  auswahl: 'Auswahl',
  rolle: { inhalt: 'Inhalt', struktur: 'Strukturdokument', ignorieren: 'Ignorieren' } satisfies Record<Rolle, string>,
  rolleVon: (name: string) => `Rolle von ${name}`,
  alleIgnorieren: 'Alle ignorieren',
  wiederEinschliessen: 'Einschließen',
  alleIgnorierenIn: (name: string) => `Alle Dateien in ${name} ignorieren`,
  wiederEinschliessenIn: (name: string) => `Dateien in ${name} wieder einschließen`,
  strukturLesbar: (name: string) => `Strukturdokument: ${name}. Zum Lesen wird es hochgeladen; der Chat behält nur den Text, höchstens einen Tag.`,
  strukturNichtLesbar: (name: string) => `Strukturdokument: ${name}. Lesen lassen kann der Chat es hier nicht.`,
  ausDokument: { themenbaum: 'Themenbaum aus dem Strukturdokument erstellen' } satisfies Record<'themenbaum', string>,
  weiter: { themenbaum: 'Themenbaum jetzt erstellen' } satisfies Record<'themenbaum', string>,
  sendet: (prozent: number) => `Wird hochgeladen … ${prozent} %`,
  liestDokument: 'Das Dokument wird gelesen …',
  gelesen: (abschnitte: string) => `Gelesen: ${abschnitte}. Bitte warten, bis die Antwort da ist.`,
  nochmal: 'Noch einmal versuchen',
  dokumentFehler: {
    bild: 'Bilder kann der Chat nicht lesen – bitte ein PDF-, Word-, Text- oder Markdown-Dokument.',
    art_unbekannt: 'Diese Dateiart kann der Chat nicht lesen (PDF, Word, Text oder Markdown).',
    zu_gross: 'Das Dokument ist zu groß.',
    zu_viele_seiten: 'Das Dokument hat zu viele Seiten.',
    entpackt_zu_gross: 'Das Dokument ist zu groß.',
    kein_text: 'Im Dokument steht kein lesbarer Text – vielleicht ist es eingescannt.',
    abgewiesen: 'Dieses Dokument kann der Chat nicht verarbeiten.',
    nur_angemeldet: 'Dafür bitte bei WLO anmelden.',
    aus: 'Dokumente lesen ist gerade ausgeschaltet.',
    keine_anfrage: 'Dieses Auswahlfeld ist nicht mehr offen. Bitte im Chat neu fragen.',
    sitzung_unbekannt: 'Dieses Auswahlfeld ist nicht mehr offen. Bitte im Chat neu fragen.',
    sitzung: 'Das Gespräch hat gewechselt. Bitte noch einmal wählen.',
    laeuft_schon: 'Es wird schon ein Dokument gelesen.',
    ausgelastet: 'Gerade ist viel los. Bitte gleich noch einmal versuchen.',
    pruefung_fehlt: 'Das Dokument konnte gerade nicht geprüft werden. Bitte später noch einmal versuchen.',
    gedrosselt: 'Zu viele Anfragen. Bitte kurz warten.',
    zu_langsam: 'Das Lesen hat zu lange gedauert.',
    unlesbar: 'Das Dokument ließ sich nicht lesen – ist es beschädigt oder geschützt?',
    netz: 'Keine Verbindung zum Server.',
    fehler: 'Das Dokument ließ sich nicht lesen.',
  },
  abschnitte: (n: number) => `${zahl('de', n)} ${mehrzahl('de', n, 'Abschnitt', 'Abschnitte')}`,
  blaseDokument: { themenbaum: (name: string) => `Themenbaum aus „${name}“ erstellen` } satisfies Record<'themenbaum', (n: string) => string>,
  nurLesenDokument: (name: string, abschnitte: string) => `Gelesen: ${name}, ${abschnitte}.`,
  datenschutz: 'Nur Ordnernamen und Zahlen gehen an den Chat – und der Name eines markierten Strukturdokuments. Andere Dateinamen und alle Inhalte bleiben auf deinem Gerät.',
  datenschutzDokument: 'Nur Ordnernamen und Zahlen gehen an den Chat. Ein Strukturdokument wird erst hochgeladen, wenn du es lesen lässt; alle anderen Dateien bleiben auf deinem Gerät.',
  dokumentOhneName: 'Dokument',
  datenschutzAblage: 'Nur Ordnernamen und Zahlen gehen an den Chat. Dateien und ihre Titel gehen erst an WLO, wenn du sie überträgst – bis dahin bleiben sie auf deinem Gerät.',
  datenschutzBeides: 'Nur Ordnernamen und Zahlen gehen an den Chat. Ein Strukturdokument wird erst hochgeladen, wenn du es lesen lässt, und Dateien gehen erst an WLO, wenn du sie überträgst – bis dahin bleibt alles auf deinem Gerät.',
  nichtVerwendet: 'Nicht verwendet.',
  alsEntwurf: 'Als Themenbaum-Entwurf übernehmen',
  befundSenden: 'Senden',
  befundSendenName: 'Senden: Auswahl an den Chat',
  andereAuswahl: 'Andere Auswahl',
  beschaeftigt: 'Bitte warten, bis die Antwort da ist.',
  ordner: (n: number) => `${zahl('de', n)} Ordner`,
  dateien: (n: number) => `${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')}`,
  ignoriert: (n: number) => `${zahl('de', n)} ignoriert`,
  warnung: {
    zu_viele: (max: number) => `Mehr als ${zahl('de', max)} Dateien – erfasst sind die ersten ${zahl('de', max)}.`,
    zu_tief: (max: number) => `Ordner tiefer als ${max} Ebenen sind in der ${max}. Ebene zusammengefasst.`,
    zu_gross: (mb: number) => `Dateien über ${zahl('de', mb)} MB sind ignoriert.`,
    leer: () => 'Leere Dateien sind ignoriert.',
    ungueltiger_pfad: () => 'Dateien mit ungültigem Pfad sind weggelassen.',
    zu_viele_ordner: () => 'Sehr viele Ordner – nicht alle gehen an den Chat.',
  } satisfies Record<AntwortWarnung, (n: number) => string>,
  blaseErfasst: (name: string, ordner: string, dateien: string) => `Ordner „${name}“ erfasst: ${ordner}, ${dateien}.`,
  blaseEntwurf: (name: string) => `Ordnerstruktur „${name}“ als Themenbaum-Entwurf übernehmen`,
  nurLesen: (ordner: string, dateien: string) => `Erfasst: ${ordner}, ${dateien}.`,
};

const EN: typeof DE = {
  titel: 'Folders and files',
  hinweisLeer: 'Drop a folder here or choose one. Nothing is uploaded yet.',
  ablage: 'Drop folders or files here',
  ordnerWaehlen: 'Choose folder',
  dateienWaehlen: 'Choose files',
  liest: 'Reading …',
  leseFehler: 'The folder could not be read. Please choose it again.',
  nichtsGefunden: 'The selection contains no files.',
  auswahl: 'Selection',
  rolle: { inhalt: 'Content', struktur: 'Structure document', ignorieren: 'Ignore' },
  rolleVon: (name: string) => `Role of ${name}`,
  alleIgnorieren: 'Ignore all',
  wiederEinschliessen: 'Include',
  alleIgnorierenIn: (name: string) => `Ignore all files in ${name}`,
  wiederEinschliessenIn: (name: string) => `Include files in ${name} again`,
  strukturLesbar: (name: string) => `Structure document: ${name}. It is uploaded to be read; the chat keeps only the text, for one day at most.`,
  strukturNichtLesbar: (name: string) => `Structure document: ${name}. The chat cannot read it here.`,
  ausDokument: { themenbaum: 'Create topic tree from the structure document' },
  weiter: { themenbaum: 'Create topic tree now' },
  sendet: (prozent: number) => `Uploading … ${prozent} %`,
  liestDokument: 'Reading the document …',
  gelesen: (abschnitte: string) => `Read: ${abschnitte}. Please wait for the answer.`,
  nochmal: 'Try again',
  dokumentFehler: {
    bild: 'The chat cannot read images – please use a PDF, Word, text or Markdown document.',
    art_unbekannt: 'The chat cannot read this file type (PDF, Word, text or Markdown).',
    zu_gross: 'The document is too large.',
    zu_viele_seiten: 'The document has too many pages.',
    entpackt_zu_gross: 'The document is too large.',
    kein_text: 'The document contains no readable text – it may be scanned.',
    abgewiesen: 'The chat cannot process this document.',
    nur_angemeldet: 'Please sign in to WLO for this.',
    aus: 'Reading documents is switched off right now.',
    keine_anfrage: 'This picker is no longer open. Please ask in the chat again.',
    sitzung_unbekannt: 'This picker is no longer open. Please ask in the chat again.',
    sitzung: 'The conversation has changed. Please choose again.',
    laeuft_schon: 'A document is already being read.',
    ausgelastet: 'The system is busy. Please try again in a moment.',
    pruefung_fehlt: 'The document could not be checked right now. Please try again later.',
    gedrosselt: 'Too many requests. Please wait a moment.',
    zu_langsam: 'Reading took too long.',
    unlesbar: 'The document could not be read – is it damaged or protected?',
    netz: 'No connection to the server.',
    fehler: 'The document could not be read.',
  },
  abschnitte: (n: number) => `${zahl('en', n)} ${mehrzahl('en', n, 'section', 'sections')}`,
  blaseDokument: { themenbaum: (name: string) => `Create topic tree from “${name}”` },
  nurLesenDokument: (name: string, abschnitte: string) => `Read: ${name}, ${abschnitte}.`,
  datenschutz: 'Only folder names and counts go to the chat – plus the name of a marked structure document. Other file names and all contents stay on your device.',
  datenschutzDokument: 'Only folder names and counts go to the chat. A structure document is uploaded only when you have it read; all other files stay on your device.',
  dokumentOhneName: 'Document',
  datenschutzAblage: 'Only folder names and counts go to the chat. Files and their titles go to WLO only when you transfer them – until then they stay on your device.',
  datenschutzBeides: 'Only folder names and counts go to the chat. A structure document is uploaded only when you have it read, and files go to WLO only when you transfer them – until then everything stays on your device.',
  nichtVerwendet: 'Not used.',
  alsEntwurf: 'Use as topic tree draft',
  befundSenden: 'Send',
  befundSendenName: 'Send: selection to the chat',
  andereAuswahl: 'Choose again',
  beschaeftigt: 'Please wait for the answer.',
  ordner: (n: number) => `${zahl('en', n)} ${mehrzahl('en', n, 'folder', 'folders')}`,
  dateien: (n: number) => `${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')}`,
  ignoriert: (n: number) => `${zahl('en', n)} ignored`,
  warnung: {
    zu_viele: (max: number) => `More than ${zahl('en', max)} files – the first ${zahl('en', max)} are included.`,
    zu_tief: (max: number) => `Folders deeper than ${max} levels are merged into level ${max}.`,
    zu_gross: (mb: number) => `Files over ${zahl('en', mb)} MB are ignored.`,
    leer: () => 'Empty files are ignored.',
    ungueltiger_pfad: () => 'Files with an invalid path are left out.',
    zu_viele_ordner: () => 'Very many folders – not all of them go to the chat.',
  },
  blaseErfasst: (name: string, ordner: string, dateien: string) => `Folder “${name}” captured: ${ordner}, ${dateien}.`,
  blaseEntwurf: (name: string) => `Use folder structure “${name}” as topic tree draft`,
  nurLesen: (ordner: string, dateien: string) => `Captured: ${ordner}, ${dateien}.`,
};

export type UploadTexte = typeof DE;

/** Wie `fehlerSatz` beim Übertragen: der Typ hält DE und EN gleich (Querschnitts-Review FE-8). */
export function dokumentFehlerSatz(t: UploadTexte, code: string): string {
  const saetze: Readonly<Record<string, string>> = t.dokumentFehler;
  return Object.hasOwn(saetze, code) ? saetze[code] : t.dokumentFehler.fehler;
}

export function texte(sprache: Sprache): UploadTexte {
  return sprache === 'en' ? EN : DE;
}

/** Einzahl oder Mehrzahl nach den Regeln der Sprache. */
export function mehrzahl(sprache: Sprache, n: number, eins: string, mehr: string): string {
  return new Intl.PluralRules(sprache === 'en' ? 'en' : 'de-DE').select(n) === 'one' ? eins : mehr;
}

export function zahl(sprache: Sprache, n: number): string {
  return new Intl.NumberFormat(sprache === 'en' ? 'en' : 'de-DE').format(n);
}

/** Größe in kB/MB mit einer Nachkommastelle, je Sprache formatiert. */
export function groesse(sprache: Sprache, bytes: number): string {
  const fmt = new Intl.NumberFormat(sprache === 'en' ? 'en' : 'de-DE', { maximumFractionDigits: 1 });
  return bytes >= 1_000_000 ? `${fmt.format(bytes / 1_000_000)} MB` : `${fmt.format(Math.max(1, Math.round(bytes / 1000)))} kB`;
}
