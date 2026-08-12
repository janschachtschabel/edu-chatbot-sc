/**
 * Which pattern actually fired, for whom, how often (9-5d / A4).
 *
 * Reads `quality_logs`, so it works independently of the eval engine: it counts
 * real turns as well as eval turns, which is why the scope filter is the first
 * control. `scope=eval` is the only view that answers "what did my runs
 * exercise"; `production` answers "what do people actually hit".
 *
 * The two distributions reuse `QualityBarsComponent` from 9-5c rather than
 * drawing bars again — it already renders "a key with a number" as a real table
 * with the bar hidden from assistive technology.
 *
 * `since` is a native `<input type="date">`: the backend parses it with
 * `datetime.fromisoformat`, which accepts a bare date, so no datepicker
 * dependency and no format to explain.
 *
 * Zweisprachig seit C1-d4b3 (`catalogue/eval-pattern.ts`). Der Name der
 * Ansicht kommt aus `eval.tab.pattern` — der Reiter der Hülle sagt ihn schon,
 * und ein zweiter Eintrag mit demselben Wortlaut wäre eine Doppelung, die
 * `en.spec.ts` bauartbedingt nicht fände.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';
import type { RichSegment } from '@boerdi/ui';

import { AsyncData } from '../core/async-data';
import { EvalApi, type PatternUsage } from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { QualityBarsComponent } from './quality-bars.component';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

/** Eingefroren war bis C1-d4b3 die Beschriftung, nicht nur die Kennung — der
 *  neunte Fall dieser Art. Jetzt trägt die Konstante nur noch das Paar aus
 *  Kennung und Schlüssel; der Text entsteht beim Rendern. */
const SCOPES: readonly { readonly value: string; readonly key: string }[] = [
  { value: 'all', key: 'evalPattern.scope.all' },
  { value: 'eval', key: 'evalPattern.scope.eval' },
  { value: 'production', key: 'evalPattern.scope.production' },
];

/** `[{pattern_id, count}]` → the `Record` the shared bar table takes. */
function distribution(
  rows: readonly Record<string, unknown>[] | undefined, idKey: string,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows ?? []) {
    const id = typeof row[idKey] === 'string' ? (row[idKey] as string) : '';
    const count = typeof row['count'] === 'number' ? row['count'] : 0;
    out[id] = (out[id] ?? 0) + count;
  }
  return out;
}

@Component({
  selector: 'studio-eval-pattern-usage',
  imports: [AsyncStateComponent, QualityBarsComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-pattern-usage.component.html',
  styleUrl: './eval-pattern-usage.component.scss',
})
export class EvalPatternUsageComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly rich = this.lang.rich;

  private readonly api = inject(EvalApi);

  readonly scopes = SCOPES;
  readonly scope = signal('all');
  readonly since = signal('');

  readonly usage = new AsyncData<PatternUsage>(
    () => this.api.patternUsage(this.scope(), this.since()), this.t);

  readonly value = computed(() => this.usage.value());
  readonly triples = computed(() => this.value()?.triples ?? []);

  readonly byPattern = computed(() =>
    distribution(this.value()?.by_pattern as readonly Record<string, unknown>[] | undefined,
                 'pattern_id'));
  readonly byIntent = computed(() =>
    distribution(this.value()?.by_intent as readonly Record<string, unknown>[] | undefined,
                 'intent_id'));

  readonly isEmpty = computed(() =>
    !this.usage.loading() && !this.usage.error() && this.triples().length === 0);

  /**
   * Die Summenzeile als EIN Satz — mit zwei Anzahlen, die jede ihre eigene
   * Mehrzahl haben. Die innere Wortgruppe entsteht deshalb zuerst und wird
   * eingesetzt; `richPlural` wählt die äussere Form und teilt den rohen
   * Katalog-Text, bevor irgendetwas eingesetzt wird.
   *
   * Beide Male wählt die ZAHL die Form und der FORMATIERTE Text füllt den
   * Platzhalter (`count` überschreibt die Voreinstellung) — sonst verlöre die
   * Zeile ihre Tausender-Trennung. Dasselbe Muster wie `overview.snapshots`.
   */
  readonly totalParts = computed<readonly RichSegment[]>(() => {
    const combos = this.triples().length;
    const turns = this.value()?.total ?? 0;
    return this.lang.richPlural('evalPattern.total', turns, {
      count: this.count(turns),
      combos: this.lang.plural('evalPattern.combos', combos, {
        count: this.count(combos),
      }),
    });
  });

  constructor() {
    void this.usage.reload();
  }

  reload(): void {
    void this.usage.reload();
  }

  setScope(value: string): void {
    if (value === this.scope()) return;
    this.scope.set(value);
    this.reload();
  }

  setSince(value: string): void {
    if (value === this.since()) return;
    this.since.set(value);
    this.reload();
  }

  /** An empty id is an unclassified turn — a blank cell reads as a bug.
   *  Derselbe Text wie in `quality-bars.component.ts`; seit C1-d4b3 EIN
   *  Katalog-Eintrag statt zweier wörtlicher Kopien. */
  id(value: string | undefined): string {
    return value || this.t('label.unclassified');
  }

  count(value: number): string {
    return this.fmt.whole(value);
  }

  /** `null` means no turn carried a confidence, which is not the same as 0. */
  confidence(value: number | null | undefined): string {
    return value === null || value === undefined ? '–' : this.fmt.decimal(value);
  }
}
