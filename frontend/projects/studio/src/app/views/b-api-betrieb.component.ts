/**
 * Die b-api-Betriebsart in der Statusleiste (Plan 2026-11-19, N1): ob das Backend zuletzt hinter
 * dem b-api-Proxy (Delegation oder durchgereichter Schlüssel) oder direkt (`B_API_KEY`) lief, wann,
 * unter welchem `B_API_KEY_MODE` — und die Warnungen dazu. Nur Wörter aus `/api/health`, nie ein
 * Wert. Die Karte selbst (Rahmen, Abstand) setzt die Statusleiste über `class="ov-status-card"`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { BApiBetrieb } from '../core/overview-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Ausgeschriebene Schlüssel statt `'overview.bapi.art.' + art`: ein unbekannter Wert soll
 *  nicht als Schlüssel auf dem Bildschirm landen. */
const ART_KEYS: Readonly<Record<string, string>> = {
  delegation: 'overview.bapi.art.delegation',
  schluessel: 'overview.bapi.art.schluessel',
  direkt: 'overview.bapi.art.direkt',
};

const WARNUNG_KEYS: Readonly<Record<string, string>> = {
  forward_ohne_token: 'overview.bapi.warnung.forward_ohne_token',
  zugangsblock_fehlt: 'overview.bapi.warnung.zugangsblock_fehlt',
};

@Component({
  selector: 'studio-b-api-betrieb',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './b-api-betrieb.component.html',
  styleUrl: './b-api-betrieb.component.scss',
})
export class BApiBetriebComponent {
  private readonly fmt = inject(StudioFormat);
  protected readonly t = inject(StudioLanguageService).t;

  readonly info = input<BApiBetrieb | null | undefined>(null);
  /** Bezugszeit der relativen Angabe — die Ladezeit der Statusleiste. */
  readonly bezugMs = input(0);

  readonly art = computed(() => {
    const zuletzt = this.info()?.zuletzt;
    if (!zuletzt) return this.t('overview.bapi.keiner');
    const key = ART_KEYS[zuletzt];
    return this.t('overview.bapi.erkannt', { art: key ? this.t(key) : zuletzt });
  });

  readonly wann = computed(() => {
    const am = this.info()?.zuletzt_am;
    return am ? this.t('overview.bapi.wann', {
      ago: this.fmt.relative(am, this.bezugMs()), exact: this.fmt.dateTime(am) }) : '';
  });

  /** Nur unter `forward` — nur dort weist das Backend einen Zug ohne Kopf ab. */
  readonly abgewiesen = computed(() => {
    const b = this.info();
    return b?.modus === 'forward'
      ? this.t('overview.bapi.abgewiesen', { count: this.fmt.whole(b.abgewiesen ?? 0) }) : '';
  });

  /** Ein unbekannter Code wird genannt, nicht verschwiegen. */
  readonly warnungen = computed(() => (this.info()?.warnungen ?? []).map((code) => {
    const key = WARNUNG_KEYS[code];
    return key ? this.t(key) : this.t('overview.bapi.warnung.andere', { code });
  }));
}
