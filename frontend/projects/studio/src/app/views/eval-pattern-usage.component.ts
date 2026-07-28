/**
 * Which pattern actually fired, for whom, how often (9-5d / A4).
 *
 * Reads `quality_logs`, so it works independently of the eval engine: it counts
 * real turns as well as eval turns, which is why the scope filter is the first
 * control. `scope=eval` is the only view that answers "what did my runs
 * exercise"; `production` answers "what do people actually hit".
 *
 * The two distributions reuse `QualityBarsComponent` from 9-5c rather than
 * drawing bars again — it already renders "a key with a number" as a real table
 * with the bar hidden from assistive technology.
 *
 * `since` is a native `<input type="date">`: the backend parses it with
 * `datetime.fromisoformat`, which accepts a bare date, so no datepicker
 * dependency and no format to explain.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { EvalApi, type PatternUsage } from '../core/eval-api.service';
import { formatDecimal, formatWhole } from '../core/format';
import { AsyncStateComponent } from './async-state.component';
import { QualityBarsComponent } from './quality-bars.component';

const SCOPES: readonly { readonly value: string; readonly label: string }[] = [
  { value: 'all', label: 'alle Turns' },
  { value: 'eval', label: 'nur Eval-Läufe' },
  { value: 'production', label: 'nur echte Nutzung' },
];

/** `[{pattern_id, count}]` → the `Record` the shared bar table takes. */
function distribution(
  rows: readonly Record<string, unknown>[] | undefined, idKey: string,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows ?? []) {
    const id = typeof row[idKey] === 'string' ? (row[idKey] as string) : '';
    const count = typeof row['count'] === 'number' ? row['count'] : 0;
    out[id] = (out[id] ?? 0) + count;
  }
  return out;
}

@Component({
  selector: 'studio-eval-pattern-usage',
  imports: [AsyncStateComponent, QualityBarsComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-pattern-usage.component.html',
  styleUrl: './eval-pattern-usage.component.scss',
})
export class EvalPatternUsageComponent {
  private readonly api = inject(EvalApi);

  readonly scopes = SCOPES;
  readonly scope = signal('all');
  readonly since = signal('');

  readonly usage = new AsyncData<PatternUsage>(
    () => this.api.patternUsage(this.scope(), this.since()));

  readonly value = computed(() => this.usage.value());
  readonly triples = computed(() => this.value()?.triples ?? []);

  readonly byPattern = computed(() =>
    distribution(this.value()?.by_pattern as readonly Record<string, unknown>[] | undefined,
                 'pattern_id'));
  readonly byIntent = computed(() =>
    distribution(this.value()?.by_intent as readonly Record<string, unknown>[] | undefined,
                 'intent_id'));

  readonly isEmpty = computed(() =>
    !this.usage.loading() && !this.usage.error() && this.triples().length === 0);

  constructor() {
    void this.usage.reload();
  }

  reload(): void {
    void this.usage.reload();
  }

  setScope(value: string): void {
    if (value === this.scope()) return;
    this.scope.set(value);
    this.reload();
  }

  setSince(value: string): void {
    if (value === this.since()) return;
    this.since.set(value);
    this.reload();
  }

  /** An empty id is an unclassified turn — a blank cell reads as a bug. */
  id(value: string | undefined): string {
    return value || '(ohne)';
  }

  count(value: number): string {
    return formatWhole(value);
  }

  /** `null` means no turn carried a confidence, which is not the same as 0. */
  confidence(value: number | null | undefined): string {
    return value === null || value === undefined ? '–' : formatDecimal(value);
  }
}
