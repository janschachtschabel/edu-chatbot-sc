/**
 * Paket N4: reine Hilfen der Freigabe-Box (Inhaltsrahmen, Art `schreib_vorschau`, mit `freigabe`)
 * — Daten prüfen, filtern, seitenweise zeigen, nach Ordner gruppieren, Texte de/en.
 */

export interface FreigabeEintrag {
  readonly titel: string;
  readonly ordner: string;
}

export interface FreigabeProblem {
  readonly titel: string;
  readonly grund: string;
}

export interface FreigabeDaten {
  readonly ablauf: string;
  readonly id: string;
  readonly anzahl: number;
  readonly eintraege: readonly FreigabeEintrag[];
  readonly probleme: readonly FreigabeProblem[];
  /** Review N4 (7): der Flow; nur beim Metadaten-Flow (`metadaten`) Kopf und Satz zu den Feldern. */
  readonly flow?: string;
  readonly metadaten?: boolean;
}

/** Review N4 (5): so viele Probleme sichtbar, der Rest hinter „Alle zeigen“. */
export const PROBLEME_SICHTBAR = 5;

/** So viele Einträge je Seite; ab mehr als einer Seite gibt es das Filterfeld. */
export const SEITE = 20;

const istText = (x: unknown): x is string => typeof x === 'string';
const istListe = <T>(x: unknown, pruefe: (e: Record<string, unknown>) => boolean): x is T[] =>
  Array.isArray(x) && x.every((e) => !!e && typeof e === 'object' && pruefe(e as Record<string, unknown>));

/** Die Liste nur aus einer System-Box (`schreib_vorschau` setzt nie die KI) mit gültiger Form. */
export function freigabeAus(daten: Record<string, unknown>): FreigabeDaten | null {
  const f = daten['freigabe'] as Record<string, unknown> | undefined;
  if (daten['art'] !== 'schreib_vorschau' || !f || typeof f !== 'object') return null;
  const gut = istText(f['ablauf']) && istText(f['id']) && typeof f['anzahl'] === 'number'
    && istListe<FreigabeEintrag>(f['eintraege'], (e) => istText(e['titel']) && istText(e['ordner']))
    && istListe<FreigabeProblem>(f['probleme'], (e) => istText(e['titel']) && istText(e['grund']))
    && (f['flow'] === undefined || istText(f['flow']))
    && (f['metadaten'] === undefined || typeof f['metadaten'] === 'boolean');
  return gut ? (f as unknown as FreigabeDaten) : null;
}

/** Gefiltert (Titel oder Ordner, ohne Groß/klein) und auf `seiten` × {@link SEITE} begrenzt. */
export function sichtbar(eintraege: readonly FreigabeEintrag[], filter: string, seiten: number): FreigabeEintrag[] {
  const f = filter.trim().toLocaleLowerCase();
  const treffer = f
    ? eintraege.filter((e) => `${e.titel} ${e.ordner}`.toLocaleLowerCase().includes(f))
    : [...eintraege];
  return treffer.slice(0, seiten * SEITE);
}

export function anzahlTreffer(eintraege: readonly FreigabeEintrag[], filter: string): number {
  return sichtbar(eintraege, filter, Number.MAX_SAFE_INTEGER / SEITE).length;
}

/** Nach Ordner gruppiert, in der Reihenfolge des ersten Auftretens. */
export function gruppen(eintraege: readonly FreigabeEintrag[]): { ordner: string; eintraege: FreigabeEintrag[] }[] {
  const nach = new Map<string, FreigabeEintrag[]>();
  for (const e of eintraege) {
    const liste = nach.get(e.ordner) ?? [];
    liste.push(e);
    nach.set(e.ordner, liste);
  }
  return [...nach].map(([ordner, liste]) => ({ ordner, eintraege: liste }));
}

const GRUENDE_DE: Readonly<Record<string, string>> = {
  not_found: 'nicht gefunden',
  not_readable: 'für dich nicht lesbar',
  not_a_record: 'kein einzelnes Material',
  is_reference: 'eine Verknüpfung in einer Sammlung',
  not_writable: 'für dich nicht schreibbar',
  unchecked: 'konnte nicht geprüft werden',
};
const GRUENDE_EN: Readonly<Record<string, string>> = {
  not_found: 'not found',
  not_readable: 'not readable for you',
  not_a_record: 'not a single material',
  is_reference: 'a link inside a collection',
  not_writable: 'not writable for you',
  unchecked: 'could not be checked',
};

const zahl = (sprache: 'de' | 'en', n: number) => new Intl.NumberFormat(sprache).format(n);

export const TEXTE_FREIGABE = {
  de: {
    kopf: (n: number) => `${zahl('de', n)} ${n === 1 ? 'Material wird' : 'Materialien werden'} in WLO erschlossen`,
    kopfFlow: (flow: string, n: number) =>
      `Dieser Auftrag schreibt in WLO: ${flow}${n ? ` (${zahl('de', n)} ${n === 1 ? 'Material' : 'Materialien'})` : ''}`,
    satz: 'Überschrieben werden Titel, Beschreibung, Schlagworte, Fach, Stufe, Zielgruppe, Typ und Sprache – je Material als neue Version.',
    probleme: (n: number) => `${zahl('de', n)} ${n === 1 ? 'Material geht' : 'Materialien gehen'} nicht mit:`,
    grund: (code: string) => (Object.hasOwn(GRUENDE_DE, code) ? GRUENDE_DE[code] : 'anderer Grund'),
    liste: (n: number) => `Liste zeigen (${zahl('de', n)})`,
    filter: 'Liste filtern',
    treffer: (n: number, gesamt: number) => `${zahl('de', n)} von ${zahl('de', gesamt)}`,
    mehr: 'Weitere zeigen',
    alleZeigen: (n: number) => `Alle zeigen (${zahl('de', n)})`,
    gesendet: (wahl: 'freigeben' | 'verwerfen') => `Entscheidung gesendet: ${wahl === 'freigeben' ? 'Freigeben' : 'Abbrechen'}`,
    ohneOrdner: 'Ohne Ordner',
    freigeben: 'Freigeben',
    abbrechen: 'Abbrechen',
    vorbei: (n: number) => `Vorschau für ${zahl('de', n)} ${n === 1 ? 'Material' : 'Materialien'} – nicht mehr offen.`,
    fehlgeschlagen: 'Deine Entscheidung kam nicht an. Bitte noch einmal.',
  },
  en: {
    kopf: (n: number) => `${zahl('en', n)} ${n === 1 ? 'material' : 'materials'} will be indexed in WLO`,
    kopfFlow: (flow: string, n: number) =>
      `This job writes to WLO: ${flow}${n ? ` (${zahl('en', n)} ${n === 1 ? 'material' : 'materials'})` : ''}`,
    satz: 'This overwrites title, description, keywords, subject, level, audience, type and language – each material as a new version.',
    probleme: (n: number) => `${zahl('en', n)} ${n === 1 ? 'material' : 'materials'} cannot be included:`,
    grund: (code: string) => (Object.hasOwn(GRUENDE_EN, code) ? GRUENDE_EN[code] : 'other reason'),
    liste: (n: number) => `Show list (${zahl('en', n)})`,
    filter: 'Filter list',
    treffer: (n: number, gesamt: number) => `${zahl('en', n)} of ${zahl('en', gesamt)}`,
    mehr: 'Show more',
    alleZeigen: (n: number) => `Show all (${zahl('en', n)})`,
    gesendet: (wahl: 'freigeben' | 'verwerfen') => `Decision sent: ${wahl === 'freigeben' ? 'Approve' : 'Cancel'}`,
    ohneOrdner: 'No folder',
    freigeben: 'Approve',
    abbrechen: 'Cancel',
    vorbei: (n: number) => `Preview for ${zahl('en', n)} ${n === 1 ? 'material' : 'materials'} – no longer open.`,
    fehlgeschlagen: 'Your decision did not get through. Please try again.',
  },
} as const;
