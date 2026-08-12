/**
 * Der Sprach-Umschalter des Studios (C1-d1).
 *
 * Eigene Komponente statt zweimal derselbe Knopf im Markup: er steht in der
 * Kopfzeile UND auf der Anmeldeseite. Ohne den zweiten Platz käme jemand, der
 * die Oberfläche nicht lesen kann, an der Anmeldung nicht vorbei — die Hülle
 * mit ihrer Kopfzeile erscheint ja erst danach.
 *
 * Text statt Flagge: eine Flagge steht für ein Land, nicht für eine Sprache.
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { StudioLanguageService } from './studio-language.service';

@Component({
  selector: 'studio-language-switcher',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      type="button"
      class="lang"
      (click)="lang.toggle()"
      [title]="lang.switchLabel()"
      [attr.aria-label]="lang.switchLabel()"
    >
      <!-- Das Kürzel ist für die Vorlesehilfe verborgen: es steht schon im
           zugänglichen Namen, und „EN, Auf Englisch umschalten" wäre doppelt. -->
      <span aria-hidden="true">{{ lang.switchCode() }}</span>
    </button>
  `,
  styles: `
    /* Dieselben Werte wie \`.btn\` in shell.component.scss. Kein \`@extend\`:
       das reicht nicht über eine Komponentengrenze, und der Umschalter steht
       in zwei Komponenten. Alle Werte kommen aus den Token — die drei Namen,
       die ich hier zuerst geraten hatte, gibt es nicht, und \`npm run
       check:tokens\` hat sie gefunden. */
    .lang {
      min-width: 2.75rem;  /* > 24px in beiden Richtungen (SC 2.5.8) */
      min-height: 2.25rem;
      padding: 0 var(--st-2);
      border: 1px solid var(--st-text-muted);
      border-radius: var(--st-radius);
      background: var(--st-panel);
      color: var(--st-text);
      font: inherit;
      font-weight: 700;
      letter-spacing: 0.03em;
      cursor: pointer;
    }
    .lang:hover { background: var(--st-accent-soft); }
  `,
})
export class LanguageSwitcherComponent {
  protected readonly lang = inject(StudioLanguageService);
}
