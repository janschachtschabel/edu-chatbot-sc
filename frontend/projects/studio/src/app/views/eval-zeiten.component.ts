/**
 * Zeiten je Schritt eines Laufs (Paket 13, F6) — wohin die Zeit eines Zuges geht.
 *
 * Je Art eine Tabelle (Knoten der Pipeline, Teilschritte, LLM-Aufrufe nach Phase), langsamste
 * zuerst, mit Median, p95 und Anzahl. Kein gestapelter Balken wie im Plan skizziert: Mediane
 * verschiedener Schritte addieren sich nicht zu einem Zug, ein Stapel behauptete eine Summe,
 * die es nicht gibt. Der Balken je Zeile (relativ zum langsamsten Schritt der Art) ist Zierde.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { AuswertungV2, ZeitArt } from '../core/eval-auswertung';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

const ARTEN: readonly ZeitArt[] = ['knoten', 'schritte', 'llm'];

@Component({
  selector: 'studio-eval-zeiten',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-zeiten.component.html',
  styleUrl: './eval-zeiten.component.scss',
})
export class EvalZeitenComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);

  readonly zeiten = input.required<AuswertungV2['zeiten']>();

  readonly tabellen = computed(() => ARTEN.flatMap((art) => {
    const eintraege = Object.entries(this.zeiten()[art] ?? {})
      .sort(([, x], [, y]) => (y.p50_ms ?? 0) - (x.p50_ms ?? 0));
    if (eintraege.length === 0) return [];
    const max = Math.max(...eintraege.map(([, v]) => v.p50_ms ?? 0), 1);
    return [{
      art,
      zeilen: eintraege.map(([name, v]) => ({
        name,
        median: v.p50_ms === null ? '—' : this.fmt.seconds(v.p50_ms),
        p95: v.p95_ms === null ? '—' : this.fmt.seconds(v.p95_ms),
        n: v.n,
        breite: `${((v.p50_ms ?? 0) / max) * 100}%`,
      })),
    }];
  }));
}
