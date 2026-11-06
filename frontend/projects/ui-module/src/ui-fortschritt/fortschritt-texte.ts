/**
 * Texte von `<boerdi-ui-fortschritt>` (Paket K1b), Deutsch und Englisch. Die Uhrzeit über `Intl`;
 * der Satz aus den Block-Daten (`text`) setzt das Element immer als `textContent`.
 */
export type Sprache = 'de' | 'en';

const DE = {
  titel: 'Auftrag im Hintergrund',
  laeuft: 'Läuft noch …',
  prueft: 'Der Stand wird geprüft …',
  stoerung: 'Den Stand kann ich gerade nicht abrufen – ich versuche es weiter.',
  stoerungManuell: 'Den Stand kann ich gerade nicht abrufen – versuch es gleich noch einmal mit „Jetzt prüfen“.',
  fertig: 'Fertig – das Ergebnis wird abgeholt …',
  fehlerAuftrag: 'Der Auftrag ist nicht gelungen – gleich steht im Chat, wie es weitergeht.',
  abgeholt: 'Erledigt – die Antwort steht im Chat.',
  abgeschlossen: 'Dieser Auftrag ist abgeschlossen.',
  halt: 'Den Stand sehe ich nur, solange du in WLO angemeldet bist.',
  manuell: 'Ich frage nicht mehr von selbst nach. Mit „Jetzt prüfen“ siehst du den Stand.',
  nurLesen: 'Dieser Auftrag wird hier nicht mehr verfolgt.',
  zuletzt: (zeit: string) => `Zuletzt geprüft um ${zeit} Uhr.`,
  jetzt: 'Jetzt prüfen',
  abholen: 'Ergebnis abholen',
  balken: 'Auftrag läuft',
};

export type FortschrittTexte = typeof DE;

const EN: FortschrittTexte = {
  titel: 'Job in the background',
  laeuft: 'Still running …',
  prueft: 'Checking the status …',
  stoerung: 'I can’t fetch the status right now – I’ll keep trying.',
  stoerungManuell: 'I can’t fetch the status right now – try “Check now” again in a moment.',
  fertig: 'Done – fetching the result …',
  fehlerAuftrag: 'The job did not succeed – the chat will say how to go on in a moment.',
  abgeholt: 'Done – the answer is in the chat.',
  abgeschlossen: 'This job is finished.',
  halt: 'I can only see the status while you are signed in to WLO.',
  manuell: 'I no longer check on my own. Use “Check now” to see the status.',
  nurLesen: 'This job is no longer tracked here.',
  zuletzt: (zeit: string) => `Last checked at ${zeit}.`,
  jetzt: 'Check now',
  abholen: 'Fetch result',
  balken: 'Job running',
};

export function texte(sprache: Sprache): FortschrittTexte {
  return sprache === 'en' ? EN : DE;
}

export function uhrzeit(sprache: Sprache, ms: number): string {
  return new Intl.DateTimeFormat(sprache === 'en' ? 'en-GB' : 'de-DE', { hour: '2-digit', minute: '2-digit' })
    .format(new Date(ms));
}
