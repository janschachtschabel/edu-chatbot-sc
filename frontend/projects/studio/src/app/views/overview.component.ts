/**
 * The studio's front page (9-5f / A5, port of ALT `HomeOverview.tsx` + the
 * `homeTab` split of `page.tsx:447-470`).
 *
 * ALT's home was two tabs — "Übersicht" and "Architektur & Referenz" — and the
 * view registry says the same thing ("Start, Architektur & Status"), which is why
 * the reference is a tab here and not a route of its own. It mounts on first
 * visit, like every other panel in 9-5.
 *
 * Three ALT behaviours are deliberately not ported:
 *
 *  - **No offline banner.** ALT took a `backendOnline` prop and painted a red
 *    card. In NEU the shell header polls `/health` and owns that state
 *    (`status-indicator.component.ts`); a second display could contradict it,
 *    and each panel here reports its own failure anyway.
 *  - **No swallowed failures.** ALT's four fetches sat in one
 *    `Promise.allSettled` whose rejections were dropped, so a broken endpoint
 *    looked like "no data" forever. Each read is its own `AsyncData` (9-5a rule)
 *    and the strip shows what failed.
 *  - **No quick-action row.** Of ALT's three buttons, two duplicated cards on
 *    this very page (Evaluation, Material-Formate) and the third opened the
 *    snapshot dialog, which is A6 and does not exist yet. It comes back with A6.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalRunSummary } from '../core/eval-api.service';
import { formatDecimal, formatWhole, germanDateTime, relativeGerman } from '../core/format';
import { OverviewApi, type HealthInfo } from '../core/overview-api.service';
import type { FactoryInfo, SnapshotRow } from '../core/snapshots-api.service';
import { ArchitectureReferenceComponent } from './architecture-reference.component';
import type { SignalElement } from './reference-catalogs';
import {
  LAYER_CARDS, OPS_CARDS, type ElementsPayload, type LayerCard, elementCounts, viewOf,
} from './overview-cards';
import { TabBarComponent, type TabDef } from './tab-bar.component';

const TABS: readonly TabDef[] = [
  { id: 'uebersicht', label: 'Übersicht' },
  { id: 'referenz', label: 'Architektur & Referenz' },
];

@Component({
  selector: 'studio-overview',
  imports: [TabBarComponent, RouterLink, ArchitectureReferenceComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './overview.component.html',
  styleUrl: './overview.component.scss',
})
export class OverviewComponent {
  private readonly api = inject(OverviewApi);
  private readonly evalApi = inject(EvalApi);

  readonly tabs = TABS;
  readonly active = signal(TABS[0].id);
  private readonly visited = signal<ReadonlySet<string>>(new Set([TABS[0].id]));
  readonly shows = computed(() => {
    const seen = this.visited();
    return (id: string): boolean => seen.has(id);
  });

  readonly layers = LAYER_CARDS;
  readonly ops = OPS_CARDS;

  readonly health = new AsyncData<HealthInfo>(() => this.api.health());
  readonly factory = new AsyncData<FactoryInfo>(() => this.api.factory());
  readonly snapshots = new AsyncData<readonly SnapshotRow[]>(() => this.api.snapshots());
  readonly elements = new AsyncData<ElementsPayload>(() => this.api.elements());
  readonly runs = new AsyncData<readonly EvalRunSummary[]>(() => this.evalApi.runs());

  private readonly reads = [this.health, this.factory, this.snapshots, this.elements, this.runs];

  /** The reference instant for every relative date on this page, refreshed with
   *  the data — recomputing it per tick would be motion without information. */
  private readonly loadedAt = signal(0);

  readonly loading = computed(() => this.reads.some((read) => read.loading()));

  /**
   * Distinct messages. With the backend down all five reads fail with the same
   * sentence, and "Backend nicht erreichbar." five times over is noise — besides,
   * identical strings would be identical `@for` track keys.
   */
  readonly errors = computed(() =>
    [...new Set(this.reads.map((read) => read.error()).filter((message) => message !== ''))]);

  readonly counts = computed(() => elementCounts(this.elements.value()));

  /** The same payload, for the reference tab's live signal table (A5-Rest). */
  readonly signals = computed<readonly SignalElement[]>(
    () => (this.elements.value()?.signals ?? []) as readonly SignalElement[]);

  /** The newest finished run. The backend writes `running`, `done` or `failed`
   *  only, and the list arrives newest-first. */
  readonly lastEval = computed<EvalRunSummary | null>(() =>
    (this.runs.value() ?? []).find((run) => run.status === 'done') ?? null);

  /** `/config/snapshots` excludes the factory row, so this is "the others". */
  readonly otherSnapshots = computed(() => this.snapshots.value()?.length ?? 0);

  /**
   * "1 weiterer Snapshot" / "3 weitere Snapshots". Hand-written because the
   * studio has no i18n layer (all German by project convention) and German needs
   * exactly two forms here; `Intl.PluralRules` would add a dependency on a rule
   * set for a case with one boundary.
   */
  snapshotLine(): string {
    const count = this.otherSnapshots();
    if (count === 0) return 'keine weiteren Snapshots';
    return count === 1 ? '1 weiterer Snapshot' : `${this.count(count)} weitere Snapshots`;
  }

  constructor() {
    void this.reload();
  }

  async reload(): Promise<void> {
    this.loadedAt.set(Date.now());
    await Promise.all(this.reads.map((read) => read.reload()));
  }

  select(id: string): void {
    this.active.set(id);
    if (!this.visited().has(id)) {
      this.visited.update((seen) => new Set(seen).add(id));
    }
  }

  label(slug: string): string {
    return viewOf(slug).label;
  }

  desc(slug: string): string {
    return viewOf(slug).desc;
  }

  primary(card: LayerCard): string {
    return card.primary(this.counts());
  }

  tags(card: LayerCard): readonly string[] {
    return card.tags(this.counts());
  }

  /** "vor 3 Stunden" — '' when there is no timestamp to describe. */
  ago(iso: string | null | undefined): string {
    return iso ? relativeGerman(iso, this.loadedAt()) : '';
  }

  /** The exact date beside the relative one: a tooltip-only value is unreachable
   *  for keyboard and screen-reader users. */
  exact(iso: string | null | undefined): string {
    return iso ? germanDateTime(iso) : '';
  }

  score(value: number | null | undefined): string {
    return typeof value === 'number' ? formatDecimal(value) : '—';
  }

  count(value: number | null | undefined): string {
    return formatWhole(value ?? 0);
  }
}
