/**
 * Der Verlauf der Noten mit dem Judge v2 (Paket 13, F8) — `trends.v2` als Tabelle.
 *
 * Eine Zeile je Lauf (älteste zuerst): Gesamt, Zug-Mittel, Skalen, Antwortzeit und Kosten je
 * Zug; ein Lauf ohne Wert hat eine Lücke („—“), keine Null. Die Spalte „Geändert“ trägt die
 * Wechselmarken: was gegenüber dem Lauf davor anders war (Modell, Weg, Konfiguration,
 * Master-Skill, Prompt-Bausteine). Kosten ohne Währung: die Trends liefern keine, die Zahl
 * steht in der Währung der Preistafel.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { TrendsV2, V2Punkt } from '../core/eval-auswertung';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

const SKALEN = ['zielgruppe', 'anliegen', 'angebot', 'werkzeuge', 'verlauf', 'qualitaet', 'sicherheit'];

@Component({
  selector: 'studio-eval-trends-v2',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-trends-v2.component.html',
  styleUrl: './eval-trends-v2.component.scss',
})
export class EvalTrendsV2Component {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);

  readonly v2 = input.required<TrendsV2>();

  readonly skalen = computed(() => SKALEN.filter((s) => (this.v2().skalen[s] ?? []).length > 0));

  readonly zeilen = computed(() => {
    const v2 = this.v2();
    const laeufe = new Map<string, string | null>();
    const reihen: readonly (readonly V2Punkt[])[] = [
      v2.gesamt, v2.zug_mittel, v2.latenz_p50_ms, v2.kosten_je_zug, ...Object.values(v2.skalen),
    ];
    for (const reihe of reihen) for (const p of reihe) laeufe.set(p.run_id, p.created_at);
    const wert = (reihe: readonly V2Punkt[] | undefined, id: string): number | undefined =>
      reihe?.find((p) => p.run_id === id)?.value;
    const note = (n: number | undefined): string => (n === undefined ? '—' : this.fmt.decimal(n));
    return [...laeufe.entries()]
      .sort(([, a], [, b]) => String(a ?? '').localeCompare(String(b ?? '')))
      .map(([id, wann]) => {
        const latenz = wert(v2.latenz_p50_ms, id);
        const kosten = wert(v2.kosten_je_zug, id);
        const w = v2.wechsel.find((x) => x.run_id === id);
        return {
          id,
          wann: wann ? this.fmt.dateTime(wann) : id,
          werte: [
            note(wert(v2.gesamt, id)), note(wert(v2.zug_mittel, id)),
            ...this.skalen().map((s) => note(wert(v2.skalen[s], id))),
            latenz === undefined ? '—' : this.fmt.seconds(latenz),
            kosten === undefined ? '—' : this.fmt.decimal(kosten),
          ],
          wechsel: w ? [
            ...w.felder.map((f) => this.t(`evalV2.feld.${f}`)),
            ...w.prompts.map((art) => this.t('evalV2.wechsel.prompt', { art })),
          ].join(', ') : '',
        };
      });
  });
}
