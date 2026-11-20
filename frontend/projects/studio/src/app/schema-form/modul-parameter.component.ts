/**
 * Plan 2026-11-20, P6: die Parameter eines UI-Moduls unter „Daten“ eines Modul-Schritts — zum
 * Lesen, nicht zum Bearbeiten (die Tabelle darüber schreibt). So sind etwa `vorauswahl`,
 * `rolle_vorgabe` und `erschliessen` von `ui_upload` ohne Code-Kenntnis pflegbar. Die Manifeste
 * kommen aus dem Katalog des Studios (`GET /api/config/ui-module`); ohne Antwort bleibt die Hilfe
 * weg. Die Beschreibungen stammen aus dem Manifest und sind deutsch (`lang="de"`).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { UiModuleApi } from '../core/ui-module-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { parameterAus } from './modul-parameter';

@Component({
  selector: 'studio-modul-parameter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    @if (parameter().length) {
      <div class="mp">
        <p class="sf-desc" [id]="kopfId()">{{ t('modulParameter.titel', { modul: modul() }) }}</p>
        <ul class="mp-liste sf-desc" [attr.aria-labelledby]="kopfId()">
          @for (p of parameter(); track p.name) {
            <li>
              <code>{{ p.name }}</code>
              @if (p.pflicht) { ({{ t('modulParameter.pflicht') }}) }
              @if (p.beschreibung) { — <span lang="de">{{ p.beschreibung }}</span> }
              @if (p.werte.length) {
                {{ t(p.liste ? 'modulParameter.werteListe' : 'modulParameter.werte', { werte: p.werte.join(', ') }) }}
              } @else if (p.typ) {
                {{ t('modulParameter.typ', { typ: p.typ }) }}
              }
              @if (p.vorgabe !== null) { {{ t('modulParameter.vorgabe', { wert: p.vorgabe }) }} }
            </li>
          }
        </ul>
      </div>
    }
  `,
})
export class ModulParameterComponent {
  private readonly api = inject(UiModuleApi);
  protected readonly t = inject(StudioLanguageService).t;

  readonly modul = input.required<string>();
  /** Die Kennung des Felds — für eine eindeutige Überschrift der Liste. */
  readonly controlId = input.required<string>();

  readonly kopfId = computed(() => `${this.controlId()}-mp`);
  readonly parameter = computed(() => parameterAus(this.api.manifeste().get(this.modul())));

  constructor() {
    void this.api.manifesteLaden();
  }
}
