/**
 * The Analyse view (9-5c): four panels over the quality log, one scope switch.
 *
 * Owns two things and nothing else: which scope is in force, and which filters
 * the log panel is showing. Both are shared state — the scope applies to every
 * panel, and a drill-down from the matrix or the diagnosis blocks has to arrive
 * at the log panel — so neither can live inside a panel.
 *
 * A panel's element is always in the DOM (`aria-controls` on a tab must resolve
 * to something) but its content is created on first visit and then kept. ALT was
 * lazy in the same way, yet re-ran the query on every switch back, because its
 * effect depended on the active tab.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';

import type { Engine } from '../core/effects-api.service';
import type { LogFilters, QualityScope } from '../core/quality-api.service';
import { StudioAnsicht } from '../core/studio-ansicht.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { QualityFlowComponent } from './quality-flow.component';
import { QualityLogsComponent } from './quality-logs.component';
import { QualityMatrixComponent } from './quality-matrix.component';
import { QualityOverviewComponent } from './quality-overview.component';
import { OriginScopeComponent } from './origin-scope.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';

/** The tab ids are also the panel ids: `#tab-x` controls `#panel-x`. */
/** Paket 13 (E5): Matrix (Persona × Intent → Muster) und Flow (Zustände) gibt es nur in der
 *  Muster-Maschine — die Agent-Schleife wählt kein Muster und führt keinen Zustand. */
const TABS: readonly { readonly id: string; readonly labelKey: string;
  readonly engines?: readonly Engine[] }[] = [
  { id: 'uebersicht', labelKey: 'qual.tab.overview' },
  { id: 'matrix', labelKey: 'qual.tab.matrix', engines: ['pattern'] },
  { id: 'flow', labelKey: 'qual.tab.flow', engines: ['pattern'] },
  { id: 'logs', labelKey: 'qual.tab.logs' },
];

@Component({
  selector: 'studio-quality',
  imports: [
    QualityFlowComponent, QualityLogsComponent, QualityMatrixComponent,
    QualityOverviewComponent, TabBarComponent, OriginScopeComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality.component.html',
  styleUrl: './quality.component.scss',
})
export class QualityComponent {
  protected readonly t = inject(StudioLanguageService).t;

  private readonly ansicht = inject(StudioAnsicht);

  readonly tabs = computed<readonly TabDef[]>(() => TABS
    .filter((tab) => this.ansicht.zeigt(tab.engines))
    .map((tab) => ({ id: tab.id, label: this.t(tab.labelKey) })));

  /** Die Maschine der Ansicht als Filter der Abfragen; „beide“ filtert nicht. */
  readonly engine = this.ansicht.maschine;
  readonly diagnose = computed(() => this.ansicht.zeigt(['pattern']));

  private readonly wanted = signal<string>(TABS[0].id);
  /** Fällt der offene Reiter mit der Ansicht weg, steht die Übersicht offen. */
  readonly active = computed(() => {
    const ids = this.tabs().map((tab) => tab.id);
    return ids.includes(this.wanted()) ? this.wanted() : ids[0];
  });
  readonly scope = signal<QualityScope>('all');
  readonly filters = signal<LogFilters>({});

  /** Panels that have been opened at least once, and therefore hold data. */
  private readonly visited = signal<ReadonlySet<string>>(new Set([TABS[0].id]));

  readonly shows = computed(() => {
    const visited = this.visited();
    return (id: string): boolean => visited.has(id);
  });

  select(id: string): void {
    this.wanted.set(id);
    if (!this.visited().has(id)) {
      this.visited.set(new Set([...this.visited(), id]));
    }
  }

  setScope(scope: QualityScope): void {
    this.scope.set(scope);
  }

  /**
   * "Show me the turns behind this row", from the matrix or a diagnosis block.
   * Switching to the log tab is part of the answer: applying a filter to a panel
   * nobody is looking at would look like nothing happened.
   */
  drill(filters: LogFilters): void {
    this.filters.set(filters);
    this.select('logs');
  }
}
