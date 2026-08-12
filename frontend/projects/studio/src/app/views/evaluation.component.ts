/**
 * The evaluation dashboard (9-5d) — the shell that makes its panels reachable.
 *
 * Three tabs: the runs (list + both start forms + the per-run detail), the
 * cross-run trends, and the pattern usage. A panel mounts on its first visit and
 * then stays, so switching tabs does not re-fetch; each panel owns its own
 * `AsyncData` (9-5a rule: one per endpoint).
 *
 * Both start forms sit above the list rather than in a tab of their own: a run
 * takes minutes, and its only progress display is that list. The shell wires
 * them together — the list is what knows whether a run is in flight (the backend
 * allows one and answers 409), so `busy` is derived from it instead of each start
 * panel reading the same endpoint again.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal, viewChild,
} from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { EvalGenerativeStartComponent } from './eval-generative-start.component';
import { EvalGoldenStartComponent } from './eval-golden-start.component';
import { EvalPatternUsageComponent } from './eval-pattern-usage.component';
import { EvalRunDetailComponent } from './eval-run-detail.component';
import { EvalRunsComponent } from './eval-runs.component';
import { EvalTrendsComponent } from './eval-trends.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';

/**
 * Nur die Kennungen und ihre Schlüssel — die Beschriftungen entstehen erst beim
 * Rendern (C1-d4b). Standen sie hier fertig, fröre die Sprache ein, die beim
 * Laden des Moduls gerade galt.
 */
const TAB_KEYS: readonly { readonly id: string; readonly labelKey: string }[] = [
  { id: 'laeufe', labelKey: 'eval.tab.laeufe' },
  { id: 'trends', labelKey: 'eval.tab.trends' },
  { id: 'pattern', labelKey: 'eval.tab.pattern' },
];

@Component({
  selector: 'studio-evaluation',
  imports: [
    TabBarComponent, EvalRunsComponent, EvalTrendsComponent,
    EvalGenerativeStartComponent, EvalGoldenStartComponent, EvalRunDetailComponent,
    EvalPatternUsageComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './evaluation.component.html',
  styleUrl: './evaluation.component.scss',
})
export class EvaluationComponent {
  protected readonly t = inject(StudioLanguageService).t;

  readonly tabs = computed<readonly TabDef[]>(() =>
    TAB_KEYS.map((tab) => ({ id: tab.id, label: this.t(tab.labelKey) })));

  readonly active = signal(TAB_KEYS[0].id);

  private readonly runsPanel = viewChild(EvalRunsComponent);

  /** The run list polls while anything runs; that is the honest source. */
  readonly busy = computed(() => this.runsPanel()?.isPolling() ?? false);

  private readonly visited = signal<ReadonlySet<string>>(new Set([TAB_KEYS[0].id]));

  /** Whether a panel has been opened at least once and may stay mounted. */
  readonly shows = computed(() => {
    const seen = this.visited();
    return (id: string): boolean => seen.has(id);
  });

  select(id: string): void {
    this.active.set(id);
    if (!this.visited().has(id)) {
      this.visited.update((seen) => new Set(seen).add(id));
    }
  }

  /** A fresh run is missing from the list until it re-reads. */
  onStarted(): void {
    this.runsPanel()?.reload();
  }

  /** Which run the detail panel shows; '' = none. Owned here, because the list
   *  only ever names a run and the panel must survive the list re-reading. */
  readonly openRun = signal('');

  openDetail(id: string): void {
    this.openRun.update((current) => (current === id ? '' : id));
  }

  closeDetail(): void {
    this.openRun.set('');
  }
}
