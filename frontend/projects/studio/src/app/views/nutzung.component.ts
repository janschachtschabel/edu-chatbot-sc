/**
 * Nutzung (Paket 16, D3) — wer wann wie oft mit dem Chatbot spricht, unter „Auswertung“.
 *
 * Zeitraum und Herkunft wie auf der Kosten-Seite (dieselben Grenz-Helfer, derselbe Server-Check).
 * Beide Maschinen zusammen, nicht die des Arbeitsbereichs (Review D-1): sonst zeigte „Maschine“
 * immer 100 % einer Maschine, und Zielgruppe/Anliegen — nur aus Muster-Zügen — blieben im
 * Agent-Arbeitsbereich leer. Von oben: Züge und Sitzungen, je Tag, Wochentag × Stunde, Verteilungen. Jede
 * Grafik ist zugleich Tabelle — die Zahlen stehen als Text in den Zellen, die Tönung hebt nur
 * hervor (WCAG 1.4.1). Kleine Zellen nennt der Server nicht genau; hier heißen sie „<5“.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AsyncData } from '../core/async-data';
import {
  FACETTEN, type Facette, NutzungApi, type NutzungUeberblick, type NutzungWert,
} from '../core/nutzung-api.service';
import type { OriginScope } from '../core/origin-scope';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { dayEnd, dayStart, isoDay } from './costs.component';
import { OriginScopeComponent } from './origin-scope.component';

const DEFAULT_DAYS = 30;
const DAY_MS = 86_400_000;
const STUNDEN = Array.from({ length: 24 }, (_, i) => i);
const KLEIN_STUFE = 0.12;
/** Zielgruppe und Anliegen setzt die Agent-Schleife fest — sie zählen nur aus Muster-Zügen. */
const NUR_MUSTER: ReadonlySet<Facette> = new Set<Facette>(['persona', 'anliegen']);

@Component({
  imports: [AsyncStateComponent, OriginScopeComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './nutzung.component.html',
  styleUrl: './nutzung.component.scss',
})
export class NutzungComponent {
  protected readonly fmt = inject(StudioFormat);
  protected readonly t = inject(StudioLanguageService).t;
  private readonly api = inject(NutzungApi);

  readonly from = signal(isoDay(Date.now() - DEFAULT_DAYS * DAY_MS));
  readonly to = signal(isoDay(Date.now()));
  /** Anders als bei den Kosten „Betrieb“ zuerst: Eval- und Lasttest-Züge sind kein Besuch. */
  readonly scope = signal<OriginScope>('production');

  readonly stunden = STUNDEN;
  readonly facetten = FACETTEN;

  readonly daten = new AsyncData<NutzungUeberblick>(
    () => this.api.ueberblick(dayStart(this.from()), dayEnd(this.to()), this.scope()),
    this.t);

  readonly incomplete = computed(() => !this.from() || !this.to());
  readonly leer = computed(() =>
    !this.daten.loading() && !this.daten.error() && this.daten.value()?.zuege === 0);

  /** Höchster Wert im Raster und je Tag — Bezug der Tönung bzw. Balkenlänge. */
  readonly rasterMax = computed(() =>
    Math.max(1, ...(this.daten.value()?.raster ?? []).flat().map((n) => n ?? 0)));
  readonly tagMax = computed(() =>
    Math.max(1, ...(this.daten.value()?.tage ?? []).map((t) => t.sitzungen)));

  constructor() {
    this.reload();
  }

  reload(): void {
    if (this.incomplete()) return;
    void this.daten.reload();
  }

  setFrom(value: string): void {
    if (value === this.from()) return;
    this.from.set(value);
    this.reload();
  }

  setTo(value: string): void {
    if (value === this.to()) return;
    this.to.set(value);
    this.reload();
  }

  setScope(scope: OriginScope): void {
    if (scope === this.scope()) return;
    this.scope.set(scope);
    this.reload();
  }

  anzahl(n: number | null): string {
    return n === null
      ? this.t('nutzung.klein', { n: this.daten.value()?.klein_unter ?? 5 })
      : this.fmt.whole(n);
  }

  /** 0 bis 1 — eine kleine Zelle ist schwach getönt, nicht leer (Review D-3: sie stand bei
   *  lauter kleinen Zellen auf der dunkelsten Stufe). */
  stufe(n: number | null): number {
    if (n === 0) return 0;
    if (n === null) return KLEIN_STUFE;
    return Math.max(KLEIN_STUFE, n / this.rasterMax());
  }

  nurMuster(f: Facette): boolean {
    return NUR_MUSTER.has(f);
  }

  wert(f: Facette, eintrag: NutzungWert): string {
    if (eintrag.wert === '') return this.t('nutzung.ohneAngabe');
    if (f === 'maschine' && (eintrag.wert === 'pattern' || eintrag.wert === 'agent')) {
      return this.t(`effect.engine.${eintrag.wert}`);
    }
    return eintrag.wert;
  }
}
