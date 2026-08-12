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
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { evalStatusLabel } from './eval-status';
import { StudioFormat } from '../i18n/studio-format.service';

/** Slower than the load test's 2 s: an eval run takes minutes, not seconds. */
const POLL_MS = 3000;

const STATUS_FILTERS: readonly { readonly value: string; readonly labelKey: string }[] = [
  { value: '', labelKey: 'evalRuns.filter.all' },
  { value: 'done', labelKey: 'evalRuns.filter.done' },
  { value: 'failed', labelKey: 'evalRuns.filter.failed' },
  { value: 'running', labelKey: 'evalRuns.filter.running' },
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
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;

  private readonly api = inject(EvalApi);

  /** The id of the run to open in detail; the view above owns that panel. */
  readonly runChange = output<string>();

  /** Erst beim Rendern beschriftet — sonst fröre die Sprache beim Laden des
   *  Moduls ein (C1-d4b). */
  readonly statusFilters = computed(() =>
    STATUS_FILTERS.map((f) => ({ value: f.value, label: this.t(f.labelKey) })));

  readonly statusFilter = signal('');

  readonly armed = signal<Armed>(null);
  readonly working = signal(false);
  readonly actionError = signal('');
  readonly status = signal('');

  readonly runs = new AsyncData<readonly EvalRunSummary[]>(() => this.api.runs(), this.t);

  readonly rows = computed(() => this.runs.value() ?? []);

  readonly isPolling = computed(() => this.rows().some((row) => row.status === 'running'));

  readonly question = computed(() => {
    const armed = this.armed();
    if (armed?.kind === 'one') return this.t('evalRuns.ask.run', { id: armed.id });
    if (armed?.kind === 'logs') return this.t('evalRuns.ask.logs');
    if (armed?.kind === 'bulk') {
      const chosen = this.statusFilter();
      if (!chosen) return this.t('evalRuns.ask.all');
      const key = STATUS_FILTERS.find((f) => f.value === chosen)?.labelKey;
      return this.t('evalRuns.ask.filtered', { label: key ? this.t(key) : chosen });
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
        this.status.set(this.t('evalRuns.done.run', { id: armed.id }));
      } else if (armed.kind === 'logs') {
        const { deleted } = await this.api.clearEvalQualityLogs();
        this.status.set(this.t('evalRuns.done.logs', { count: deleted }));
        this.armed.set(null);
        this.working.set(false);
        return; // the run list is unaffected — no reload needed
      } else {
        const { deleted } = await this.api.deleteRuns({
          status: this.statusFilter() || undefined,
        });
        this.status.set(this.lang.plural('evalRuns.done.runs', deleted));
      }
      this.armed.set(null);
      await this.load();
    } catch (err) {
      this.actionError.set(describeApiError(err, this.t));
    } finally {
      this.working.set(false);
    }
  }

  statusLabel(status: string): string {
    return evalStatusLabel(status, this.t);
  }

  /** Die Zähl-Zeile als GANZER Satz, gebeugt nach der Regel der aktiven
   *  Sprache — bis C1-d4b stand hier fest `{n} Läufe`, und ein einzelner Lauf
   *  las sich „1 Läufe". */
  countLine(): string {
    return this.lang.plural('evalRuns.count', this.rows().length);
  }

  when(iso: string): string {
    return this.fmt.dateTime(iso);
  }

  score(value: number | null): string {
    return value === null ? '–' : this.fmt.decimal(value);
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
