/**
 * One evaluation run in detail (9-5d / A1): the scorecard and the transcript.
 *
 * **No polling here, unlike the load-test detail.** This response carries the
 * full `conversations` blob — a 12-flow gold run is ~40 turns of text, a
 * generative run far more — and re-reading that every few seconds to watch a
 * progress line would move megabytes. The run LIST already polls and already
 * shows `current_activity`, so watching happens there; this panel says out loud
 * that it is a snapshot and offers a refresh.
 *
 * Two renderings, never both, so no conversation is shown twice:
 *  - with `summary.golden_metrics` (a gold run) the per-turn table carries the
 *    checks, and opening a turn reveals that turn's bot answer plus what was
 *    observed (`studio-eval-gold-turns`, seit Paket 6 eigene Komponente);
 *  - without it (a generative run, or one that died early) the transcript is the
 *    only account of what happened, so it gets its own section.
 *
 * Fünf Sätze dieser Ansicht tragen Auszeichnung MITTEN im Satz. Sie stehen als
 * ganzer Satz im Katalog und werden über `lang.rich()` geteilt, gerendert von
 * `<studio-rich>` (C1-d4b2).
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, computed, effect,
  inject, input, output, untracked, viewChild,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalRunDetail } from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { engineLabel } from './engine-label';
import { EvalGoldTurnsComponent } from './eval-gold-turns.component';
import { EvalPatternPanelsComponent } from './eval-pattern-panels.component';
import { EvalRunProfileComponent } from './eval-run-profile.component';
import { evalStatusLabel } from './eval-status';
import type { TranscriptConv } from './eval-transcript';
import { catLabel, type GoldMetrics } from './gold-scorecard';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

/**
 * Art des Laufs → Katalog-Schlüssel, wie bei den Status-Wörtern eine
 * Erlaubnisliste: eine dritte Art des Backends soll ihren rohen Wert zeigen,
 * nicht einen Schlüssel.
 */
const MODE_KEYS: Readonly<Record<string, string>> = {
  golden: 'evalDetail.mode.golden',
  generative: 'evalDetail.mode.generative',
};

/** A counter from the free-form summary; anything but a number counts as 0. */
function countAt(summary: Readonly<Record<string, unknown>>, key: string): number {
  const n = summary[key];
  return typeof n === 'number' ? n : 0;
}

@Component({
  selector: 'studio-eval-run-detail',
  imports: [
    AsyncStateComponent, EvalGoldTurnsComponent, EvalPatternPanelsComponent,
    EvalRunProfileComponent, RichTextComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-run-detail.component.html',
  styleUrl: './eval-run-detail.component.scss',
})
export class EvalRunDetailComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;

  /** Zerlegt einen Satz mit Auszeichnung in Stücke — siehe Klassen-Kommentar. */
  protected readonly rich = this.lang.rich;

  private readonly api = inject(EvalApi);

  readonly runId = input.required<string>();
  readonly dismiss = output<void>();

  private readonly injector = inject(Injector);
  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');

  readonly detail = new AsyncData<EvalRunDetail>(() => this.api.run(this.runId()), this.t);
  readonly run = computed(() => this.detail.value());

  /** The free-form run summary; each figure below reads one key of it. */
  private readonly summary = computed(
    () => (this.run()?.summary ?? {}) as Readonly<Record<string, unknown>>);

  readonly metrics = computed<GoldMetrics | null>(
    () => (this.summary()['golden_metrics'] as GoldMetrics | undefined) ?? null);

  /** ST-7a: die Maschine, die den Lauf beantwortet hat. Bis dahin stand hier
   *  die WAHL aus `summary.engine` — bei „Server-Vorgabe" also „default", ohne
   *  zu sagen, was gemessen wurde. Die Vorgabe bleibt als Zusatz sichtbar:
   *  ein generativer Lauf misst sie immer, ein Gold-Lauf, wenn er sie wählte. */
  readonly engine = computed(() => {
    const run = this.run();
    if (!run) return '';
    const label = engineLabel(run.engine, this.t);
    const vorgabe = run.mode === 'generative' || this.summary()['engine'] === 'default';
    return vorgabe ? this.t('evalDetail.engineDefault', { engine: label }) : label;
  });

  /** ST-7d: die Muster-Tafeln — nicht bei Agent-Läufen, dort gibt es weder
   *  Hinweis noch Musterwahl zu zeigen. */
  readonly classification = computed(() => {
    const cm = this.summary()['classification_metrics'];
    return this.run()?.engine !== 'agent' && cm && typeof cm === 'object'
      ? cm as Record<string, unknown> : null;
  });

  readonly agentRun = computed(() => this.run()?.engine === 'agent');

  /** GV4: judge outages are COUNTED, not averaged in as zeros. */
  readonly judgeFailed = computed(() => countAt(this.summary(), 'judge_failed_turns'));

  /** Review-Befund 4 (2026-08-22): Züge, die der Chat nie beantwortet hat —
   *  ohne den Zähler stand ein Lauf mit toten Zügen grün da. */
  readonly chatErrors = computed(() => countAt(this.summary(), 'chat_error_turns'));

  readonly conversations = computed<readonly TranscriptConv[]>(
    () => (this.run()?.conversations ?? []) as readonly TranscriptConv[]);

  readonly isRunning = computed(() => this.run()?.status === 'running');

  readonly activity = computed(() => {
    const activity = this.summary()['current_activity'];
    return typeof activity === 'string' ? activity : '';
  });

  constructor() {
    // The panel is reused for whichever run the list points at; without this the
    // previous run's scorecard would stay on screen under a new id.
    effect(() => {
      this.runId();
      untracked(() => {
        void this.detail.reload();
        // Nutzer-Befund 2026-09-27: das Detail steht unter der ganzen Liste —
        // bei 21 Läufen 3.000 px tiefer; ohne Sprung sah ein Klick aus, als
        // geschehe nichts. Der Fokus zieht die Überschrift ins Bild.
        afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
      });
    });
  }

  reload(): void {
    void this.detail.reload();
  }

  label(category: string): string {
    return catLabel(category, this.t);
  }

  rate(value: number | null | undefined): string {
    return value === null || value === undefined ? '–' : this.fmt.percent(value, 0);
  }

  score(value: number | null | undefined): string {
    return value === null || value === undefined ? '–' : this.fmt.decimal(value);
  }

  when(iso: string | null): string {
    return iso ? this.fmt.dateTime(iso) : '–';
  }

  statusLabel(status: string): string {
    return evalStatusLabel(status, this.t);
  }

  modeLabel(mode: string): string {
    const key = MODE_KEYS[mode];
    return key ? this.t(key) : mode;
  }
}
