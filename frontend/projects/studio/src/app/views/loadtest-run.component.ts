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
import type { RichSegment } from '@boerdi/ui';

import { AsyncData } from '../core/async-data';
import { LoadtestApi, type LoadTestRun } from '../core/loadtest-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { latencyChart } from './loadtest-chart';
import { loadtestStatusLabel } from './loadtest-status';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

/** ALT's cadence. A stage takes seconds, so a faster poll only adds load. */
const POLL_MS = 2000;

@Component({
  selector: 'studio-loadtest-run',
  imports: [AsyncStateComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './loadtest-run.component.html',
  styleUrl: './loadtest-run.component.scss',
})
export class LoadtestRunComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;
  /** Zwei ausgezeichnete Sätze: das Urteil und der Hinweis auf den Prozess. */
  protected readonly rich = this.lang.rich;

  private readonly api = inject(LoadtestApi);

  readonly runId = input.required<string>();
  /** Raised once when a watched run stops running, so the list can re-read. */
  readonly finished = output<void>();

  readonly run = new AsyncData<LoadTestRun>(() => this.api.run(this.runId()), this.t);
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
    return loadtestStatusLabel(status, this.t);
  }

  /** Das Urteil — die Anzahl wählt die FORM, nicht nur das Substantiv:
   *  „bis 1 gleichzeitigen Nutzer" gegen „bis 4 gleichzeitige Nutzer". */
  stableParts(count: number, threshold: number): readonly RichSegment[] {
    return this.lang.richPlural('ltRun.stable', count, { threshold });
  }

  /** Zwei Anzahlen in einem Satz — zwei Wortgruppen statt vier Sätzen. */
  totals(requests: number, errors: number): string {
    return this.t('ltRun.totals', {
      requests: this.lang.plural('lt.requests', requests),
      errors: this.lang.plural('lt.errors', errors),
    });
  }

  peaks(rss: number, cpu: number, samples: number): string {
    return this.t('ltRun.peaks', {
      rss: this.fmt.decimal(rss),
      cpu: this.fmt.decimal(cpu),
      samples: this.lang.plural('lt.samples', samples),
    });
  }

  /** Zugänglicher Name des Diagramms; die Stufenzahl beugt mit. */
  chartAlt(stages: number): string {
    return this.t('ltRun.chart.alt', { stages: this.lang.plural('lt.stageCount', stages) });
  }

  profileLine(profile: LoadTestRun['profile']): string {
    return this.t('ltRun.profile', {
      stages: profile.stages.join(' → '),
      requests: this.lang.plural('lt.requests', profile.requests_per_stage),
      mix: this.mixLine(profile.mix),
      threshold: profile.p95_threshold_s,
    });
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
