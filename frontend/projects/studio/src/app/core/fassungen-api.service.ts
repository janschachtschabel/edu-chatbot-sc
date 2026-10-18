/**
 * Werk und eigene Fassung je Konfigurationsbereich — `api/config_fassungen.py` (Paket 12).
 *
 * Die Werksfassung ist der Seed im Abbild, die gelebte Fassung steht in der Datenbank. Der Status
 * kommt fertig vom Server (`services/werkfassung.py`); das Studio rechnet nichts nach. Der Bereich
 * reist im Body bzw. in der Abfrage, nie im Pfad: Bereichsnamen enthalten `/`.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

/** Mirror of the backend statuses (`services/werkfassung.py`). */
export type FassungStatus =
  | 'werk'
  | 'werk-veraltet'
  | 'eigen'
  | 'eigen-neues-werk'
  | 'nur-eigen'
  | 'werk-entfernt'
  | 'werk-fehlt';

export interface FassungZeile {
  readonly area: string;
  readonly status: FassungStatus;
  /** `null`, wenn es den Bereich in der Datenbank nicht gibt (gelöscht oder nie angelegt). */
  readonly version: number | null;
  /** Eine eigene Fassung liegt still und lässt sich zurückholen. */
  readonly hat_eigene_fassung: boolean;
}

export interface FassungListe {
  /** `false`: das Abbild bringt keine Werksfassung mit (`CONFIG_SEED_DIR`). */
  readonly available: boolean;
  readonly bereiche: readonly FassungZeile[];
}

export interface Werksabgleich {
  readonly neu: number;
  readonly aktualisiert: number;
  readonly zugeordnet: number;
  readonly neues_werk: number;
  /** Seit dem Lesen geändert (Studio, andere Replika) — der nächste Abgleich sieht sie neu. */
  readonly uebersprungen: number;
  /** Kennung schon vergeben — nicht angelegt. */
  readonly konflikt: number;
}

export interface Vergleich {
  readonly area: string;
  readonly werk: string;
  readonly gelebt: string;
  readonly eigene: string | null;
  /** Unified diff (`difflib`), erste zwei Zeilen sind die Kopfzeilen `--- werk` / `+++ gelebt`. */
  readonly zeilen: readonly string[];
  /** Stillgelegte Fassung gegen die Werksfassung (leer, wenn keine stillliegt). */
  readonly zeilen_eigene: readonly string[];
  /** Paket 16, C6: dieselben Unterschiede je Feld (höchstens 100), `*_gesamt` = alle. */
  readonly felder?: readonly FeldUnterschied[];
  readonly felder_gesamt?: number;
  readonly felder_eigene?: readonly FeldUnterschied[];
  readonly felder_eigene_gesamt?: number;
}

/** Ein abweichendes Blatt: Werte als gekürzter JSON-Text, `null` = das Feld fehlt dort. */
export interface FeldUnterschied {
  readonly pfad: string;
  readonly werk: string | null;
  readonly eigen: string | null;
}

/** `geprueft`: eigene Fassung behalten, aktuelle Werksfassung als gesehen merken. */
export type FassungZiel = 'werk' | 'eigen' | 'geprueft';

const BASE = '/config/fassungen';

@Injectable({ providedIn: 'root' })
export class FassungenApi {
  private readonly api = inject(StudioApi);

  list(): Promise<FassungListe> {
    return this.api.get<FassungListe>(BASE);
  }

  werksabgleich(): Promise<Werksabgleich> {
    return this.api.post<Werksabgleich>(`${BASE}/werksabgleich`, {});
  }

  umschalten(
    area: string, ziel: FassungZiel, expectedVersion: number | null,
  ): Promise<{ status: string; area: string; version: number }> {
    return this.api.post(`${BASE}/umschalten`, {
      area, ziel, expected_version: expectedVersion,
    });
  }

  vergleich(area: string): Promise<Vergleich> {
    return this.api.get<Vergleich>(`${BASE}/vergleich`, { area });
  }
}
