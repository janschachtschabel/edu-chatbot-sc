/**
 * Nutzung im Überblick (Paket 16, D3) — wie das Studio `GET /api/nutzung/ueberblick` liest.
 *
 * Quelle ist das Qualitätsprotokoll; `protokoll_an` sagt, ob es gerade schreibt. Zellen von 1 bis
 * `klein_unter` − 1 kommen als `null` und heißen in der Ansicht „<5“.
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
  /** `null`: weniger als `klein_unter`, aber mehr als null. */
  readonly anzahl: number | null;
}

export const FACETTEN = ['maschine', 'sprache', 'geraet', 'seitenart', 'persona', 'anliegen'] as const;
export type Facette = (typeof FACETTEN)[number];

export interface NutzungUeberblick {
  readonly zuege: number;
  readonly sitzungen: number;
  readonly zuege_je_sitzung: { readonly mittel: number; readonly median: number };
  readonly tage: readonly NutzungTag[];
  /** 7 × 24, Zeile 0 = Montag, Spalte = Stunde (deutsche Zeit). */
  readonly raster: readonly (readonly (number | null)[])[];
  readonly verteilungen: Readonly<Record<Facette, readonly NutzungWert[]>>;
  readonly klein_unter: number;
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
