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
import type { RichSegment } from '@boerdi/ui';

import { AsyncData, describeApiError } from '../core/async-data';
import { EvalApi, type EvalConfig, type EvalEstimate, type EvalMode }
  from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

/** `StartRequest`/`EstimateRequest` bounds — mirrored, not guessed. */
const MIN_PER_COMBO = 1;
const MAX_PER_COMBO = 10;

/** Eingefroren war bis C1-d4c die Beschriftung, nicht nur die Kennung — der
 *  elfte Fall dieser Art. Jetzt trägt die Konstante das Paar aus Kennung und
 *  Schlüssel; der Text entsteht beim Rendern. */
const MODES: readonly { readonly value: EvalMode; readonly key: string }[] = [
  { value: 'both', key: 'evalStart.gen.mode.both' },
  { value: 'scenarios', key: 'evalStart.gen.mode.scenarios' },
  { value: 'conversations', key: 'evalStart.gen.mode.conversations' },
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
  imports: [AsyncStateComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-generative-start.component.html',
  styleUrl: './eval-generative-start.component.scss',
})
export class EvalGenerativeStartComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;
  protected readonly rich = this.lang.rich;

  private readonly api = inject(EvalApi);

  /** True while any run is in flight — the backend allows one and answers 409. */
  readonly busy = input(false);

  /** The id of the run that was just started, for the list to pick up. */
  readonly started = output<string>();

  readonly modes = MODES;
  readonly minPerCombo = MIN_PER_COMBO;
  readonly maxPerCombo = MAX_PER_COMBO;

  readonly config = new AsyncData<EvalConfig>(() => this.api.config(), this.t);

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

  readonly combosParts = computed<readonly RichSegment[]>(() =>
    this.lang.richPlural('evalStart.gen.combos', this.combos(), {
      count: this.fmt.whole(this.combos()),
    }));

  /**
   * Die Kostenzeile trägt VIER Anzahlen, jede mit eigener Mehrzahl (C1-d4c).
   *
   * Vier Wortgruppen statt einer Schlüssel-Matrix aus 2⁴ Sätzen: jede entsteht
   * für sich über `plural()` und wird eingesetzt. Die ZAHL wählt dabei die
   * Form, der FORMATIERTE Text füllt den Platzhalter — sonst verlöre ein
   * vierstelliger Wert seine Tausender-Trennung.
   */
  readonly costParts = computed<readonly RichSegment[]>(() => {
    const cost = this.estimate();
    if (!cost) return [];
    return this.rich('evalStart.gen.cost', {
      chat: this.phrase('evalStart.gen.chatCalls', cost.chat_calls),
      judge: this.phrase('evalStart.judgeCalls', cost.judge_calls),
      sim: this.phrase('evalStart.gen.simCalls', cost.simulator_calls),
      turns: this.phrase('evalStart.gen.ratedTurns', cost.total_turns),
    });
  });

  readonly bandParts = computed<readonly RichSegment[]>(() => {
    const cost = this.estimate();
    if (!cost) return [];
    return this.rich('evalStart.gen.band', {
      min: this.fmt.usd(cost.est_usd_min),
      max: this.fmt.usd(cost.est_usd_max),
      expected: this.fmt.usd(cost.est_usd),
    });
  });

  /** Der Fehlersatz des Backends wird eingesetzt, NACHDEM geteilt wurde — er
   *  kann also keine Auszeichnung erzeugen (die Zusage aus C1-d4b2). */
  readonly blindParts = computed<readonly RichSegment[]>(() =>
    this.lang.richPlural('evalStart.gen.blind', this.combos(), {
      error: this.estimateError(),
      count: this.fmt.whole(this.combos()),
    }));

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
      this.estimateError.set(describeApiError(err, this.t));
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
      this.status.set(this.t('evalStart.gen.started', { id: result.run_id }));
      this.warnings.set(result.warnings ?? []);
      this.started.emit(result.run_id);
    } catch (err) {
      this.startError.set(describeApiError(err, this.t));
    } finally {
      this.starting.set(false);
    }
  }

  disarm(): void {
    this.armed.set(false);
    this.estimate.set(null);
    this.estimateError.set('');
  }

  /** Eine gezählte Wortgruppe für die Kostenzeile. */
  private phrase(key: string, count: number): string {
    return this.lang.plural(key, count, { count: this.fmt.whole(count) });
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
