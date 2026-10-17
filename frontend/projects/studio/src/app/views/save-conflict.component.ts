/**
 * „Inzwischen anderswo gespeichert" — der Hinweis nach einem 409 (Paket 4, D5).
 *
 * Bis dahin überschrieb, wer als zweites speicherte, den ersten still
 * (externes Audit F14). Jetzt lehnt der Server ab, und hier steht, wann und
 * über welchen Weg gespeichert wurde, mit den beiden Auswegen:
 *
 *   - „Neu laden" zeigt den gespeicherten Stand; der Entwurf geht verloren.
 *   - „Trotzdem speichern" ersetzt die andere Änderung — gegen genau die
 *     gemeldete Version, nicht bedingungslos (`AreaDocEditor.save`).
 *
 * Der Entwurf bleibt bis zur Wahl erhalten. Der Hinweis holt den Fokus: unter
 * einem langen Formular stünde er sonst unbemerkt. Die Gruppe trägt den Satz
 * als Namen, den ein Screenreader beim Fokussieren vorliest.
 *
 * Wer gespeichert hat, weiß der Server nicht — das Studio teilt eine Anmeldung.
 * `updated_by` nennt den Weg (`studio-form`, `restore` …); bekannte Wege stehen
 * ausgeschrieben, ein unbekannter so, wie er kam.
 */
import {
  ChangeDetectionStrategy, Component, type ElementRef, afterRenderEffect, computed, inject,
  input, output, viewChild,
} from '@angular/core';

import type { SaveConflict } from '../core/studio-api-error';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Ausgeschrieben statt zur Laufzeit zusammengesetzt (vgl. `rag-ingest`). */
const WEG: Readonly<Record<string, string>> = {
  'studio-form': 'conflict.via.form',
  'config-file-api': 'conflict.via.raw',
  studio: 'conflict.via.studio',
  restore: 'conflict.via.restore',
  'seed-apply': 'conflict.via.seed',
  'seed-apply-cli': 'conflict.via.seed',
  import: 'conflict.via.import',
  'import-cli': 'conflict.via.import',
  werksabgleich: 'conflict.via.werksabgleich',
  werkfassung: 'conflict.via.werkfassung',
  'werk-geprueft': 'conflict.via.geprueft',
  'eigene-fassung': 'conflict.via.eigeneFassung',
};

let zaehler = 0;

@Component({
  selector: 'studio-save-conflict',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #box class="sk" role="group" tabindex="-1" [attr.aria-labelledby]="textId">
      <p class="cs-state cs-state--error sk-text" [id]="textId">{{ text() }}</p>
      <p class="cs-state sk-hint">{{ t('conflict.choice') }}</p>
      <div class="sk-actions">
        <button type="button" class="cs-btn" [disabled]="busy()" (click)="reload.emit()">
          {{ t('conflict.reload') }}
        </button>
        <button type="button" class="cs-btn cs-btn--primary" [disabled]="busy()"
                (click)="force.emit()">
          {{ t('conflict.force') }}
        </button>
      </div>
    </div>
  `,
  styleUrl: './save-conflict.component.scss',
})
export class SaveConflictComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly format = inject(StudioFormat);

  readonly conflict = input.required<SaveConflict>();
  /** Speichern oder Laden läuft — beide Auswege warten. */
  readonly busy = input(false);
  readonly reload = output<void>();
  readonly force = output<void>();

  readonly textId = `sk-text-${++zaehler}`;
  private readonly box = viewChild.required<ElementRef<HTMLElement>>('box');

  readonly text = computed(() => {
    const c = this.conflict();
    if (c.version === null) return this.t('conflict.gone');
    const weg = c.updatedBy ? WEG[c.updatedBy] : undefined;
    return this.t('conflict.changed', {
      when: c.updatedAt ? this.format.dateTime(c.updatedAt) : this.t('conflict.recently'),
      via: weg ? this.t(weg) : (c.updatedBy ?? this.t('conflict.unknownVia')),
    });
  });

  constructor() {
    // Bei jedem neuen Konflikt — auch dem zweiten nach „Trotzdem speichern".
    afterRenderEffect(() => {
      this.conflict();
      this.box().nativeElement.focus();
    });
  }
}
