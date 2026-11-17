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
  lesenNachAnmeldung: 'Ein Dokument lesen lassen geht erst, wenn du bei WLO angemeldet bist.',
  ablageNachAnmeldung: 'Dateien in deinen persönlichen Bereich in WLO übertragen – dort entstehen Volltexte und Metadaten – geht, wenn du bei WLO angemeldet bist.',
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
  // Plan 2026-11-16, TG-3e: mehrere Strukturdokumente, nacheinander gelesen
  strukturLesbarMehrere: (namen: string) => `Strukturdokumente: ${namen}. Zum Lesen wird jedes hochgeladen; der Chat behält nur den Text, höchstens einen Tag.`,
  strukturNichtLesbarMehrere: (namen: string) => `Strukturdokumente: ${namen}. Lesen lassen kann der Chat sie hier nicht.`,
  sendetNr: (nr: number, von: number, prozent: number) => `Dokument ${nr} von ${von} wird hochgeladen … ${prozent} %`,
  liestNr: (nr: number, von: number) => `Dokument ${nr} von ${von} wird gelesen …`,
  gelesenMehrere: (n: number, abschnitte: string) => `Gelesen: ${n} Dokumente, ${abschnitte}. Bitte warten, bis die Antwort da ist.`,
  fehlerBei: (name: string, satz: string) => `„${name}“: ${satz}`,
  ohneWeiter: 'Ohne dieses weiter',
  ohneWeiterName: (name: string) => `Ohne „${name}“ weiterlesen`,
  weiterNachLesenNameMehrere: 'Weiter: gelesene Dokumente an den Chat',
  blaseDokumente: (n: number) => `${n} Dokumente lesen lassen`,
  nurLesenDokumente: (n: number, abschnitte: string) => `Gelesen: ${n} Dokumente, ${abschnitte}.`,
  // Plan 2026-11-16, TG-1 (G-E4): neutral — was mit dem Dokument geschieht, klären Ablauf oder KI
  lesenLassen: 'Lesen lassen',
  weiterNachLesen: 'Weiter',
  // Review TG-1, m4: der Name enthält die Beschriftung (Label in Name) und sagt, was gesendet wird
  weiterNachLesenName: 'Weiter: gelesenes Dokument an den Chat',
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
  blaseDokument: (name: string) => `Dokument „${name}“ lesen lassen`,
  nurLesenDokument: (name: string, abschnitte: string) => `Gelesen: ${name}, ${abschnitte}.`,
  // Plan 2026-11-16, TG-3a (G-E1): seit dem Teil `struktur` gehen auch die Dateinamen an den Chat —
  // Inhalte erst, wenn die Person ein Dokument lesen oder Dateien nach WLO übertragen lässt
  datenschutz: 'Ordner- und Dateinamen gehen an den Chat; alle Inhalte bleiben auf deinem Gerät.',
  datenschutzDokument: 'Ordner- und Dateinamen gehen an den Chat. Das Strukturdokument wird erst hochgeladen, wenn du es lesen lässt; alle anderen Inhalte bleiben auf deinem Gerät.',
  dokumentOhneName: 'Dokument',
  // Review TG-3a–c, NIT: ein Dateiname nur aus Leerzeichen
  dateiOhneName: '(ohne Namen)',
  datenschutzAblage: 'Ordner- und Dateinamen gehen an den Chat. Dateien gehen erst an WLO, wenn du sie überträgst – bis dahin bleiben sie auf deinem Gerät.',
  datenschutzBeides: 'Ordner- und Dateinamen gehen an den Chat. Das Strukturdokument wird erst hochgeladen, wenn du es lesen lässt, und Dateien gehen erst an WLO, wenn du sie überträgst – bis dahin bleibt alles auf deinem Gerät.',
  nichtVerwendet: 'Nicht verwendet.',
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
    namen_gekuerzt: () => 'Namen über 120 Zeichen sind gekürzt.',
  } satisfies Record<AntwortWarnung, (n: number) => string>,
  blaseErfasst: (name: string, ordner: string, dateien: string) => `Ordner „${name}“ erfasst: ${ordner}, ${dateien}.`,
  nurLesen: (ordner: string, dateien: string) => `Erfasst: ${ordner}, ${dateien}.`,
};

const EN: typeof DE = {
  titel: 'Folders and files',
  hinweisLeer: 'Drop a folder here or choose one. Nothing is uploaded yet.',
  lesenNachAnmeldung: 'Having a document read only works once you are signed in to WLO.',
  ablageNachAnmeldung: 'Transferring files to your personal area in WLO – where full texts and metadata are created – works once you are signed in to WLO.',
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
  strukturLesbarMehrere: (namen: string) => `Structure documents: ${namen}. Each is uploaded to be read; the chat keeps only the text, for one day at most.`,
  strukturNichtLesbarMehrere: (namen: string) => `Structure documents: ${namen}. The chat cannot read them here.`,
  sendetNr: (nr: number, von: number, prozent: number) => `Uploading document ${nr} of ${von} … ${prozent} %`,
  liestNr: (nr: number, von: number) => `Reading document ${nr} of ${von} …`,
  gelesenMehrere: (n: number, abschnitte: string) => `Read: ${n} documents, ${abschnitte}. Please wait for the answer.`,
  fehlerBei: (name: string, satz: string) => `“${name}”: ${satz}`,
  ohneWeiter: 'Continue without it',
  ohneWeiterName: (name: string) => `Continue reading without “${name}”`,
  weiterNachLesenNameMehrere: 'Continue: read documents to the chat',
  blaseDokumente: (n: number) => `Read ${n} documents`,
  nurLesenDokumente: (n: number, abschnitte: string) => `Read: ${n} documents, ${abschnitte}.`,
  lesenLassen: 'Read document',
  weiterNachLesen: 'Continue',
  weiterNachLesenName: 'Continue: read document to the chat',
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
  blaseDokument: (name: string) => `Read “${name}”`,
  nurLesenDokument: (name: string, abschnitte: string) => `Read: ${name}, ${abschnitte}.`,
  datenschutz: 'Folder and file names go to the chat; all contents stay on your device.',
  datenschutzDokument: 'Folder and file names go to the chat. The structure document is uploaded only when you have it read; all other contents stay on your device.',
  dokumentOhneName: 'Document',
  dateiOhneName: '(no name)',
  datenschutzAblage: 'Folder and file names go to the chat. Files go to WLO only when you transfer them – until then they stay on your device.',
  datenschutzBeides: 'Folder and file names go to the chat. The structure document is uploaded only when you have it read, and files go to WLO only when you transfer them – until then everything stays on your device.',
  nichtVerwendet: 'Not used.',
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
    namen_gekuerzt: () => 'Names longer than 120 characters are shortened.',
  },
  blaseErfasst: (name: string, ordner: string, dateien: string) => `Folder “${name}” captured: ${ordner}, ${dateien}.`,
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
