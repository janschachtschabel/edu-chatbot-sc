/**
 * Rollen der erfassten Dateien (Paket U3-1a) — reine Regeln, jede Änderung gibt eine neue Erfassung.
 *
 * Strukturdokumente (z. B. ein Lehrplan), nur PDF, DOCX, TXT oder MD — die liest der Chatbot selbst
 * (U3-2). Plan 2026-11-16, TG-3e (Nutzer: „aus einem oder mehreren Strukturdokumenten“): bis zu
 * {@link MAX_STRUKTUR} je Erfassung (vorher genau eins; ein zweites nahm dem ersten die Rolle). Mehr
 * lässt die Rolle nicht zu — das Auswahlfeld sperrt die Wahl dann. Leere und zu große Dateien bleiben
 * ignoriert, auch wenn die Person einen ganzen Ordner wieder einschließt.
 */
import type { Erfassung, ErfassteDatei, Rolle } from './upload-erfassen';

const STRUKTUR_ENDUNG = /\.(pdf|docx|txt|md)$/i;
/** TG-3e: so viele Strukturdokumente je Erfassung — wie `dokumente/ablage.MAX_JE_SITZUNG` im
 *  Backend (dort ersetzte ein sechstes das älteste) und die Antwortform (`zahlen.strukturdokumente`). */
export const MAX_STRUKTUR = 5;
const LEHRPLAN = /(lehrplan|curricul|bildungsplan|rahmenplan|fachanforderung|kompetenzraster)/i;

export function kannStrukturSein(d: Pick<ErfassteDatei<unknown>, 'name' | 'typ' | 'grund'>): boolean {
  return !d.grund && !d.typ.startsWith('image/') && STRUKTUR_ENDUNG.test(d.name);
}

function mitRollen<T>(e: Erfassung<T>, neu: (d: ErfassteDatei<T>, i: number) => Rolle): Erfassung<T> {
  return { ...e, dateien: e.dateien.map((d, i) => {
    const rolle = neu(d, i);
    return rolle === d.rolle ? d : { ...d, rolle };
  }) };
}

/**
 * Genau ein Lehrplan-Kandidat direkt in der Wurzel → Strukturdokument. Mit `einzelneAlsStruktur`
 * (der Block verlangt es, `einzeldatei_als_struktur` — nur der Ablauf „Themenbaum aus einem
 * Dokument“) ebenso eine **einzelne** Datei ohne Ordner, die ein Strukturdokument sein kann
 * (Rückmeldung 11.11.: dort blieb sonst „Senden“ der Hauptknopf). Review 12.11., Befund 1: nicht in
 * jedem Upload-Feld — beim Übertragen nach WLO wäre die Datei sonst still als Strukturdokument
 * markiert. Sonst bleibt alles, wie es ist.
 *
 * Plan 2026-11-16, TG-1 (G-E4): die Automatik merkt nur vor — gelesen wird erst auf „Lesen lassen“.
 */
export function vorschlagen<T>(e: Erfassung<T>, einzelneAlsStruktur = false): Erfassung<T> {
  const nutzbar = e.dateien.filter((d) => d.rolle === 'inhalt');
  if (einzelneAlsStruktur && !e.wurzel.ordner.length && nutzbar.length === 1
      && kannStrukturSein(nutzbar[0])) {
    return setzeRolle(e, e.dateien.indexOf(nutzbar[0]), 'struktur');
  }
  const kandidaten = e.wurzel.dateien.filter((i) => {
    const d = e.dateien[i];
    return d.rolle === 'inhalt' && kannStrukturSein(d) && LEHRPLAN.test(d.name);
  });
  if (kandidaten.length !== 1) return e;
  return setzeRolle(e, kandidaten[0], 'struktur');
}

/** Wie viele Dateien gerade die Rolle `struktur` tragen. */
export function strukturZahl<T>(e: Erfassung<T>): number {
  return e.dateien.filter((d) => d.rolle === 'struktur').length;
}

/** Kann diese Datei (noch) Strukturdokument werden? Sie muss lesbar sein, und es dürfen nicht schon
 *  {@link MAX_STRUKTUR} andere markiert sein (TG-3e). */
export function strukturWaehlbar<T>(e: Erfassung<T>, index: number): boolean {
  const d = e.dateien[index];
  return !!d && kannStrukturSein(d) && (d.rolle === 'struktur' || strukturZahl(e) < MAX_STRUKTUR);
}

export function setzeRolle<T>(e: Erfassung<T>, index: number, rolle: Rolle): Erfassung<T> {
  const ziel = e.dateien[index];
  if (!ziel || ziel.grund) return e;
  // TG-3e: andere Strukturdokumente behalten ihre Rolle; über der Grenze bleibt alles, wie es ist
  if (rolle === 'struktur' && !strukturWaehlbar(e, index)) return e;
  return mitRollen(e, (d, i) => (i === index ? rolle : d.rolle));
}

/** Alle Dateien unter `ordnerPfad` ignorieren (`an`) oder wieder als Inhalt einschließen. */
export function alleIgnorieren<T>(e: Erfassung<T>, ordnerPfad: string, an: boolean): Erfassung<T> {
  const praefix = ordnerPfad ? `${ordnerPfad}/` : '';
  return mitRollen(e, (d) => {
    if (praefix && !d.relPfad.startsWith(praefix)) return d.rolle;
    if (an) return 'ignorieren';
    return d.grund || d.rolle !== 'ignorieren' ? d.rolle : 'inhalt';
  });
}
