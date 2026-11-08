/**
 * Texte von `ui_strukturabgleich` (Paket U4), Deutsch und Englisch. Zahlen über `Intl.NumberFormat`,
 * Einzahl/Mehrzahl über `Intl.PluralRules` — nie zusammengesetzt. Fremdtext (Titel) setzt das Element
 * immer als `textContent`.
 */
export type Sprache = 'de' | 'en';
export type Art = 'vorhanden' | 'aehnlich' | 'neu';

interface AbgleichTexte {
  titel: (entwurf: string) => string;
  mit: string;
  ohneTitel: string;
  art: Record<Art, string>;
  nichtGefunden: string;
  zusammenfassung: (z: { vorhanden: number; aehnlich: number; neu: number; nurInWlo: number }) => string;
  inhalte: (n: number) => string;
  inWlo: string;
  nurInWlo: (gezeigt: number, gesamt: number) => string;
  nurInWloLeer: string;
  ebene: (n: 1 | 2) => string;
  unter: (titel: string) => string;
  gekuerzt: string;
  direkt: string;
  leer: string;
  oeffnet: string;
  treffer: (n: number) => string;
  luecke: string;
  luecken: (n: number) => string;
  lueckenHinweis: (bis: number) => string;
  trefferKurz: (n: number) => string;
  geraten: string;
  gezaehltVon: (gezaehlt: number, alle: number) => string;
  nichtZustande: string;
  gesperrt: string;
  keineLuecken: string;
  nichtGezaehlt: string;
  filterUnbekannt: string;
  beispiele: string;
  zahl: (n: number) => string;
}

function zahl(sprache: Sprache, n: number): string {
  return new Intl.NumberFormat(sprache).format(n);
}

function mehrzahl(sprache: Sprache, n: number, eins: string, viele: string): string {
  return new Intl.PluralRules(sprache).select(n) === 'one' ? eins : viele;
}

const DE: AbgleichTexte = {
  titel: (entwurf) => (entwurf ? `Abgleich: ${entwurf}` : 'Abgleich mit WLO'),
  mit: 'mit der Sammlung',
  ohneTitel: 'in WLO',
  art: { vorhanden: 'Vorhanden', aehnlich: 'Ähnlich', neu: 'Neu' },
  nichtGefunden: 'Nicht gefunden',
  zusammenfassung: (z) => `${zahl('de', z.vorhanden)} vorhanden · ${zahl('de', z.aehnlich)} ähnlich · ${zahl('de', z.neu)} neu · ${zahl('de', z.nurInWlo)} nur in WLO`,
  inhalte: (n) => `${zahl('de', n)} ${mehrzahl('de', n, 'Inhalt', 'Inhalte')}`,
  inWlo: 'in WLO:',
  nurInWlo: (gezeigt, gesamt) => (gezeigt < gesamt
    ? `Nur in WLO (${zahl('de', gezeigt)} von ${zahl('de', gesamt)})` : `Nur in WLO (${zahl('de', gesamt)})`),
  nurInWloLeer: 'Jede Sammlung hat einen Punkt im Entwurf.',
  ebene: (n) => `Ebene ${n}`,
  unter: (titel) => `unter ${titel}`,
  gekuerzt: 'Die Sammlung ist größer als hier gezeigt. „Nicht gefunden“ heißt: dort nicht mitgeliefert, nicht sicher neu.',
  direkt: 'Die Zahl der Inhalte zählt, was direkt in einer Sammlung liegt.',
  leer: 'Der Entwurf hat keine Punkte zum Abgleichen.',
  oeffnet: 'öffnet in einem neuen Tab',
  treffer: (n) => `${zahl('de', n)} ${mehrzahl('de', n, 'Treffer', 'Treffer')} in ganz WLO`,
  luecke: 'Lücke',
  luecken: (n) => `Lücken (${zahl('de', n)})`,
  lueckenHinweis: (bis) => `Punkte mit höchstens ${zahl('de', bis)} Treffern in ganz WLO – nicht nur in dieser Sammlung.`,
  trefferKurz: (n) => `${zahl('de', n)} Treffer`,
  geraten: '(Fach oder Stufe geschätzt)',
  gezaehltVon: (g, a) => `${zahl('de', g)} von ${zahl('de', a)} Punkten gezählt.`,
  nichtZustande: 'Die Zählung kam nicht zustande – über Lücken lässt sich nichts sagen.',
  gesperrt: 'Treffer zu zählen ist hier gerade nicht möglich.',
  keineLuecken: 'Zu jedem gezählten Punkt gibt es in WLO mehr als 2 Treffer.',
  nichtGezaehlt: 'nicht gezählt',
  filterUnbekannt: 'Treffer ließen sich nicht zählen: Fach oder Bildungsstufe des Entwurfs kennt WLO nicht.',
  beispiele: 'Beispiele:',
  zahl: (n) => zahl('de', n),
};

const EN: AbgleichTexte = {
  titel: (entwurf) => (entwurf ? `Comparison: ${entwurf}` : 'Comparison with WLO'),
  mit: 'with the collection',
  ohneTitel: 'in WLO',
  art: { vorhanden: 'Exists', aehnlich: 'Similar', neu: 'New' },
  nichtGefunden: 'Not found',
  zusammenfassung: (z) => `${zahl('en', z.vorhanden)} exist · ${zahl('en', z.aehnlich)} similar · ${zahl('en', z.neu)} new · ${zahl('en', z.nurInWlo)} only in WLO`,
  inhalte: (n) => `${zahl('en', n)} ${mehrzahl('en', n, 'item', 'items')}`,
  inWlo: 'in WLO:',
  nurInWlo: (gezeigt, gesamt) => (gezeigt < gesamt
    ? `Only in WLO (${zahl('en', gezeigt)} of ${zahl('en', gesamt)})` : `Only in WLO (${zahl('en', gesamt)})`),
  nurInWloLeer: 'Every collection has a point in the draft.',
  ebene: (n) => `Level ${n}`,
  unter: (titel) => `under ${titel}`,
  gekuerzt: 'The collection is larger than shown here. “Not found” means: not delivered there, not surely new.',
  direkt: 'The number of items counts what lies directly in a collection.',
  leer: 'The draft has no points to compare.',
  oeffnet: 'opens in a new tab',
  treffer: (n) => `${zahl('en', n)} ${mehrzahl('en', n, 'match', 'matches')} in all of WLO`,
  luecke: 'Gap',
  luecken: (n) => `Gaps (${zahl('en', n)})`,
  lueckenHinweis: (bis) => `Points with at most ${zahl('en', bis)} matches in all of WLO – not just in this collection.`,
  trefferKurz: (n) => `${zahl('en', n)} ${mehrzahl('en', n, 'match', 'matches')}`,
  geraten: '(subject or level estimated)',
  gezaehltVon: (g, a) => `${zahl('en', g)} of ${zahl('en', a)} points counted.`,
  nichtZustande: 'The count did not come through – nothing can be said about gaps.',
  gesperrt: 'Counting matches is not possible here right now.',
  keineLuecken: 'Every counted point has more than 2 matches in WLO.',
  nichtGezaehlt: 'not counted',
  filterUnbekannt: 'Matches could not be counted: WLO does not know the subject or level of the draft.',
  beispiele: 'Examples:',
  zahl: (n) => zahl('en', n),
};

export function texte(sprache: Sprache): AbgleichTexte {
  return sprache === 'en' ? EN : DE;
}
