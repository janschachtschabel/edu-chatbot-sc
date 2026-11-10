/**
 * Paket AS-8b (Plan 2026-11-09 §5n, P-9): „Im Widget ausprobieren“ — die Startdaten der Probe und
 * der Weg vom Ablauf in die Vorschau. Rein (aus `@boerdi/ui` nur die Grenzen der Startdaten).
 *
 * Die Vorschau gibt die Startdaten an `element.startAblauf(id, daten)` (Browser-Abnahme AS-8, B-1:
 * nicht als Attribut); das Widget prüft sie noch einmal (`ablaufStartPruefen`, dieselben Grenzen),
 * das Backend gegen das Startschema des Ablaufs. Hier geht es darum, dass die Redaktion einen
 * Fehler am Feld sieht und nicht als stumme Probe (Review AS-8b, Befund 2).
 */

import { START_JSON_MAX, START_SCHLUESSEL_MAX } from '@boerdi/ui';

export type StartdatenErgebnis =
  | { readonly ok: true; readonly json: string | null }
  | { readonly ok: false; readonly fehler: StartdatenFehler };

export type StartdatenFehler = 'json' | 'objekt' | 'gross' | 'schluessel';

/** Leer = ohne Startdaten; sonst muss es ein JSON-Objekt sein (kompakt zurück). */
export function startdatenPruefen(roh: string): StartdatenErgebnis {
  const text = roh.trim();
  if (!text) return { ok: true, json: null };
  let wert: unknown;
  try {
    wert = JSON.parse(text);
  } catch {
    return { ok: false, fehler: 'json' };
  }
  if (wert === null || typeof wert !== 'object' || Array.isArray(wert)) {
    return { ok: false, fehler: 'objekt' };
  }
  const json = JSON.stringify(wert);
  if (json.length > START_JSON_MAX) return { ok: false, fehler: 'gross' };
  if (Object.keys(wert).length > START_SCHLUESSEL_MAX) return { ok: false, fehler: 'schluessel' };
  return { ok: true, json };
}

/** Relativ zur aktuellen Studio-Seite in die Vorschau (die Ansichten liegen auf einer Ebene). */
export function probeHref(id: unknown): string | null {
  return typeof id === 'string' && id ? `vorschau?ablauf=${encodeURIComponent(id)}` : null;
}
