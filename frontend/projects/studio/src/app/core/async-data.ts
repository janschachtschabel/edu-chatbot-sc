/**
 * One read-only thing the studio fetches: its value, whether it is loading, and
 * why it last failed (9-5a).
 *
 * Written because the same twelve lines had been copied into four components by
 * the end of 9-4 — and the copies disagreed. Two of them dropped the last good
 * value on a failed refresh (an empty table reads as "there is nothing", not as
 * "the request failed"), and only two had the generation guard that keeps a slow
 * answer from overwriting a newer one. Both defects are pinned here instead.
 *
 * Deliberately NOT Angular's `resource()`: that reloads from a reactive request
 * signal, and these dashboards reload on an explicit "Aktualisieren" or after a
 * delete — the trigger is an event, not a changed input.
 */
import { computed, signal } from '@angular/core';

import { StudioApiError } from './studio-api-error';

export class AsyncData<T> {
  /** `null` until the first successful load — distinct from "loaded, but empty". */
  private readonly current = signal<T | null>(null);
  private readonly busy = signal(false);
  private readonly failure = signal('');

  readonly value = this.current.asReadonly();
  readonly loading = this.busy.asReadonly();
  readonly error = this.failure.asReadonly();

  /**
   * Something was loaded and it is an empty list. `false` before the first load,
   * because "nothing here yet" and "still fetching" are different sentences.
   */
  readonly isEmpty = computed(() => {
    const value = this.current();
    return Array.isArray(value) && value.length === 0;
  });

  private generation = 0;

  constructor(private readonly fetch: () => Promise<T>) {}

  async reload(): Promise<void> {
    const generation = ++this.generation;
    this.busy.set(true);
    try {
      const value = await this.fetch();
      if (generation !== this.generation) return;
      this.current.set(value);
      this.failure.set('');
    } catch (err) {
      if (generation !== this.generation) return;
      // The value is deliberately left standing: a failed refresh must not make
      // the page claim the data is gone.
      this.failure.set(describeApiError(err));
    } finally {
      if (generation === this.generation) this.busy.set(false);
    }
  }

}

/**
 * The backend's own sentence, or a German fallback.
 *
 * `StudioApiError.message` is the transport envelope ("HTTP 400 /pfad — …") and
 * must never reach the page; `detail` is what the endpoint wrote.
 */
export function describeApiError(err: unknown): string {
  if (!(err instanceof StudioApiError)) return 'Unerwarteter Fehler.';
  if (err.status === 0) return 'Backend nicht erreichbar.';
  return err.detail.trim() || 'Unbekannter Fehler.';
}
