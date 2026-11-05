/**
 * Typ eines Modul-Manifests (`<modul-ordner>/manifest.json`). Maßgeblich ist das JSON Schema
 * `manifest.schema.json` daneben; Backend (`boerdi/ui_module/katalog.py`) und
 * `npm run module:register` prüfen dagegen. Dieser Typ ist nur die Lesehilfe für TypeScript.
 */
import type { UiModulArt } from './ui-block';

/** `nachladen` (U1-h): Daten über den Host nachholen, ohne Zug (`ModulHost.zweig`). */
export type ModulFaehigkeit = 'antworten' | 'drucken' | 'herunterladen' | 'nachladen' | 'oeffnen';

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
  } | null;
  readonly faehigkeiten?: readonly ModulFaehigkeit[];
  readonly textfassung: { readonly vorlage: string; readonly feld?: string };
  /** `platz`: `oben` (Vorgabe) vor den Trefferboxen, `unten` danach. */
  readonly darstellung?: { readonly breit?: boolean; readonly platz?: 'oben' | 'unten' };
  readonly beispiele: readonly {
    readonly titel: string;
    readonly daten: Record<string, unknown>;
    readonly antwort?: Record<string, unknown>;
  }[];
}
