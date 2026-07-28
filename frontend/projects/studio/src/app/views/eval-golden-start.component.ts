/**
 * Start a golden-flow run (9-5d / A2).
 *
 * Like the generative start this fires real chat requests, so it asks first —
 * inline, not via `confirm()`. Unlike it, the cost is **exact rather than
 * estimated**: a gold run does one chat call per configured turn, and the turns
 * are right there in `gold-flows.yaml`. So the count is summed on the spot
 * instead of asking `/eval/estimate`, and the text says a count, not a band.
 *
 * The `judge` switch is the expensive one: since C3 it really runs, adding one
 * LLM call per answered turn (`services/eval/golden.py`). The confirmation names
 * that number rather than leaving "mit Judge" to be interpreted.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, output, signal,
} from '@angular/core';

import { AsyncData, describeApiError } from '../core/async-data';
import { EvalApi, type GoldFlow } from '../core/eval-api.service';
import { formatWhole } from '../core/format';
import { AsyncStateComponent } from './async-state.component';

@Component({
  selector: 'studio-eval-golden-start',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-golden-start.component.html',
  styleUrl: './eval-golden-start.component.scss',
})
export class EvalGoldenStartComponent {
  private readonly api = inject(EvalApi);

  /** True while any run is in flight — the backend allows one and answers 409. */
  readonly busy = input(false);
  readonly started = output<string>();

  readonly flowList = new AsyncData<readonly GoldFlow[]>(() => this.api.goldFlows());
  readonly flows = computed<readonly GoldFlow[]>(() => this.flowList.value() ?? []);

  readonly judge = signal(false);
  private readonly chosen = signal<ReadonlySet<string>>(new Set());

  readonly armed = signal(false);
  readonly starting = signal(false);
  readonly startError = signal('');
  readonly status = signal('');
  readonly warnings = signal<readonly string[]>([]);

  /** Empty selection means all — the rule `start_golden_eval_run` applies. */
  readonly selected = computed<readonly GoldFlow[]>(() => {
    const ids = this.chosen();
    return ids.size === 0 ? this.flows() : this.flows().filter((f) => ids.has(f.id));
  });

  /** Exactly what will be fired: one chat call per configured turn. */
  readonly turns = computed(() =>
    this.selected().reduce((sum, flow) => sum + (flow.turns?.length ?? 0), 0));

  readonly noFlows = computed(() => !this.flowList.loading() && this.flows().length === 0);
  readonly ready = computed(() => !this.flowList.error() && this.turns() > 0);

  constructor() {
    void this.flowList.reload();
  }

  isChosen(id: string): boolean {
    return this.chosen().has(id);
  }

  toggle(id: string): void {
    this.chosen.update((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
    this.disarm();
  }

  setJudge(on: boolean): void {
    this.judge.set(on);
    this.disarm();
  }

  arm(): void {
    if (this.busy() || !this.ready()) return;
    this.startError.set('');
    this.status.set('');
    this.warnings.set([]);
    this.armed.set(true);
  }

  disarm(): void {
    this.armed.set(false);
  }

  async start(): Promise<void> {
    if (this.starting() || this.busy() || !this.armed()) return;
    this.starting.set(true);
    this.startError.set('');
    try {
      const result = await this.api.startGoldenRun({
        flow_ids: [...this.chosen()], judge: this.judge(), config_slug: '',
      });
      this.armed.set(false);
      this.status.set(`Gold-Lauf ${result.run_id} gestartet.`);
      this.warnings.set(result.warnings ?? []);
      this.started.emit(result.run_id);
    } catch (err) {
      this.startError.set(describeApiError(err));
    } finally {
      this.starting.set(false);
    }
  }

  count(value: number): string {
    return formatWhole(value);
  }

  /** "4 Turns · P-LEH · I03, I04" — what this flow is going to exercise. */
  flowMeta(flow: GoldFlow): string {
    const parts = [`${flow.turns?.length ?? 0} Turns`];
    if (flow.persona) parts.push(flow.persona);
    if (flow.intents?.length) parts.push(flow.intents.join(', '));
    return parts.join(' · ');
  }
}
