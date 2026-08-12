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

import type { Translate } from '../i18n/studio-language.service';
import { StudioApiError } from './studio-api-error';

export class AsyncData<T> {
  /** `null` until the first successful load — distinct from "loaded, but empty". */
  private readonly current = signal<T | null>(null);
  private readonly busy = signal(false);

  /**
   * Der ROHE Fehler, nicht sein Satz — in einer Hülle, weil `null` als
   * Geworfenes zulässig ist und „nichts fehlgeschlagen" davon unterscheidbar
   * bleiben muss.
   */
  private readonly failure = signal<{ readonly err: unknown } | null>(null);

  readonly value = this.current.asReadonly();
  readonly loading = this.busy.asReadonly();

  /**
   * Warum es zuletzt fehlschlug, in der Sprache, die JETZT gilt — `''`, wenn
   * nichts fehlschlug.
   *
   * Errechnet statt gemerkt (C1-d4a): stünde hier der fertige Satz, bliebe
   * nach einem Sprachwechsel die alte Sprache stehen, auf einer Seite, die
   * sonst vollständig gewechselt hat. `I18n.t` liest das Sprach-Signal im
   * Aufruf, also hängt diese Ableitung von selbst daran.
   */
  readonly error = computed(() => {
    const failed = this.failure();
    return failed ? describeApiError(failed.err, this.t) : '';
  });

  /**
   * Something was loaded and it is an empty list. `false` before the first load,
   * because "nothing here yet" and "still fetching" are different sentences.
   */
  readonly isEmpty = computed(() => {
    const value = this.current();
    return Array.isArray(value) && value.length === 0;
  });

  private generation = 0;

  /**
   * @param t Übersetzer für den Fehlersatz. Als Parameter und nicht per
   *   `inject()` geholt: das hier ist eine schlichte Klasse, die auch ausserhalb
   *   eines Injektor-Kontexts gebaut wird (die Tests tun genau das). Dieselbe
   *   Entscheidung wie bei `describeAreaError` (C1-d3a) und `describeRagError`
   *   (C1-d3c) — wer übersetzt, bekommt den Übersetzer gereicht.
   */
  constructor(private readonly fetch: () => Promise<T>, private readonly t: Translate) {}

  async reload(): Promise<void> {
    const generation = ++this.generation;
    this.busy.set(true);
    try {
      const value = await this.fetch();
      if (generation !== this.generation) return;
      this.current.set(value);
      this.failure.set(null);
    } catch (err) {
      if (generation !== this.generation) return;
      // The value is deliberately left standing: a failed refresh must not make
      // the page claim the data is gone.
      this.failure.set({ err });
    } finally {
      if (generation === this.generation) this.busy.set(false);
    }
  }

}

/**
 * The backend's own sentence, or one from the catalogue.
 *
 * `StudioApiError.message` is the transport envelope ("HTTP 400 /pfad — …") and
 * must never reach the page; `detail` is what the endpoint wrote.
 *
 * `detail` bleibt unübersetzt stehen: es ist der Satz des Endpunkts, nicht der
 * der Oberfläche, und die einzige konkrete Auskunft im Fehlerfall. Er wird
 * serverseitig übersetzt (C1-e), nicht hier ersetzt.
 */
export function describeApiError(err: unknown, t: Translate): string {
  if (!(err instanceof StudioApiError)) return t('error.unexpected');
  if (err.status === 0) return t('error.offline');
  return err.detail.trim() || t('error.unknown');
}
