/**
 * The Safety-Logs dashboard (9-5b): what the safety pipeline decided, and why.
 *
 * ALT fetched the list and the numbers together with `Promise.all`, checked
 * `res.ok` and dropped anything else into `console.error` — so a broken /stats
 * left stale numbers on screen and a broken /logs read as "Keine Safety-Events
 * gefunden". Here they are two independent reads: each says for itself whether
 * it is loading, failed, or empty, and one failing never speaks for the other.
 *
 * The numbers deliberately do not follow the risk filter — /stats aggregates
 * the whole window server-side. That is stated in the interface instead of
 * being left for an editor to discover by disbelieving the totals.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { AsyncData } from '../core/async-data';
import { germanDateTime } from '../core/format';
import { SafetyApi, type RiskFilter, type SafetyLog, type SafetyStats }
  from '../core/safety-api.service';
import { AsyncStateComponent } from './async-state.component';
import { SafetyLogDetailComponent } from './safety-log-detail.component';
import { legalLabel, riskLabel } from './safety-labels';

const FILTERS: readonly RiskFilter[] = ['', 'medium', 'high'];

@Component({
  selector: 'studio-safety-logs',
  imports: [AsyncStateComponent, SafetyLogDetailComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './safety-logs.component.html',
  styleUrl: './safety-logs.component.scss',
})
export class SafetyLogsComponent {
  private readonly api = inject(SafetyApi);

  readonly filter = signal<RiskFilter>('');
  readonly logs = new AsyncData<readonly SafetyLog[]>(() => this.api.logs(this.filter()));
  readonly stats = new AsyncData<SafetyStats>(() => this.api.stats());

  readonly rows = computed<readonly SafetyLog[]>(() => this.logs.value() ?? []);

  private readonly selectedId = signal(0);
  /**
   * Derived from the current rows, not stored: when a filter change drops the
   * chosen event from the list, its detail panel has to go with it — a record
   * shown next to a list that no longer contains it invites the wrong reading.
   */
  readonly selected = computed<SafetyLog | null>(
    () => this.rows().find((row) => row.id === this.selectedId()) ?? null,
  );

  readonly legalRows = computed(() => {
    const byLegal = this.stats.value()?.by_legal ?? {};
    // `key` is carried along as the track identity: labels are what a reader
    // sees, but an unmapped key falls back to itself and two of those could
    // collide where the keys never do.
    return Object.entries(byLegal).map(([key, count]) => ({ key, label: legalLabel(key), count }));
  });

  /** Says what would be here — and, under a filter, that the filter may be why. */
  readonly emptyText = computed(() =>
    this.filter()
      ? 'Kein Event mit dieser Risikostufe im geladenen Fenster. Der Filter oben zeigt wieder alle.'
      : 'Noch keine Safety-Events. Hier steht jede Nachricht, die die Sicherheits-Pipeline '
        + 'geprüft und als auffällig eingestuft hat.');

  constructor() {
    this.reload();
  }

  reload(): void {
    void this.logs.reload();
    void this.stats.reload();
  }

  setFilter(value: string): void {
    this.filter.set(FILTERS.includes(value as RiskFilter) ? (value as RiskFilter) : '');
    // Only the list: /stats ignores the filter, so re-reading it would be a
    // round-trip that cannot change a single number on screen.
    void this.logs.reload();
  }

  select(id: number): void {
    this.selectedId.set(this.selectedId() === id ? 0 : id);
  }

  isSelected(id: number): boolean {
    return this.selectedId() === id;
  }

  riskLabel(level: string): string {
    return riskLabel(level);
  }

  /** The row's flags as one readable line, empty when the event carries none. */
  markers(log: SafetyLog): string {
    const parts = [...log.legal_flags.map(legalLabel)];
    if (log.rate_limited) parts.push('rate-limited');
    if (log.escalated) parts.push('an das LLM eskaliert');
    return parts.join(' · ');
  }

  formatTime(iso: string): string {
    return germanDateTime(iso);
  }
}
