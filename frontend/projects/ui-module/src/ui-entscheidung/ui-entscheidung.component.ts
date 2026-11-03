import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';

import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';

/** Eingabe laut manifest.json (`eingabe`). */
export interface UiEntscheidungDaten {
  readonly frage: string;
  readonly optionen: readonly { readonly id: string; readonly label: string; readonly hinweis?: string }[];
  readonly mehrfach?: boolean;
  readonly freitext?: boolean;
}

/** Antwort laut manifest.json (`antwort`). */
export interface UiEntscheidungAntwort {
  readonly gewaehlt: readonly string[];
  readonly freitext?: string;
}

const FREITEXT_MAX = 1000;

const TEXTE = {
  de: {
    antworten: 'Antworten', freitext: 'Eigene Ergänzung (optional)', mehrfach: 'Mehrere Antworten möglich.',
    beantwortet: 'Deine Antwort', veraltet: 'Diese Frage ist nicht mehr offen.',
  },
  en: {
    antworten: 'Answer', freitext: 'Your own addition (optional)', mehrfach: 'You can choose more than one.',
    beantwortet: 'Your answer', veraltet: 'This question is no longer open.',
  },
} as const;

/**
 * Eine Frage mit festen Möglichkeiten (Paket U1-d1) — das erste abfragende Modul. Die KI ruft es
 * als Werkzeug; der Zug endet, die Person wählt. „Antworten“ geht über den Host
 * (`antworten(daten, text)`): `daten` nach dem Antwort-Schema, `text` die lesbare Fassung für die
 * Nutzerblase. Gesperrt ohne Wahl und während eines Zugs (`host.beschaeftigt()`).
 *
 * Native Formularelemente statt eigener Widgets: `fieldset`/`legend` gibt der Gruppe ihren Namen,
 * Radio bzw. Checkbox bringen Tastatur (Pfeile, Leertaste) und Zustand für Screenreader mit,
 * Enter sendet das Formular. Nur lesend (`kontext().nurLesen`): beantwortet mit der gegebenen
 * Antwort, sonst ehrlich als nicht mehr offen.
 */
@Component({
  selector: 'ui-entscheidung',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './ui-entscheidung.component.scss',
  template: `
    <form class="ui-entscheidung" (submit)="senden($event)">
      <fieldset class="ui-entscheidung__gruppe" [disabled]="kontext().nurLesen">
        <legend class="ui-entscheidung__frage">{{ daten().frage }}</legend>
        @if (mehrfach() && !kontext().nurLesen) {
          <p class="ui-entscheidung__anleitung">{{ texte().mehrfach }}</p>
        }
        <div class="ui-entscheidung__optionen">
          @for (o of daten().optionen; track o.id) {
            <label class="ui-entscheidung__option">
              <input [type]="mehrfach() ? 'checkbox' : 'radio'" [name]="gruppe()" [value]="o.id"
                     [checked]="gewaehlt().includes(o.id)" (change)="umschalten(o.id)"
                     [attr.aria-describedby]="o.hinweis ? kennung('opt-' + o.id) : null" />
              <span class="ui-entscheidung__text">
                <span class="ui-entscheidung__label">{{ o.label }}</span>
                @if (o.hinweis) {
                  <span class="ui-entscheidung__hinweis" [id]="kennung('opt-' + o.id)">{{ o.hinweis }}</span>
                }
              </span>
            </label>
          }
        </div>
        @if (daten().freitext && !kontext().nurLesen) {
          <label class="ui-entscheidung__freitext-label" [for]="kennung('eingabe-freitext')">{{ texte().freitext }}</label>
          <textarea class="ui-entscheidung__freitext" [id]="kennung('eingabe-freitext')" rows="2" [maxLength]="freitextMax"
                    [value]="freitext()" (input)="freitext.set(wert($event))"></textarea>
        }
      </fieldset>
      @if (kontext().nurLesen) {
        <p class="ui-entscheidung__status">{{ status() }}</p>
      } @else {
        <button type="submit" class="ui-entscheidung__senden" [disabled]="gesperrt()">{{ texte().antworten }}</button>
      }
    </form>
  `,
})
export class UiEntscheidung {
  readonly daten = input.required<UiEntscheidungDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);

  protected readonly freitextMax = FREITEXT_MAX;
  protected readonly texte = computed(() => TEXTE[this.kontext().sprache]);
  protected readonly mehrfach = computed(() => this.daten().mehrfach === true);
  protected readonly gruppe = computed(() => `ue-${this.kontext().blockId}`);

  private readonly auswahl = signal<readonly string[]>([]);
  protected readonly freitext = signal('');

  /** Die gegebene Antwort, solange nur gelesen wird — sonst die eigene Wahl. */
  private readonly gegeben = computed<UiEntscheidungAntwort | null>(() => {
    const a = this.kontext().antwort;
    return a && Array.isArray(a['gewaehlt']) ? (a as unknown as UiEntscheidungAntwort) : null;
  });

  protected readonly gewaehlt = computed<readonly string[]>(() =>
    this.kontext().nurLesen ? (this.gegeben()?.gewaehlt ?? []) : this.auswahl());

  protected readonly gesperrt = computed(() => !this.auswahl().length || this.host.beschaeftigt());

  protected readonly status = computed(() => {
    const a = this.gegeben();
    if (!a) return this.texte().veraltet;
    const zusatz = a.freitext?.trim() ? ` — ${a.freitext.trim()}` : '';
    return `${this.texte().beantwortet}: ${this.labels(a.gewaehlt).join(', ')}${zusatz}`;
  });

  /** Eine id im Block. Getrennte Namensräume (Review U1-d1): `opt-<id>` für Möglichkeiten,
   *  `eingabe-…` für eigene Felder — eine Möglichkeit mit der Kennung `freitext` traf sonst
   *  die id des Freitextfelds. */
  protected kennung(teil: string): string {
    return `${this.gruppe()}-${teil}`;
  }

  protected wert(ereignis: Event): string {
    return (ereignis.target as HTMLTextAreaElement).value;
  }

  protected umschalten(id: string): void {
    if (!this.mehrfach()) {
      this.auswahl.set([id]);
      return;
    }
    this.auswahl.update((liste) => (liste.includes(id) ? liste.filter((k) => k !== id) : [...liste, id]));
  }

  /** Beschriftungen in der Reihenfolge der Möglichkeiten (nicht der Klicks). */
  private labels(ids: readonly string[]): string[] {
    return this.daten().optionen.filter((o) => ids.includes(o.id)).map((o) => o.label);
  }

  protected senden(ereignis: Event): void {
    ereignis.preventDefault();
    if (this.kontext().nurLesen || this.gesperrt()) return;
    const gewaehlt = this.daten().optionen.map((o) => o.id).filter((id) => this.auswahl().includes(id));
    const zusatz = this.daten().freitext ? this.freitext().trim().slice(0, FREITEXT_MAX) : '';
    const daten: Record<string, unknown> = zusatz ? { gewaehlt, freitext: zusatz } : { gewaehlt };
    this.host.antworten(daten, [this.labels(gewaehlt).join(', '), zusatz].filter(Boolean).join('\n'));
  }
}
