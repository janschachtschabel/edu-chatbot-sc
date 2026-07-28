/**
 * The log window (9-5c): 200 turns, filtered, with one turn open in detail.
 *
 * Controlled from the outside: the applied filters are an input and every change
 * is emitted, because the matrix and the diagnosis blocks drill into this panel.
 * Keeping a second copy of the filters here would let the fields and the list
 * disagree about what is being shown.
 *
 * The form applies the filters on submit rather than on each keystroke. ALT
 * rebuilt its `load()` callback from the three filter strings and ran it from an
 * effect, so every character fired five requests — four of them to endpoints
 * that accept nothing but the scope. A form also gets Enter-to-submit from the
 * platform and needs no debounce timer.
 *
 * Deleting arms an inline question first, like the sessions view; `confirm()` is
 * not used anywhere in this studio.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal, untracked,
} from '@angular/core';

import { AsyncData, describeApiError } from '../core/async-data';
import { formatDecimal, germanDateTime } from '../core/format';
import {
  QualityApi, type LogFilters, type QualityLog, type QualityScope,
} from '../core/quality-api.service';
import { AsyncStateComponent } from './async-state.component';
import { QualityLogDetailComponent } from './quality-log-detail.component';

/** Which destructive action is waiting for a confirmation. */
type Armed = { readonly kind: 'one'; readonly id: number } | { readonly kind: 'bulk' } | null;

@Component({
  selector: 'studio-quality-logs',
  imports: [AsyncStateComponent, QualityLogDetailComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-logs.component.html',
  styleUrl: './quality-logs.component.scss',
})
export class QualityLogsComponent {
  private readonly api = inject(QualityApi);

  readonly scope = input.required<QualityScope>();
  /** The filters in force. The form edits a draft and emits on submit. */
  readonly filters = input.required<LogFilters>();

  readonly filtersChange = output<LogFilters>();

  readonly draftPattern = signal('');
  readonly draftIntent = signal('');
  readonly draftSession = signal('');

  readonly selected = signal(0);
  readonly armed = signal<Armed>(null);
  readonly working = signal(false);
  readonly actionError = signal('');
  readonly status = signal('');

  readonly logs = new AsyncData<readonly QualityLog[]>(
    () => this.api.logs(this.scope(), this.filters()));

  readonly rows = computed(() => this.logs.value() ?? []);

  readonly hasFilter = computed(() => {
    const filters = this.filters();
    return Boolean(filters.patternId || filters.intentId || filters.sessionId);
  });

  readonly openLog = computed(() =>
    this.rows().find((row) => row.id === this.selected()) ?? null);

  /** Empty because nothing matched, or empty because nothing was ever logged. */
  readonly emptyText = computed(() => this.hasFilter()
    ? 'Kein Turn passt zu diesem Filter. Setze den Filter zurück oder suche weiter gefasst.'
    : 'Noch keine Turns aufgezeichnet. Sobald jemand mit dem Widget chattet, '
      + 'erscheinen die Turns hier.');

  readonly bulkQuestion = computed(() => {
    const filters = this.filters();
    if (!this.hasFilter()) {
      return 'ALLE Quality-Logs löschen — auch die, die dieser Filter gerade nicht zeigt?';
    }
    const parts = [
      filters.patternId && `Pattern ${filters.patternId}*`,
      filters.intentId && `Intent ${filters.intentId}*`,
      filters.sessionId && `Session ${filters.sessionId}`,
    ].filter(Boolean);
    return `Alle Turns löschen, die den Filter treffen (${parts.join(', ')})?`;
  });

  constructor() {
    effect(() => {
      this.scope();
      this.filters();
      untracked(() => {
        this.armed.set(null);
        void this.logs.reload();
      });
    });

    // A drill-in from the matrix has to show up in the fields too, or the list
    // looks arbitrarily short with no visible reason.
    effect(() => {
      const filters = this.filters();
      untracked(() => {
        this.draftPattern.set(filters.patternId ?? '');
        this.draftIntent.set(filters.intentId ?? '');
        this.draftSession.set(filters.sessionId ?? '');
      });
    });
  }

  reload(): void {
    void this.logs.reload();
  }

  apply(event: Event): void {
    event.preventDefault();
    this.status.set('');
    this.filtersChange.emit({
      patternId: this.draftPattern().trim() || undefined,
      intentId: this.draftIntent().trim() || undefined,
      sessionId: this.draftSession().trim() || undefined,
    });
  }

  reset(): void {
    this.status.set('');
    this.filtersChange.emit({});
  }

  select(id: number): void {
    this.selected.set(this.selected() === id ? 0 : id);
  }

  arm(armed: Armed): void {
    this.actionError.set('');
    this.status.set('');
    this.armed.set(armed);
  }

  disarm(): void {
    this.armed.set(null);
  }

  isArmed(id: number): boolean {
    const armed = this.armed();
    return armed?.kind === 'one' && armed.id === id;
  }

  async confirm(): Promise<void> {
    const armed = this.armed();
    if (!armed || this.working()) return;
    this.working.set(true);
    this.actionError.set('');
    try {
      if (armed.kind === 'one') {
        await this.api.deleteLog(armed.id);
        if (this.selected() === armed.id) this.selected.set(0);
        this.status.set(`Turn #${armed.id} gelöscht.`);
      } else {
        const { deleted } = await this.api.clearLogs(this.scope(), this.filters());
        this.selected.set(0);
        this.status.set(`${deleted} Turns gelöscht.`);
      }
      this.armed.set(null);
      await this.logs.reload();
    } catch (err) {
      // The list is left standing: a failed delete must not look like a success.
      this.actionError.set(describeApiError(err));
    } finally {
      this.working.set(false);
    }
  }

  when(iso: string): string {
    return germanDateTime(iso);
  }

  confidence(value: number): string {
    return formatDecimal(value);
  }
}
