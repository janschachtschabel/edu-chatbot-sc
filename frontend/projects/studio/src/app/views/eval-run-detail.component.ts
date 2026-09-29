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
 *
 * Fünf Sätze dieser Ansicht tragen Auszeichnung MITTEN im Satz. Sie stehen als
 * ganzer Satz im Katalog und werden über `lang.rich()` geteilt, gerendert von
 * `<studio-rich>` (C1-d4b2).
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, computed, effect,
  inject, input, output, signal, untracked, viewChild,
} from '@angular/core';
import type { RichSegment } from '@boerdi/ui';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalRunDetail } from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { engineLabel } from './engine-label';
import { EvalPatternPanelsComponent } from './eval-pattern-panels.component';
import { EvalRunProfileComponent } from './eval-run-profile.component';
import { evalStatusLabel } from './eval-status';
import {
  catLabel, flowGroups, hardCats, hardRate, type GoldMetrics, type GoldPerTurn,
} from './gold-scorecard';
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
  imports: [
    AsyncStateComponent, EvalPatternPanelsComponent, EvalRunProfileComponent, RichTextComponent,
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

  /** Which `flow·turn` row is open; '' = none. */
  readonly openTurn = signal('');

  /** The free-form run summary; each figure below reads one key of it. */
  private readonly summary = computed(
    () => (this.run()?.summary ?? {}) as Readonly<Record<string, unknown>>);

  readonly metrics = computed<GoldMetrics | null>(
    () => (this.summary()['golden_metrics'] as GoldMetrics | undefined) ?? null);

  readonly groups = computed(() => flowGroups(this.metrics()?.per_turn ?? []));

  /** Spalten der Turn-Tabelle aus den Kategorien DES Laufs (Review-Nachlauf
   *  2026-08-22): die Liste war hartkodiert v1 — ein v2-Lauf hatte keine
   *  Werkzeug-Soll-Spalte und zwei tote (Persona/Intent). ``hardCats`` liefert
   *  für gespeicherte v1-Läufe exakt die alte Liste. */
  readonly cats = computed(() => hardCats(this.metrics()));

  /** v1 hat Persona/Intent-Solls, v2 Register/Struktur — die Kompaktspalte
   *  zeigt, was der Lauf wirklich behauptet hat. */
  sollText(turn: GoldPerTurn): string {
    if (this.cats().includes('persona')) {
      return `${this.expected(turn, 'persona')}/${this.expected(turn, 'intent')}`;
    }
    return `${this.expected(turn, 'register')} · ${this.expected(turn, 'structure')}`;
  }

  istText(turn: GoldPerTurn): string {
    if (this.cats().includes('persona')) {
      return `${this.observed(turn, 'persona')}/${this.observed(turn, 'intent')}/`;
    }
    return `${this.observed(turn, 'register')} · `;
  }

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
    return this.botByTurn().get(key) || this.t('evalDetail.noBotText');
  }

  flowRate(flow: string): string {
    const { ok, total, rate } = hardRate(
      this.metrics()?.per_flow?.[flow], hardCats(this.metrics()));
    if (rate === null) return this.t('evalDetail.flowNothing');
    return this.t('evalDetail.flowRate', { rate: this.fmt.percent(rate, 0), ok, total });
  }

  /** `null` means the check was not asserted for this turn, not that it failed. */
  checkGlyph(value: boolean | null | undefined): string {
    return value === true ? '✓' : value === false ? '✗' : '–';
  }

  checkWord(value: boolean | null | undefined): string {
    if (value === true) return this.t('evalDetail.check.passed');
    return this.t(value === false ? 'evalDetail.check.failed' : 'evalDetail.check.skipped');
  }

  checkClass(value: boolean | null | undefined): string {
    return value === true ? 'erd-ok' : value === false ? 'erd-bad' : 'erd-none';
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

  observed(turn: GoldPerTurn, key: string): string {
    return this.field(turn.observed, key);
  }

  expected(turn: GoldPerTurn, key: string): string {
    return this.field(turn.expected, key);
  }

  /** Die geöffnete Zeile als EIN Satz: bis C1-d4b2 stand er als sechs
   *  Bruchstücke im Template, deren Reihenfolge der Übersetzung gehört. */
  turnDetail(turn: GoldPerTurn): readonly RichSegment[] {
    return this.rich('evalDetail.turnDetail', {
      mustOffer: this.expected(turn, 'must_offer'),
      sie: this.observed(turn, 'sie'),
      du: this.observed(turn, 'du'),
      cards: this.observed(turn, 'cards'),
      idocs: this.observed(turn, 'idocs'),
      qr: this.observed(turn, 'qr'),
    });
  }

  /** AG-5: die Skills, die der Zug geladen hat, als eine Zeile — leer, wenn
   *  keiner geladen wurde (dann steht die Zeile gar nicht erst da). */
  skills(turn: GoldPerTurn): string {
    const liste = turn.observed['skills'];
    return Array.isArray(liste)
      ? liste.filter((s): s is string => typeof s === 'string' && s !== '').join(', ')
      : '';
  }

  private field(source: Readonly<Record<string, unknown>>, key: string): string {
    const value = source[key];
    return value === undefined || value === null || value === '' ? '–' : String(value);
  }
}
