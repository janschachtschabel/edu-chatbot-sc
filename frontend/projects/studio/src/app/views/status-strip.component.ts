/**
 * Die Statusleiste der Übersicht (Rundgang 3): mit welchem Modell das Backend antwortet, der
 * eigene Grundstand samt Snapshots und der letzte fertige Eval-Lauf. Aus `overview.component`
 * gelöst, damit beide Arbeitsbereiche denselben Status oben zeigen; `maschine` schränkt den
 * letzten Lauf auf eine Maschine ein.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, type OnInit, output, signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalRunSummary } from '../core/eval-api.service';
import { OverviewApi, type HealthInfo } from '../core/overview-api.service';
import type { FactoryInfo, SnapshotRow } from '../core/snapshots-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-status-strip',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './status-strip.component.html',
  styleUrl: './status-strip.component.scss',
})
export class StatusStripComponent implements OnInit {
  private readonly fmt = inject(StudioFormat);
  private readonly api = inject(OverviewApi);
  private readonly evalApi = inject(EvalApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  /** Der letzte Lauf nur dieser Maschine; `null` = jeder. */
  readonly maschine = input<'agent' | 'pattern' | null>(null);
  /** Fehler eines Lesens der Seite selbst — zusammen mit den eigenen nur einmal genannt. */
  readonly zusatzFehler = input('');
  /** „Aktualisieren“: die Seite lädt ihre eigenen Daten mit. */
  readonly neuLaden = output<void>();

  readonly health = new AsyncData<HealthInfo>(() => this.api.health(), this.t);
  readonly factory = new AsyncData<FactoryInfo>(() => this.api.factory(), this.t);
  readonly snapshots = new AsyncData<readonly SnapshotRow[]>(() => this.api.snapshots(), this.t);
  readonly runs = new AsyncData<readonly EvalRunSummary[]>(
    () => this.evalApi.runs(this.maschine() ?? undefined), this.t);

  private readonly reads = [this.health, this.factory, this.snapshots, this.runs];

  /** Bezugszeitpunkt aller relativen Angaben, mit den Daten erneuert. */
  private readonly loadedAt = signal(0);

  readonly loading = computed(() => this.reads.some((read) => read.loading()));

  /** Verschiedene Sätze nur einmal — bei totem Backend scheitern alle Lesungen gleich. */
  readonly errors = computed(() => [...new Set(
    [...this.reads.map((read) => read.error()), this.zusatzFehler()]
      .filter((message) => message !== ''))]);

  /** Der jüngste fertige Lauf; die Liste kommt neueste zuerst. */
  readonly lastEval = computed<EvalRunSummary | null>(() =>
    (this.runs.value() ?? []).find((run) => run.status === 'done') ?? null);

  readonly otherSnapshots = computed(() => this.snapshots.value()?.length ?? 0);

  snapshotLine(): string {
    const count = this.otherSnapshots();
    if (count === 0) return this.t('overview.snapshots.zero');
    return this.lang.plural('overview.snapshots', count, { count: this.count(count) });
  }

  /** Erst hier: im Konstruktor ist `maschine` noch nicht gesetzt — die Leiste fragte nach jedem Lauf. */
  ngOnInit(): void {
    void this.laden();
  }

  /** „Aktualisieren“: die Seite lädt ihre eigenen Daten mit — beim ersten Laden tut sie es selbst. */
  async reload(): Promise<void> {
    this.neuLaden.emit();
    await this.laden();
  }

  private async laden(): Promise<void> {
    this.loadedAt.set(Date.now());
    await Promise.all(this.reads.map((read) => read.reload()));
  }

  ago(iso: string | null | undefined): string {
    return iso ? this.fmt.relative(iso, this.loadedAt()) : '';
  }

  exact(iso: string | null | undefined): string {
    return iso ? this.fmt.dateTime(iso) : '';
  }

  score(value: number | null | undefined): string {
    return typeof value === 'number' ? this.fmt.decimal(value) : '—';
  }

  count(value: number | null | undefined): string {
    return this.fmt.whole(value ?? 0);
  }
}
