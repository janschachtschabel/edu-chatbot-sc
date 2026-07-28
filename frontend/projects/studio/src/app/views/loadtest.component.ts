/**
 * The load-test dashboard (9-5e): describe a profile, start a run, read the
 * result.
 *
 * This is the one screen in the studio whose button costs money — every request
 * goes through the real chat pipeline with real LLM and MCP calls. Three things
 * follow from that and shape the component:
 *  - the form shows the EFFECTIVE profile (`loadtest-profile.ts`), because the
 *    backend clamps silently and ALT displayed the typed numbers instead;
 *  - the start button is disabled while ANY run is in flight, not just the one
 *    on screen — the backend allows one at a time and answers 409, and ALT
 *    checked only the open run, so the usual way to learn this was the error;
 *  - deleting asks first, inline, instead of `confirm()`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { AsyncData, describeApiError } from '../core/async-data';
import { germanDateTime } from '../core/format';
import { LoadtestApi, type MixOption, type RunListItem } from '../core/loadtest-api.service';
import { AsyncStateComponent } from './async-state.component';
import { LoadtestRunComponent } from './loadtest-run.component';
import { effectiveProfile, MAX_CONCURRENCY, MAX_REQUESTS_PER_STAGE, MAX_STAGES }
  from './loadtest-profile';

@Component({
  selector: 'studio-loadtest',
  imports: [AsyncStateComponent, LoadtestRunComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './loadtest.component.html',
  styleUrl: './loadtest.component.scss',
})
export class LoadtestComponent {
  private readonly api = inject(LoadtestApi);

  readonly maxStages = MAX_STAGES;
  readonly maxConcurrency = MAX_CONCURRENCY;
  readonly maxRequestsPerStage = MAX_REQUESTS_PER_STAGE;

  readonly runs = new AsyncData<readonly RunListItem[]>(() => this.api.runs());
  readonly options = new AsyncData<readonly MixOption[]>(() => this.api.mixOptions());
  readonly rows = computed<readonly RunListItem[]>(() => this.runs.value() ?? []);
  readonly mixOptions = computed<readonly MixOption[]>(() => this.options.value() ?? []);

  readonly stagesText = signal('1, 2, 4, 8');
  readonly requestsPerStage = signal(8);
  readonly thresholdS = signal(20);
  readonly mix = signal<Record<string, number>>({
    wissen: 2, suche: 2, orientierung: 1, lernpfad: 0,
  });

  readonly profile = computed(() => effectiveProfile({
    stagesText: this.stagesText(),
    requestsPerStage: this.requestsPerStage(),
    thresholdS: this.thresholdS(),
    mix: this.mix(),
  }));

  /** The backend runs one at a time; the list is what knows about all of them. */
  readonly busyRun = computed(() => this.rows().find((r) => r.status === 'running') ?? null);

  readonly selected = signal('');
  readonly armed = signal('');
  readonly starting = signal(false);
  readonly working = signal(false);
  readonly actionError = signal('');
  readonly status = signal('');

  constructor() {
    void this.runs.reload();
    void this.options.reload();
  }

  reload(): void {
    void this.runs.reload();
  }

  weightOf(key: string): number {
    return this.mix()[key] ?? 0;
  }

  setWeight(key: string, raw: string): void {
    const parsed = Number.parseInt(raw, 10);
    this.mix.update((current) => ({
      ...current,
      [key]: Number.isFinite(parsed) ? Math.max(0, Math.min(10, parsed)) : 0,
    }));
  }

  setNumber(target: 'requestsPerStage' | 'thresholdS', raw: string): void {
    const parsed = Number.parseFloat(raw);
    // NaN is kept out of the signal: `effectiveProfile` would substitute a
    // minimum, but the field would still read as a number the user never typed.
    if (!Number.isFinite(parsed)) return;
    if (target === 'requestsPerStage') this.requestsPerStage.set(parsed);
    else this.thresholdS.set(parsed);
  }

  select(id: string): void {
    this.selected.set(this.selected() === id ? '' : id);
  }

  async start(): Promise<void> {
    const profile = this.profile();
    if (profile.problem || this.starting() || this.busyRun()) return;
    this.starting.set(true);
    this.actionError.set('');
    this.status.set('');
    try {
      const { id } = await this.api.start({
        stages: profile.stages,
        requests_per_stage: profile.requestsPerStage,
        mix: profile.mix,
        p95_threshold_s: profile.thresholdS,
      });
      this.selected.set(id);
      this.status.set(`Lasttest ${id} gestartet.`);
      await this.runs.reload();
    } catch (err) {
      this.actionError.set(describeApiError(err));
    } finally {
      this.starting.set(false);
    }
  }

  arm(id: string): void {
    this.actionError.set('');
    this.armed.set(id);
  }

  disarm(): void {
    this.armed.set('');
  }

  async confirmDelete(): Promise<void> {
    const id = this.armed();
    if (!id || this.working()) return;
    this.working.set(true);
    this.actionError.set('');
    try {
      await this.api.remove(id);
      if (this.selected() === id) this.selected.set('');
      this.armed.set('');
      this.status.set(`Lauf ${id} gelöscht.`);
      await this.runs.reload();
    } catch (err) {
      this.actionError.set(describeApiError(err));
    } finally {
      this.working.set(false);
    }
  }

  /** A watched run reached its end — the list summary is stale until re-read. */
  onRunFinished(): void {
    void this.runs.reload();
  }

  statusLabel(status: string): string {
    if (status === 'running') return 'läuft';
    if (status === 'completed') return 'abgeschlossen';
    if (status === 'failed') return 'fehlgeschlagen';
    return status;
  }

  summaryLine(row: RunListItem): string {
    if (!row.summary) return '';
    const stable = row.summary.stable_concurrency;
    return `${stable === null ? 'keine stabile Stufe' : `stabil bis ${stable} parallel`}`
      + ` · ${row.summary.total_requests} Requests`
      + ` · ${row.summary.total_errors} Fehler`;
  }

  formatTime(iso: string): string {
    return germanDateTime(iso);
  }
}
