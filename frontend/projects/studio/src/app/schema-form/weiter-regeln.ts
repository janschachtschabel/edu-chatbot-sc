/**
 * AS-2a (Plan 2026-11-09): die reinen Regeln des Editors für `weiter` eines Ablaufschritts.
 *
 * `weiter` ist leer (der folgende Schritt der Liste), eine Schritt-Kennung oder eine Liste von
 * Regeln — je Regel genau eine Bedingung (`wenn_gewaehlt`, `wenn_teil` oder `wenn_wert`) mit `dann`, zuletzt
 * `sonst` (Modell `Weiter`, Treiber `_waehle`). Was der Editor nicht zeigen kann (zwei Bedingungen in
 * einer Regel, fremde Felder), bleibt als JSON (`json`).
 *
 * Wo Regeln gelten, sagt die Prüfung (`pruefung._regeln`): genau an einer `verzweigung`, dort mit
 * `sonst` zuletzt; an jedem anderen Schritt ist eine Liste ein Fehler (der Treiber nähme sie wie
 * leer). `regelFehlerVon` rechnet das aus dem Dokument — das Formular sperrt damit das Speichern,
 * unabhängig davon, welcher Schritt gerade im Editor steht (Review AS-2, Befund 2).
 */
import { getAt, type ValuePath } from './form-value';

export type WeiterArt = 'folge' | 'schritt' | 'regeln' | 'json';
export type Bedingung = 'gewaehlt' | 'teil' | 'wert' | 'seite' | 'sonst';

/** AS-3c: die Vergleiche von `wenn_wert` — wie `vergleich.VERGLEICHE` im Backend. */
export const VERGLEICHE = ['gleich', 'enthaelt', 'vorhanden', 'leer', 'groesser', 'kleiner'] as const;
/** Diese brauchen einen Wert (`vorhanden` und `leer` keinen). */
export const MIT_WERT: ReadonlySet<string> = new Set(['gleich', 'enthaelt', 'groesser', 'kleiner']);
/** Wie `vergleich.quelle` im Backend: `teil.<name>[.<pfad>]` (Review AS-3c, Befund 4). */
export const QUELLE = /^teil\.([a-z][a-z0-9_]{1,29})(?:\.[A-Za-z0-9_-]{1,64}(?:\.[A-Za-z0-9_-]{1,64}){0,7})?$/;
/** Wie `vergleich.zahl`: Vorzeichen, Ziffern, ein Dezimalkomma oder -punkt. */
const ZAHL = /^[+-]?\d{1,40}(?:[.,]\d{1,40})?$/;

export interface RegelZeile {
  readonly bedingung: Bedingung;
  /** Die Wahl (Kennung einer Möglichkeit), der Name eines Teils bzw. der Vergleichswert; leer bei
   *  `sonst`. */
  readonly wert: string;
  readonly ziel: string;
  /** AS-3c, nur `wert`: `teil.<name>[.<pfad>]` und der Vergleich. */
  readonly quelle?: string;
  readonly vergleich?: string;
}

export interface RegelFehler {
  readonly art: 'leer' | 'wert' | 'ziel' | 'sonstZuletzt' | 'sonstFehlt' | 'nurVerzweigung' | 'wahlWeiter'
    | 'quelle' | 'quelleForm' | 'zahl' | 'muster';
  readonly zeile: number;
}

export interface SchrittInfo {
  readonly id: string;
  readonly typ: string;
}

const FELDER = new Set(['wenn_gewaehlt', 'wenn_teil', 'wenn_wert', 'wenn_seite', 'dann', 'sonst']);
/** AS-7b: `wenn_seite` ist eine Liste von Pfadmustern — im Editor eine Zeile, mit Komma getrennt. */
const MUSTER_TRENNER = ',';
const WERT_FELDER = new Set(['quelle', 'vergleich', 'wert']);

function istObjekt(wert: unknown): wert is Record<string, unknown> {
  return typeof wert === 'object' && wert !== null && !Array.isArray(wert);
}

function regelLesbar(regel: unknown): boolean {
  if (!istObjekt(regel) || Object.keys(regel).some((k) => !FELDER.has(k))) return false;
  const text = (k: string) => regel[k] === undefined || regel[k] === null || typeof regel[k] === 'string';
  if (![...FELDER].filter((k) => k !== 'wenn_wert' && k !== 'wenn_seite').every(text)) return false;
  const s = regel['wenn_seite'];
  // AS-7b: Muster sind Texte ohne Komma (das Komma trennt sie im Editor) — sonst JSON
  if (s !== undefined && s !== null && (!Array.isArray(s) || s.some(
    (m) => typeof m !== 'string' || m.includes(MUSTER_TRENNER)))) return false;
  // AS-3c: ein Vergleich ist ein Objekt aus Text (Quelle, Vergleich, Wert) — mehr zeigt der Editor nicht
  const w = regel['wenn_wert'];
  if (w !== undefined && w !== null && (!istObjekt(w) || Object.entries(w).some(
    ([k, v]) => !WERT_FELDER.has(k) || (v !== null && typeof v !== 'string')))) return false;
  // Review AS-3c, Befund 3: einen unbekannten Vergleich zeigte das Auswahlfeld falsch — JSON
  if (istObjekt(w) && w['vergleich'] != null && !(VERGLEICHE as readonly unknown[]).includes(w['vergleich'])) {
    return false;
  }
  // gezählt wird, welche Bedingung DA ist — eine halbe Regel aus dem Editor (leerer Wert) bleibt eine
  const da = (k: string) => regel[k] !== undefined && regel[k] !== null;
  const bedingungen = ['wenn_gewaehlt', 'wenn_teil', 'wenn_wert', 'wenn_seite', 'sonst'].filter(da);
  return bedingungen.length === 1 && !(da('sonst') && regel['dann']);
}

export function artVon(wert: unknown): WeiterArt {
  if (wert === undefined || wert === null || wert === '') return 'folge';
  if (typeof wert === 'string') return 'schritt';
  if (Array.isArray(wert)) return wert.every(regelLesbar) ? 'regeln' : 'json';
  return 'json';
}

export function regelnAus(wert: unknown): RegelZeile[] {
  if (!Array.isArray(wert)) return [];
  return wert.filter(istObjekt).map((r): RegelZeile => {
    if (typeof r['sonst'] === 'string') return { bedingung: 'sonst', wert: '', ziel: r['sonst'] };
    if (typeof r['wenn_teil'] === 'string') return { bedingung: 'teil', wert: r['wenn_teil'], ziel: String(r['dann'] ?? '') };
    if (Array.isArray(r['wenn_seite'])) {
      return { bedingung: 'seite', wert: r['wenn_seite'].join(`${MUSTER_TRENNER} `), ziel: String(r['dann'] ?? '') };
    }
    const w = r['wenn_wert'];
    if (istObjekt(w)) {
      return { bedingung: 'wert', quelle: String(w['quelle'] ?? ''), vergleich: String(w['vergleich'] ?? 'gleich'),
               wert: String(w['wert'] ?? ''), ziel: String(r['dann'] ?? '') };
    }
    return { bedingung: 'gewaehlt', wert: String(r['wenn_gewaehlt'] ?? ''), ziel: String(r['dann'] ?? '') };
  });
}

/** Werte ohne Leerzeichen am Rand: der Treiber vergleicht genau — „neu “ griffe nie
 *  (Querschnitts-Review AS-0…AS-2, Befund 5). Kennungen tragen keine Leerzeichen. */
export function weiterAus(zeilen: readonly RegelZeile[]): Record<string, unknown>[] {
  return zeilen.map((z): Record<string, unknown> => {
    const wert = z.wert.trim();
    if (z.bedingung === 'sonst') return { sonst: z.ziel };
    if (z.bedingung === 'seite') return { wenn_seite: musterAus(z.wert), dann: z.ziel };
    if (z.bedingung === 'wert') {
      const vergleich = z.vergleich || 'gleich';
      return { wenn_wert: { quelle: (z.quelle ?? '').trim(), vergleich,
                            ...(MIT_WERT.has(vergleich) ? { wert } : {}) }, dann: z.ziel };
    }
    return z.bedingung === 'teil' ? { wenn_teil: wert, dann: z.ziel } : { wenn_gewaehlt: wert, dann: z.ziel };
  });
}

/** AS-7b: die Muster einer Zeile — mit Komma getrennt, ohne Leerraum am Rand, leere fallen weg. */
export function musterAus(zeile: string): string[] {
  return zeile.split(MUSTER_TRENNER).map((m) => m.trim()).filter(Boolean);
}

/** Die erste halbe Regel — solange es eine gibt, sperrt der Editor das Speichern. */
export function fehlerVon(zeilen: readonly RegelZeile[]): RegelFehler | null {
  if (!zeilen.length) return { art: 'leer', zeile: 0 };
  for (const [i, z] of zeilen.entries()) {
    if (z.bedingung === 'wert' && !(z.quelle ?? '').trim()) return { art: 'quelle', zeile: i };
    if (z.bedingung === 'wert' && !QUELLE.test((z.quelle ?? '').trim())) return { art: 'quelleForm', zeile: i };
    const braucht = z.bedingung === 'wert' ? MIT_WERT.has(z.vergleich || 'gleich') : z.bedingung !== 'sonst';
    if (braucht && !z.wert.trim()) return { art: 'wert', zeile: i };
    // Review AS-7b, Befund 9: nur Kommas sind kein Muster (das Backend läse eine leere Liste als keine)
    if (z.bedingung === 'seite' && !musterAus(z.wert).length) return { art: 'wert', zeile: i };
    if (z.bedingung === 'wert' && (z.vergleich === 'groesser' || z.vergleich === 'kleiner')
        && !ZAHL.test(z.wert.trim())) return { art: 'zahl', zeile: i };
    // AS-7b: wie die Prüfung im Backend (`seiten_muster.fehler`) — jedes Muster ist ein Pfad
    if (z.bedingung === 'seite' && musterAus(z.wert).some((m) => !m.startsWith('/'))) {
      return { art: 'muster', zeile: i };
    }
    if (!z.ziel.trim()) return { art: 'ziel', zeile: i };
    if (z.bedingung === 'sonst' && i < zeilen.length - 1) return { art: 'sonstZuletzt', zeile: i };
  }
  // Review AS-2, Befund 3: ohne `sonst` am Ende lehnt die Prüfung die Verzweigung ab
  if (zeilen[zeilen.length - 1].bedingung !== 'sonst') return { art: 'sonstFehlt', zeile: zeilen.length - 1 };
  return null;
}

/** Was an `weiter` eines Schritts vom Typ `typ` das Speichern sperrt — wie die Prüfung. Ein Schritt
 *  ohne Typ (frisch angelegt) darf alles; eine Liste, die der Editor nicht lesen kann, prüft der
 *  Server. */
export function regelFehlerVon(typ: string, wert: unknown, mitWahl = false): RegelFehler | null {
  // AS-3a: mit Schnellantworten entscheidet die Wahl — `weiter` bleibt leer (`pruefung._wahl`)
  if (mitWahl) return wert === undefined || wert === null || wert === '' ? null : { art: 'wahlWeiter', zeile: 0 };
  if (typ === 'verzweigung') {
    if (!Array.isArray(wert)) return { art: 'leer', zeile: 0 };
    return artVon(wert) === 'regeln' ? fehlerVon(regelnAus(wert)) : null;
  }
  if (!Array.isArray(wert)) return null;
  if (typ) return { art: 'nurVerzweigung', zeile: 0 };
  return artVon(wert) === 'regeln' ? fehlerVon(regelnAus(wert)) : null;
}

/** Die Felder `schritte.<i>.weiter` eines Ablaufs, an denen `regelFehlerVon` etwas findet. */
export function regelFehlerOrte(ablauf: unknown): string[] {
  return schritte(ablauf).flatMap((s, i) => {
    if (!istObjekt(s)) return [];
    const typ = typeof s['typ'] === 'string' ? s['typ'] : '';
    return regelFehlerVon(typ, s['weiter'], mitWahl(s)) ? [`schritte.${i}.weiter`] : [];
  });
}

/** AS-3a: wie `pruefung.mit_wahl` — ein `nachricht`- oder `modul`-Schritt mit Schnellantworten
 *  oder Freitext wartet auf die Wahl. */
export function mitWahl(s: unknown): boolean {
  if (!istObjekt(s) || (s['typ'] !== 'nachricht' && s['typ'] !== 'modul')) return false;
  return (Array.isArray(s['optionen']) && s['optionen'].length > 0) || istObjekt(s['freitext']);
}

/** Der Schritt, dem ein `weiter` gehört (Pfad `…, schritte, i, weiter`), roh aus dem Dokument —
 *  auch einer ohne Kennung (Review AS-2, Befund 4) — samt seinem Ablauf. */
export function eigenerSchritt(dok: unknown, pfad: ValuePath): {
  readonly ablauf: unknown; readonly nr: number; readonly id: string; readonly typ: string;
  readonly mitWahl: boolean;
} | null {
  const nr = pfad[pfad.length - 2];
  if (typeof nr !== 'number' || pfad[pfad.length - 3] !== 'schritte') return null;
  const ablauf = getAt(dok, pfad.slice(0, -3));
  const s = schritte(ablauf)[nr];
  const text = (k: string) => (istObjekt(s) && typeof s[k] === 'string' ? s[k] : '');
  return { ablauf, nr, id: text('id'), typ: text('typ'), mitWahl: mitWahl(s) };
}

/** Die Kennung des Schritts nach `nr` — das naheliegende Ziel „bestimmter Schritt“. */
export function folgendeKennung(ablauf: unknown, nr: number): string {
  const s = schritte(ablauf)[nr + 1];
  return istObjekt(s) && typeof s['id'] === 'string' ? s['id'] : '';
}

function schritte(dok: unknown): unknown[] {
  const roh = istObjekt(dok) ? dok['schritte'] : null;
  return Array.isArray(roh) ? roh : [];
}

export function schritteAus(dok: unknown): SchrittInfo[] {
  return schritte(dok).filter(istObjekt)
    .filter((s) => typeof s['id'] === 'string' && s['id'])
    .map((s) => ({ id: String(s['id']), typ: String(s['typ'] ?? '') }));
}

/** Die Möglichkeiten der Auswahlfelder im Ablauf — `wenn_gewaehlt` prüft ihre Kennung. */
export function wahlenAus(dok: unknown): { value: string; label: string }[] {
  const aus = new Map<string, string>();
  for (const s of schritte(dok).filter(istObjekt)) {
    const modul = istObjekt(s['daten']) ? s['daten']['optionen'] : null;
    // AS-3a (Review, Befund 5): auch die Schnellantworten des Schritts — ihr Label je Sprache
    const schnell = Array.isArray(s['optionen']) ? s['optionen'] : [];
    for (const o of [...(Array.isArray(modul) ? modul : []), ...schnell].filter(istObjekt)) {
      if (typeof o['id'] === 'string' && o['id'] && !aus.has(o['id'])) {
        const roh = o['label'];
        const label = istObjekt(roh) ? (typeof roh['de'] === 'string' ? roh['de'] : '') : String(roh ?? '');
        aus.set(o['id'], `${label || o['id']} (${String(s['id'] ?? '')})`);
      }
    }
  }
  return [...aus].map(([value, label]) => ({ value, label }));
}

/** Die Teile, die Schritte des Ablaufs schreiben — `wenn_teil` prüft, ob es sie gibt. */
export function teileAus(dok: unknown): string[] {
  const aus = new Set<string>();
  for (const s of schritte(dok).filter(istObjekt)) {
    // wie `pruefung._schreibt_je_schritt`: `schreibt` wirkt nur an Werkzeug und Auftrag
    const wirkt = s['typ'] === 'werkzeug' || s['typ'] === 'auftrag';
    if (wirkt && typeof s['schreibt'] === 'string' && s['schreibt']) aus.add(s['schreibt']);
    const freitext = s['freitext'];
    if (istObjekt(freitext) && typeof freitext['schreibt'] === 'string' && freitext['schreibt']) {
      aus.add(freitext['schreibt']);
    }
    const agent = s['agent'];
    if (istObjekt(agent) && typeof agent['ausgabe'] === 'string' && agent['ausgabe']) aus.add(agent['ausgabe']);
  }
  return [...aus];
}
