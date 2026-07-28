/**
 * One evaluation run in detail (9-5d / A1): the scorecard and the transcript.
 *
 * **No polling here, unlike the load-test detail.** This response carries the
 * full `conversations` blob — a 12-flow gold run is ~40 turns of text, a
 * generative run far more — and re-reading that every few seconds to watch a
 * progress line would move megabytes. The run LIST already polls and already
 * shows `current_activity`, so watching happens there; this panel says out loud
 * that it is a snapshot and offers "Aktualisieren".
 *
 * Two renderings, never both, so no conversation is shown twice:
 *  - with `summary.golden_metrics` (a gold run) the per-turn table carries the
 *    checks, and opening a turn reveals that turn's bot answer plus what was
 *    observed — the same place ALT put it;
 *  - without it (a generative run, or one that died early) the transcript is the
 *    only account of what happened, so it gets its own section.
 *
 * ALT defects not ported: the per-turn row was a `<tr onClick>` — the densest
 * information in the view, unreachable without a mouse (now a `<button>` in the
 * first cell with `aria-expanded`); and its rate colours (`#16a34a`/`#d97706`/
 * `#dc2626` on white ≈ 3.4 / 2.9 / 4.0∶1) miss AA for the small text they were
 * used on, so the checked `--st-*-text` trio carries them instead — the number
 * is always spelled out beside the colour anyway.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal,
  untracked,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalRunDetail } from '../core/eval-api.service';
import { formatDecimal, formatPercent, germanDateTime } from '../core/format';
import { AsyncStateComponent } from './async-state.component';
import {
  catLabel, flowGroups, hardRate, type GoldMetrics, type GoldPerTurn,
} from './gold-scorecard';

const STATUS_LABELS: Readonly<Record<string, string>> = {
  running: 'läuft', done: 'fertig', completed: 'fertig', failed: 'fehlgeschlagen',
};

const MODE_LABELS: Readonly<Record<string, string>> = {
  golden: 'Gold-Flows', generative: 'Generativ',
};

/** One turn of a persisted conversation, as much of it as this view reads. */
interface TranscriptTurn {
  readonly user?: string;
  readonly bot?: string;
  readonly error?: string;
  readonly judge?: { readonly total?: number; readonly notes?: string };
}

interface TranscriptConv {
  readonly flow_id?: string;
  readonly title?: string;
  readonly persona_id?: string;
  readonly intent_id?: string;
  readonly turns?: readonly TranscriptTurn[];
}

@Component({
  selector: 'studio-eval-run-detail',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-run-detail.component.html',
  styleUrl: './eval-run-detail.component.scss',
})
export class EvalRunDetailComponent {
  private readonly api = inject(EvalApi);

  readonly runId = input.required<string>();
  readonly dismiss = output<void>();

  readonly detail = new AsyncData<EvalRunDetail>(() => this.api.run(this.runId()));
  readonly run = computed(() => this.detail.value());

  /** Which `flow·turn` row is open; '' = none. */
  readonly openTurn = signal('');

  readonly metrics = computed<GoldMetrics | null>(() => {
    const summary = this.run()?.summary as Record<string, unknown> | undefined;
    const metrics = summary?.['golden_metrics'];
    return metrics ? (metrics as GoldMetrics) : null;
  });

  readonly groups = computed(() => flowGroups(this.metrics()?.per_turn ?? []));

  readonly conversations = computed<readonly TranscriptConv[]>(
    () => (this.run()?.conversations ?? []) as readonly TranscriptConv[]);

  readonly isRunning = computed(() => this.run()?.status === 'running');

  readonly activity = computed(() => {
    const summary = this.run()?.summary as Record<string, unknown> | undefined;
    const activity = summary?.['current_activity'];
    return typeof activity === 'string' ? activity : '';
  });

  /** Bot answers by `flow·turn`, for the row a reader opens. */
  private readonly botByTurn = computed(() => {
    const index = new Map<string, string>();
    for (const conv of this.conversations()) {
      const flow = conv.flow_id || conv.persona_id || '?';
      (conv.turns ?? []).forEach((turn, i) => {
        index.set(this.turnKey(flow, i + 1), turn.bot ?? '');
      });
    }
    return index;
  });

  constructor() {
    // The panel is reused for whichever run the list points at; without this the
    // previous run's scorecard would stay on screen under a new id.
    effect(() => {
      this.runId();
      untracked(() => {
        this.openTurn.set('');
        void this.detail.reload();
      });
    });
  }

  reload(): void {
    void this.detail.reload();
  }

  turnKey(flow: string, turn: number): string {
    return `${flow}·${turn}`;
  }

  toggleTurn(key: string): void {
    this.openTurn.update((current) => (current === key ? '' : key));
  }

  isOpen(key: string): boolean {
    return this.openTurn() === key;
  }

  botText(key: string): string {
    return this.botByTurn().get(key) || '(kein Antworttext gespeichert)';
  }

  flowRate(flow: string): string {
    const { ok, total, rate } = hardRate(this.metrics()?.per_flow?.[flow]);
    if (rate === null) return 'nichts geprüft';
    return `${formatPercent(rate, 0)} · ${ok}/${total} Checks`;
  }

  /** `null` means the check was not asserted for this turn, not that it failed. */
  checkGlyph(value: boolean | null | undefined): string {
    return value === true ? '✓' : value === false ? '✗' : '–';
  }

  checkWord(value: boolean | null | undefined): string {
    return value === true ? 'bestanden' : value === false ? 'nicht bestanden' : 'nicht geprüft';
  }

  checkClass(value: boolean | null | undefined): string {
    return value === true ? 'erd-ok' : value === false ? 'erd-bad' : 'erd-none';
  }

  label(category: string): string {
    return catLabel(category);
  }

  rate(value: number | null | undefined): string {
    return value === null || value === undefined ? '–' : formatPercent(value, 0);
  }

  score(value: number | null | undefined): string {
    return value === null || value === undefined ? '–' : formatDecimal(value);
  }

  when(iso: string | null): string {
    return iso ? germanDateTime(iso) : '–';
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }

  modeLabel(mode: string): string {
    return MODE_LABELS[mode] ?? mode;
  }

  observed(turn: GoldPerTurn, key: string): string {
    return this.field(turn.observed, key);
  }

  expected(turn: GoldPerTurn, key: string): string {
    return this.field(turn.expected, key);
  }

  private field(source: Readonly<Record<string, unknown>>, key: string): string {
    const value = source[key];
    return value === undefined || value === null || value === '' ? '–' : String(value);
  }
}
