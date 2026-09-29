/**
 * Wo ein Config-Bereich wirkt, je Maschine (ST-5) — die Zuordnung liegt im
 * Backend (`domain/area_effects.py`, festgehalten von einem Wächter), das
 * Studio zeigt sie nur.
 *
 * Geladen von der Shell: beim Start und nach jedem Seitenwechsel, damit ein
 * Wechsel der Vorgabe-Maschine auf der Agent-Seite ankommt. Die Abschnitte
 * lesen nur das Signal und lösen selbst keine Anfrage aus.
 *
 * Ein Fehlschlag leert das Signal: dann zeigt das Studio keine Hinweise —
 * lieber keiner als ein veralteter, der eine andere Maschine nennt als die,
 * die gerade antwortet.
 */
import { Injectable, inject, signal } from '@angular/core';

import { StudioApi } from './studio-api.service';

export type Engine = 'pattern' | 'agent';
/** `krise`: nur bei Krisen- und Drohungs-Zügen — die beantwortet auch unter der
 *  Agent-Schleife der Muster-Weg (SF-1). */
export type EffectLevel = 'voll' | 'teilweise' | 'krise' | 'keine';

export interface AreaEffects {
  /** Die gepflegte Vorgabe — Einbettungen können per Kopfzeile die andere wählen. */
  readonly engine: Engine;
  readonly areas: Readonly<Record<string, Readonly<Record<Engine, EffectLevel>>>>;
}

@Injectable({ providedIn: 'root' })
export class EffectsApi {
  private readonly api = inject(StudioApi);

  readonly effects = signal<AreaEffects | null>(null);

  async refresh(): Promise<void> {
    try {
      this.effects.set(await this.api.get<AreaEffects>('/config/effects'));
    } catch {
      // bewusst still: ein Hinweis-Streifen, keine Funktion — siehe Kopf
      this.effects.set(null);
    }
  }
}
