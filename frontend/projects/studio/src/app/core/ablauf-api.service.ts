/**
 * Paket K2c-4: einen Ablauf prüfen, ohne ihn zu speichern — `POST /api/config/ablauf-pruefen`
 * (K2c-1). Dieselben Befunde wie beim Speichern, je mit der Stelle des Schritts.
 *
 * Ein Entwurf, der das Modell nicht besteht, kommt als 422 zurück (`StudioApiError.problems`,
 * Pfade unter `body`); die Befunde der Prüfung gibt es erst für einen Entwurf, der es besteht.
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

@Injectable({ providedIn: 'root' })
export class AblaufApi {
  private readonly api = inject(StudioApi);

  async pruefen(ablauf: unknown): Promise<readonly AblaufBefund[]> {
    const antwort = await this.api.post<{ befunde: AblaufBefund[] }>('/config/ablauf-pruefen', ablauf);
    return antwort.befunde;
  }
}
