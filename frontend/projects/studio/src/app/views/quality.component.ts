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

import type { LogFilters, QualityScope } from '../core/quality-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { QualityFlowComponent } from './quality-flow.component';
import { QualityLogsComponent } from './quality-logs.component';
import { QualityMatrixComponent } from './quality-matrix.component';
import { QualityOverviewComponent } from './quality-overview.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';

/** The tab ids are also the panel ids: `#tab-x` controls `#panel-x`. */
const TABS: readonly { readonly id: string; readonly labelKey: string }[] = [
  { id: 'uebersicht', labelKey: 'qual.tab.overview' },
  { id: 'matrix', labelKey: 'qual.tab.matrix' },
  { id: 'flow', labelKey: 'qual.tab.flow' },
  { id: 'logs', labelKey: 'qual.tab.logs' },
];

/** Ids and key names only: the wording is the catalogue's (C1-d4d1). */
const SCOPES: readonly { readonly id: QualityScope; readonly labelKey: string;
  readonly hintKey: string }[] = [
  { id: 'all', labelKey: 'qual.scope.all', hintKey: 'qual.scope.all.hint' },
  { id: 'production', labelKey: 'qual.scope.production', hintKey: 'qual.scope.production.hint' },
  { id: 'eval', labelKey: 'qual.scope.eval', hintKey: 'qual.scope.eval.hint' },
];

@Component({
  selector: 'studio-quality',
  imports: [
    QualityFlowComponent, QualityLogsComponent, QualityMatrixComponent,
    QualityOverviewComponent, TabBarComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality.component.html',
  styleUrl: './quality.component.scss',
})
export class QualityComponent {
  protected readonly t = inject(StudioLanguageService).t;

  readonly tabs = computed<readonly TabDef[]>(() =>
    TABS.map((tab) => ({ id: tab.id, label: this.t(tab.labelKey) })));

  readonly scopes = computed(() => SCOPES.map((scope) => ({
    id: scope.id, label: this.t(scope.labelKey), hint: this.t(scope.hintKey),
  })));

  readonly active = signal<string>(TABS[0].id);
  readonly scope = signal<QualityScope>('all');
  readonly filters = signal<LogFilters>({});

  /** Panels that have been opened at least once, and therefore hold data. */
  private readonly visited = signal<ReadonlySet<string>>(new Set([TABS[0].id]));

  readonly shows = computed(() => {
    const visited = this.visited();
    return (id: string): boolean => visited.has(id);
  });

  select(id: string): void {
    this.active.set(id);
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
