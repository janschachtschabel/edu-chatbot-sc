/**
 * Die Problemliste eines Laufs (Paket 13, F5): wo nachzubessern ist, schwächste Abläufe zuerst.
 *
 * Aufgenommen wird ein Ablauf mit Gesamt unter 4, einer Skala unter 4 oder ohne Ablauf-Urteil
 * (der steht ganz oben: dort fehlt die Aussage überhaupt). Je Eintrag die Noten unter 4 als
 * Chips, das Statement und die Auffälligkeiten des Judge; der Knopf springt zur Ablauf-Karte.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { type AblaufAuswertung, stufe } from '../core/eval-auswertung';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Unter dieser Note gilt eine Skala als Baustelle („gut, mit Kleinigkeit“ ist 4). */
const SCHWELLE = 4;

@Component({
  selector: 'studio-eval-problemliste',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-problemliste.component.html',
  styleUrl: './eval-problemliste.component.scss',
})
export class EvalProblemlisteComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);

  readonly ablaeufe = input.required<readonly AblaufAuswertung[]>();
  readonly springe = output<string>();

  readonly eintraege = computed(() => this.ablaeufe()
    .filter((a) => a.urteil_fehler || (a.gesamt ?? 5) < SCHWELLE
      || Object.values(a.skalen).some((note) => note < SCHWELLE))
    .sort((x, y) => (x.urteil_fehler ? -1 : x.gesamt ?? 5) - (y.urteil_fehler ? -1 : y.gesamt ?? 5))
    .map((a) => ({
      ablauf: a,
      chips: [
        ...(a.gesamt !== null && a.gesamt < SCHWELLE ? [this.chip('gesamt', a.gesamt)] : []),
        ...Object.entries(a.skalen).filter(([, note]) => note < SCHWELLE)
          .sort(([, x], [, y]) => x - y)
          .map(([skala, note]) => this.chip(skala, note)),
      ],
    })));

  private chip(skala: string, note: number): { text: string; stufe: string } {
    return {
      text: this.t('evalV2.note', { skala: this.t(`evalV2.skala.${skala}`), note: this.fmt.decimal(note) }),
      stufe: stufe(note),
    };
  }
}
