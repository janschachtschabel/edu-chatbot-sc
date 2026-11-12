/**
 * Rollen der erfassten Dateien (Paket U3-1a) — reine Regeln, jede Änderung gibt eine neue Erfassung.
 *
 * Höchstens **ein** Strukturdokument (z. B. ein Lehrplan) je Erfassung, nur PDF, DOCX, TXT oder MD —
 * das liest der Chatbot später selbst (U3-2). Leere und zu große Dateien bleiben ignoriert, auch wenn die
 * Person einen ganzen Ordner wieder einschließt.
 */
import type { Erfassung, ErfassteDatei, Rolle } from './upload-erfassen';

const STRUKTUR_ENDUNG = /\.(pdf|docx|txt|md)$/i;
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
 * Genau ein Lehrplan-Kandidat direkt in der Wurzel → Strukturdokument; ebenso eine **einzelne** Datei
 * ohne Ordner, die ein Strukturdokument sein kann (Rückmeldung 11.11.: wer nur ein Dokument wählt,
 * will es lesen lassen — sonst blieb „Senden“ der Hauptknopf, und es wurde nur gezählt). Sonst
 * bleibt alles, wie es ist.
 */
export function vorschlagen<T>(e: Erfassung<T>): Erfassung<T> {
  const nutzbar = e.dateien.filter((d) => d.rolle === 'inhalt');
  if (!e.wurzel.ordner.length && nutzbar.length === 1 && kannStrukturSein(nutzbar[0])) {
    return setzeRolle(e, e.dateien.indexOf(nutzbar[0]), 'struktur');
  }
  const kandidaten = e.wurzel.dateien.filter((i) => {
    const d = e.dateien[i];
    return d.rolle === 'inhalt' && kannStrukturSein(d) && LEHRPLAN.test(d.name);
  });
  if (kandidaten.length !== 1) return e;
  return setzeRolle(e, kandidaten[0], 'struktur');
}

export function setzeRolle<T>(e: Erfassung<T>, index: number, rolle: Rolle): Erfassung<T> {
  const ziel = e.dateien[index];
  if (!ziel || ziel.grund) return e;
  if (rolle === 'struktur' && !kannStrukturSein(ziel)) return e;
  return mitRollen(e, (d, i) => {
    if (i === index) return rolle;
    return rolle === 'struktur' && d.rolle === 'struktur' ? 'inhalt' : d.rolle;
  });
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
