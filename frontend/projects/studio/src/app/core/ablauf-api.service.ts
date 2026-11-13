/**
 * Paket K2c-4: einen Ablauf prüfen, ohne ihn zu speichern — `POST /api/config/ablauf-pruefen`
 * (K2c-1). Dieselben Befunde wie beim Speichern, je mit der Stelle des Schritts; seit AS-0 dazu
 * Warnungen, die das Speichern nicht sperren (dieselbe Wendung in einem anderen aktiven Ablauf).
 *
 * Ein Entwurf, der das Modell nicht besteht, kommt als 422 zurück (`StudioApiError.problems`,
 * Pfade unter `body`); die Befunde der Prüfung gibt es erst für einen Entwurf, der es besteht.
 * Seit AS-Dc liefert die Prüfung dazu die Sicht „Daten“ (`teile`).
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

export interface AblaufBefund {
  /** Die Kennung des Schritts; `null`: ein Befund des ganzen Ablaufs. */
  readonly schritt: string | null;
  /** Die Stelle in `schritte` (0…); `null` wie `schritt`. */
  readonly nr: number | null;
  readonly text: string;
}

/** AS-Dc: eine Zeile der Sicht „Daten“ (`services/ablauf/datensicht`). */
export interface AblaufTeil {
  readonly name: string;
  /** `?`: Ausgabe einer KI; `…`: Teil eines Moduls ohne bekannte Normalform. */
  readonly typen: readonly string[];
  readonly schreiber: readonly number[];
  readonly leser: readonly number[];
  readonly vor_dem_start?: boolean;
  /** Kann ein Modul im Gespräch hinterlassen — ohne Schreiber und ohne das schreibt ihn nichts. */
  readonly aus_gespraech?: boolean;
  readonly beispiel?: string | null;
}

export interface AblaufPruefung {
  readonly befunde: readonly AblaufBefund[];
  readonly warnungen: readonly string[];
  readonly teile: readonly AblaufTeil[];
}

/** Das Ergebnis eines simulierten Testfalls (`POST /api/config/ablauf-testen`, AS-1). */
export interface AblaufTestErgebnis {
  readonly name: string;
  readonly ok: boolean;
  readonly status: string;
  readonly weg: readonly string[];
  readonly ende: string;
  readonly abweichungen: readonly string[];
  /** AS-3b: was der Lauf ausgab, mit eingesetzten Platzhaltern (gekürzt). */
  readonly texte?: readonly string[];
}

/** Eine Zeile der Liste `GET /api/config/ablaeufe` (AS-0). */
export interface AblaufZeile {
  /** `06-ablaeufe/<id>` — so wird das Dokument gelesen und gespeichert. */
  readonly key: string;
  readonly id: string;
  readonly titel: Readonly<Record<string, string>>;
  readonly aktiv: boolean;
  readonly ausloeser: readonly string[];
  readonly module: readonly string[];
  readonly befunde: number;
  /** `false`: das Dokument besteht das Modell nicht — es bleibt erreichbar, um es zu reparieren. */
  readonly lesbar: boolean;
  /** R2-a: die KI startet den Ablauf direkt (`modus: direkt` am Auslöser `agent`). */
  readonly direkt?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AblaufApi {
  private readonly api = inject(StudioApi);

  async pruefen(ablauf: unknown): Promise<AblaufPruefung> {
    const antwort = await this.api.post<Partial<AblaufPruefung>>('/config/ablauf-pruefen', ablauf);
    return { befunde: antwort.befunde ?? [], warnungen: antwort.warnungen ?? [], teile: antwort.teile ?? [] };
  }

  /** AS-2c: die Liste der Abläufe (`GET /api/config/ablaeufe`) — für die Querverweise am Modul. */
  async liste(): Promise<readonly AblaufZeile[]> {
    const antwort = await this.api.get<{ ablaeufe?: AblaufZeile[] }>('/config/ablaeufe');
    return antwort.ablaeufe ?? [];
  }

  /** AS-1: die Testfälle des Entwurfs simulieren — schreibt nichts, ruft keinen Fremddienst. */
  async testen(ablauf: unknown): Promise<readonly AblaufTestErgebnis[]> {
    const antwort = await this.api.post<{ ergebnisse?: AblaufTestErgebnis[] }>(
      '/config/ablauf-testen', ablauf);
    return antwort.ergebnisse ?? [];
  }
}
