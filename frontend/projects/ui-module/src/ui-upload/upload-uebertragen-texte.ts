/**
 * Texte des Übertragens in den persönlichen Bereich (Paket U3-3b), Deutsch und Englisch — eigene
 * Datei neben `upload-texte.ts`, damit beide bei einer Aufgabe bleiben. Zahlen und Mehrzahl über die
 * Helfer dort; Fremdtext (Datei- und Ordnernamen) setzt das Element immer als `textContent`.
 */
import { groesse, mehrzahl, type Sprache, zahl } from './upload-texte';
import type { Stand } from './upload-uebertragen';

const DE = {
  titel: 'In deinen persönlichen Bereich in WLO übertragen',
  auswahl: 'Auswahl',
  liste: 'Dateien der Übertragung',
  angebot: (dateien: string) => `${dateien} kannst du in deinen persönlichen Bereich in WLO übertragen. Erst nach deiner Bestätigung wird etwas hochgeladen.`,
  ausgelassen: (ohneArt: number, zuGross: number, mb: number) => [
    ohneArt ? `${zahl('de', ohneArt)} ${mehrzahl('de', ohneArt, 'Datei hat', 'Dateien haben')} eine Art, die WLO hier nicht annimmt.` : '',
    zuGross ? `${zahl('de', zuGross)} ${mehrzahl('de', zuGross, 'Datei ist', 'Dateien sind')} größer als ${zahl('de', mb)} MB.` : '',
  ].filter(Boolean).join(' '),
  zuViele: (max: number) => `Höchstens ${zahl('de', max)} Dateien je Übertragung – bitte einige ignorieren.`,
  keine: 'Keine der Dateien lässt sich übertragen.',
  pruefen: 'Übertragen vorbereiten …',
  prueft: (k: number, n: number) => `Dateien werden geprüft: ${zahl('de', k)} von ${zahl('de', n)}`,
  bereitet: 'Die Freigabe wird vorbereitet …',
  zielOrdner: (ordner: string) => `Ziel: dein persönlicher Bereich in WLO, neuer Ordner „${ordner}“.`,
  zielFlach: 'Ziel: dein persönlicher Bereich in WLO, ohne eigenen Ordner (dein Konto darf dort keine Ordner anlegen).',
  umfang: (dateien: string, bytes: number) => `${dateien}, zusammen ${groesse('de', bytes)}.`,
  jetzt: 'Jetzt übertragen',
  abbrechen: 'Abbrechen',
  anhalten: 'Nach dieser Datei anhalten',
  haeltAn: 'Hält nach dieser Datei an …',
  sendet: (k: number, n: number, prozent: number) => `Datei ${zahl('de', k)} von ${zahl('de', n)} wird übertragen … ${prozent} %`,
  fertig: (abgelegt: number, n: number) => `${zahl('de', abgelegt)} von ${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')} in WLO abgelegt.`,
  ordnerVerweigert: 'Den Ordner durfte dein Konto nicht anlegen – die Dateien liegen direkt in deinem persönlichen Bereich.',
  vorgangFehlt: 'Die Übersichtsdatei (vorgang.json) ließ sich nicht ablegen; die Dateien sind trotzdem da.',
  nochmal: 'Nicht übertragene noch einmal senden',
  weiter: 'Im Chat weitermachen',
  ansehen: (name: string) => `${name} in WLO ansehen`,
  stand: {
    wartet: 'wartet', sendet: 'wird übertragen', stored: 'abgelegt', dropped: 'angelegt, Inhalt nicht übernommen',
    unverified: 'unklar – keine Antwort von WLO', failed: 'nicht abgelegt', abgebrochen: 'nicht gesendet',
  } satisfies Record<Stand, string>,
  fehler: {
    nur_angemeldet: 'Dafür bitte bei WLO anmelden.',
    aus: 'Das Übertragen in WLO ist gerade ausgeschaltet.',
    keine_anfrage: 'Dieses Auswahlfeld ist nicht mehr offen. Bitte im Chat neu fragen.',
    sitzung_unbekannt: 'Dieses Auswahlfeld ist nicht mehr offen. Bitte im Chat neu fragen.',
    sitzung: 'Das Gespräch hat gewechselt. Bitte noch einmal wählen.',
    fremder_stapel: 'Diese Freigabe gehört nicht mehr zu diesem Gespräch. Bitte neu vorbereiten.',
    neu_vorbereiten: 'Die Freigabe ist abgelaufen. Bitte neu vorbereiten.',
    stapel_offen: 'Eine frühere Übertragung ist noch nicht abgeschlossen. Läuft sie noch in einem anderen Fenster, schließe sie dort ab; sonst gibt ihre Freigabe spätestens nach einer halben Stunde nach, dann geht es hier weiter.',
    kein_recht: 'Dein Konto darf in deinem persönlichen Bereich nichts anlegen.',
    abgewiesen: 'WLO hat die Übertragung abgewiesen.',
    passt_nicht: 'Die Datei passt nicht zur Freigabe (geändert?).',
    groesse: 'Die Datei ist nicht mehr so groß wie bei der Freigabe (geändert?).',
    zu_gross: 'Die Datei ist zu groß.',
    art: 'Diese Dateiart nimmt WLO nicht an.',
    erneut: 'Kurz nicht angekommen – ein neuer Versuch hilft meist.',
    voll: 'WLO nimmt gerade keine weiteren Dateien an. Bitte später noch einmal.',
    anmeldungen: 'Zu viele Anmeldungen bei WLO. Bitte später noch einmal.',
    gedrosselt: 'Zu viele Anfragen. Bitte kurz warten.',
    nicht_erreichbar: 'WLO ist gerade nicht erreichbar.',
    nicht_gespeichert: 'Die Freigabe ließ sich nicht festhalten. Bitte noch einmal versuchen.',
    nichts_abgelegt: 'Es wurde noch nichts abgelegt.',
    zu_langsam: 'Keine Antwort von WLO – die Datei kann trotzdem angekommen sein.',
    netz: 'Keine Verbindung zum Server.',
    unsicher: 'Übertragen geht nur, wenn diese Seite sicher (über https) geladen ist.',
    abgebrochen: 'Das Übertragen wurde abgebrochen.',
    fehler: 'Das Übertragen ist nicht gelungen.',
  },
  blase: (abgelegt: number, n: number) => `${zahl('de', abgelegt)} von ${zahl('de', n)} ${mehrzahl('de', n, 'Datei', 'Dateien')} in meinen persönlichen Bereich in WLO übertragen.`,
  nurLesen: (abgelegt: number, n: number) => `Übertragen: ${zahl('de', abgelegt)} von ${zahl('de', n)} in WLO abgelegt.`,
};

const EN: typeof DE = {
  titel: 'Transfer to your personal area in WLO',
  auswahl: 'Selection',
  liste: 'Files in the transfer',
  angebot: (dateien: string) => `You can transfer ${dateien} to your personal area in WLO. Nothing is uploaded until you confirm.`,
  ausgelassen: (ohneArt: number, zuGross: number, mb: number) => [
    ohneArt ? `${zahl('en', ohneArt)} ${mehrzahl('en', ohneArt, 'file has', 'files have')} a type WLO does not accept here.` : '',
    zuGross ? `${zahl('en', zuGross)} ${mehrzahl('en', zuGross, 'file is', 'files are')} larger than ${zahl('en', mb)} MB.` : '',
  ].filter(Boolean).join(' '),
  zuViele: (max: number) => `At most ${zahl('en', max)} files per transfer – please ignore some.`,
  keine: 'None of the files can be transferred.',
  pruefen: 'Prepare transfer …',
  prueft: (k: number, n: number) => `Checking files: ${zahl('en', k)} of ${zahl('en', n)}`,
  bereitet: 'Preparing the approval …',
  zielOrdner: (ordner: string) => `Destination: your personal area in WLO, new folder “${ordner}”.`,
  zielFlach: 'Destination: your personal area in WLO, without a folder of its own (your account may not create folders there).',
  umfang: (dateien: string, bytes: number) => `${dateien}, ${groesse('en', bytes)} in total.`,
  jetzt: 'Transfer now',
  abbrechen: 'Cancel',
  anhalten: 'Stop after this file',
  haeltAn: 'Stopping after this file …',
  sendet: (k: number, n: number, prozent: number) => `Transferring file ${zahl('en', k)} of ${zahl('en', n)} … ${prozent} %`,
  fertig: (abgelegt: number, n: number) => `${zahl('en', abgelegt)} of ${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')} stored in WLO.`,
  ordnerVerweigert: 'Your account was not allowed to create the folder – the files are directly in your personal area.',
  vorgangFehlt: 'The overview file (vorgang.json) could not be stored; the files are there anyway.',
  nochmal: 'Send the remaining files again',
  weiter: 'Continue in the chat',
  ansehen: (name: string) => `View ${name} in WLO`,
  stand: {
    wartet: 'waiting', sendet: 'transferring', stored: 'stored', dropped: 'created, content not kept',
    unverified: 'unclear – no answer from WLO', failed: 'not stored', abgebrochen: 'not sent',
  },
  fehler: {
    nur_angemeldet: 'Please sign in to WLO for this.',
    aus: 'Transferring to WLO is switched off right now.',
    keine_anfrage: 'This picker is no longer open. Please ask in the chat again.',
    sitzung_unbekannt: 'This picker is no longer open. Please ask in the chat again.',
    sitzung: 'The conversation has changed. Please choose again.',
    fremder_stapel: 'This approval no longer belongs to this conversation. Please prepare again.',
    neu_vorbereiten: 'The approval has expired. Please prepare again.',
    stapel_offen: 'An earlier transfer is not finished yet. If it is still running in another window, finish it there; otherwise its approval lapses within half an hour, and you can go on here.',
    kein_recht: 'Your account may not create anything in your personal area.',
    abgewiesen: 'WLO rejected the transfer.',
    passt_nicht: 'The file does not match the approval (changed?).',
    groesse: 'The file size differs from the approval (changed?).',
    zu_gross: 'The file is too large.',
    art: 'WLO does not accept this file type.',
    erneut: 'Did not arrive just now – trying again usually helps.',
    voll: 'WLO is not accepting more files right now. Please try later.',
    anmeldungen: 'Too many sign-ins at WLO. Please try later.',
    gedrosselt: 'Too many requests. Please wait a moment.',
    nicht_erreichbar: 'WLO cannot be reached right now.',
    nicht_gespeichert: 'The approval could not be recorded. Please try again.',
    nichts_abgelegt: 'Nothing has been stored yet.',
    zu_langsam: 'No answer from WLO – the file may have arrived anyway.',
    netz: 'No connection to the server.',
    unsicher: 'Transferring only works when this page is loaded securely (over https).',
    abgebrochen: 'The transfer was cancelled.',
    fehler: 'The transfer did not work.',
  },
  blase: (abgelegt: number, n: number) => `Transferred ${zahl('en', abgelegt)} of ${zahl('en', n)} ${mehrzahl('en', n, 'file', 'files')} to my personal area in WLO.`,
  nurLesen: (abgelegt: number, n: number) => `Transferred: ${zahl('en', abgelegt)} of ${zahl('en', n)} stored in WLO.`,
};

export type UebertragenTexte = typeof DE;

/** Der Satz zu einem Fehlercode; unbekannte Codes bekommen den allgemeinen. Die Schlüssel sind bewusst
 *  nicht `Record<string, string>` — so prüft der Typ, dass DE und EN dieselben Codes kennen
 *  (Querschnitts-Review FE-8). */
export function fehlerSatz(t: UebertragenTexte, code: string): string {
  const saetze: Readonly<Record<string, string>> = t.fehler;
  // `Object.hasOwn`: ein Code wie `constructor` träfe sonst den Prototyp (Review Q1, Befund 10).
  return Object.hasOwn(saetze, code) ? saetze[code] : t.fehler.fehler;
}

export function uebertragenTexte(sprache: Sprache): UebertragenTexte {
  return sprache === 'en' ? EN : DE;
}
