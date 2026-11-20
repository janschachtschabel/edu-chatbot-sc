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
  // Review der Oberfläche, 8: die Namen der Orte statt „lesen lassen“/„übertragen“
  lesenNachAnmeldung: 'Dateien „Hier im Chat“ hochladen geht erst, wenn du bei WLO angemeldet bist.',
  ablageNachAnmeldung: 'Dateien „In WLO ablegen“ – in deinem persönlichen Bereich, dort entstehen Volltexte und Metadaten – geht, wenn du bei WLO angemeldet bist.',
  // Review Paket E, MINOR 8: auf dem Dokument-Weg läuft kein Flow — keine Metadaten versprechen
  ablageNachAnmeldungDokument: 'Dateien „In WLO ablegen“ – in deinem persönlichen Bereich, dort liest der Chat danach ihren Text – geht, wenn du bei WLO angemeldet bist.',
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
  // Plan 2026-11-17, Paket U4: „Wo sollen sie verarbeitet werden?“ — Chips, ein Knopf „Hochladen“
  frage: 'Wo sollen sie verarbeitet werden?',
  ort: { chat: 'Hier im Chat', wlo: 'In WLO ablegen und erschließen' },
  // Plan 2026-11-20 §8, E3: ohne folgenden Flow (Dokument-Weg, kein Flow-Träger) kein „erschließen“
  ortWloAblegen: 'In WLO ablegen',
  // Review der Oberfläche, 9: „ohne Anmeldung“ nur, wenn die Schalter es tragen
  // zweites Review, 2: die Frist beginnt bei jeder Nutzung neu (`ablage.beruehren`)
  erklaerChat: (n: number, h: number, ohneAnmeldung: boolean) => `schnell, ${ohneAnmeldung ? 'ohne Anmeldung, ' : ''}bis ${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')} – Text bleibt bis zu ${zahl('de', h)} ${mehrzahl('de', h, 'Stunde', 'Stunden')} nach der letzten Nutzung hier`,
  erklaerWlo: 'alle Dateien, mit WLO-Anmeldung – Titel, Beschreibung, Fach und Stufe entstehen in WLO im Hintergrund',
  erklaerWloOhne: 'alle Dateien, mit WLO-Anmeldung – nur ablegen; Angaben werden gerade nicht erzeugt',
  erklaerWloDokument: 'alle Dateien, mit WLO-Anmeldung – nur ablegen; den Text liest der Chat danach aus WLO',
  nichtWaehlbar: (grund: string) => `nicht wählbar – ${grund}`,
  gesperrt: {
    aus: 'gerade ausgeschaltet', nur_angemeldet: 'braucht eine WLO-Anmeldung',
    ablauf: 'in diesem Ablauf nicht vorgesehen', keine: 'keine der Dateien hat eine Art, die WLO annimmt',
  },
  // zweites Review, 5: mit dem Ausweg (Frist, „Arbeitsstand löschen“, WLO)
  sitzungVoll: (h: number, wlo: boolean) => `hier im Chat ist für dieses Gespräch kein Platz mehr – wieder frei nach ${zahl('de', h)} ${mehrzahl('de', h, 'Stunde', 'Stunden')} ohne Nutzung oder mit „Arbeitsstand löschen“${wlo ? ' – oder in WLO ablegen' : ''}`,
  keineHier: 'keine Datei, die der Chat lesen kann – PDF, Word, Text oder Markdown',
  zuGrossDateiHier: (mb: number) => `jede Datei ist zu groß für hier (höchstens ${zahl('de', mb)} MB je Datei)`,
  zuVieleHier: (n: number) => `zu viele Dateien für hier (höchstens ${zahl('de', n)})`,
  zuGrossHier: (mb: number) => `zu viel für hier (höchstens ${zahl('de', mb)} MB zusammen)`,
  // der Rest der Sitzung (`lokal_frei_*`)
  freiHier: (n: number) => `zu viele Dateien für hier – in diesem Gespräch ${mehrzahl('de', n, 'geht', 'gehen')} noch ${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')}`,
  freiMbHier: (mb: number) => `zu viel für hier – in diesem Gespräch gehen noch ${zahl('de', mb)} MB`,
  mitAnmeldung: (satz: string) => `${satz} – mit Anmeldung über WLO`,
  zuVieleStapel: (n: number) => `höchstens ${zahl('de', n)} Dateien auf einmal – bitte einige ignorieren`,
  hochladen: 'Hochladen',
  nurNamen: 'Nur Namen senden (nichts hochladen)',
  nichtLesbar: (n: number) => `${zahl('de', n)} ${mehrzahl('de', n, 'Datei kann', 'Dateien kann')} der Chat nicht lesen – davon geht nur der Name mit.`,
  zuGrossHinweis: (n: number, mb: number) => `${zahl('de', n)} ${mehrzahl('de', n, 'Datei ist', 'Dateien sind')} größer als ${zahl('de', mb)} MB – davon geht nur der Name mit.`,
  sendetDatei: (k: number, n: number, prozent: number) => `Datei ${zahl('de', k)} von ${zahl('de', n)} wird hochgeladen … ${prozent} %`,
  liestDatei: (k: number, n: number) => `Datei ${zahl('de', k)} von ${zahl('de', n)} wird gelesen …`,
  // Plan 2026-11-19, Paket C: ob eine PDF gescannt ist, weiß erst der Server — darum „bei gescannten Seiten“
  // Review 11: ehrlich zur Frist (80 s Texterkennung, dazu Moderation und Speichern)
  texterkennungLaeuft: 'Bei gescannten Seiten läuft eine Texterkennung – das kann bis zu anderthalb Minuten dauern.',
  dateiVon: (k: number, n: number) => `Datei ${zahl('de', k)} von ${zahl('de', n)}`,
  gelesenWartet: (n: number) => `Gelesen: ${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')}. Bitte warten, bis die Antwort da ist.`,
  fehlerBei: (name: string, satz: string) => `„${name}“: ${satz}`,
  ohneWeiter: 'Ohne diese weiter',
  // Review der Oberfläche, 1 und 2: Anhalten und das Ende an der Sitzungsgrenze
  anhalten: 'Nach dieser Datei anhalten',
  haeltAn: 'Hält nach dieser Datei an …',
  angehalten: (dateien: string) => `Angehalten – gelesen: ${dateien}.`,
  mitGelesenen: 'Mit den gelesenen weiter',
  weiterOderNamen: 'Mach mit den gelesenen weiter oder sende nur die Namen.',
  nurNamenRest: 'Sende nur die Namen.',
  bleibenHier: (h: number) => `Bereits gelesene Dateien bleiben bis zu ${zahl('de', h)} ${mehrzahl('de', h, 'Stunde', 'Stunden')} nach der letzten Nutzung hier im Chat; ein daraus erstellter Entwurf bleibt im Arbeitsstand.`,
  weiterNachLesen: 'Weiter',
  // Review TG-1, m4: der Name enthält die Beschriftung (Label in Name) und sagt, was gesendet wird
  weiterNachLesenName: 'Weiter: gelesene Dateien an den Chat',
  nochmal: 'Noch einmal versuchen',
  chatFehler: {
    bild: 'Bilder kann der Chat nicht lesen.',
    art_unbekannt: 'Diese Dateiart kann der Chat nicht lesen (PDF, Word, Text oder Markdown).',
    zu_gross: 'Die Datei ist zu groß.',
    zu_viele_seiten: 'Die Datei hat zu viele Seiten.',
    entpackt_zu_gross: 'Die Datei ist zu groß.',
    kein_text: 'In der Datei steht kein lesbarer Text – vielleicht ist sie eingescannt.',
    // Review Paket C, 3: das Seitenbudget der Texterkennung je Sitzung
    grenze_ocr: 'Für dieses Gespräch sind schon so viele gescannte Seiten gelesen, wie gehen. Text-PDFs gehen weiter.',
    abgewiesen: 'Diese Datei kann der Chat nicht verarbeiten.',
    // Der Satz nennt nur Knöpfe, die es gibt (Review der Oberfläche, 1): den Weg nach `grenze_anzahl`
    // hängt die Ansicht an (`weiterOderNamen`/`nurNamenRest`); nach `grenze_gesamt` geht es weiter.
    grenze_anzahl: 'Hier im Chat liegen für dieses Gespräch schon so viele Dateien, wie gehen.',
    // zweites Review, 7: der Ablauf lässt den Ort nicht zu — endet wie `grenze_anzahl`
    ort_nicht_erlaubt: 'In diesem Ablauf ist „Hier im Chat“ nicht vorgesehen.',
    grenze_gesamt: 'Diese Datei passt nicht mehr dazu – hier im Chat liegt für dieses Gespräch schon fast so viel, wie geht. Mach ohne diese weiter; eine kleinere passt vielleicht noch.',
    nur_angemeldet: 'Dafür bitte bei WLO anmelden.',
    aus: 'Dateien im Chat lesen ist gerade ausgeschaltet.',
    keine_anfrage: 'Dieses Auswahlfeld ist nicht mehr offen. Bitte im Chat neu fragen.',
    sitzung_unbekannt: 'Dieses Auswahlfeld ist nicht mehr offen. Bitte im Chat neu fragen.',
    sitzung: 'Das Gespräch hat gewechselt. Bitte noch einmal wählen.',
    laeuft_schon: 'Es wird schon eine Datei gelesen.',
    ausgelastet: 'Gerade ist viel los. Bitte gleich noch einmal versuchen.',
    pruefung_fehlt: 'Die Datei konnte gerade nicht geprüft werden. Bitte später noch einmal versuchen.',
    gedrosselt: 'Zu viele Anfragen. Bitte kurz warten.',
    zu_langsam: 'Das Lesen hat zu lange gedauert.',
    unlesbar: 'Die Datei ließ sich nicht lesen – ist sie beschädigt oder geschützt?',
    netz: 'Keine Verbindung zum Server.',
    fehler: 'Die Datei ließ sich nicht lesen.',
  },
  // ältere Antworten (`aktion: dokument`, vor Paket U) in der Anzeige „nur lesen“
  nurLesenDokumente: (n: number, abschnitte: string) => `Gelesen: ${n} Dokumente, ${abschnitte}.`,
  abschnitte: (n: number) => `${zahl('de', n)} ${mehrzahl('de', n, 'Abschnitt', 'Abschnitte')}`,
  nurLesenDokument: (name: string, abschnitte: string) => `Gelesen: ${name}, ${abschnitte}.`,
  // Plan 2026-11-16, TG-3a (G-E1): seit dem Teil `struktur` gehen auch die Dateinamen an den Chat.
  // Paket U4: der Satz richtet sich nach dem gewählten Ort — was geht wohin, wie lange
  datenschutzLeer: 'Beim Auswählen wird nichts hochgeladen. Danach wählst du, wo die Dateien verarbeitet werden.',
  datenschutz: 'Ordner- und Dateinamen gehen an den Chat; alle Inhalte bleiben auf deinem Gerät.',
  // Paket C: angehängt, wenn der Server `orte.chat.texterkennung` meldet
  datenschutzOcr: 'Gescannte Seiten gehen als Bild an das KI-Modell.',
  datenschutzChat: (h: number) => `Ordner- und Dateinamen gehen an den Chat. „Hochladen“ schickt die lesbaren Dateien an den Chat; er behält nur ihren Text, bis zu ${zahl('de', h)} ${mehrzahl('de', h, 'Stunde', 'Stunden')} nach der letzten Nutzung, und für kurze Angaben liest sein KI-Modell den Anfang jedes Inhalts; ein daraus erstellter Entwurf bleibt im Arbeitsstand. Alle anderen Dateien bleiben auf deinem Gerät.`,
  datenschutzWlo: 'Ordner- und Dateinamen gehen an den Chat. „Hochladen“ legt die Dateien nach deiner Bestätigung in deinem persönlichen Bereich in WLO ab; dort bleiben sie, bis du sie löschst, und WLO erzeugt daraus Titel, Beschreibung, Fach und Stufe.',
  datenschutzWloOhne: 'Ordner- und Dateinamen gehen an den Chat. „Hochladen“ legt die Dateien nach deiner Bestätigung in deinem persönlichen Bereich in WLO ab; dort bleiben sie, bis du sie löschst.',
  // Review Paket E, MINOR 9: der Dokument-Weg — was mit dem Text geschieht
  datenschutzWloDokument: 'Ordner- und Dateinamen gehen an den Chat. „Hochladen“ legt die Dateien nach deiner Bestätigung in deinem persönlichen Bereich in WLO ab; danach liest der Chat den Text aus WLO, sein KI-Modell erstellt daraus den Entwurf.',
  // Review TG-3a–c, NIT: ein Dateiname nur aus Leerzeichen
  dateiOhneName: '(ohne Namen)',
  nichtVerwendet: 'Nicht verwendet.',
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
  blaseNamen: (name: string, ordner: string, dateien: string) => `Nur die Namen gesendet – „${name}“: ${ordner}, ${dateien}.`,
  // Review 12: eigene Form, wenn alle per Texterkennung gelesen sind
  blaseChat: (n: number, ocr = 0) => `Hier im Chat bereitgestellt: ${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')}${
    !ocr ? '' : ocr < n ? `, davon ${zahl('de', ocr)} per Texterkennung gelesen` : n === 1 ? ', per Texterkennung gelesen' : ', alle per Texterkennung gelesen'}.`,
  nurLesen: (ordner: string, dateien: string) => `Erfasst: ${ordner}, ${dateien}.`,
  nurLesenNamen: (ordner: string, dateien: string) => `Nur Namen gesendet: ${ordner}, ${dateien}.`,
  nurLesenChat: (dateien: string) => `Hier im Chat bereitgestellt: ${dateien}.`,
};

const EN: typeof DE = {
  titel: 'Folders and files',
  hinweisLeer: 'Drop a folder here or choose one. Nothing is uploaded yet.',
  lesenNachAnmeldung: 'Uploading files “Here in the chat” only works once you are signed in to WLO.',
  ablageNachAnmeldung: '“Store in WLO” – in your personal area, where full texts and metadata are created – works once you are signed in to WLO.',
  ablageNachAnmeldungDokument: '“Store in WLO” – in your personal area, where the chat then reads their text – works once you are signed in to WLO.',
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
  frage: 'Where should they be processed?',
  ort: { chat: 'Here in the chat', wlo: 'Store and index in WLO' },
  ortWloAblegen: 'Store in WLO',
  erklaerChat: (n: number, h: number, ohneAnmeldung: boolean) => `quick, ${ohneAnmeldung ? 'no sign-in, ' : ''}up to ${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')} – the text stays here for up to ${zahl('en', h)} ${mehrzahl('en', h, 'hour', 'hours')} after last use`,
  erklaerWlo: 'all files, with WLO sign-in – title, description, subject and level are created in WLO in the background',
  erklaerWloOhne: 'all files, with WLO sign-in – store only; details are not being created right now',
  erklaerWloDokument: 'all files, with WLO sign-in – store only; the chat then reads the text from WLO',
  nichtWaehlbar: (grund: string) => `not available – ${grund}`,
  gesperrt: {
    aus: 'switched off right now', nur_angemeldet: 'needs a WLO sign-in',
    ablauf: 'not intended in this workflow', keine: 'none of the files has a type WLO accepts',
  },
  sitzungVoll: (h: number, wlo: boolean) => `no room left here in the chat for this conversation – free again after ${zahl('en', h)} ${mehrzahl('en', h, 'hour', 'hours')} without use or with “Delete work in progress”${wlo ? ' – or store in WLO' : ''}`,
  keineHier: 'no file the chat can read – PDF, Word, text or Markdown',
  zuGrossDateiHier: (mb: number) => `every file is too large for here (at most ${zahl('en', mb)} MB per file)`,
  zuVieleHier: (n: number) => `too many files for here (at most ${zahl('en', n)})`,
  zuGrossHier: (mb: number) => `too much for here (at most ${zahl('en', mb)} MB in total)`,
  freiHier: (n: number) => `too many files for here – ${zahl('en', n)} more ${mehrzahl('en', n, 'file fits', 'files fit')} in this conversation`,
  freiMbHier: (mb: number) => `too much for here – ${zahl('en', mb)} MB more fit in this conversation`,
  mitAnmeldung: (satz: string) => `${satz} – with sign-in via WLO`,
  zuVieleStapel: (n: number) => `at most ${zahl('en', n)} files at once – please ignore some`,
  hochladen: 'Upload',
  nurNamen: 'Send names only (upload nothing)',
  nichtLesbar: (n: number) => `The chat cannot read ${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')} – only the name goes along.`,
  zuGrossHinweis: (n: number, mb: number) => `${zahl('en', n)} ${mehrzahl('en', n, 'file is', 'files are')} larger than ${zahl('en', mb)} MB – only the name goes along.`,
  sendetDatei: (k: number, n: number, prozent: number) => `Uploading file ${zahl('en', k)} of ${zahl('en', n)} … ${prozent} %`,
  liestDatei: (k: number, n: number) => `Reading file ${zahl('en', k)} of ${zahl('en', n)} …`,
  texterkennungLaeuft: 'For scanned pages, text recognition is running – this can take up to a minute and a half.',
  dateiVon: (k: number, n: number) => `File ${zahl('en', k)} of ${zahl('en', n)}`,
  gelesenWartet: (n: number) => `Read: ${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')}. Please wait for the answer.`,
  fehlerBei: (name: string, satz: string) => `“${name}”: ${satz}`,
  ohneWeiter: 'Continue without it',
  anhalten: 'Stop after this file',
  haeltAn: 'Stopping after this file …',
  angehalten: (dateien: string) => `Stopped – read: ${dateien}.`,
  mitGelesenen: 'Continue with the files read',
  weiterOderNamen: 'Continue with the files read or send names only.',
  nurNamenRest: 'Send names only.',
  bleibenHier: (h: number) => `Files already read stay here in the chat for up to ${zahl('en', h)} ${mehrzahl('en', h, 'hour', 'hours')} after last use; a draft made from them stays in your work in progress.`,
  weiterNachLesen: 'Continue',
  weiterNachLesenName: 'Continue: read files to the chat',
  nochmal: 'Try again',
  chatFehler: {
    bild: 'The chat cannot read images.',
    art_unbekannt: 'The chat cannot read this file type (PDF, Word, text or Markdown).',
    zu_gross: 'The file is too large.',
    zu_viele_seiten: 'The file has too many pages.',
    entpackt_zu_gross: 'The file is too large.',
    kein_text: 'The file contains no readable text – it may be scanned.',
    grenze_ocr: 'This conversation has used up its scanned pages. PDFs with text still work.',
    abgewiesen: 'The chat cannot process this file.',
    grenze_anzahl: 'This conversation already holds as many files here in the chat as allowed.',
    ort_nicht_erlaubt: 'This workflow does not provide for “Here in the chat”.',
    grenze_gesamt: 'This file no longer fits – this conversation already holds nearly as much here in the chat as allowed. Continue without it; a smaller one may still fit.',
    nur_angemeldet: 'Please sign in to WLO for this.',
    aus: 'Reading files in the chat is switched off right now.',
    keine_anfrage: 'This picker is no longer open. Please ask in the chat again.',
    sitzung_unbekannt: 'This picker is no longer open. Please ask in the chat again.',
    sitzung: 'The conversation has changed. Please choose again.',
    laeuft_schon: 'A file is already being read.',
    ausgelastet: 'The system is busy. Please try again in a moment.',
    pruefung_fehlt: 'The file could not be checked right now. Please try again later.',
    gedrosselt: 'Too many requests. Please wait a moment.',
    zu_langsam: 'Reading took too long.',
    unlesbar: 'The file could not be read – is it damaged or protected?',
    netz: 'No connection to the server.',
    fehler: 'The file could not be read.',
  },
  nurLesenDokumente: (n: number, abschnitte: string) => `Read: ${n} documents, ${abschnitte}.`,
  abschnitte: (n: number) => `${zahl('en', n)} ${mehrzahl('en', n, 'section', 'sections')}`,
  nurLesenDokument: (name: string, abschnitte: string) => `Read: ${name}, ${abschnitte}.`,
  datenschutzLeer: 'Nothing is uploaded while you choose. Afterwards you pick where the files are processed.',
  datenschutz: 'Folder and file names go to the chat; all contents stay on your device.',
  datenschutzOcr: 'Scanned pages go to the AI model as images.',
  datenschutzChat: (h: number) => `Folder and file names go to the chat. “Upload” sends the readable files to the chat; it keeps only their text, for up to ${zahl('en', h)} ${mehrzahl('en', h, 'hour', 'hours')} after last use, and its AI model reads the beginning of each content file for short details; a draft made from them stays in your work in progress. All other files stay on your device.`,
  datenschutzWlo: 'Folder and file names go to the chat. After you confirm, “Upload” stores the files in your personal area in WLO; they stay there until you delete them, and WLO creates title, description, subject and level from them.',
  datenschutzWloOhne: 'Folder and file names go to the chat. After you confirm, “Upload” stores the files in your personal area in WLO; they stay there until you delete them.',
  datenschutzWloDokument: 'Folder and file names go to the chat. After you confirm, “Upload” stores the files in your personal area in WLO; the chat then reads the text from WLO, and its AI model creates the draft from it.',
  dateiOhneName: '(no name)',
  nichtVerwendet: 'Not used.',
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
  blaseNamen: (name: string, ordner: string, dateien: string) => `Sent names only – “${name}”: ${ordner}, ${dateien}.`,
  blaseChat: (n: number, ocr = 0) => `Provided here in the chat: ${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')}${
    !ocr ? '' : ocr < n ? `, ${zahl('en', ocr)} of them read by text recognition` : n === 1 ? ', read by text recognition' : ', all read by text recognition'}.`,
  nurLesen: (ordner: string, dateien: string) => `Captured: ${ordner}, ${dateien}.`,
  nurLesenNamen: (ordner: string, dateien: string) => `Sent names only: ${ordner}, ${dateien}.`,
  nurLesenChat: (dateien: string) => `Provided here in the chat: ${dateien}.`,
};

export type UploadTexte = typeof DE;

/** Wie `fehlerSatz` beim Übertragen: der Typ hält DE und EN gleich (Querschnitts-Review FE-8). */
export function chatFehlerSatz(t: UploadTexte, code: string): string {
  const saetze: Readonly<Record<string, string>> = t.chatFehler;
  return Object.hasOwn(saetze, code) ? saetze[code] : t.chatFehler.fehler;
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
