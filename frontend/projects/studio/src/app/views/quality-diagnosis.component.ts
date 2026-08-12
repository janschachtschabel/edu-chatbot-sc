/**
 * The three "where is routing going wrong" breakdowns (9-5c).
 *
 * Each is its own read with its own state: they are separate endpoints and one
 * of them failing says nothing about the other two. ALT fetched all three in the
 * same `Promise.all` as the logs and the stats, on every keystroke in a filter
 * field — although none of the three accepts a pattern, intent or session
 * filter, so they could not have returned anything different.
 *
 * `<details>` rather than a hand-built accordion: the open/close semantics,
 * keyboard handling and screen-reader announcement come from the browser. ALT
 * kept an `openDetail` state that allowed exactly one open section, which is a
 * restriction with no reason behind it.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, output, untracked,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import {
  QualityApi, type Breakdown, type DegradationGroup, type EmptyEntityGroup,
  type LogFilters, type LowConfidence, type QualityScope,
} from '../core/quality-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

@Component({
  selector: 'studio-quality-diagnosis',
  imports: [AsyncStateComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-diagnosis.component.html',
  styleUrl: './quality-diagnosis.component.scss',
})
export class QualityDiagnosisComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;
  /** Der Hilfetext des ersten Blocks fuehrt einen Fachbegriff ein und nennt
   *  zwei Slot-Namen — Auszeichnung mitten im Satz. */
  protected readonly rich = this.lang.rich;

  private readonly api = inject(QualityApi);

  readonly scope = input.required<QualityScope>();

  /** Asks the view to show the matching turns; the shell owns the log filters. */
  readonly drill = output<LogFilters>();

  readonly degradations = new AsyncData<Breakdown<DegradationGroup>>(
    () => this.api.degradations(this.scope()), this.t);
  readonly emptyEntities = new AsyncData<Breakdown<EmptyEntityGroup>>(
    () => this.api.emptyEntities(this.scope()), this.t);
  readonly lowConfidence = new AsyncData<LowConfidence>(
    () => this.api.lowConfidence(this.scope()), this.t);

  readonly degradationGroups = computed(() => this.degradations.value()?.groups ?? []);
  readonly emptyEntityGroups = computed(() => this.emptyEntities.value()?.groups ?? []);
  readonly lowConfidenceTurns = computed(() => this.lowConfidence.value()?.turns ?? []);

  constructor() {
    effect(() => {
      this.scope();
      untracked(() => {
        void this.degradations.reload();
        void this.emptyEntities.reload();
        void this.lowConfidence.reload();
      });
    });
  }

  /** Called by the panel's own "Aktualisieren"; all three are one answer. */
  reload(): void {
    void this.degradations.reload();
    void this.emptyEntities.reload();
    void this.lowConfidence.reload();
  }

  confidence(value: number): string {
    return this.fmt.decimal(value);
  }

  /**
   * „12 Turns · 3 Muster" — ZWEI unabhängige Anzahlen in einer Zeile.
   *
   * Zwei Wortgruppen, in einen Satz eingesetzt, und keine Schlüssel-Matrix aus
   * vier Sätzen: die Formen sind unabhängig voneinander. Bis C1-d4d1 stand die
   * Mehrzahl fest im Template und gab schon auf Deutsch „1 Turns" aus.
   */
  counts(turns: number, groups: number): string {
    return this.t('qual.diag.counts', {
      turns: this.lang.plural('qual.diag.turns', turns),
      groups: this.lang.plural('qual.diag.groups', groups),
    });
  }

  /** „2 Turns unter 0,6" — eine Anzahl und die Schwelle, die sie schnitt. */
  lowCount(turns: number, threshold: number): string {
    return this.t('qual.diag.low.count', {
      turns: this.lang.plural('qual.diag.turns', turns),
      threshold: this.confidence(threshold),
    });
  }

  /**
   * Beschriftung beider Drilldown-Knöpfe. Ein leerer Bezeichner ist ein Turn
   * ohne Zuordnung; dann steht dort das Wort statt der Kennung.
   */
  drillLabel(id: string, fallbackKey: string): string {
    return this.t('qual.diag.drill', { id: id || this.t(fallbackKey) });
  }
}
