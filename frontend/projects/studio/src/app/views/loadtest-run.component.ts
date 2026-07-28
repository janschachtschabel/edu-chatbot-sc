/**
 * One load-test run: the verdict, the latency curve and the stage table (9-5e).
 *
 * While the run is in flight this re-reads it. Two differences to ALT, both
 * about not lying while waiting:
 *  - a `setTimeout` chain instead of `setInterval`, so a slow answer cannot
 *    stack a second request on top of the first;
 *  - a failed poll surfaces (via `AsyncData`) while the last good state stays
 *    on screen. ALT caught poll errors with an empty block, so a backend that
 *    died mid-run left the page saying "läuft" forever.
 */
import {
  ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, output,
  untracked,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { LoadtestApi, type LoadTestRun } from '../core/loadtest-api.service';
import { AsyncStateComponent } from './async-state.component';
import { latencyChart } from './loadtest-chart';

/** ALT's cadence. A stage takes seconds, so a faster poll only adds load. */
const POLL_MS = 2000;

@Component({
  selector: 'studio-loadtest-run',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './loadtest-run.component.html',
  styleUrl: './loadtest-run.component.scss',
})
export class LoadtestRunComponent {
  private readonly api = inject(LoadtestApi);

  readonly runId = input.required<string>();
  /** Raised once when a watched run stops running, so the list can re-read. */
  readonly finished = output<void>();

  readonly run = new AsyncData<LoadTestRun>(() => this.api.run(this.runId()));
  readonly value = computed(() => this.run.value());
  readonly isRunning = computed(() => this.value()?.status === 'running');

  readonly chart = computed(() => {
    const run = this.value();
    return run && run.stages.length > 0
      ? latencyChart(run.stages, run.profile.p95_threshold_s)
      : null;
  });

  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      this.runId();
      untracked(() => void this.load());
    });
    inject(DestroyRef).onDestroy(() => this.stopPolling());
  }

  async load(): Promise<void> {
    await this.run.reload();
    this.scheduleNextPoll();
  }

  private scheduleNextPoll(): void {
    this.stopPolling();
    if (!this.isRunning()) return;
    this.timer = setTimeout(() => void this.poll(), POLL_MS);
  }

  private async poll(): Promise<void> {
    this.timer = null;
    const wasRunning = this.isRunning();
    await this.run.reload();
    if (wasRunning && !this.isRunning()) {
      this.finished.emit();
      return;
    }
    this.scheduleNextPoll();
  }

  private stopPolling(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  statusLabel(status: string): string {
    if (status === 'running') return 'läuft';
    if (status === 'completed') return 'abgeschlossen';
    if (status === 'failed') return 'fehlgeschlagen';
    return status;
  }

  /** "wissen 3 · suche 2" — the weights as they were sent. */
  mixLine(mix: Readonly<Record<string, number>>): string {
    return Object.entries(mix).map(([key, weight]) => `${key} ${weight}`).join(' · ');
  }

  /** Per-category p95 of one stage, for the last table column. */
  byKindLine(byKind: Readonly<Record<string, { p95_s: number }>>): string {
    return Object.entries(byKind).map(([key, v]) => `${key} ${v.p95_s}s`).join(' · ');
  }
}
