/**
 * Which runs are ticked for a comparison (ST-7c).
 *
 * Its own small class and not three more signals in the run list: the list
 * already owns filtering, polling and three kinds of delete. The selection
 * deliberately outlives the engine filter — the natural way to compare is to
 * tick the pattern runs, switch the filter, tick the agent runs.
 *
 * Insertion order is kept: within one engine it is the order of the repeats in
 * the comparison.
 */
import { computed, signal } from '@angular/core';

/** The server compares at most this many runs (`GET /eval/compare`). */
export const MAX_COMPARE = 20;

export class RunSelection {
  private readonly chosen = signal<ReadonlySet<string>>(new Set());

  readonly ids = computed(() => [...this.chosen()]);
  readonly count = computed(() => this.chosen().size);
  readonly full = computed(() => this.chosen().size >= MAX_COMPARE);

  has(id: string): boolean {
    return this.chosen().has(id);
  }

  /** Ticks or unticks; ticking stops at the server's limit, unticking never. */
  toggle(id: string): void {
    const next = new Set(this.chosen());
    if (next.has(id)) next.delete(id);
    else if (next.size < MAX_COMPARE) next.add(id);
    else return;
    this.chosen.set(next);
  }

  /** A deleted run cannot be compared any more. */
  remove(id: string): void {
    if (!this.chosen().has(id)) return;
    const next = new Set(this.chosen());
    next.delete(id);
    this.chosen.set(next);
  }

  clear(): void {
    this.chosen.set(new Set());
  }
}
