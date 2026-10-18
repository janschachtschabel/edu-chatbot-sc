/**
 * One load-test run: the verdict, the latency curve and the stage table (9-5e).
 *
 * While the run is in flight this re-reads it. Two differences to ALT, both
 * about not lying while waiting:
 *  - a `setTimeout` chain instead of `setInterval`, so a slow answer cannot
 *    stack a second request on top of the first;
 *  - a failed poll surfaces (via `AsyncData`) while the last good state stays
 *    on screen. ALT caught poll errors with an empty block, so a backend that
 *    died mid-run left the page saying "läuft" forever.
 */
import {
  ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, output,
  signal, untracked,
} from '@angular/core';
import type { RichSegment } from '@boerdi/ui';

import { AsyncData, describeApiError } from '../core/async-data';
import {
  type LoadAnfrage, LoadtestApi, type LoadTestRun, type ZeitKategorie,
} from '../core/loadtest-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { latencyChart } from './loadtest-chart';
import { LtEngstelleComponent } from './lt-engstelle.component';
import { loadtestStatusLabel } from './loadtest-status';
import { RichTextComponent } from './rich-text.component';
import { StudioFormat } from '../i18n/studio-format.service';

/** ALT's cadence. A stage takes seconds, so a faster poll only adds load. */
const POLL_MS = 2000;

@Component({
  selector: 'studio-loadtest-run',
  imports: [AsyncStateComponent, LtEngstelleComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './loadtest-run.component.html',
  styleUrl: './loadtest-run.component.scss',
})
export class LoadtestRunComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;
  /** Zwei ausgezeichnete Sätze: das Urteil und der Hinweis auf den Prozess. */
  protected readonly rich = this.lang.rich;

  private readonly api = inject(LoadtestApi);

  readonly runId = input.required<string>();
  /** Raised once when a watched run stops running, so the list can re-read. */
  readonly finished = output<void>();

  readonly run = new AsyncData<LoadTestRun>(() => this.api.run(this.runId()), this.t);
  readonly value = computed(() => this.run.value());
  readonly isRunning = computed(() => this.value()?.status === 'running');

  readonly chart = computed(() => {
    const run = this.value();
    return run && run.stages.length > 0
      ? latencyChart(run.stages, run.profile.p95_threshold_s)
      : null;
  });

  /** Die Notbremse auch hier, nicht nur in der Liste (Prod-Befund 3,
   *  2026-08-22): wer einen Lauf beobachtet, sieht an dieser Stelle zuerst,
   *  dass er aus dem Ruder läuft — und soll ihn dort anhalten können, wo er
   *  ihn liest. Der Teilstand bleibt; die gemessenen Stufen sind Messwert. */
  readonly armed = signal(false);
  readonly working = signal(false);
  readonly stopError = signal('');

  private timer: ReturnType<typeof setTimeout> | null = null;
  /** Set on destroy: a request still in flight must not re-arm the poll —
   *  `stopPolling()` found no timer then (Audit 2026-09-29). */
  private destroyed = false;

  constructor() {
    effect(() => {
      this.runId();
      untracked(() => void this.load());
    });
    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      this.stopPolling();
    });
  }

  async load(): Promise<void> {
    await this.run.reload();
    this.scheduleNextPoll();
  }

  private scheduleNextPoll(): void {
    this.stopPolling();
    if (this.destroyed || !this.isRunning()) return;
    this.timer = setTimeout(() => void this.poll(), POLL_MS);
  }

  private async poll(): Promise<void> {
    this.timer = null;
    const wasRunning = this.isRunning();
    await this.run.reload();
    if (this.destroyed) return;
    if (wasRunning && !this.isRunning()) {
      this.finished.emit();
      return;
    }
    this.scheduleNextPoll();
  }

  private stopPolling(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  arm(): void {
    this.stopError.set('');
    this.armed.set(true);
  }

  disarm(): void {
    this.armed.set(false);
  }

  async confirmStop(): Promise<void> {
    if (this.working()) return;
    this.working.set(true);
    this.stopError.set('');
    try {
      await this.api.cancel(this.runId());
      this.armed.set(false);
      // Neu lesen statt raten: die Antwort des Stopps sagt nichts über die
      // Stufen, und die Zeile trägt danach ihren Endstand.
      await this.load();
      this.finished.emit();
    } catch (err) {
      this.stopError.set(describeApiError(err, this.t));
    } finally {
      this.working.set(false);
    }
  }

  statusLabel(status: string): string {
    return loadtestStatusLabel(status, this.t);
  }

  /** Das Urteil — die Anzahl wählt die FORM, nicht nur das Substantiv:
   *  „bis 1 gleichzeitigen Nutzer" gegen „bis 4 gleichzeitige Nutzer". */
  stableParts(count: number, threshold: number): readonly RichSegment[] {
    return this.lang.richPlural('ltRun.stable', count, { threshold });
  }

  /** Zwei Anzahlen in einem Satz — zwei Wortgruppen statt vier Sätzen. */
  totals(requests: number, errors: number): string {
    return this.t('ltRun.totals', {
      requests: this.lang.plural('lt.requests', requests),
      errors: this.lang.plural('lt.errors', errors),
    });
  }

  peaks(rss: number, cpu: number, samples: number): string {
    return this.t('ltRun.peaks', {
      rss: this.fmt.decimal(rss),
      cpu: this.fmt.decimal(cpu),
      samples: this.lang.plural('lt.samples', samples),
    });
  }

  /** Zugänglicher Name des Diagramms; die Stufenzahl beugt mit. */
  chartAlt(stages: number): string {
    return this.t('ltRun.chart.alt', { stages: this.lang.plural('lt.stageCount', stages) });
  }

  profileLine(profile: LoadTestRun['profile']): string {
    const zeile = this.t('ltRun.profile', {
      stages: profile.stages.join(' → '),
      requests: this.lang.plural('lt.requests', profile.requests_per_stage),
      mix: this.mixLine(profile.mix),
      threshold: profile.p95_threshold_s,
    });
    // Review-Runde 2: „ohne Aufwärmen“ ist etwas anderes als ein Lauf von vor Paket 15.
    if (profile.warmup === undefined) return zeile;
    return `${zeile} · ${this.t(profile.warmup ? 'ltRun.profile.mitAufwaermen' : 'ltRun.profile.ohneAufwaermen')}`;
  }

  /** "wissen 3 · suche 2" — the weights as they were sent. */
  mixLine(mix: Readonly<Record<string, number>>): string {
    return Object.entries(mix).map(([key, weight]) => `${key} ${weight}`).join(' · ');
  }

  /** Per-category duration of one stage, for the last table column. Paket 15 (E1, Review #6):
   *  unter 20 erfolgreichen Messungen sagt ein p95 wenig — dann das echte Maximum samt n. Zahlen
   *  wie in der Karte daneben über `sekunden()` (Review-Runde 2). */
  byKindLine(byKind: Readonly<Record<string, { ok?: number; p95_s: number; max_s?: number }>>): string {
    return Object.entries(byKind).map(([kind, v]) => (
      // Ohne Erfolg schickt der Server 0,0 s — das läse sich wie die schnellste Art (Review PR #18).
      v.ok === 0 ? this.t('ltRun.byKind.keine', { kind })
      : v.max_s !== undefined && v.ok !== undefined && v.ok < 20
        ? this.t('ltRun.byKind.max', { kind, dauer: this.sekunden(v.max_s), n: v.ok })
        : this.t('ltRun.byKind.p95', { kind, dauer: this.sekunden(v.p95_s) }))).join(' · ');
  }

  sekunden(wert: number): string {
    return `${this.fmt.decimal(wert)} s`;
  }

  /** Paket 16 (D4): die Teile, die die Anfragen-Tabelle als Spalten führt — die übrigen
   *  stehen in der Engstelle darüber. */
  readonly anfrageTeile: readonly ZeitKategorie[] = ['llm', 'vorabsuche', 'rerank', 'rest'];

  /** Alle Anfragen aller Stufen, je mit ihrer Stufe (Parallelität) — einmal je Lauf-Stand
   *  gerechnet, nicht bei jedem Zeichnen (Review-Runde 2; der Lauf pollt alle 2 s). */
  readonly anfragenListe = computed<readonly { stufe: number; a: LoadAnfrage }[]>(() =>
    (this.run.value()?.stages ?? [])
      .flatMap((s) => (s.anfragen ?? []).map((a) => ({ stufe: s.concurrency, a }))));
}
