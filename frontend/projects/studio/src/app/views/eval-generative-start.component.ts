/**
 * Start a generative evaluation run (9-5d / A3).
 *
 * This button spends money at two providers: every judged turn is a chat call
 * through the real pipeline PLUS a judge call, and the simulator adds one per
 * combination. With the full config that is 144 combinations. So the flow is
 * two-step on purpose: "Kosten prüfen" fetches `/eval/estimate` and opens an
 * inline confirmation carrying the band; only the second button starts the run.
 * The cost figure is therefore impossible to skip, and it costs exactly one
 * request — not one per keystroke, which is how ALT's quality view behaved.
 *
 * A confirmation is spent once used: after a start (or any change to the form)
 * the estimate no longer describes what would run, so it is dropped rather than
 * left on screen next to different numbers.
 *
 * Nothing here is clamped silently. The numeric bounds mirror `StartRequest`
 * (1…10), which the backend enforces with a 422 that names no field — clamping
 * locally keeps the number on screen the number that runs. The 9-5e lesson.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, output, signal,
} from '@angular/core';

import { AsyncData, describeApiError } from '../core/async-data';
import { EvalApi, type EvalConfig, type EvalEstimate, type EvalMode }
  from '../core/eval-api.service';
import { formatUsd, formatWhole } from '../core/format';
import { AsyncStateComponent } from './async-state.component';

/** `StartRequest`/`EstimateRequest` bounds — mirrored, not guessed. */
const MIN_PER_COMBO = 1;
const MAX_PER_COMBO = 10;

const MODES: readonly { readonly value: EvalMode; readonly label: string }[] = [
  { value: 'both', label: 'Szenarien und Gespräche' },
  { value: 'scenarios', label: 'nur Szenarien (ein Turn je Szenario)' },
  { value: 'conversations', label: 'nur Gespräche (mehrere Turns)' },
];

interface Choice {
  readonly id: string;
  readonly label: string;
}

/** The config endpoint returns free-form dicts; only id and label are used. */
function choices(rows: readonly Record<string, unknown>[] | undefined): readonly Choice[] {
  return (rows ?? []).flatMap((row) => {
    const id = typeof row['id'] === 'string' ? row['id'] : '';
    if (!id) return [];
    const label = typeof row['label'] === 'string' && row['label'] ? row['label'] : id;
    return [{ id, label }];
  });
}

@Component({
  selector: 'studio-eval-generative-start',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-generative-start.component.html',
  styleUrl: './eval-generative-start.component.scss',
})
export class EvalGenerativeStartComponent {
  private readonly api = inject(EvalApi);

  /** True while any run is in flight — the backend allows one and answers 409. */
  readonly busy = input(false);

  /** The id of the run that was just started, for the list to pick up. */
  readonly started = output<string>();

  readonly modes = MODES;
  readonly minPerCombo = MIN_PER_COMBO;
  readonly maxPerCombo = MAX_PER_COMBO;

  readonly config = new AsyncData<EvalConfig>(() => this.api.config());

  readonly personas = computed(() => choices(this.config.value()?.personas));
  readonly intents = computed(() => choices(this.config.value()?.intents));

  readonly mode = signal<EvalMode>('both');
  readonly scenariosPerCombo = signal(2);
  readonly turnsPerConv = signal(3);
  private readonly chosenPersonas = signal<ReadonlySet<string>>(new Set());
  private readonly chosenIntents = signal<ReadonlySet<string>>(new Set());

  /** The pending confirmation: the estimate, or the reason there is none. */
  readonly estimate = signal<EvalEstimate | null>(null);
  readonly estimateError = signal('');
  readonly armed = signal(false);
  readonly checking = signal(false);
  readonly starting = signal(false);
  readonly startError = signal('');
  readonly status = signal('');
  readonly warnings = signal<readonly string[]>([]);

  /** Empty selection means "all" — the same rule `estimate()` applies server-side. */
  readonly combos = computed(() => {
    const personas = this.chosenPersonas().size || this.personas().length;
    const intents = this.chosenIntents().size || this.intents().length;
    return personas * intents;
  });

  readonly ready = computed(() => !this.config.error() && this.combos() > 0);

  /**
   * A config with no personas or no intents cannot produce a single combination.
   * Without saying so, the form would show two empty lists and a dead button.
   */
  readonly nothingConfigured = computed(() =>
    !this.config.loading() && !this.config.error() && this.combos() === 0);

  constructor() {
    void this.config.reload();
  }

  isChosen(kind: 'persona' | 'intent', id: string): boolean {
    return this.chosen(kind)().has(id);
  }

  toggle(kind: 'persona' | 'intent', id: string): void {
    this.chosen(kind).update((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
    this.disarm();
  }

  setMode(value: EvalMode): void {
    this.mode.set(value);
    this.disarm();
  }

  setNumber(target: 'scenariosPerCombo' | 'turnsPerConv', raw: string): void {
    const parsed = Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed)) return;
    const clamped = Math.max(MIN_PER_COMBO, Math.min(MAX_PER_COMBO, parsed));
    this[target].set(clamped);
    this.disarm();
  }

  /** Step one: price the run and open the confirmation. Starts nothing. */
  async check(): Promise<void> {
    if (this.checking() || this.busy() || !this.ready()) return;
    this.checking.set(true);
    this.estimateError.set('');
    this.startError.set('');
    this.status.set('');
    this.warnings.set([]);
    try {
      this.estimate.set(await this.api.estimate(this.request()));
    } catch (err) {
      // Not fatal: the operator authorises the spend, not the estimate. But the
      // confirmation must then say it has no price rather than imply one.
      this.estimate.set(null);
      this.estimateError.set(describeApiError(err));
    } finally {
      this.armed.set(true);
      this.checking.set(false);
    }
  }

  /** Step two: the money leaves here. */
  async start(): Promise<void> {
    if (this.starting() || this.busy() || !this.armed()) return;
    this.starting.set(true);
    this.startError.set('');
    try {
      const result = await this.api.startRun({ ...this.request(), config_slug: '' });
      this.disarm();
      this.status.set(`Lauf ${result.run_id} gestartet.`);
      this.warnings.set(result.warnings ?? []);
      this.started.emit(result.run_id);
    } catch (err) {
      this.startError.set(describeApiError(err));
    } finally {
      this.starting.set(false);
    }
  }

  disarm(): void {
    this.armed.set(false);
    this.estimate.set(null);
    this.estimateError.set('');
  }

  usd(value: number): string {
    return formatUsd(value);
  }

  count(value: number): string {
    return formatWhole(value);
  }

  private chosen(kind: 'persona' | 'intent') {
    return kind === 'persona' ? this.chosenPersonas : this.chosenIntents;
  }

  private request() {
    return {
      mode: this.mode(),
      persona_ids: [...this.chosenPersonas()],
      intent_ids: [...this.chosenIntents()],
      scenarios_per_combo: this.scenariosPerCombo(),
      turns_per_conv: this.turnsPerConv(),
    };
  }
}
