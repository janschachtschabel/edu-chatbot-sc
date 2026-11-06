/**
 * Übertragen in den persönlichen Bereich in WLO (Paket U3-3b, Plan U3-3 T7) — Regeln ohne DOM.
 *
 * Erlaubt nur, wenn das System es im Block sagt (`schalter.ablage_in_wlo`: Studio UND bestätigte
 * Anmeldung). Übertragen werden die nicht ignorierten Dateien einer Art, die das MCP kennt, bis zur
 * Größe der Ablage (`grenzen.max_mb_ablage`). Die Freigabe trägt je Datei nur Titel, sha256, Größe und
 * Art — keinen Pfad, keinen Inhalt. Die Antwort an den Chat zählt nur (`aktion: "uebertragen"`):
 * keine Kennungen, keine Dateinamen. Die Links je Datei bleiben im Modul.
 */
import { antwortDaten, einZeiler, type UploadAntwort } from './upload-antwort';
import { codeVon } from './upload-dokument';
import type { Erfassung } from './upload-erfassen';

/** Höchstzahl je Freigabe (Backend `Vorbereiten.eintraege`). */
export const MAX_STAPEL = 200;
const MAX_TITEL = 200;
const VORGABE_MB = 10;

/** Endung → Art des MCP (`_ART` in `api/ui_ablage.py`). */
const ARTEN: Readonly<Record<string, string>> = {
  pdf: 'pdf', docx: 'docx', pptx: 'pptx', xlsx: 'xlsx', odt: 'odt', ods: 'ods', odp: 'odp',
  png: 'png', jpg: 'jpg', jpeg: 'jpg', gif: 'gif', webp: 'webp', mp3: 'mp3', mp4: 'mp4',
  txt: 'txt', md: 'md', markdown: 'md',
};

/** Fehler einer einzelnen Datei — der Stapel geht weiter. Jeder andere Code hält ihn an. */
const DATEI_CODES = new Set(['passt_nicht', 'groesse', 'zu_gross', 'art', 'abgewiesen', 'erneut', 'zu_langsam', 'fehler']);
/** Was ein neuer Versuch derselben Datei heilen kann (Netz, Platz im MCP, Frist). */
const WIEDERHOLBAR = new Set(['erneut', 'zu_langsam', 'fehler', 'netz', 'gedrosselt', 'anmeldungen', 'voll', 'nicht_erreichbar']);

export interface Kandidat<T> {
  /** Index in `Erfassung.dateien`. */
  readonly datei: number;
  readonly titel: string;
  readonly art: string;
  readonly groesse: number;
  readonly handle: T;
}

export interface Auswahl<T> {
  readonly kandidaten: readonly Kandidat<T>[];
  readonly ohneArt: number;
  readonly zuGross: number;
}

/** Was der Server zur Freigabe sagt (normalisierte Namen, Ordner oder flach). */
export interface Plan {
  readonly token: string;
  readonly layout: 'ordner' | 'flach';
  readonly ordner: string;
  readonly gesamt: number;
  readonly eintraege: readonly { readonly index: number; readonly titel: string; readonly art: string;
    readonly groesse: number; readonly name: string }[];
}

export type Stand = 'wartet' | 'sendet' | 'stored' | 'dropped' | 'unverified' | 'failed' | 'abgebrochen';

export interface Ergebnis {
  readonly stand: Stand;
  /** Code, wenn das Backend die Datei abwies (`passt_nicht`, `erneut` …). */
  readonly code?: string;
  /** Link zum Ansehen (vom Backend; das Modul baut keine Adressen). */
  readonly link?: string | null;
}

export function artVon(name: string): string | null {
  const punkt = name.lastIndexOf('.');
  if (punkt <= 0) return null;
  return ARTEN[name.slice(punkt + 1).toLowerCase()] ?? null;
}

/** Name ohne Endung, eine Zeile, nach Codepunkten auf 200 gekürzt (`einZeiler` kürzt auf 120 — das gilt
 *  für Ordnernamen an den Chat, der Titel geht nur an das MCP). */
export function titelVon(name: string): string {
  const zeile = (t: string) => t.replace(/\s+/g, ' ').trim();
  const punkt = name.lastIndexOf('.');
  const ohne = zeile(punkt > 0 ? name.slice(0, punkt) : name);
  return Array.from(ohne || zeile(name)).slice(0, MAX_TITEL).join('');
}

export function ablageErlaubt(daten: Readonly<Record<string, unknown>>): boolean {
  const schalter = daten['schalter'];
  return !!schalter && typeof schalter === 'object' && (schalter as Record<string, unknown>)['ablage_in_wlo'] === true;
}

export function maxBytesAblage(daten: Readonly<Record<string, unknown>>): number {
  const mb = ((daten['grenzen'] ?? {}) as Record<string, unknown>)['max_mb_ablage'];
  return (typeof mb === 'number' && mb > 0 ? mb : VORGABE_MB) * 1024 * 1024;
}

export function auswahl<T>(e: Erfassung<T>, maxBytes: number): Auswahl<T> {
  const kandidaten: Kandidat<T>[] = [];
  let ohneArt = 0;
  let zuGross = 0;
  e.dateien.forEach((d, i) => {
    if (d.rolle === 'ignorieren') return;
    const art = artVon(d.name);
    if (!art) ohneArt++;
    else if (d.groesse > maxBytes) zuGross++;
    else kandidaten.push({ datei: i, titel: titelVon(d.name), art, groesse: d.groesse, handle: d.handle });
  });
  return { kandidaten, ohneArt, zuGross };
}

/** SHA-256 als Hex; `lesen` nur für Tests (jsdom kennt `Blob.arrayBuffer` nicht überall). Ohne
 *  `crypto.subtle` (eine Seite ohne https) lehnt es mit dem Code `unsicher` ab. */
export async function sha256Hex(blob: Blob, lesen: (b: Blob) => Promise<ArrayBuffer> = (b) => b.arrayBuffer()): Promise<string> {
  if (!globalThis.crypto?.subtle) throw Object.assign(new Error('crypto.subtle fehlt'), { code: 'unsicher' });
  const summe = await crypto.subtle.digest('SHA-256', await lesen(blob));
  return Array.from(new Uint8Array(summe), (b) => b.toString(16).padStart(2, '0')).join('');
}

/** Wird die Datei an Stelle `position` von `anzahl` angesagt? Die erste, jede zehnte und die letzte —
 *  200 Ansagen in der Warteschlange eines Screenreaders hört niemand (Querschnitts-Review FE-5). */
export function ansageFaellig(position: number, anzahl: number): boolean {
  return position === 1 || position === anzahl || position % 10 === 0;
}

/** Der Plan aus der Antwort von `vorbereiten` — nur, wenn er genau `anzahl` Einträge in Reihenfolge trägt. */
export function planAus(roh: Readonly<Record<string, unknown>>, anzahl: number): Plan | null {
  const token = roh['batch_token'];
  const liste = roh['eintraege'];
  if (typeof token !== 'string' || !token || !Array.isArray(liste) || liste.length !== anzahl) return null;
  const eintraege: Plan['eintraege'][number][] = [];
  for (const [i, x] of liste.entries()) {
    const e = (x ?? {}) as Record<string, unknown>;
    if (e['index'] !== i) return null;
    eintraege.push({
      index: i, titel: einZeiler(String(e['titel'] ?? '')), art: String(e['art'] ?? ''),
      groesse: typeof e['groesse'] === 'number' ? e['groesse'] : 0, name: einZeiler(String(e['name'] ?? e['titel'] ?? '')),
    });
  }
  return {
    // Seit dem Querschnitts-Review spricht das Backend den Wortschatz des Moduls (`ordner` | `flach`);
    // `folder` bleibt verstanden (ältere Antworten, Review U3-3b, Befund 1).
    token, layout: roh['layout'] === 'folder' || roh['layout'] === 'ordner' ? 'ordner' : 'flach', ordner: einZeiler(String(roh['ordner'] ?? '')),
    gesamt: typeof roh['gesamt'] === 'number' ? roh['gesamt'] : 0, eintraege,
  };
}

const ENDSTAENDE = new Set<Stand>(['stored', 'dropped', 'unverified', 'failed']);

/** Der Stand aus der Antwort von `datei`; ein Link nur, wenn er `https:` ist. */
export function standAus(roh: Readonly<Record<string, unknown>>): Ergebnis | null {
  const stand = roh['stand'] as Stand;
  if (!ENDSTAENDE.has(stand)) return null;
  const link = typeof roh['link'] === 'string' && roh['link'].startsWith('https://') ? roh['link'] : null;
  return { stand, link };
}

/** Hält dieser Code den ganzen Stapel an (Anmeldung, Schalter, Freigabe abgelaufen, Netz …)? */
export function stapelEnde(code: string): boolean {
  return !DATEI_CODES.has(code);
}

export function zaehlung(ergebnisse: readonly Ergebnis[]): {
  abgelegt: number; unklar: number; fehler: number; abgebrochen: number;
} {
  const z = { abgelegt: 0, unklar: 0, fehler: 0, abgebrochen: 0 };
  for (const e of ergebnisse) {
    if (e.stand === 'stored' || e.stand === 'dropped') z.abgelegt++;
    else if (e.stand === 'unverified') z.unklar++;
    else if (e.stand === 'failed') z.fehler++;
    else z.abgebrochen++;
  }
  return z;
}

/** Indizes, die ein neuer Versuch senden kann: nicht gesendet, mit einem heilbaren Code abgewiesen oder
 *  „unklar“, weil die Antwort ausblieb (dann sagt das Backend beim zweiten Mal den wahren Stand). */
export function nochmalSenden(ergebnisse: readonly Ergebnis[]): number[] {
  return ergebnisse.flatMap((e, i) =>
    e.stand === 'abgebrochen' || e.stand === 'wartet' || (e.stand === 'unverified' && !!e.code)
      || (e.stand === 'failed' && !!e.code && WIEDERHOLBAR.has(e.code)) ? [i] : []);
}

/** Der Code eines abgelehnten Schritts: ein Abbruch (Widget entfernt) beendet den Stapel; der eigene Code
 *  des Backends geht vor der Deutung des Status (429 `voll` ≠ gedrosselt, Review U3-3b, Befund 7). */
export function codeAblage(fehler: unknown): string {
  const f = fehler as { name?: unknown; code?: unknown } | null;
  if (f?.name === 'AbortError') return 'abgebrochen';
  if (typeof f?.code === 'string' && f.code !== 'fehler' && /^[a-z_]{1,40}$/.test(f.code)) return f.code;
  return codeVon(fehler);
}

export function wiederholbarAblage(code: string): boolean {
  return WIEDERHOLBAR.has(code);
}

export function uebertragenAntwort<T>(
  e: Erfassung<T>, plan: Plan, ergebnisse: readonly Ergebnis[],
  o: { readonly ordnerVerweigert: boolean; readonly vorgangAbgelegt: boolean },
): UploadAntwort {
  return {
    ...antwortDaten(e, 'uebertragen'),
    ablage: {
      layout: o.ordnerVerweigert ? 'flach' : plan.layout, gesamt: ergebnisse.length, ...zaehlung(ergebnisse),
      ordner_verweigert: o.ordnerVerweigert, vorgang_abgelegt: o.vorgangAbgelegt,
    },
  };
}
