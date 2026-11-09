/**
 * Typ eines Modul-Manifests (`<modul-ordner>/manifest.json`). Maßgeblich ist das JSON Schema
 * `manifest.schema.json` daneben; Backend (`boerdi/ui_module/katalog.py`) und
 * `npm run module:register` prüfen dagegen. Dieser Typ ist nur die Lesehilfe für TypeScript.
 */
import type { UiModulArt } from './ui-block';

/** `nachladen` (U1-h): Daten über den Host nachholen, ohne Zug (`ModulHost.zweig`). `auftrag` (K1b): den Stand
 *  eines Ablauf-Auftrags abfragen und ihn abholen lassen (`ModulHost.auftrag`). */
export type ModulFaehigkeit = 'antworten' | 'auftrag' | 'drucken' | 'herunterladen' | 'hochladen' | 'nachladen' | 'oeffnen';

export interface UiModulManifest {
  readonly name: string;
  readonly version: number;
  readonly art: UiModulArt;
  readonly titel: { readonly de: string; readonly en?: string };
  readonly beschreibung: string;
  readonly wann?: readonly string[];
  readonly nicht_wann?: readonly string[];
  readonly agent?: boolean;
  /** JSON Schema der Daten — für die KI zugleich die Werkzeug-Parameter. */
  readonly eingabe: Record<string, unknown>;
  /** JSON Schema der Antwort (nur abfragende Module). */
  readonly antwort?: Record<string, unknown>;
  /** Große Daten holt das Backend (U1-e): die KI nennt nur `argumente`, `vorgaben` setzt es fest. */
  readonly datenquelle?: {
    readonly werkzeug: string;
    readonly argumente: readonly string[];
    readonly vorgaben?: Readonly<Record<string, unknown>>;
  } | null;
  /** Paket U2: Daten erzeugt ein Dienst des Backends; die KI nennt nur den Auftrag (`parameter`). */
  readonly dienst?: {
    readonly name: string;
    readonly parameter: Record<string, unknown>;
    /** Paket U4: MCP-Werkzeuge, die der Dienst ruft — ohne sie wird das Modul nicht angeboten. */
    readonly braucht?: readonly string[];
  } | null;
  readonly faehigkeiten?: readonly ModulFaehigkeit[];
  /** Paket V2: welchen Teil des Vorgangs eine Antwort setzt, welche Teile der Dienst liest. */
  readonly vorgang?: { readonly schreibt?: readonly string[]; readonly liest?: readonly string[] };
  readonly textfassung: { readonly vorlage: string; readonly feld?: string };
  /** `platz`: `oben` (Vorgabe) vor den Trefferboxen, `unten` danach. */
  readonly darstellung?: { readonly breit?: boolean; readonly platz?: 'oben' | 'unten' };
  /** Paket U3-0: `bei_bedarf` = eigenes Bündel (Custom Element), erst beim ersten Block geladen. */
  readonly laden?: 'sofort' | 'bei_bedarf';
  readonly beispiele: readonly {
    readonly titel: string;
    readonly daten: Record<string, unknown>;
    readonly antwort?: Record<string, unknown>;
  }[];
}
