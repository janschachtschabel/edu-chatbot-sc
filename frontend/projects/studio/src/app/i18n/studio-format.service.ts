/**
 * Zahlen, Datum und Zeitabstand in der aktiven Sprache (C1-d4f).
 *
 * Bis hierher trugen die sechs Formatierer in `core/format.ts` ihr `de-DE`
 * fest verdrahtet. Das war richtig, solange das Studio eine Sprache sprach —
 * und still falsch in dem Moment, in dem es zwei spricht: die englische
 * Oberfläche hätte „24.7.2026" und „0,81" geantwortet.
 *
 * Dieselbe Gattung wie `plural()`, `list()` und `rich()` in
 * `StudioLanguageService`: die Ansicht bekommt das fertige Ergebnis, nicht die
 * Bausteine dafür. Ein eigener Dienst und keine sechs weiteren Methoden dort,
 * weil es ein anderer Grund zur Änderung ist — Grammatik gegen Zahlen-Typografie.
 *
 * Wohnt in `i18n/` und nicht in `core/`: er liest den Katalog, und `core` darf
 * nicht nach `i18n` importieren (Abhängigkeit nach innen, siehe
 * `studio-language.service.ts`). Die reinen Funktionen bleiben in `core` und
 * nehmen das Kürzel als Parameter — prüfbar ohne Injector.
 *
 * Alle Methoden lesen `format.locale` über `t()` und damit das Sprach-Signal:
 * ein Aufruf im Template rendert beim Umschalten neu, wie `t()` selbst.
 */
import { Injectable, inject } from '@angular/core';

import {
  formatBytes, formatCalendarDay, formatDateTime, formatDecimal, formatMoney, formatPercent, formatRelative,
  formatSeconds, formatWhole,
} from '../core/format';
import { StudioLanguageService } from './studio-language.service';

@Injectable({ providedIn: 'root' })
export class StudioFormat {
  private readonly lang = inject(StudioLanguageService);

  /** Das BCP-47-Kürzel der aktiven Sprache, aus dem Katalog. */
  private locale(): string {
    return this.lang.t('format.locale');
  }

  /** Eine Bewertung oder Rate als Zahl: „0,81" / „0.81". */
  readonly decimal = (value: number): string => formatDecimal(this.locale(), value);

  /** Eine Anzahl: „12.345" / „12,345". */
  readonly whole = (value: number): string => formatWhole(this.locale(), value);

  /** Eine Größe in Byte: „20,5 MB" / „20.5 MB" (ST-6, Datenbank-Wartung). */
  readonly bytes = (value: number): string => formatBytes(this.locale(), value);

  /** Eine Dauer aus Millisekunden: „12,3 s" (ST-7b, Zugdauer der Eval-Läufe). */
  readonly seconds = (milliseconds: number): string =>
    formatSeconds(this.locale(), milliseconds);

  /**
   * Ein exakter Betrag samt Währung: „4,92 €" / „€4.92" (K5).
   *
   * Nimmt eine Zeichenkette und keine Zahl — so verlässt der Betrag den Server
   * (K4), damit die `Decimal`-Rechnung nicht auf dem letzten Meter zu einem
   * Gleitkommawert wird. Die Währung kommt aus der Preistafel; seit Paket 7
   * (K7) auch für die Kostenschätzung der Evaluation, die vorher fest USD war.
   */
  readonly money = (amount: string, currency: string): string =>
    formatMoney(this.locale(), amount, currency);

  /** Ein Verhältnis 0…1 als Prozentwert: „2,5 %" / „2.5%". */
  readonly percent = (value: number, digits = 1): string =>
    formatPercent(this.locale(), value, digits);

  /** Ein Kalendertag `JJJJ-MM-TT` ohne Uhrzeit (Kosten je Tag). */
  readonly day = (isoDate: string): string => formatCalendarDay(this.locale(), isoDate);

  /** Ein ISO-Zeitstempel in der Reihenfolge der aktiven Sprache. */
  readonly dateTime = (iso: string): string => formatDateTime(this.locale(), iso);

  /** Wie lange ein Zeitstempel her ist: „vor 5 Minuten" / „5 minutes ago". */
  readonly relative = (iso: string, nowMs: number): string =>
    formatRelative(this.locale(), iso, nowMs, this.lang.t('format.justNow'));
}
