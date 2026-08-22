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

/** Feedback 2026-08-22: AGENT/HYBRID sind keine Muster, sondern
 *  Maschinen-Marker in `quality_logs.pattern_id` — zwischen M01–M20
 *  einsortiert verfälschten sie das Bild. Der Filter läuft CLIENT-seitig
 *  über die Kombinationen (der Server aggregiert Betriebsart-blind). */
const ENGINES: readonly { readonly value: string; readonly key: string }[] = [
  { value: 'alle', key: 'evalPattern.engine.all' },
  { value: 'muster', key: 'evalPattern.engine.muster' },
  { value: 'agent', key: 'evalPattern.engine.agent' },
  { value: 'hybrid', key: 'evalPattern.engine.hybrid' },
];

/** Betriebsart eines `pattern_id`-Werts. Alles, was weder M-Nummer noch
 *  Maschinen-Marker ist (Direkt-Aktionen `ACTION:…`, unklassifiziert ``/NULL),
 *  erscheint nur unter „alle". Verglichen wird der KOPF-Token vor dem ersten
 *  Leerzeichen (verziert wie `M15 (Orientierung)` bleibt lesbar), und zwar
 *  EXAKT — ein Präfix-Vergleich sortierte „AGENTUR" als Agent ein
 *  (Review-Runde 3). */
function betriebsartOf(patternId: string | null | undefined): string {
  const kopf = (patternId ?? '').trim().toUpperCase().split(' ')[0] ?? '';
  if (/^M\d{2}$/.test(kopf)) return 'muster';
  if (kopf === 'AGENT') return 'agent';
  if (kopf === 'HYBRID') return 'hybrid';
  return 'sonst';
}

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

/** One `pattern_id × persona_id` pivot row. */
interface MatrixRow {
  readonly pattern: string;
  readonly cells: readonly number[];
  readonly total: number;
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

  readonly engines = ENGINES;
  /** Betriebsart-Filter — client-seitig, löst KEINEN neuen Request aus. */
  readonly engine = signal('alle');

  readonly usage = new AsyncData<PatternUsage>(
    () => this.api.patternUsage(this.scope(), this.since()), this.t);

  readonly value = computed(() => this.usage.value());
  readonly triples = computed(() => this.value()?.triples ?? []);

  /** Die Kombinationen der gewählten Betriebsart — Quelle ALLER Anzeigen
   *  unterhalb des Filters (Balken, Matrix, Tabelle, Summenzeile). */
  readonly filtered = computed(() => {
    const engine = this.engine();
    if (engine === 'alle') return this.triples();
    return this.triples().filter((triple) => betriebsartOf(triple.pattern_id) === engine);
  });

  // Beide Verteilungen aus den GEFILTERTEN Kombinationen statt aus den
  // Server-Aggregaten `by_pattern`/`by_intent` — die sind Betriebsart-blind
  // und könnten dem Filter nicht folgen. Bei „alle" sind die Summen identisch.
  readonly byPattern = computed(() =>
    distribution(this.filtered() as readonly Record<string, unknown>[], 'pattern_id'));
  readonly byIntent = computed(() =>
    distribution(this.filtered() as readonly Record<string, unknown>[], 'intent_id'));

  /** ALT-Auswertung (Feedback 2026-08-22): Pattern × Persona als Pivot —
   *  Zeilen und Spalten je nach Turn-Summe absteigend. */
  readonly matrix = computed<{ personas: readonly string[]; rows: readonly MatrixRow[] }>(() => {
    const perPattern = new Map<string, Map<string, number>>();
    const personaTotals = new Map<string, number>();
    for (const triple of this.filtered()) {
      const pattern = triple.pattern_id || '';
      const persona = triple.persona_id || '';
      const row = perPattern.get(pattern) ?? new Map<string, number>();
      row.set(persona, (row.get(persona) ?? 0) + triple.count);
      perPattern.set(pattern, row);
      personaTotals.set(persona, (personaTotals.get(persona) ?? 0) + triple.count);
    }
    const personas = [...personaTotals.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([id]) => id);
    const rows = [...perPattern.entries()]
      .map(([pattern, cells]) => ({
        pattern,
        cells: personas.map((persona) => cells.get(persona) ?? 0),
        total: [...cells.values()].reduce((sum, n) => sum + n, 0),
      }))
      .sort((a, b) => b.total - a.total);
    return { personas, rows };
  });

  readonly isEmpty = computed(() =>
    !this.usage.loading() && !this.usage.error() && this.triples().length === 0);

  /** Daten da, aber keine Turns dieser Betriebsart — sonst verschwänden die
   *  Tabellen kommentarlos. */
  readonly engineEmpty = computed(() =>
    this.triples().length > 0 && this.filtered().length === 0);

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
    // Aus den GEFILTERTEN Kombinationen, damit die Zeile zum Filter passt;
    // bei „alle" ist die Summe identisch mit dem Server-`total`.
    const combos = this.filtered().length;
    const turns = this.filtered().reduce((sum, triple) => sum + triple.count, 0);
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

  /** Client-seitig — im Gegensatz zu Scope/Datum ohne neuen Request. */
  setEngine(value: string): void {
    this.engine.set(value);
  }

  /** An empty id is an unclassified turn — a blank cell reads as a bug.
   *  Derselbe Text wie in `quality-bars.component.ts`; seit C1-d4b3 EIN
   *  Katalog-Eintrag statt zweier wörtlicher Kopien. */
  id(value: string | null | undefined): string {
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
