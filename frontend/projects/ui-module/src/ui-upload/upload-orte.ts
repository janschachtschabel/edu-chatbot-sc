/**
 * „Wo sollen sie verarbeitet werden?“ (Plan 2026-11-17, Paket U4, E13) — Regeln ohne DOM.
 *
 * Das Backend rechnet im Zug die Orte (`orte`: Vorauswahl, je Ort `geht`, Codes `grund`/`hinweis`/
 * `ueber_grenze`, `docs/ui-module.md` §6 „Ein Upload-Weg“). Die Oberfläche übersetzt nur die Codes
 * und prüft die Grenzen „Hier im Chat“ (`grenzen.lokal_*`) gegen die Auswahl: Gezählt werden nur
 * lesbare Dateien (PDF, Word, Text, Markdown; Inhalte und Strukturdokumente zusammen) bis zur Grenze
 * je Datei (`lokal_max_mb_datei`; größere gehen wie nicht lesbare nur mit dem Namen). Überschreitet
 * die Auswahl eine Grenze, ist „Hier im Chat“ für sie gesperrt (Code aus `chat.ueber_grenze`), und
 * eine Vorauswahl `chat` wechselt zu `wlo`, wenn es geht, sonst zu den Namen. Den Rest der Sitzung
 * (`lokal_frei_dateien`, `lokal_frei_mb`) prüft sie ebenso, wenn das Backend ihn schickt; ohne ihn
 * (älteres Backend) gilt nur die Grenze je Auswahl, und den Rest weist der Server ab (`grenze_*`).
 *
 * Ohne `orte` (älteres Backend, Studio-Vorschau) leiten sich die Orte aus `schalter` ab.
 */
import type { AblageRolle } from '../_vertrag/modul-host';
import type { Erfassung } from './upload-erfassen';
import { kannStrukturSein } from './upload-rollen';
import { auswahl, MAX_STAPEL, maxBytesAblage } from './upload-uebertragen';

export type Ort = 'chat' | 'wlo' | 'namen';
/** Vertrag: `aus`, `nur_angemeldet`, `ablauf`, `grenze_sitzung` (Sitzung voll), `ueber_grenze(_anmelden)`;
 *  nur hier: `stapel`, `keine`. */
export type OrtGrund = 'aus' | 'nur_angemeldet' | 'ablauf' | 'grenze_sitzung' | 'ueber_grenze' | 'ueber_grenze_anmelden'
  | 'stapel' | 'keine';

export interface OrtStand {
  readonly geht: boolean;
  readonly grund?: OrtGrund;
  readonly hinweis?: 'ohne_erschliessung';
  /** Nur chat, vom Backend: der Code, wenn die Auswahl die Grenzen überschreitet. */
  readonly ueber_grenze?: 'ueber_grenze' | 'ueber_grenze_anmelden';
  /** Nur chat, vom Backend (Plan 2026-11-19, Paket C): gescannte PDF liest der Server per
   *  Texterkennung — ihre Seiten gehen als Bild an das KI-Modell. */
  readonly texterkennung?: true;
  /** Nur chat, hier gerechnet: welche Grenze die Auswahl überschreitet — je Auswahl, Rest der
   *  Sitzung (`frei_*`) oder (bei `keine`) jede lesbare Datei über der Grenze je Datei. */
  readonly grenze?: 'anzahl' | 'gesamt' | 'frei_anzahl' | 'frei_gesamt' | 'datei';
}

export interface Orte {
  readonly vorauswahl: Ort;
  readonly chat: OrtStand;
  readonly wlo: OrtStand;
  /** Plan 2026-11-20 §8, E3: auf dem Dokument-Weg (`einzeldatei_als_struktur`) folgt der Ablage kein
   *  Flow — der Ort heißt nur „In WLO ablegen“ und verspricht keine Angaben. */
  readonly nurAblegen?: true;
}

export interface LokaleGrenzen {
  readonly maxDateien: number;
  readonly maxBytes: number;
  readonly aufbewahrungH: number;
  /** Je Datei (`lokal_max_mb_datei`); ohne Angabe unbegrenzt — dann entscheidet der Server. */
  readonly maxBytesDatei: number;
  /** Rest der Sitzung (`lokal_frei_*`); `null` = unbekannt (älteres Backend). */
  readonly freiDateien: number | null;
  readonly freiBytes: number | null;
}

/** Eine Datei, die „Hier im Chat“ hochgeladen wird — `i` ist ihre feste Nummer in der Auswahl. */
export interface LokaleDatei<T> {
  readonly i: number;
  readonly rolle: AblageRolle;
  readonly name: string;
  readonly groesse: number;
  readonly handle: T;
}

export interface LokaleAuswahl<T> {
  /** Alle, die hochgehen (Dubletten eingeschlossen — jede bekommt ihre `upload_id`). */
  readonly lesbar: readonly LokaleDatei<T>[];
  /** Wie viele davon zählen: Dubletten einmal (zweites Review, 4) — so zählt auch der Server. */
  readonly anzahl: number;
  /** Nicht ignoriert, aber kein lesbares Format: davon geht nur der Name mit. */
  readonly nichtLesbar: number;
  /** Lesbar, aber über der Grenze je Datei: davon geht ebenso nur der Name mit. */
  readonly zuGross: number;
  /** Größe der zählenden (ohne Dubletten). */
  readonly bytes: number;
}

const MB = 1024 * 1024;
const VORGABE = { maxDateien: 10, mbGesamt: 50, aufbewahrungH: 24 };
const GRUENDE = new Set<string>(['aus', 'nur_angemeldet', 'ablauf', 'grenze_sitzung']);
const UEBER = new Set<string>(['ueber_grenze', 'ueber_grenze_anmelden']);
const ORTE = new Set<string>(['chat', 'wlo', 'namen']);

function objekt(x: unknown): Record<string, unknown> | null {
  return x && typeof x === 'object' && !Array.isArray(x) ? x as Record<string, unknown> : null;
}

/** Ein Ort aus dem Vertrag; Unbrauchbares gilt als gesperrt (`aus`) — nie als wählbar. */
function stand(roh: unknown): OrtStand {
  const o = objekt(roh);
  if (!o || typeof o['geht'] !== 'boolean') return { geht: false, grund: 'aus' };
  if (!o['geht']) return { geht: false, grund: GRUENDE.has(String(o['grund'])) ? o['grund'] as OrtGrund : 'aus' };
  return {
    geht: true,
    ...(o['hinweis'] === 'ohne_erschliessung' ? { hinweis: 'ohne_erschliessung' as const } : {}),
    ...(UEBER.has(String(o['ueber_grenze'])) ? { ueber_grenze: o['ueber_grenze'] as OrtStand['ueber_grenze'] } : {}),
    ...(o['texterkennung'] === true ? { texterkennung: true as const } : {}),
  };
}

function ausSchaltern(daten: Readonly<Record<string, unknown>>): Orte {
  const s = objekt(daten['schalter']) ?? {};
  const chat: OrtStand = s['dokument_im_chat'] === true ? { geht: true }
    : { geht: false, grund: s['lesen_nach_anmeldung'] === true ? 'nur_angemeldet' : 'aus' };
  const wlo: OrtStand = s['ablage_in_wlo'] === true ? { geht: true }
    : { geht: false, grund: s['ablage_nach_anmeldung'] === true ? 'nur_angemeldet' : 'aus' };
  // E13: mit bestätigter Anmeldung (die Ablage geht) ist WLO die Vorgabe
  return { vorauswahl: wlo.geht ? 'wlo' : chat.geht ? 'chat' : 'namen', chat, wlo };
}

export function orteAus(daten: Readonly<Record<string, unknown>>): Orte {
  const o = objekt(daten['orte']);
  const orte = !o || !ORTE.has(String(o['vorauswahl'])) ? ausSchaltern(daten)
    : { vorauswahl: o['vorauswahl'] as Ort, chat: stand(o['chat']), wlo: stand(o['wlo']) };
  return daten['einzeldatei_als_struktur'] === true ? { ...orte, nurAblegen: true } : orte;
}

export function lokaleGrenzen(daten: Readonly<Record<string, unknown>>): LokaleGrenzen {
  const g = objekt(daten['grenzen']) ?? {};
  const n = (v: unknown, vorgabe: number) => (typeof v === 'number' && v > 0 ? v : vorgabe);
  // Der Rest darf 0 sein (Sitzung voll); Unbrauchbares heißt unbekannt
  const rest = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null);
  const freiMb = rest(g['lokal_frei_mb']);
  return {
    maxDateien: n(g['lokal_max_dateien'], VORGABE.maxDateien),
    maxBytes: n(g['lokal_max_mb_gesamt'], VORGABE.mbGesamt) * MB,
    aufbewahrungH: n(g['lokal_aufbewahrung_h'], VORGABE.aufbewahrungH),
    maxBytesDatei: n(g['lokal_max_mb_datei'], Infinity) * MB,
    freiDateien: rest(g['lokal_frei_dateien']),
    freiBytes: freiMb === null ? null : freiMb * MB,
  };
}

/** Dieselbe Datei für „Hier im Chat“: gleiche Rolle, Größe und gleicher Name — wie
 *  `upload_bereitgestellt._dubletten_grund` — und im Browser zusätzlich das Änderungsdatum. Der Server
 *  ersetzt ein Dokument nur bei gleichem Text; zwei Dateien mit diesem Schlüssel gehen deshalb einmal
 *  hoch und teilen die `upload_id` (zweites Review, 1/3). */
export function dublettenSchluessel(d: Pick<LokaleDatei<unknown>, 'rolle' | 'groesse' | 'name' | 'handle'>): string {
  const geaendert = (d.handle as { lastModified?: unknown } | null)?.lastModified;
  return `${d.rolle}/${d.groesse}/${typeof geaendert === 'number' ? geaendert : ''}/${d.name}`;
}

/** Was „Hier im Chat“ hochlädt: lesbare, nicht ignorierte Dateien bis zur Grenze je Datei (`g`). */
export function lokaleAuswahl<T>(e: Erfassung<T>, g?: Pick<LokaleGrenzen, 'maxBytesDatei'>): LokaleAuswahl<T> {
  const lesbar: LokaleDatei<T>[] = [];
  let nichtLesbar = 0;
  let zuGross = 0;
  e.dateien.forEach((d, i) => {
    if (d.rolle === 'ignorieren') return;
    if (!kannStrukturSein(d)) { nichtLesbar++; return; }
    if (g && d.groesse > g.maxBytesDatei) { zuGross++; return; }
    lesbar.push({ i, rolle: d.rolle === 'struktur' ? 'struktur' : 'inhalt', name: d.name, groesse: d.groesse, handle: d.handle });
  });
  const zaehlend = new Map(lesbar.map((d) => [dublettenSchluessel(d), d.groesse]));
  return { lesbar, anzahl: zaehlend.size, nichtLesbar, zuGross, bytes: [...zaehlend.values()].reduce((s, b) => s + b, 0) };
}

function chatFuer(chat: OrtStand, a: LokaleAuswahl<unknown>, g: LokaleGrenzen): OrtStand {
  if (!chat.geht) return chat;
  if (!a.lesbar.length) return { geht: false, grund: 'keine', ...(a.zuGross ? { grenze: 'datei' as const } : {}) };
  // Die Grenze je Auswahl zuerst — sie gilt auch in einem neuen Gespräch
  const n = a.anzahl;
  const grenze = n > g.maxDateien ? 'anzahl' : a.bytes > g.maxBytes ? 'gesamt'
    : g.freiDateien !== null && n > g.freiDateien ? 'frei_anzahl'
      : g.freiBytes !== null && a.bytes > g.freiBytes ? 'frei_gesamt' : null;
  return grenze ? { geht: false, grund: chat.ueber_grenze ?? 'ueber_grenze', grenze } : chat;
}

function wloFuer<T>(wlo: OrtStand, e: Erfassung<T>, daten: Readonly<Record<string, unknown>>): OrtStand {
  if (!wlo.geht) return wlo;
  const n = auswahl(e, maxBytesAblage(daten)).kandidaten.length;
  if (!n) return { geht: false, grund: 'keine' };
  return n > MAX_STAPEL ? { geht: false, grund: 'stapel' } : wlo;
}

/** Die Orte für diese Auswahl: Grenzen „Hier im Chat“, Größe einer Übertragung, Vorauswahl. */
export function orteFuer<T>(daten: Readonly<Record<string, unknown>>, e: Erfassung<T>): Orte {
  const o = orteAus(daten);
  const g = lokaleGrenzen(daten);
  const chat = chatFuer(o.chat, lokaleAuswahl(e, g), g);
  const wlo = wloFuer(o.wlo, e, daten);
  const geht = { chat: chat.geht, wlo: wlo.geht, namen: true };
  const ersatz: Ort = o.vorauswahl === 'wlo' ? (chat.geht ? 'chat' : 'namen') : (wlo.geht ? 'wlo' : 'namen');
  return { ...o, vorauswahl: geht[o.vorauswahl] ? o.vorauswahl : ersatz, chat, wlo };
}

/** Darf die Erklärzeile „ohne Anmeldung“ sagen? Nur, wenn die Schalter es tragen: ausdrücklich
 *  `dokument_ohne_anmeldung`, sonst (älteres Backend) solange Lesen nicht erst nach der Anmeldung geht. */
export function chatOhneAnmeldung(daten: Readonly<Record<string, unknown>>): boolean {
  const s = objekt(daten['schalter']) ?? {};
  return typeof s['dokument_ohne_anmeldung'] === 'boolean' ? s['dokument_ohne_anmeldung'] : s['lesen_nach_anmeldung'] !== true;
}

/** Der Ort, den „Hochladen“ nimmt: die Wahl der Person, solange er geht, sonst die Vorauswahl;
 *  `null`, wenn nur die Namen gehen. */
export function gewaehlt(o: Orte, wahl: Ort | null): 'chat' | 'wlo' | null {
  if ((wahl === 'chat' || wahl === 'wlo') && o[wahl].geht) return wahl;
  const v = o.vorauswahl;
  return v !== 'namen' && o[v].geht ? v : null;
}
