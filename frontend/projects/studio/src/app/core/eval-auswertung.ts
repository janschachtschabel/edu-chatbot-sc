/**
 * Die Auswertung eines Golden-Laufs mit dem Judge v2 (Paket 13, F1) — Typen und reine Helfer.
 *
 * Das Backend rechnet beim Lesen (`services/eval/auswertung_v2.py`) und schickt das Ergebnis
 * als `auswertung` am Lauf-Detail; Messbedingungen und Kurzbericht stehen im frei geformten
 * `summary`. Ein Lauf von vor Paket 13 hat keine Auswertung — jedes Feld ist deshalb optional
 * gelesen, nie vorausgesetzt.
 */

/** Note 1–5 als Mittel mit Anzahl (eine Zelle einer Matrix). */
export interface NotenZelle {
  readonly mittel: number | null;
  readonly n: number;
}

export type NotenMatrix = Readonly<Record<string, Readonly<Record<string, NotenZelle>>>>;

export interface Quote {
  readonly bestanden: number;
  readonly geprueft: number;
}

export interface Auffaelligkeit {
  readonly zug: number | null;
  readonly art: string;
  readonly text: string;
}

export interface AblaufAuswertung {
  readonly flow_id: string;
  readonly title: string;
  readonly zielgruppe: string;
  readonly skalen: Readonly<Record<string, number>>;
  readonly gesamt: number | null;
  readonly statement: string;
  readonly auffaelligkeiten: readonly Auffaelligkeit[];
  readonly urteil_fehler: string;
  readonly harte_quote: Quote;
  readonly zug_mittel: number | null;
  readonly zuege: number;
  readonly chat_fehler: number;
  readonly latenz_p50_ms: number | null;
  readonly kosten: number | null;
  readonly werkzeugaufrufe: number;
}

export interface GesamtAuswertung {
  readonly ablaeufe: number;
  readonly zuege: number;
  readonly gesamt_mittel: number | null;
  readonly skalen_mittel: Readonly<Record<string, number | null>>;
  readonly zug_mittel: number | null;
  readonly harte_quote: Quote;
  readonly latenz: { readonly p50_ms: number | null; readonly p95_ms: number | null };
  readonly kosten_je_zug: number | null;
  readonly chat_fehler: number;
  readonly judge_fehler: number;
  readonly judge_kosten: number | null;
  readonly judge_aufrufe: number | null;
  readonly judge_fassung: string;
}

export interface Verteilung {
  readonly p50_ms: number | null;
  readonly p95_ms: number | null;
  readonly n: number;
}

export type ZeitArt = 'knoten' | 'schritte' | 'llm';

export interface AuswertungV2 {
  readonly je_ablauf: readonly AblaufAuswertung[];
  readonly gesamt: GesamtAuswertung;
  readonly matrix_zielgruppe_anwendungsfall: NotenMatrix;
  readonly matrix_ablauf_skala: Readonly<Record<string, Readonly<Record<string, number | null>>>>;
  readonly matrix_persona_intent: NotenMatrix;
  readonly zeiten: Readonly<Record<ZeitArt, Readonly<Record<string, Verteilung>>>>;
}

export interface Baustelle {
  readonly ablauf: string | null;
  readonly text: string;
}

export interface Kurzbericht {
  readonly text: string;
  readonly baustellen: readonly Baustelle[];
  /** Gesetzt, wenn der Bericht ausfiel — der Lauf ist trotzdem gültig. */
  readonly fehler: string;
}

/** Womit ein Modell angesprochen wurde (`services/llm_weg.py`). */
export interface LlmWeg {
  readonly anbieter?: string;
  readonly modell?: string;
  readonly api?: string;
  readonly basis?: string;
  /** Paket 17 (A4): Route des b-api-Routers — `null`, wenn ohne Router gerufen. */
  readonly route?: string | null;
  readonly reasoning_effort?: string | null;
  readonly verbosity?: string | null;
  readonly service_tier?: string | null;
}

export interface Messbedingungen {
  readonly provider?: string;
  readonly chat_model?: string;
  readonly judge_model?: string;
  readonly maschine?: string;
  readonly weg?: LlmWeg | null;
  readonly judge_weg?: LlmWeg | null;
  readonly app?: { readonly version?: string; readonly commit?: string };
  readonly konfiguration?: { readonly hash?: string; readonly fehler?: string };
  readonly gold_flows?: { readonly hash?: string; readonly ids?: readonly string[] } | null;
  readonly master_skill?: {
    readonly enabled?: boolean | null; readonly version?: string; readonly sha256?: string;
  };
}

export interface V2Punkt {
  readonly run_id: string;
  readonly created_at: string | null;
  readonly value: number;
}

export interface Wechsel {
  readonly run_id: string;
  readonly created_at: string | null;
  readonly felder: readonly string[];
  readonly prompts: readonly string[];
}

export interface TrendsV2 {
  readonly gesamt: readonly V2Punkt[];
  readonly zug_mittel: readonly V2Punkt[];
  readonly latenz_p50_ms: readonly V2Punkt[];
  readonly kosten_je_zug: readonly V2Punkt[];
  readonly skalen: Readonly<Record<string, readonly V2Punkt[]>>;
  readonly wechsel: readonly Wechsel[];
}

export interface PromptFassung {
  readonly hash: string;
  readonly art: string;
  readonly erstmals: string | null;
  readonly zuletzt: string | null;
}

export interface PromptDiff {
  readonly a: PromptFassung;
  readonly b: PromptFassung;
  readonly gleiche_art: boolean;
  readonly diff: readonly string[];
}

/** Farbstufe einer Note (Plan §5.6): ≥ 4,5 · ≥ 3,5 · ≥ 2,5 · darunter · ohne Daten. */
export type Stufe = 'sehr-gut' | 'gut' | 'mittel' | 'schwach' | 'leer';

export function stufe(note: number | null | undefined): Stufe {
  if (note === null || note === undefined) return 'leer';
  if (note >= 4.5) return 'sehr-gut';
  if (note >= 3.5) return 'gut';
  if (note >= 2.5) return 'mittel';
  return 'schwach';
}

function objekt(wert: unknown): Readonly<Record<string, unknown>> | null {
  return wert && typeof wert === 'object' && !Array.isArray(wert)
    ? wert as Readonly<Record<string, unknown>> : null;
}

export function messbedingungenAus(summary: Readonly<Record<string, unknown>>): Messbedingungen | null {
  return objekt(summary['messbedingungen']) as Messbedingungen | null;
}

export function kurzberichtAus(summary: Readonly<Record<string, unknown>>): Kurzbericht | null {
  const bericht = objekt(summary['kurzbericht']);
  if (bericht) {
    return {
      text: String(bericht['text'] ?? ''),
      baustellen: (Array.isArray(bericht['baustellen']) ? bericht['baustellen'] : []) as Baustelle[],
      fehler: '',
    };
  }
  const fehler = summary['kurzbericht_fehler'];
  return typeof fehler === 'string' && fehler ? { text: '', baustellen: [], fehler } : null;
}
