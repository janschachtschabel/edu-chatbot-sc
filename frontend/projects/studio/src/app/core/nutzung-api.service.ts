/**
 * Nutzung im Überblick (Paket 16, D3) — wie das Studio `GET /api/nutzung/ueberblick` liest.
 *
 * Quelle ist das Qualitätsprotokoll; `protokoll_an` sagt, ob es gerade schreibt. Alle Zahlen sind
 * genau (seit 2026-10-18; vorher kamen Zellen aus weniger als fünf Sitzungen als `null`).
 */
import { Injectable, inject } from '@angular/core';

import { type OriginScope, scopeParams } from './origin-scope';
import { StudioApi } from './studio-api.service';

export interface NutzungTag {
  readonly tag: string;
  readonly sitzungen: number;
  readonly zuege: number;
}

export interface NutzungWert {
  readonly wert: string;
  readonly anzahl: number;
}

export const FACETTEN = ['maschine', 'sprache', 'geraet', 'seitenart', 'persona', 'anliegen'] as const;
export type Facette = (typeof FACETTEN)[number];

export interface NutzungUeberblick {
  readonly zuege: number;
  readonly sitzungen: number;
  readonly zuege_je_sitzung: { readonly mittel: number; readonly median: number };
  readonly tage: readonly NutzungTag[];
  /** 7 × 24, Zeile 0 = Montag, Spalte = Stunde (deutsche Zeit). */
  readonly raster: readonly (readonly number[])[];
  readonly verteilungen: Readonly<Record<Facette, readonly NutzungWert[]>>;
  readonly protokoll_an: boolean;
}

@Injectable({ providedIn: 'root' })
export class NutzungApi {
  private readonly api = inject(StudioApi);

  ueberblick(
    from: string, to: string, scope: OriginScope = 'all', engine?: 'pattern' | 'agent',
  ): Promise<NutzungUeberblick> {
    return this.api.get<NutzungUeberblick>('/nutzung/ueberblick', {
      from, to, ...scopeParams(scope), engine,
    });
  }
}
