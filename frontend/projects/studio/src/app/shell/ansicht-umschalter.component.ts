/**
 * „Arbeitsbereich: Agent | Muster“ — der Umschalter im Kopf (Paket 13 E2, Paket 14).
 *
 * Steht man beim Wechsel auf einer Seite des bisherigen Arbeitsbereichs, führt er zur
 * Startseite des neuen — sonst stünde eine Seite offen, die die Navigation nicht mehr zeigt.
 * Umgestellt wird erst, wenn der Wechsel gelingt: bricht man die Rückfrage einer ungespeicherten
 * Änderung ab, bleiben Seite, Arbeitsbereich und Auswahl, wie sie waren.
 *
 * Echte Radios in einem Fieldset wie bei der Herkunft (`studio-origin-scope`): Gruppenname,
 * Pfeiltasten und Auswahlzustand kommen von der Plattform. Kompakter als dort, weil er in der
 * Kopfzeile neben Sprache und Abmelden steht; die Erklärung trägt das `title` des Fieldsets und
 * — für Tastatur und Screenreader, die `title` nicht erreicht — ein verknüpfter, unsichtbarer Satz
 * (Review PR #18: der Wechsel kann die Seite wechseln, WCAG 3.2.2).
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router } from '@angular/router';

import { ANSICHTEN, type Ansicht, StudioAnsicht } from '../core/studio-ansicht.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { startView, workspaceOf } from '../studio-views';

@Component({
  selector: 'studio-ansicht-umschalter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <fieldset class="au" [title]="t('ansicht.hint')">
      <legend class="au-legend">{{ t('ansicht.legend') }}</legend>
      <span class="au-sr" id="studio-ansicht-hinweis">{{ t('ansicht.hint') }}</span>
      @for (option of options(); track option.id) {
        <label class="au-option">
          <input
            type="radio"
            name="studio-ansicht"
            [value]="option.id"
            [checked]="aktuell() === option.id"
            aria-describedby="studio-ansicht-hinweis"
            (change)="waehle(option.id, $event)"
          />
          <span>{{ option.label }}</span>
        </label>
      }
    </fieldset>
  `,
  styles: `
    .au-sr {
      position: absolute;
      inline-size: 1px;
      block-size: 1px;
      overflow: hidden;
      clip-path: inset(50%);
      white-space: nowrap;
    }
    .au {
      display: flex;
      align-items: center;
      gap: var(--st-1);
      margin: 0;
      padding: 0;
      border: 0;
    }

    .au-legend {
      float: inline-start;
      margin-inline-end: var(--st-1);
      padding: 0;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--st-text-muted);
    }

    .au-option {
      display: inline-flex;
      align-items: center;
      gap: var(--st-1);
      min-block-size: 2.25rem; /* > 24px Ziel (SC 2.5.8) */
      padding: 0 var(--st-2);
      border: 1px solid var(--st-text-muted);
      border-radius: var(--st-radius);
      background: var(--st-panel);
      color: var(--st-text);
      cursor: pointer;
    }

    .au-option:hover {
      background: var(--st-accent-soft);
    }

    /* Der Ring sitzt am ganzen Etikett: das Radio selbst ist klein. */
    .au-option:has(input:focus-visible) {
      outline: 2px solid var(--st-accent);
      outline-offset: 2px;
    }

    /* Nicht nur Farbe: das gewählte Radio bleibt sichtbar gefüllt, dazu Rahmen und Gewicht. */
    .au-option:has(input:checked) {
      border-color: var(--st-accent);
      background: var(--st-accent-soft);
      font-weight: 700;
    }
  `,
})
export class AnsichtUmschalterComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly ansicht = inject(StudioAnsicht);

  readonly aktuell = this.ansicht.ansicht;
  readonly options = computed(() => ANSICHTEN.map((id) => ({
    id, label: this.t(`ansicht.${id}`),
  })));

  private readonly router = inject(Router);

  async waehle(ansicht: Ansicht, event?: Event): Promise<void> {
    const bereich = workspaceOf(this.router.url.split(/[/?#]/)[1] ?? '');
    if (bereich && bereich !== ansicht
      && !(await this.router.navigate(['/', startView(ansicht)]))) {
      // Das Radio hat die Plattform schon umgesetzt; der Signalwert blieb — zurückstellen.
      const gruppe = (event?.target as HTMLElement | undefined)?.closest('fieldset');
      gruppe?.querySelectorAll<HTMLInputElement>('input[type="radio"]')
        .forEach((radio) => { radio.checked = radio.value === this.aktuell(); });
      return;
    }
    this.ansicht.waehle(ansicht);
  }
}
