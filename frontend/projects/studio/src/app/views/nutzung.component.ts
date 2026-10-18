/**
 * Nutzung (Paket 16, D3) — wer wann wie oft mit dem Chatbot spricht, unter „Auswertung“.
 *
 * Zeitraum und Herkunft wie auf der Kosten-Seite (dieselben Grenz-Helfer, derselbe Server-Check).
 * Beide Maschinen zusammen, nicht die des Arbeitsbereichs (Review D-1): sonst zeigte „Maschine“
 * immer 100 % einer Maschine, und Zielgruppe/Anliegen — nur aus Muster-Zügen — blieben im
 * Agent-Arbeitsbereich leer. Von oben: Züge und Sitzungen, je Tag, Wochentag × Stunde, Verteilungen. Jede
 * Grafik ist zugleich Tabelle — die Zahlen stehen als Text in den Zellen, die Tönung hebt nur
 * hervor (WCAG 1.4.1). Seit dem Studio-Rundgang 2026-10-18 genau, ohne „<5“; die Tönung folgt
 * Stufen aus den vorkommenden Zahlen (`nutzung-stufen.ts`), die Legende nennt die Bereiche.
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
import { type NutzungStufe, nutzungStufen, stufeVon } from './nutzung-stufen';
import { OriginScopeComponent } from './origin-scope.component';

const DEFAULT_DAYS = 30;
const DAY_MS = 86_400_000;
const STUNDEN = Array.from({ length: 24 }, (_, i) => i);
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

  /** Farbstufen aus den Zahlen des Rasters — Tönung der Zellen und Legende. */
  readonly stufen = computed(() => nutzungStufen((this.daten.value()?.raster ?? []).flat()));
  /** Höchste Sitzungszahl eines Tages — Bezug der Balkenlänge. */
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

  /** Die Stufe einer Rasterzelle (0 = keine Züge) — als Attribut für die Tönung. */
  stufe(n: number): number {
    return stufeVon(n, this.stufen());
  }

  /** Deckkraft der Tönung, 0 bis 1: die höchste Stufe am dunkelsten. */
  anteil(n: number): number {
    const zahl = this.stufen().length;
    return zahl ? this.stufe(n) / zahl : 0;
  }

  legende(s: NutzungStufe): string {
    if (s.bis === null) return this.t('nutzung.legende.ab', { von: this.fmt.whole(s.von) });
    if (s.bis === s.von) return this.fmt.whole(s.von);
    return this.t('nutzung.legende.bereich',
      { von: this.fmt.whole(s.von), bis: this.fmt.whole(s.bis) });
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
