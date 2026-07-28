/**
 * One writing action the studio runs on demand: which one is in flight, and what
 * it reported (9-6 / A6). The write-side twin of `AsyncData` (9-5a).
 *
 * `busyKey` is the action's own name rather than a boolean, because a panel with
 * several buttons must disable all of them while showing progress on exactly the
 * one that was pressed — a shared boolean makes every button say "…".
 *
 * The result is ONE signal, not an `ok`/`error` pair: a state where both are set
 * is not representable, so no template can render a success line above the
 * failure that replaced it.
 */
import { computed, signal } from '@angular/core';

import { describeApiError } from './async-data';

export interface ActionMessage {
  readonly kind: 'ok' | 'error';
  /** German, from the backend where it wrote one. Safe to render as text. */
  readonly text: string;
}

export class ActionState {
  private readonly running = signal('');
  private readonly last = signal<ActionMessage | null>(null);

  readonly busyKey = this.running.asReadonly();
  readonly message = this.last.asReadonly();
  readonly busy = computed(() => this.running() !== '');

  isRunning(key: string): boolean {
    return this.running() === key;
  }

  /** Runs `work`, shows what it returned, and answers whether it succeeded. */
  async run(key: string, work: () => Promise<string>): Promise<boolean> {
    this.running.set(key);
    this.last.set(null);
    try {
      this.last.set({ kind: 'ok', text: await work() });
      return true;
    } catch (err) {
      this.last.set({ kind: 'error', text: describeApiError(err) });
      return false;
    } finally {
      this.running.set('');
    }
  }
}
