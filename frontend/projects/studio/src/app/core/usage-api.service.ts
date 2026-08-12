/**
 * Die Kostenschau, wie das Studio sie liest (K5).
 *
 * **`amount` ist eine Zeichenkette, keine Zahl.** Der Server rechnet mit
 * `Decimal` und gibt den Betrag als Text aus (K4): als JSON-Zahl würde aus
 * `13.27743099` beim Serialisieren wieder `13.277430990000001`. Wer dieses Feld
 * in eine Zahl umwandelt, wirft genau das weg, wofür der Umweg gebaut wurde —
 * formatiert wird es über `StudioFormat.money`.
 *
 * **`price_unavailable` gehört neben den Betrag, nicht daneben in eine Ecke.**
 * `amount` deckt nur die bepreisten Modelle; ohne die Liste läse sich eine
 * Teilsumme als Gesamtsumme.
 *
 * Der Zeitraum ist `from`/`to` — beide Grenzen zählen mit, und `to` schickt die
 * Ansicht als Tagesende (siehe `costs.component.ts`), weil ein blosses Datum
 * serverseitig Mitternacht bedeutet und der letzte Tag sonst stumm fehlte.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

/** Die Zahlen einer Gruppe — je Modell wie je Sitzung dieselbe Form. */
export interface UsageTotals {
  readonly calls: number;
  readonly prompt_tokens: number;
  /** In `prompt_tokens` ENTHALTEN, nicht zusätzlich. */
  readonly cached_tokens: number;
  readonly completion_tokens: number;
  /** In `completion_tokens` ENTHALTEN, nicht zusätzlich. */
  readonly reasoning_tokens: number;
  /** Exakter Betrag als Text; `null` = für kein Modell ein Preis gepflegt. */
  readonly amount: string | null;
}

export interface UsageModelRow extends UsageTotals {
  readonly model: string;
}

export interface UsageSessionRow extends UsageTotals {
  readonly session_id: string;
  /** Modelle dieser Sitzung ohne gepflegten Preis. */
  readonly price_unavailable: readonly string[];
}

export interface UsageReport extends UsageTotals {
  /** Keine einzige Verbrauchszeile — kein Fehler, sondern ein leerer Zeitraum. */
  readonly empty: boolean;
  readonly currency: string;
  readonly price_unavailable: readonly string[];
  /**
   * Die Preistafel ist unlesbar — nicht bloss ungepflegt. Beide Zustände
   * enden ohne Betrag; ohne dieses Feld sähe ein YAML-Tippfehler aus wie eine
   * frische Installation, und der Grund stünde nur im Server-Log.
   */
  readonly price_config_broken: boolean;
  readonly models: readonly UsageModelRow[];
  /** Nur beim Zeitraum; die Einzelsitzung führt keine Sitzungsliste. */
  readonly sessions?: readonly UsageSessionRow[];
}

@Injectable({ providedIn: 'root' })
export class UsageApi {
  private readonly api = inject(StudioApi);

  /** `from`/`to` als ISO-Zeitpunkte; beide Grenzen zählen mit. */
  period(from: string, to: string): Promise<UsageReport> {
    return this.api.get<UsageReport>('/usage/period', { from, to });
  }
}
