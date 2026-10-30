/**
 * Die Zugakte unter einer Antwort im Sitzungs-Verlauf (Paket 18C/D, Phase 4).
 *
 * Was das Log seit Phase 2 nicht mehr enthält, steht hier: die Werkzeugaufrufe
 * des Zugs mit Status, Dauer, Antwortlänge und Fehlertext — die Argumente
 * eingeklappt, die gesendeten nur, wenn sie von den eingegangenen abweichen —,
 * die Umschreibungen der Antwort (vorher/nachher) und die Schnellwege.
 *
 * Eingeklappt wie die Runden der Spur (`agent-trace.component`): ein Verlauf mit
 * zwanzig Zügen soll ein Verlauf bleiben. Eine leere Akte zeigt nichts.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import {
  type Werkzeugaufruf, readZugakte, schnellwegLabel, statusLabel, umschreibungLabel,
} from './zugakte';

@Component({
  selector: 'studio-zugakte',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './zugakte.component.html',
  styleUrl: './zugakte.component.scss',
})
export class ZugakteComponent {
  protected readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly fmt = inject(StudioFormat);

  /** `debug._zugakte` einer Nachricht — gespeichertes JSON, ungeprüft. */
  readonly akte = input<unknown>(undefined);

  protected readonly gelesen = computed(() => readZugakte(this.akte()));

  protected statusText(aufruf: Werkzeugaufruf): string {
    return statusLabel(aufruf.status, this.t);
  }

  protected zeichenText(aufruf: Werkzeugaufruf): string {
    return aufruf.zeichen === null
      ? this.t('st.za.noAnswer')
      : this.t('st.za.chars', { count: this.fmt.whole(aufruf.zeichen) });
  }

  protected umschreibungText(art: string): string {
    return umschreibungLabel(art, this.t);
  }

  protected schnellwegText(art: string): string {
    return schnellwegLabel(art, this.t);
  }
}
