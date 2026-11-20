/**
 * Rollen der erfassten Dateien (Paket U3-1a) — reine Regeln, jede Änderung gibt eine neue Erfassung.
 *
 * Strukturdokumente (z. B. ein Lehrplan), nur PDF, DOCX, TXT oder MD — dieselben Formate, die „Hier im
 * Chat“ liest (`kannStrukturSein` ist zugleich die Regel „lesbar“, Paket U4). Plan 2026-11-16, TG-3e (Nutzer: „aus einem oder mehreren Strukturdokumenten“): bis zu
 * {@link MAX_STRUKTUR} je Erfassung (vorher genau eins; ein zweites nahm dem ersten die Rolle). Mehr
 * lässt die Rolle nicht zu — das Auswahlfeld sperrt die Wahl dann. Leere und zu große Dateien bleiben
 * ignoriert, auch wenn die Person einen ganzen Ordner wieder einschließt.
 *
 * Plan 2026-11-20, P1 (UO-4): `beides` (Gliederung und Material) gilt als Strukturdokument UND als
 * Inhalt — Höchstzahl und lesbare Formate gelten auch dafür ({@link istGliederung}).
 */
import type { AblageRolle } from '../_vertrag/modul-host';
import type { Erfassung, ErfassteDatei, Rolle } from './upload-erfassen';

const STRUKTUR_ENDUNG = /\.(pdf|docx|txt|md)$/i;
/** TG-3e: so viele Strukturdokumente je Erfassung. Paket U4 (Teil b) prüfte die Grenze gegen den
 *  neuen Vertrag: sie bleibt 5 — so viele erlaubt das Antwort-Schema (`zahlen.strukturdokumente`,
 *  `dokumente`) und die Ablage in WLO (`api/ui_ablage._STRUKTUR_HOECHSTENS`). „Hier im Chat“ zählt
 *  Strukturdokumente zusammen mit Inhalten gegen `grenzen.lokal_max_dateien` (`upload-orte.ts`);
 *  die Sitzungsgrenze des Backends (`dokumente/ablage.max_je_sitzung`) weist ab, verdrängt nicht. */
export const MAX_STRUKTUR = 5;
const LEHRPLAN = /(lehrplan|curricul|bildungsplan|rahmenplan|fachanforderung|kompetenzraster)/i;

/** Liefert die Datei die Struktur (`struktur` oder `beides`)? */
export function istGliederung(r: Rolle): boolean {
  return r === 'struktur' || r === 'beides';
}

/** Wird die Datei einsortiert (`inhalt` oder `beides`)? */
export function istMaterial(r: Rolle): boolean {
  return r === 'inhalt' || r === 'beides';
}

/** Die Rolle für Ablage und `hochladen` — aus der Erfassung oder einer Antwort des Backends; was
 *  keine Gliederung ist, geht als `inhalt`. */
export function alsAblageRolle(r: unknown): AblageRolle {
  return r === 'struktur' || r === 'beides' ? r : 'inhalt';
}

export function kannStrukturSein(d: Pick<ErfassteDatei<unknown>, 'name' | 'typ' | 'grund'>): boolean {
  return !d.grund && !d.typ.startsWith('image/') && STRUKTUR_ENDUNG.test(d.name);
}

function mitRollen<T>(e: Erfassung<T>, neu: (d: ErfassteDatei<T>, i: number) => Rolle): Erfassung<T> {
  return { ...e, dateien: e.dateien.map((d, i) => {
    const rolle = neu(d, i);
    return rolle === d.rolle ? d : { ...d, rolle };
  }) };
}

/** Plan 2026-11-20, P2: mit welcher Rolle die Dateien beginnen (Block-Daten `rolle_vorgabe`, aus dem
 *  Ablauf-Schritt; im freien Chat `auto`). */
export type RollenVorgabe = 'auto' | 'gliederung' | 'material' | 'beides';
const VORGABEN = new Set<string>(['auto', 'gliederung', 'material', 'beides']);

/** Die Rollen-Vorgabe des Blocks. Ein ausdrücklicher Wert zählt; sonst heißt der alte Schlüssel
 *  `einzeldatei_als_struktur: true` `gliederung` (wie `ui_module/rollen.vorgabe` im Backend). */
export function rollenVorgabe(daten: Readonly<Record<string, unknown>>): RollenVorgabe {
  const wert = daten['rolle_vorgabe'];
  if (typeof wert === 'string' && VORGABEN.has(wert)) return wert as RollenVorgabe;
  return daten['einzeldatei_als_struktur'] === true ? 'gliederung' : 'auto';
}

/**
 * Plan 2026-11-20, P2: die Rollen am Anfang nach der Vorgabe des Blocks. `gliederung`/`beides`: jede
 * nutzbare, lesbare Datei bekommt diese Rolle (höchstens {@link MAX_STRUKTUR}, der Rest bleibt
 * Material); `material`: alle bleiben Material. `auto`: genau ein Lehrplan-Kandidat direkt in der
 * Wurzel → Gliederung (Review 12.11., Befund 1: nicht jede Einzeldatei — beim Übertragen nach WLO
 * wäre sie sonst still als Strukturdokument markiert).
 *
 * Plan 2026-11-16, TG-1 (G-E4): die Automatik merkt nur vor — hochgeladen wird erst auf den Knopf.
 */
export function vorschlagen<T>(e: Erfassung<T>, vorgabe: RollenVorgabe = 'auto'): Erfassung<T> {
  if (vorgabe === 'material') return e;
  if (vorgabe === 'gliederung' || vorgabe === 'beides') {
    const rolle: Rolle = vorgabe === 'beides' ? 'beides' : 'struktur';
    let zahl = 0;
    return mitRollen(e, (d) => (d.rolle === 'inhalt' && kannStrukturSein(d) && zahl++ < MAX_STRUKTUR ? rolle : d.rolle));
  }
  const kandidaten = e.wurzel.dateien.filter((i) => {
    const d = e.dateien[i];
    return d.rolle === 'inhalt' && kannStrukturSein(d) && LEHRPLAN.test(d.name);
  });
  if (kandidaten.length !== 1) return e;
  return setzeRolle(e, kandidaten[0], 'struktur');
}

/** Wie viele Dateien gerade Strukturdokument sind (`struktur` oder `beides`). */
export function strukturZahl<T>(e: Erfassung<T>): number {
  return e.dateien.filter((d) => istGliederung(d.rolle)).length;
}

/** Kann diese Datei (noch) Strukturdokument werden? Sie muss lesbar sein, und es dürfen nicht schon
 *  {@link MAX_STRUKTUR} andere markiert sein (TG-3e). */
export function strukturWaehlbar<T>(e: Erfassung<T>, index: number): boolean {
  const d = e.dateien[index];
  return !!d && kannStrukturSein(d) && (istGliederung(d.rolle) || strukturZahl(e) < MAX_STRUKTUR);
}

export function setzeRolle<T>(e: Erfassung<T>, index: number, rolle: Rolle): Erfassung<T> {
  const ziel = e.dateien[index];
  if (!ziel || ziel.grund) return e;
  // TG-3e: andere Strukturdokumente behalten ihre Rolle; über der Grenze bleibt alles, wie es ist
  if (istGliederung(rolle) && !strukturWaehlbar(e, index)) return e;
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
