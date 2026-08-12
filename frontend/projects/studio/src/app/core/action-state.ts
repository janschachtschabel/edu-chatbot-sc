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

import type { Translate } from '../i18n/studio-language.service';
import { describeApiError } from './async-data';

export interface ActionMessage {
  readonly kind: 'ok' | 'error';
  /**
   * Fertiger Text in der Sprache, die beim Auslösen der Aktion galt — vom
   * Backend, wo es einen geschrieben hat, sonst aus dem Katalog. Sicher als
   * Text zu rendern.
   *
   * simplify: eine gemeldete Aktion übersetzt sich beim Sprachwechsel nicht
   * mit; sie bleibt in der Sprache stehen, in der sie ausgeführt wurde.
   * Bekannte Grenze, kein Versehen — die Meldung ist die Beschreibung eines
   * vergangenen Ereignisses, und die Sätze vom Backend liessen sich ohnehin
   * nicht nachübersetzen (C1-e). Wer sie mitziehen will, müsste hier
   * Schlüssel + Parameter halten statt des Textes.
   */
  readonly text: string;
}

export class ActionState {
  private readonly running = signal('');
  private readonly last = signal<ActionMessage | null>(null);

  readonly busyKey = this.running.asReadonly();
  readonly message = this.last.asReadonly();
  readonly busy = computed(() => this.running() !== '');

  /** @param t Übersetzer für den Fehlersatz — siehe `AsyncData`. */
  constructor(private readonly t: Translate) {}

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
      this.last.set({ kind: 'error', text: describeApiError(err, this.t) });
      return false;
    } finally {
      this.running.set('');
    }
  }
}
