/**
 * The list of evaluation runs (9-5d): what ran, how far it got, what it cost.
 *
 * Re-reads itself while any run is in flight, with the 9-5e pattern: a
 * `setTimeout` chain (a slow answer cannot stack a second request), the timer
 * tied to `DestroyRef`, and a failed poll made visible while the last good list
 * stays on screen.
 *
 * A failed run's `error_message` is shown, not hidden — for a generative run it
 * is the only account of what went wrong halfway through, and the run keeps the
 * transcript it managed to collect before dying.
 */
import {
  ChangeDetectionStrategy, Component, DestroyRef, computed, inject, output, signal,
} from '@angular/core';

import { AsyncData, describeApiError } from '../core/async-data';
import { EvalApi, type EvalRunSummary } from '../core/eval-api.service';
import { formatDecimal, germanDateTime } from '../core/format';
import { AsyncStateComponent } from './async-state.component';

/** Slower than the load test's 2 s: an eval run takes minutes, not seconds. */
const POLL_MS = 3000;

const STATUS_LABELS: Readonly<Record<string, string>> = {
  running: 'läuft',
  done: 'fertig',
  completed: 'fertig',
  failed: 'fehlgeschlagen',
};

const STATUS_FILTERS: readonly { readonly value: string; readonly label: string }[] = [
  { value: '', label: 'alle Status' },
  { value: 'done', label: 'fertige' },
  { value: 'failed', label: 'fehlgeschlagene' },
  { value: 'running', label: 'laufende' },
];

type Armed =
  | { readonly kind: 'one'; readonly id: string }
  | { readonly kind: 'bulk' }
  | { readonly kind: 'logs' }
  | null;

@Component({
  selector: 'studio-eval-runs',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-runs.component.html',
  styleUrl: './eval-runs.component.scss',
})
export class EvalRunsComponent {
  private readonly api = inject(EvalApi);

  /** The id of the run to open in detail; the view above owns that panel. */
  readonly runChange = output<string>();

  readonly statusFilters = STATUS_FILTERS;
  readonly statusFilter = signal('');

  readonly armed = signal<Armed>(null);
  readonly working = signal(false);
  readonly actionError = signal('');
  readonly status = signal('');

  readonly runs = new AsyncData<readonly EvalRunSummary[]>(() => this.api.runs());

  readonly rows = computed(() => this.runs.value() ?? []);

  readonly isPolling = computed(() => this.rows().some((row) => row.status === 'running'));

  readonly question = computed(() => {
    const armed = this.armed();
    if (armed?.kind === 'one') return `Lauf ${armed.id} endgültig löschen?`;
    if (armed?.kind === 'logs') {
      return 'Alle Quality-Logs löschen, die Eval-Läufe geschrieben haben? '
        + 'Echte Chat-Turns bleiben unberührt.';
    }
    if (armed?.kind === 'bulk') {
      const chosen = this.statusFilter();
      if (!chosen) return 'ALLE Eval-Läufe löschen — auch die laufenden?';
      const label = STATUS_FILTERS.find((f) => f.value === chosen)?.label ?? chosen;
      return `Alle ${label} Eval-Läufe löschen?`;
    }
    return '';
  });

  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    void this.load();
    inject(DestroyRef).onDestroy(() => this.stopPolling());
  }

  async load(): Promise<void> {
    await this.runs.reload();
    this.scheduleNextPoll();
  }

  reload(): void {
    void this.load();
  }

  open(id: string): void {
    this.runChange.emit(id);
  }

  arm(armed: Armed): void {
    this.actionError.set('');
    this.status.set('');
    this.armed.set(armed);
  }

  disarm(): void {
    this.armed.set(null);
  }

  isArmed(id: string): boolean {
    const armed = this.armed();
    return armed?.kind === 'one' && armed.id === id;
  }

  onStatusFilter(value: string): void {
    this.statusFilter.set(value);
    this.armed.set(null);
  }

  async confirm(): Promise<void> {
    const armed = this.armed();
    if (!armed || this.working()) return;
    this.working.set(true);
    this.actionError.set('');
    try {
      if (armed.kind === 'one') {
        await this.api.deleteRun(armed.id);
        this.status.set(`Lauf ${armed.id} gelöscht.`);
      } else if (armed.kind === 'logs') {
        const { deleted } = await this.api.clearEvalQualityLogs();
        this.status.set(`${deleted} Eval-Quality-Logs gelöscht.`);
        this.armed.set(null);
        this.working.set(false);
        return; // the run list is unaffected — no reload needed
      } else {
        const { deleted } = await this.api.deleteRuns({
          status: this.statusFilter() || undefined,
        });
        this.status.set(`${deleted} Läufe gelöscht.`);
      }
      this.armed.set(null);
      await this.load();
    } catch (err) {
      this.actionError.set(describeApiError(err));
    } finally {
      this.working.set(false);
    }
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }

  when(iso: string): string {
    return germanDateTime(iso);
  }

  score(value: number | null): string {
    return value === null ? '–' : formatDecimal(value);
  }

  private scheduleNextPoll(): void {
    this.stopPolling();
    if (!this.isPolling()) return;
    this.timer = setTimeout(() => void this.poll(), POLL_MS);
  }

  private async poll(): Promise<void> {
    this.timer = null;
    await this.runs.reload();
    this.scheduleNextPoll();
  }

  private stopPolling(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }
}
