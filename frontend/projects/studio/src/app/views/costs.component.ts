/**
 * Was der Betrieb kostet (K5): Zeitraum, Summenband, Betrag, zwei Tabellen.
 *
 * **Der Betrag ist der Anker der Seite** — alles andere erklärt ihn. Er kommt
 * als Zeichenkette vom Server (K4) und wird über `StudioFormat.money`
 * gerendert; ihn in eine Zahl zu wandeln würfe die `Decimal`-Rechnung auf dem
 * letzten Meter weg.
 *
 * **Neben dem Betrag steht immer, was er NICHT enthält.** `amount` deckt nur
 * die bepreisten Modelle; ohne die Lücke daneben läse sich eine Teilsumme als
 * Gesamtsumme. Das ist die ausdrückliche Auflage aus K4, keine Verzierung.
 *
 * **Vertauschte Grenzen prüft die Ansicht NICHT selbst.** Der Server weist sie
 * mit 422 und einem übersetzten Satz ab (C1-e); ihn hier zu wiederholen hiesse,
 * dieselbe Regel an zwei Stellen zu pflegen. Der Zustands-Streifen zeigt den
 * Satz des Endpunkts. Was die Ansicht sehr wohl verhindert, ist ein Abruf mit
 * leerer Grenze — daraus entstünde eine Fehlermeldung über einen Tippfehler,
 * den die Bedienung selbst sieht.
 *
 * `<input type="date">` statt eines Datumswählers: die Plattform bringt
 * Tastatur, Sprache und Format mit, eine Abhängigkeit brächte davon nichts
 * dazu. Dieselbe Entscheidung wie in `eval-pattern-usage.component.ts`.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { UsageApi, type UsageReport } from '../core/usage-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { RichTextComponent } from './rich-text.component';

/** Womit die Ansicht aufmacht: der zurückliegende Monat. */
const DEFAULT_DAYS = 30;

const DAY_MS = 86_400_000;

/**
 * Ein Zeitpunkt als Tagesangabe `JJJJ-MM-TT`, wie `<input type="date">` sie führt.
 *
 * Der Tag der **Bedienung**, nicht der UTC-Tag: `toISOString().slice(0, 10)`
 * zeigte in Berlin zwischen 00:00 und 02:00 Ortszeit gestern im Feld „Bis".
 */
export function isoDay(ms: number): string {
  const day = new Date(ms);
  return [
    day.getFullYear(),
    String(day.getMonth() + 1).padStart(2, '0'),
    String(day.getDate()).padStart(2, '0'),
  ].join('-');
}

/**
 * Der gewählte Tag als Zeitpunkt — Anfang bzw. **Ende**, in der Zeitzone der
 * Bedienung.
 *
 * Das Ende ist der erste Grund für dieses Paar: der Server liest ein blosses
 * Datum als Mitternacht, also fiele bei „bis heute" der ganze heutige Tag
 * heraus — stumm, denn eine kleinere Summe sieht aus wie eine kleinere Summe.
 * Für einen Menschen heisst „bis 11.08." einschliesslich des 11.08.
 *
 * Der zweite Grund ist dieselbe Falle eine Ebene tiefer, gemessen 2026-08-12:
 * ein angehängtes `Z` verschiebt die Grenze um den Zonen-Versatz. In Berlin
 * (+02:00) lag ein Zug um 00:30 Ortszeit **vor** dem Beginn seines eigenen
 * Tages und fiel aus dem Fenster, während das Fenster zwei Stunden in den
 * Folgetag hineinreichte. Beides lautlos. Die Grenze wird darum aus dem
 * ÖRTLICHEN Kalendertag gebaut; die Umrechnung nach UTC macht `toISOString`.
 *
 * Unlesbares kommt unverändert zurück statt als `RangeError`: der Server weist
 * es dann mit 422 ab und nennt den Parameter — sichtbar statt leerer Seite.
 * `<input type="date">` liefert die Form ohnehin, das ist der Rückfall für
 * Aufrufer ausserhalb dieser Ansicht.
 */
function localInstant(day: string, endOfDay: boolean): string {
  const [year = NaN, month = NaN, date = NaN] = day.split('-').map(Number);
  const moment = endOfDay
    ? new Date(year, month - 1, date, 23, 59, 59, 999)
    : new Date(year, month - 1, date);
  return Number.isNaN(moment.getTime()) ? day : moment.toISOString();
}

export function dayStart(day: string): string {
  return localInstant(day, false);
}

export function dayEnd(day: string): string {
  return localInstant(day, true);
}

@Component({
  selector: 'studio-costs',
  imports: [AsyncStateComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './costs.component.html',
  styleUrl: './costs.component.scss',
})
export class CostsComponent {
  private readonly fmt = inject(StudioFormat);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly rich = this.lang.rich;
  private readonly api = inject(UsageApi);

  readonly from = signal(isoDay(Date.now() - DEFAULT_DAYS * DAY_MS));
  readonly to = signal(isoDay(Date.now()));

  readonly report = new AsyncData<UsageReport>(
    () => this.api.period(dayStart(this.from()), dayEnd(this.to())), this.t);

  readonly value = computed(() => this.report.value());
  readonly models = computed(() => this.value()?.models ?? []);
  readonly sessions = computed(() => this.value()?.sessions ?? []);

  /** Eine geleerte Grenze ist kein Fehler, sondern ein unfertiges Formular. */
  readonly incomplete = computed(() => !this.from() || !this.to());

  readonly isEmpty = computed(() =>
    !this.report.loading() && !this.report.error() && this.value()?.empty === true);

  /** Der Betrag, oder ein Strich — nie eine erfundene Null. */
  readonly amount = computed(() => {
    const report = this.value();
    return !report || report.amount === null
      ? '—' : this.fmt.money(report.amount, report.currency);
  });

  /** Für KEIN Modell ist ein Preis gepflegt: der Strich braucht seinen Grund. */
  readonly withoutPrice = computed(() => this.value()?.amount === null);

  /**
   * Und zwar den RICHTIGEN Grund: „nichts gepflegt" und „Tafel unlesbar"
   * enden beide beim Strich, verlangen aber verschiedene Handgriffe. Ein
   * gemeinsamer Satz schickte die Redaktion beim Tippfehler ins Leere.
   */
  readonly noPriceReason = computed(() => (
    this.value()?.price_config_broken
      ? this.t('costs.amount.broken')
      : this.t('costs.amount.none')
  ));

  /**
   * Der Betrag deckt nicht alles — `''`, wenn er es tut.
   *
   * Als Satz mit den Modellnamen darin und nicht als blosses Warnzeichen: wer
   * die Lücke schliessen will, muss wissen, welches Modell sie aufreisst.
   */
  readonly partial = computed(() => {
    const report = this.value();
    const missing = report?.price_unavailable ?? [];
    return report && report.amount !== null && missing.length > 0
      ? this.t('costs.amount.partial', { models: this.lang.list([...missing]) })
      : '';
  });

  constructor() {
    void this.report.reload();
  }

  reload(): void {
    if (this.incomplete()) return;
    void this.report.reload();
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

  count(value: number): string {
    return this.fmt.whole(value);
  }

  /** Eine Zeile ohne Preis sagt das, statt eine leere Zelle zu zeigen. */
  rowAmount(amount: string | null): string {
    const currency = this.value()?.currency ?? '';
    return amount === null ? this.t('costs.noPrice') : this.fmt.money(amount, currency);
  }
}
