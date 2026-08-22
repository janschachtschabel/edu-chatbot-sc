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
import type { RichSegment } from '@boerdi/ui';

import { AsyncData, describeApiError } from '../core/async-data';
import {
  EvalApi, GOLDEN_ENGINES, type GoldenEngine, type GoldFlow,
} from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

@Component({
  selector: 'studio-eval-golden-start',
  imports: [AsyncStateComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-golden-start.component.html',
  styleUrl: './eval-golden-start.component.scss',
})
export class EvalGoldenStartComponent {
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
  readonly started = output<string>();

  readonly flowList = new AsyncData<readonly GoldFlow[]>(() => this.api.goldFlows(), this.t);
  readonly flows = computed<readonly GoldFlow[]>(() => this.flowList.value() ?? []);

  readonly judge = signal(false);

  /** GV5: eine Maschine je Lauf. "default" = keine Kopfzeile, der Lauf misst
   *  die Server-Vorgabe aus `engine.yaml`. */
  readonly engine = signal<GoldenEngine>('default');
  readonly engines = GOLDEN_ENGINES;

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

  /**
   * Die drei Wortgruppen, die Kostenzeile und Rückfrage teilen (C1-d4c).
   *
   * Jede trägt ihre eigene Mehrzahl — die Kostenzeile sagt „1 Chat-Anfrage in
   * 1 Flow" genauso richtig wie „7 Chat-Anfragen in 2 Flows"; bis hierher stand
   * dort `Flow(s)`. Die ZAHL wählt dabei die Form, der FORMATIERTE Text füllt
   * den Platzhalter, sonst verlöre ein vierstelliger Wert seine
   * Tausender-Trennung (dasselbe Muster wie `overview.snapshots`).
   */
  private readonly phrases = computed(() => {
    const turns = this.turns();
    const flows = this.selected().length;
    return {
      calls: this.lang.plural('evalStart.gold.calls', turns, { count: this.fmt.whole(turns) }),
      judgeCalls: this.lang.plural('evalStart.judgeCalls', turns, { count: this.fmt.whole(turns) }),
      flows: this.lang.plural('evalStart.gold.flows', flows, { count: this.fmt.whole(flows) }),
    };
  });

  /** Zwei ganze Sätze statt eines mit eingebautem `@if`: ein Nebensatz, den
   *  das Template ein- und ausblendet, ist kein übersetzbarer Satz. */
  readonly costParts = computed<readonly RichSegment[]>(() =>
    this.rich(
      this.judge() ? 'evalStart.gold.cost.judge' : 'evalStart.gold.cost.plain',
      this.phrases(),
    ));

  readonly confirmText = computed(() =>
    this.t(
      this.judge() ? 'evalStart.gold.confirm.judge' : 'evalStart.gold.confirm.plain',
      this.phrases(),
    ));

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

  /** Feedback 2026-08-22: „alles außer einem" (etwa GV-RED-1 abwählen)
   *  brauchte vorher N−1 Einzelklicks — leer hieß zwar alle, aber der erste
   *  Haken hieß NUR dieser. */
  selectAll(): void {
    this.chosen.set(new Set(this.flows().map((flow) => flow.id)));
    this.disarm();
  }

  clearSelection(): void {
    this.chosen.set(new Set());
    this.disarm();
  }

  setJudge(on: boolean): void {
    this.judge.set(on);
    this.disarm();
  }

  setEngine(engine: GoldenEngine): void {
    this.engine.set(engine);
    this.disarm();
  }

  engineLabel(engine: GoldenEngine): string {
    // Nur die Vorgabe braucht einen Namen — die drei Maschinen heißen im
    // Studio wie in der Konfig und der Kopfzeile (technische Werte).
    return engine === 'default' ? this.t('evalStart.gold.engine.default') : engine;
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
        engine: this.engine(),
      });
      this.armed.set(false);
      this.status.set(this.t('evalStart.gold.started', { id: result.run_id }));
      this.warnings.set(result.warnings ?? []);
      this.started.emit(result.run_id);
    } catch (err) {
      this.startError.set(describeApiError(err, this.t));
    } finally {
      this.starting.set(false);
    }
  }

  /** "4 Turns · P-LEH" — what this flow is going to exercise. v2 flows carry
   *  the Zielgruppe; `persona`/`intents` remain readable for stored v1 sets. */
  flowMeta(flow: GoldFlow): string {
    const parts = [this.lang.plural('evalStart.gold.turns', flow.turns?.length ?? 0)];
    const gruppe = flow.zielgruppe || flow.persona;
    if (gruppe) parts.push(gruppe);
    if (flow.intents?.length) parts.push(flow.intents.join(', '));
    return parts.join(' · ');
  }
}
