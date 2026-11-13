/**
 * Läufe vergleichen (ST-7c): die Tafel des K0-Berichts im Studio.
 *
 * Gerechnet wird im Backend (`GET /eval/compare`, dieselben Funktionen wie das
 * Messwerkzeug K0-1); hier werden Zahlen beschriftet, Warn-Codes zu Sätzen und
 * die Regel R2(a) zu einem Urteil. Welche Zahl in welche Zeile gehört, steht
 * rein und getestet in `compare-rows.ts`.
 *
 * Beim Öffnen und bei jeder neuen Auswahl springt der Fokus auf die
 * Überschrift: die Tafel erscheint unter der Liste, außer Sicht, und wer
 * „Gewählte vergleichen" drückt, will das Ergebnis lesen.
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, computed, effect,
  inject, input, output, untracked, viewChild,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { EvalApi } from '../core/eval-api.service';
import type {
  CompareCondition, CompareWarning, EngineComparison,
} from '../core/eval-profile';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { compareRows, engineColumns } from './compare-rows';
import { engineLabel } from './engine-label';
import { evalStatusLabel } from './eval-status';
import { EvalVergleichV2Component } from './eval-vergleich-v2.component';

/** Die Gründe der Regel sind feste Wörter des Backends — Erlaubnisliste, damit
 *  ein neues Wort roh erscheint statt als Schlüssel. */
const REASON_KEYS: Readonly<Record<string, string>> = {
  stabiler: 'evalCompare.reason.stabiler',
  billiger: 'evalCompare.reason.billiger',
  schneller: 'evalCompare.reason.schneller',
};

@Component({
  selector: 'studio-eval-compare',
  imports: [AsyncStateComponent, EvalVergleichV2Component],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-compare.component.html',
  styleUrl: './eval-compare.component.scss',
})
export class EvalCompareComponent {
  private readonly fmt = inject(StudioFormat);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  private readonly api = inject(EvalApi);
  private readonly injector = inject(Injector);

  readonly runIds = input.required<readonly string[]>();
  readonly dismiss = output<void>();

  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');

  readonly comparison = new AsyncData<EngineComparison>(
    () => this.api.compare(this.runIds()), this.t);
  readonly data = computed(() => this.comparison.value());

  readonly title = computed(() => this.lang.plural('evalCompare.title', this.runIds().length));

  readonly columns = computed(() => {
    const data = this.data();
    return data ? engineColumns(data.engines) : [];
  });

  readonly headers = computed(() => {
    const data = this.data();
    if (!data) return [];
    return this.columns().map((engine) => this.lang.plural(
      'evalCompare.col.engine', data.engines[engine].runs,
      { engine: engineLabel(engine, this.t) }));
  });

  readonly rows = computed(() => {
    const data = this.data();
    return data ? compareRows(data, this.columns(), this.fmt, this.t) : [];
  });

  readonly warnings = computed(() =>
    (this.data()?.warnings ?? []).map((warning) => this.warningText(warning)));

  readonly rule = computed(() => {
    const r2a = this.data()?.rules.R2a;
    if (!r2a) return this.t('evalCompare.r2a.missing');
    if (!r2a.erfuellt) return this.t('evalCompare.r2a.no');
    const reasons = r2a.gruende.map((g) => (REASON_KEYS[g] ? this.t(REASON_KEYS[g]) : g));
    return this.t('evalCompare.r2a.yes', { reasons: this.lang.list(reasons) });
  });

  readonly factors = computed(() => {
    const r2a = this.data()?.rules.R2a;
    if (!r2a) return '';
    const points = r2a.d_agreement === null ? null : Math.round(r2a.d_agreement * 100);
    const factor = (v: number | null): string => (v === null ? '–' : this.fmt.decimal(v));
    return this.t('evalCompare.r2a.factors', {
      agreement: points === null ? '–' : `${points > 0 ? '+' : ''}${this.fmt.whole(points)}`,
      cost: factor(r2a.kosten_faktor),
      p50: factor(r2a.p50_faktor),
    });
  });

  readonly conditions = computed(() =>
    (this.data()?.conditions ?? []).map((condition) => this.conditionText(condition)));

  constructor() {
    effect(() => {
      this.runIds();
      untracked(() => {
        void this.comparison.reload();
        afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
      });
    });
  }

  reload(): void {
    void this.comparison.reload();
  }

  private warningText(warning: CompareWarning): string {
    const key = `evalCompare.warn.${warning.code}`;
    if (!this.lang.has(key)) return warning.code;
    switch (warning.code) {
      case 'not_done':
        return this.t(key, { run: warning.run, status: evalStatusLabel(warning.status, this.t) });
      case 'not_found':
      case 'engine_unknown':
        return this.t(key, { run: warning.run });
      case 'price_missing':
        return this.t(key, { models: warning.models.join(', ') });
      case 'master_skill_off':
        return this.t(key, { runs: this.lang.list(warning.runs) });
      default:
        return this.t(key);
    }
  }

  private conditionText(condition: CompareCondition): string {
    const skill = condition.master_skill;
    const sha = skill.sha256 || '–';
    const skillText = skill.enabled === true ? this.t('evalCompare.skill.on', { sha })
      : skill.enabled === false ? this.t('evalCompare.skill.off', { sha })
        : this.t('evalCompare.skill.unknown');
    const limits = condition.agent_limits;
    const number = (v: unknown): string => (typeof v === 'number' ? this.fmt.whole(v) : '–');
    // R3-g: die Gruppen trennten die Läufe schon nach UI-Modulen — jetzt steht es auch im Text
    return this.t('evalCompare.condition', {
      runs: this.lang.list(condition.runs),
      provider: condition.provider || '–',
      model: condition.chat_model || '–',
      judge: condition.judge_model || '–',
      skill: skillText,
      limits: limits ? this.t('evalCompare.limits', {
        rounds: number(limits['max_iterations']),
        seconds: number(limits['deadline_s']),
        tokens: number(limits['token_budget']),
      }) : '–',
      module: this.moduleText(condition),
    });
  }

  /** Querschnitts-Review R1–R4, Befund 1: `ui_module_wirksam` ist ein Objekt (Backend
   *  `run_conditions._wirksame_module`), keine Liste. */
  private moduleText(condition: CompareCondition): string {
    const gemeldet = condition.ui_module;
    const wirksam = condition.ui_module_wirksam;
    if (gemeldet == null && wirksam == null) return '–';
    const liste = (namen: readonly string[]): string => namen.join(', ') || this.t('evalCompare.module.keine');
    if (wirksam?.fehler !== undefined) {
      return this.t('evalCompare.module.unbekannt', { module: liste(gemeldet ?? []) });
    }
    const module = wirksam?.module ?? gemeldet ?? [];
    const agentAus = new Set(wirksam?.agent_aus ?? []);
    const text = liste(module.map((n) => (agentAus.has(n) ? this.t('evalCompare.module.agentAus', { name: n }) : n)));
    const abweichend = gemeldet != null && (gemeldet.length !== module.length || gemeldet.some((n) => !module.includes(n)));
    return abweichend ? this.t('evalCompare.module.gemeldet', { module: text, gemeldet: liste(gemeldet) }) : text;
  }
}
