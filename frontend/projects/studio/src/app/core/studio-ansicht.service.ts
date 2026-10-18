/**
 * Der Arbeitsbereich des Studios (Paket 14): Agent-Schleife oder Muster-Maschine.
 *
 * Jeder Arbeitsbereich hat seine eigene, fest kuratierte Navigation (`studio-views.ts`); die
 * Ansicht „beide“ aus Paket 13 gibt es nicht mehr — der Nutzer wollte getrennte Arbeitsbereiche,
 * keinen Filter über alles (Plan `2026-10-17-paket-14-studio-arbeitsbereiche.md`).
 *
 * - **Startwert** ist die Vorgabe-Maschine des Servers (`EffectsApi`), solange niemand gewählt
 *   hat; ohne geladene Wirkungen der Agent, die Vorgabe im Betrieb. Ein gescheitertes Nachladen
 *   (`effects` → `null`) behält die zuletzt bekannte Vorgabe — sonst kippte der Arbeitsbereich
 *   beim nächsten Seitenwechsel ohne Zutun. `ermittle()` wartet auf die Vorgabe (Startseite).
 * - **Gemerkt** wird eine Wahl je Browser (`localStorage`). Ein gesperrter Speicher ist kein
 *   Fehler: die Wahl gilt dann bis zum Neuladen. Ein gemerktes `beide` zählt als keine Wahl.
 */
import { Injectable, computed, inject, linkedSignal, signal } from '@angular/core';

import { EffectsApi, type Engine } from './effects-api.service';

export type Ansicht = Engine;

export const ANSICHT_STORAGE_KEY = 'boerdi_studio_ansicht';
export const ANSICHTEN: readonly Ansicht[] = ['agent', 'pattern'];

function gemerkt(): Ansicht | null {
  try {
    const wert = localStorage.getItem(ANSICHT_STORAGE_KEY);
    return ANSICHTEN.includes(wert as Ansicht) ? (wert as Ansicht) : null;
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class StudioAnsicht {
  private readonly effectsApi = inject(EffectsApi);
  private readonly gewaehlt = signal<Ansicht | null>(gemerkt());
  private readonly vorgabe = linkedSignal<Ansicht | null, Ansicht | null>({
    source: () => this.effectsApi.effects()?.engine ?? null,
    computation: (engine, vorher) => engine ?? vorher?.value ?? null,
  });

  readonly ansicht = computed<Ansicht>(() => this.gewaehlt() ?? this.vorgabe() ?? 'agent');

  /** Die Maschine des Arbeitsbereichs als Filter (Analyse, Evaluation). */
  readonly maschine = this.ansicht;

  /** Der Arbeitsbereich, sobald er feststeht: ohne Wahl erst nach dem Laden der Vorgabe. */
  async ermittle(): Promise<Ansicht> {
    if (!this.gewaehlt() && !this.vorgabe()) await this.effectsApi.refresh();
    return this.ansicht();
  }

  waehle(ansicht: Ansicht): void {
    this.gewaehlt.set(ansicht);
    try {
      localStorage.setItem(ANSICHT_STORAGE_KEY, ansicht);
    } catch { /* bewusst still: die Wahl gilt dann bis zum Neuladen — siehe Kopf */ }
  }

  /** Ein Element, das nur in bestimmten Maschinen etwas bedeutet; ohne Angabe überall. */
  zeigt(engines: readonly Engine[] | undefined): boolean {
    return !engines || engines.includes(this.ansicht());
  }
}
