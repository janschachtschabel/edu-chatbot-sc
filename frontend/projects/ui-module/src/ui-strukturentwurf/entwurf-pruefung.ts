/**
 * Struktur-Hinweise nach dem Leitfaden „Themenbäume“ (Paket R4, Plan 2026-11-10 TB-4, Entscheid
 * R-E11: nur Warnungen, nie eine Sperre — ein Baum darf vom Raster abweichen, etwa wenn die Quelle
 * eine Ordnung vorgibt). Ohne Angular; gerechnet über den bearbeiteten Baum, also nach jeder
 * Änderung neu. Dieselben Richtwerte nennt der Generator (`services/strukturentwurf_prompt.py`).
 *
 * Was Auslegung ist (Begriffsart der Geschwister, Facette oder Thema), prüft hier nichts — das steht
 * im Master-Skill bzw. im Hinweis des KI-Schritts.
 */
import type { Baum } from './entwurf-regeln';

/** Richtwerte des Leitfadens. */
export const OBEN_MIN = 5;
export const OBEN_MAX = 15;
export const KINDER_MAX = 12;
export const TIEFE_MAX = 3;
/** So viele Hinweise stehen höchstens da — der Rest als Zahl (`weitere`). */
export const HOECHSTENS = 10;

export type Hinweis =
  | { readonly code: 'oben'; readonly anzahl: number }
  | { readonly code: 'tief'; readonly anzahl: number }
  | { readonly code: 'einzelkind' | 'name' | 'doppelt'; readonly titel: string }
  | { readonly code: 'breit'; readonly titel: string; readonly anzahl: number }
  | { readonly code: 'weitere'; readonly anzahl: number };

/** Jahreszahl, Klassenstufe, Format oder Materialart, Sammelpunkt — Inhalte quer zum Baum. */
const QUER = new RegExp([
  // Querschnitts-Review, Befund 6: nur Schuljahre oder ein Jahr allein — „Revolution 1848“ ist ein Thema
  '\\bschuljahr\\b',
  '\\b(19|20)\\d{2}\\s*/\\s*\\d{2}\\b',
  '^(19|20)\\d{2}$',
  '\\b(klasse|klassenstufe|jahrgang|jahrgangsstufe)\\s*\\d',
  '\\b\\d{1,2}\\.\\s*(klasse|jahrgang)',
  '\\b(arbeitsbl[aä]tt(er)?|videos?|pdfs?|pr[aä]sentation(en)?|folien|quiz(ze)?|tafelbilder?)\\b',
  '^(sonstiges|sonstige|weiteres|weitere|allgemeines|verschiedenes|diverses)$',
].join('|'), 'i');

function tiefe(baum: Baum): number {
  return baum.reduce((max, k) => Math.max(max, 1 + tiefe(k.kinder ?? [])), 0);
}

function zweige(baum: Baum, hinweise: Hinweis[]): void {
  const gesehen = new Set<string>();
  for (const k of baum) {
    const titel = k.titel.trim();
    const schluessel = titel.toLocaleLowerCase('de');
    if (gesehen.has(schluessel)) hinweise.push({ code: 'doppelt', titel });
    gesehen.add(schluessel);
    if (QUER.test(titel)) hinweise.push({ code: 'name', titel });
    const kinder = k.kinder ?? [];
    if (kinder.length === 1) hinweise.push({ code: 'einzelkind', titel });
    if (kinder.length > KINDER_MAX) hinweise.push({ code: 'breit', titel, anzahl: kinder.length });
    zweige(kinder, hinweise);
  }
}

/** Die Hinweise zu `baum` — leer, wenn er den Richtwerten folgt. */
export function strukturHinweise(baum: Baum): Hinweis[] {
  const hinweise: Hinweis[] = [];
  if (baum.length && (baum.length < OBEN_MIN || baum.length > OBEN_MAX)) {
    hinweise.push({ code: 'oben', anzahl: baum.length });
  }
  const t = tiefe(baum);
  if (t > TIEFE_MAX) hinweise.push({ code: 'tief', anzahl: t });
  zweige(baum, hinweise);
  if (hinweise.length <= HOECHSTENS) return hinweise;
  return [...hinweise.slice(0, HOECHSTENS), { code: 'weitere', anzahl: hinweise.length - HOECHSTENS }];
}

