import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, type ElementRef, inject, Injector, input, signal,
  viewChild,
} from '@angular/core';

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
    antworten: 'Antworten', eigen: 'Eigene Antwort', mehrfach: 'Mehrere Antworten möglich.',
    eigenHinweisEinzel: 'Schreiben wählt „Eigene Antwort“ statt der Möglichkeiten oben.',
    eigenHinweisMehrfach: 'Schreiben wählt „Eigene Antwort“ mit aus.',
    beantwortet: 'Deine Antwort', veraltet: 'Diese Frage ist nicht mehr offen.',
  },
  en: {
    antworten: 'Answer', eigen: 'Your own answer', mehrfach: 'You can choose more than one.',
    eigenHinweisEinzel: 'Typing selects “Your own answer” instead of the options above.',
    eigenHinweisMehrfach: 'Typing also selects “Your own answer”.',
    beantwortet: 'Your answer', veraltet: 'This question is no longer open.',
  },
} as const;

/**
 * Eine Frage mit festen Möglichkeiten (Paket U1-d1) — das erste abfragende Modul. Die KI ruft es
 * als Werkzeug; der Zug endet, die Person wählt. „Antworten“ geht über den Host
 * (`antworten(daten, text)`): `daten` nach dem Antwort-Schema, `text` die lesbare Fassung für die
 * Nutzerblase. Gesperrt ohne Wahl und während eines Zugs (`host.beschaeftigt()`) — dann mit
 * `aria-disabled`, damit der Knopf in der Tab-Reihenfolge bleibt; nach dem Antworten verschwindet
 * er, und der Fokus geht an die Statuszeile (WCAG 2.4.3, Review U1 gesamt).
 *
 * Native Formularelemente statt eigener Widgets: `fieldset`/`legend` gibt der Gruppe ihren Namen,
 * Radio bzw. Checkbox bringen Tastatur (Pfeile, Leertaste) und Zustand für Screenreader mit,
 * Enter sendet das Formular. Nur lesend (`kontext().nurLesen`): beantwortet mit der gegebenen
 * Antwort, sonst ehrlich als nicht mehr offen.
 *
 * Mit `freitext` ist die eigene Antwort ein Punkt der Gruppe („Eigene Antwort“, Rückmeldung
 * 2026-11-09): bei Einzelwahl ein Radio wie die anderen — wer schreibt, wählt ihn, und die Wahl oben
 * springt heraus; wer wieder oben wählt, schickt den Text nicht mit. Bei Mehrfachwahl eine Checkbox:
 * abgehakt geht der Text nicht mit. Vorher schickte, wer oben wählte und dann schrieb, beides.
 * Ins Feld springt der Fokus nur nach einem Klick mit Maus oder Finger (Review, Befund 1, WCAG
 * 3.2.2): Pfeiltasten wählen in der Radio-Gruppe ebenfalls, und dort muss die Gruppe bleiben.
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
          @if (daten().freitext) {
            <label class="ui-entscheidung__option" (pointerdown)="zeiger = true">
              <input data-eigen [type]="mehrfach() ? 'checkbox' : 'radio'" [name]="gruppe()" value=""
                     [checked]="eigenAngehakt()" (change)="eigenUmschalten($event)" (click)="eigenKlick($event)"
                     [attr.aria-controls]="kontext().nurLesen ? null : kennung('eingabe-freitext')" />
              <span class="ui-entscheidung__text">
                <span class="ui-entscheidung__label" [id]="kennung('eingabe-eigen')">{{ texte().eigen }}</span>
              </span>
            </label>
            @if (!kontext().nurLesen) {
              <textarea #freitextFeld class="ui-entscheidung__freitext" [id]="kennung('eingabe-freitext')" rows="2"
                        [maxLength]="freitextMax" [attr.aria-labelledby]="kennung('eingabe-eigen')"
                        [attr.aria-describedby]="kennung('eingabe-eigen-hinweis')"
                        [value]="freitext()" (input)="freitextEingabe($event)"></textarea>
              <span class="ui-entscheidung__nur-vorlesen" [id]="kennung('eingabe-eigen-hinweis')">{{
                mehrfach() ? texte().eigenHinweisMehrfach : texte().eigenHinweisEinzel }}</span>
            }
          }
        </div>
      </fieldset>
      @if (kontext().nurLesen) {
        <p #statusZeile class="ui-entscheidung__status" tabindex="-1">{{ status() }}</p>
      } @else {
        <button type="submit" class="ui-entscheidung__senden" [disabled]="!bereit()"
                [attr.aria-disabled]="beschaeftigt() ? 'true' : null">{{ texte().antworten }}</button>
      }
    </form>
  `,
})
export class UiEntscheidung {
  readonly daten = input.required<UiEntscheidungDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);
  private readonly injector = inject(Injector);
  private readonly statusZeile = viewChild<ElementRef<HTMLElement>>('statusZeile');
  private readonly freitextFeld = viewChild<ElementRef<HTMLTextAreaElement>>('freitextFeld');

  protected readonly freitextMax = FREITEXT_MAX;
  protected readonly texte = computed(() => TEXTE[this.kontext().sprache]);
  protected readonly mehrfach = computed(() => this.daten().mehrfach === true);
  protected readonly gruppe = computed(() => `ue-${this.kontext().blockId}`);

  protected readonly auswahl = signal<readonly string[]>([]);
  protected readonly freitext = signal('');
  /** Der Punkt „Eigene Antwort“ ist gewählt — nur dann geht der Text mit. */
  protected readonly eigen = signal(false);
  /** Was mit der Antwort mitgeht: der Text, wenn „Eigene Antwort“ gewählt und er nicht leer ist. */
  private readonly eigeneAntwort = computed(() =>
    this.daten().freitext && this.eigen() ? this.freitext().trim().slice(0, FREITEXT_MAX) : '');
  protected readonly bereit = computed(() => this.auswahl().length > 0 || this.eigeneAntwort() !== '');
  /** Review, Befund 1: der letzte Druck auf „Eigene Antwort“ kam von Maus oder Finger. */
  protected zeiger = false;

  /** Die gegebene Antwort, solange nur gelesen wird — sonst die eigene Wahl. */
  private readonly gegeben = computed<UiEntscheidungAntwort | null>(() => {
    const a = this.kontext().antwort;
    return a && Array.isArray(a['gewaehlt']) ? (a as unknown as UiEntscheidungAntwort) : null;
  });

  protected readonly gewaehlt = computed<readonly string[]>(() =>
    this.kontext().nurLesen ? (this.gegeben()?.gewaehlt ?? []) : this.auswahl());

  /** Review, Befund 3: nur lesend ist „Eigene Antwort“ angehakt, wenn die Antwort einen Text trug. */
  protected readonly eigenAngehakt = computed(() =>
    this.kontext().nurLesen ? !!this.gegeben()?.freitext?.trim() : this.eigen());

  protected readonly beschaeftigt = computed(() => this.host.beschaeftigt());
  protected readonly gesperrt = computed(() => !this.bereit() || this.beschaeftigt());

  protected readonly status = computed(() => {
    const a = this.gegeben();
    if (!a) return this.texte().veraltet;
    const teile = [this.labels(a.gewaehlt).join(', '), a.freitext?.trim() ?? ''].filter(Boolean);
    return `${this.texte().beantwortet}: ${teile.join(' — ')}`;
  });

  /** Eine id im Block. Getrennte Namensräume (Review U1-d1): `opt-<id>` für Möglichkeiten,
   *  `eingabe-…` für eigene Felder — eine Möglichkeit mit der Kennung `freitext` traf sonst
   *  die id des Freitextfelds. */
  protected kennung(teil: string): string {
    return `${this.gruppe()}-${teil}`;
  }

  /** Schreiben wählt „Eigene Antwort“ (bei Einzelwahl springt die Wahl oben heraus). */
  protected freitextEingabe(ereignis: Event): void {
    const text = (ereignis.target as HTMLTextAreaElement).value;
    this.freitext.set(text);
    if (text.trim() && !this.eigen()) this.eigenWaehlen(true);
  }

  /** „Eigene Antwort“ gewählt oder abgehakt — mit Maus, Finger oder Tastatur. Der Zustand kommt
   *  aus dem Element selbst (Radio: immer an, Checkbox: wie angehakt). */
  protected eigenUmschalten(ereignis: Event): void {
    this.eigenWaehlen((ereignis.target as HTMLInputElement).checked);
  }

  /** Nach einem Klick mit Maus oder Finger ins Textfeld — nicht nach Pfeil- oder Leertaste
   *  (Review, Befund 1): die feuern ebenfalls `click`, aber ohne `pointerdown` davor. */
  protected eigenKlick(ereignis: Event): void {
    const mitZeiger = this.zeiger;
    this.zeiger = false;
    if (mitZeiger && (ereignis.target as HTMLInputElement).checked) this.freitextFeld()?.nativeElement.focus();
  }

  private eigenWaehlen(an: boolean): void {
    this.eigen.set(an);
    if (an && !this.mehrfach()) this.auswahl.set([]);
  }

  protected umschalten(id: string): void {
    if (!this.mehrfach()) {
      this.auswahl.set([id]);
      this.eigen.set(false);
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
    const zusatz = this.eigeneAntwort();
    const daten: Record<string, unknown> = zusatz ? { gewaehlt, freitext: zusatz } : { gewaehlt };
    this.host.antworten(daten, [this.labels(gewaehlt).join(', '), zusatz].filter(Boolean).join('\n'));
    // Die Shell vermerkt die Antwort sofort: der Knopf verschwindet, die Statuszeile erscheint.
    // Nahm sie die Antwort nicht an, gibt es keine Statuszeile — der Fokus bleibt am Knopf.
    afterNextRender(() => this.statusZeile()?.nativeElement.focus(), { injector: this.injector });
  }
}
