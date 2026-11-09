/**
 * Paket K2c-3: `argumente`/`daten` eines Ablaufschritts als Tabelle statt rohem JSON — je Zeile
 * Name, Art (fester Text, Teil des Vorgangs, JSON) und Wert. Die Teile zur Auswahl: die der Schritte
 * davor (`schreibt`, `agent.ausgabe`, aus dem ganzen Dokument) und die der Module (Katalog
 * `vorgang_teile`). Freitext bleibt möglich — ein Teil kann aus einem Modul kommen, das der Katalog
 * noch nicht kennt.
 *
 * Ein halber Stand (leerer oder doppelter Name, Teil ohne Namen, kaputtes JSON) schreibt nichts und
 * meldet sich wie ein JSON-Feld (`errorChange`) — das Formular sperrt dann das Speichern. „Als JSON“
 * zeigt den ganzen Wert in der gewohnten JSON-Box; ein Wert, der kein Objekt ist (oder ein Verweis
 * auf einen ganzen Teil), steht nur dort.
 *
 * Review K2c-3: eine JSON-Zeile wird erst beim Verlassen gelesen (wie die JSON-Box, Befund 2); das
 * eigene Echo des Formulars lässt den Entwurf stehen (kein Springen des Cursors, kein Wechsel der Art
 * mitten im Tippen); eine andere Kennung (anderer Schritt derselben Instanz) setzt alles zurück
 * (Befund 4); zwischen Tabelle und JSON-Box geht es nur ohne offene Meldung (Befund 3/5).
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';

import { ChoicesApi } from '../core/choices-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { FORM_DOKUMENT } from './form-dokument';
import { FORM_EPOCHE } from './form-epoche';
import { JsonValueComponent } from './json-value.component';
import {
  alsTabelleLesbar, type TeilArt, type TeilZeile, vorigeTeile, wertAus, type ZeilenFehler, zeilenAus,
} from './teil-werte';

const ARTEN: readonly TeilArt[] = ['text', 'teil', 'json'];

@Component({
  selector: 'studio-teil-werte',
  imports: [JsonValueComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    @if (alsJson() || !lesbar()) {
      <studio-json-value
        [fieldId]="controlId()"
        [value]="value()"
        [describedByBase]="describedBy()"
        (valueChange)="valueChange.emit($event)"
        (errorChange)="boxMeldung($event)"
      />
      @if (lesbar()) {
        <button type="button" class="sf-add" [disabled]="boxFehler()" (click)="zeigeTabelle()">
          {{ t('teilWerte.alsTabelle') }}
        </button>
      }
    } @else {
      <div class="tw" role="group" [id]="controlId()" [attr.aria-labelledby]="beschriftetVon()"
        [attr.aria-describedby]="describedBy()">
        @if (!zeilen().length) {
          <p class="sf-desc">{{ t('teilWerte.leer') }}</p>
        } @else {
          <!-- Review K2c-3 (2), Befund 4: sichtbare Spaltenköpfe; für Screenreader tragen die Felder
               ihren Namen mit der Zeilennummer selbst (aria-label). -->
          <div class="tw-kopf" aria-hidden="true">
            <span>{{ t('teilWerte.spalte.name') }}</span>
            <span>{{ t('teilWerte.spalte.art') }}</span>
            <span class="tw-kopf-wert">{{ t('teilWerte.spalte.wert') }}</span>
          </div>
        }
        @for (z of zeilen(); track $index; let i = $index) {
          <div class="tw-zeile">
            <input class="sf-input tw-name" type="text" [value]="z.name"
              [id]="controlId() + '-name-' + i"
              [attr.aria-label]="t('teilWerte.name', { n: i + 1 })"
              [attr.aria-invalid]="fehltAn(i, 'name') ? 'true' : null"
              [attr.aria-describedby]="fehltAn(i, 'name') ? fehlerId() : null"
              (input)="eingabe(i, 'name', $event)" />
            <select class="sf-input tw-art" [attr.aria-label]="t('teilWerte.art', { n: i + 1 })"
              (change)="eingabe(i, 'art', $event)">
              @for (art of arten; track art) {
                <option [value]="art" [selected]="art === z.art">{{ t('teilWerte.art.' + art) }}</option>
              }
            </select>
            @switch (z.art) {
              @case ('json') {
                <textarea class="sf-input tw-wert" rows="2" [value]="z.wert"
                  [attr.aria-label]="t('teilWerte.wert', { n: i + 1 })"
                  [attr.aria-invalid]="fehltAn(i, 'wert') ? 'true' : null"
                  [attr.aria-describedby]="fehltAn(i, 'wert') ? fehlerId() : null"
                  (input)="eingabe(i, 'wert', $event)" (change)="festhalten()"></textarea>
              }
              @case ('teil') {
                <input class="sf-input tw-wert" type="text" [value]="z.wert" [attr.list]="listId()"
                  [attr.aria-label]="t('teilWerte.teil', { n: i + 1 })"
                  [attr.aria-invalid]="fehltAn(i, 'wert') ? 'true' : null"
                  [attr.aria-describedby]="(fehltAn(i, 'wert') ? fehlerId() + ' ' : '') + hinweisId()"
                  (input)="eingabe(i, 'wert', $event)" />
              }
              @default {
                <input class="sf-input tw-wert" type="text" [value]="z.wert"
                  [attr.aria-label]="t('teilWerte.wert', { n: i + 1 })"
                  (input)="eingabe(i, 'wert', $event)" />
              }
            }
            <button type="button" class="sf-remove tw-weg" (click)="entfernen(i)"
              [attr.aria-label]="z.name.trim() ? t('teilWerte.entfernen', { n: i + 1, name: z.name }) : t('teilWerte.entfernenOhneName', { n: i + 1 })">{{ t('teilWerte.weg') }}</button>
          </div>
        }
        <datalist [id]="listId()">
          @for (teil of teile(); track teil.value) { <option [value]="teil.value" [label]="teil.label"></option> }
        </datalist>
        @if (zeilen().length) {
          <p class="sf-desc" [id]="hinweisId()">{{ t('teilWerte.pfadHinweis') }}</p>
        }
        <div class="tw-aktionen">
          <button type="button" class="sf-add" [id]="controlId() + '-neu'" (click)="neu()">{{ t('teilWerte.neu') }}</button>
          <button type="button" class="sf-add" [disabled]="fehler() !== null" (click)="zeigeJson()">
            {{ t('teilWerte.alsJson') }}
          </button>
        </div>
        <p class="sf-error live" [id]="fehlerId()" aria-live="polite">{{ fehlerText() }}</p>
      </div>
    }
  `,
})
export class TeilWerteComponent {
  private readonly lang = inject(StudioLanguageService);
  private readonly choices = inject(ChoicesApi);
  private readonly dokument = inject(FORM_DOKUMENT, { optional: true });
  private readonly epoche = inject(FORM_EPOCHE, { optional: true });
  protected readonly t = this.lang.t;
  protected readonly arten = ARTEN;

  readonly controlId = input.required<string>();
  readonly value = input<unknown>();
  readonly describedBy = input<string | null>(null);
  /** Die Kennung der Beschriftung des Felds — der Name der Gruppe (Review K2c-3, Befund 8). */
  readonly beschriftetVon = input<string | null>(null);
  /** Der Pfad des Felds im Dokument — für die Teile der Schritte davor. */
  readonly pfad = input<readonly (string | number)[]>([]);

  readonly valueChange = output<unknown>();
  /** Wie ein JSON-Feld: ein halber Stand sperrt das Speichern; `''` hebt die Meldung auf. */
  readonly errorChange = output<string>();

  readonly alsJson = signal(false);
  /** Die JSON-Box meldet gerade einen Fehler — zurück zur Tabelle erst danach (Befund 3). */
  readonly boxFehler = signal(false);
  private readonly entwurf = signal<TeilZeile[] | null>(null);
  readonly fehler = signal<ZeilenFehler | null>(null);
  /** Was diese Tabelle zuletzt schrieb (als JSON) — kommt es als Wert zurück, bleibt der Entwurf. */
  private gesendet: string | undefined;
  private letzteId = '';
  private letzteEpoche: number | undefined;

  readonly lesbar = computed(() => alsTabelleLesbar(this.value()));
  readonly zeilen = computed(() => this.entwurf() ?? zeilenAus(this.value()));
  readonly listId = computed(() => `${this.controlId()}-teile`);
  readonly fehlerId = computed(() => `${this.controlId()}-tw-err`);
  /** Review K2d-1 (2), Befund 7: der Pfad-Hinweis beschreibt die Teil-Eingaben. */
  readonly hinweisId = computed(() => `${this.controlId()}-tw-pfad`);
  readonly teile = computed(() => {
    const aus = new Map<string, string>();
    for (const t of vorigeTeile(this.dokument?.(), this.pfad())) aus.set(t, t);
    for (const e of this.choices.entries('vorgang_teile')) if (!aus.has(e.value)) aus.set(e.value, e.label);
    return [...aus].map(([value, label]) => ({ value, label }));
  });
  readonly fehlerText = computed(() => {
    const f = this.fehler();
    if (!f) return '';
    return this.t(`teilWerte.fehler.${f.art}`, {
      zeile: f.zeile + 1, name: 'name' in f ? f.name : '',
    });
  });

  constructor() {
    // Ein Wert von außen (Speichern, Verwerfen, anderer Schritt) macht Entwurf und Meldung
    // hinfällig — das eigene Echo nicht.
    effect(() => {
      const id = this.controlId();
      const wert = this.value();
      const epoche = this.epoche?.();
      untracked(() => {
        const anderer = id !== this.letzteId || epoche !== this.letzteEpoche;
        this.letzteId = id;
        this.letzteEpoche = epoche;
        if (!anderer && this.gesendet !== undefined && JSON.stringify(wert ?? null) === this.gesendet) return;
        this.gesendet = undefined;
        if (anderer) {
          // Review K2c-3 (2), Befund 1: eine Meldung der JSON-Box gehört dem alten Schritt — die
          // Box wird abgebaut, ohne sie zurückzunehmen (`schema-field` lenkt `''` auf den alten Pfad).
          if (this.boxFehler()) {
            this.boxFehler.set(false);
            this.errorChange.emit('');
          }
          this.alsJson.set(false);
        }
        if (this.entwurf() === null && !this.fehler()) return;
        this.entwurf.set(null);
        this.melde(null);
      });
    });
  }

  /** Steht die Meldung an diesem Feld dieser Zeile? */
  fehltAn(i: number, feld: 'name' | 'wert'): boolean {
    const f = this.fehler();
    if (!f || f.zeile !== i) return false;
    return feld === 'name' ? f.art === 'name_leer' || f.art === 'name_doppelt' : f.art === 'teil_leer' || f.art === 'json';
  }

  eingabe(i: number, feld: keyof TeilZeile, ereignis: Event): void {
    const wert = (ereignis.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement).value;
    const zeilen = this.zeilen().map((z, j) => (j === i ? { ...z, [feld]: wert } : z));
    // Befund 2: JSON ist beim Tippen meist unvollständig — erst beim Verlassen lesen.
    if (feld === 'wert' && zeilen[i]?.art === 'json') {
      this.entwurf.set(zeilen);
      return;
    }
    this.setze(zeilen);
  }

  /** Eine JSON-Zeile verlassen: jetzt lesen. */
  festhalten(): void {
    this.setze(this.zeilen());
  }

  neu(): void {
    // Die neue Zeile ist noch ohne Namen — sie schreibt erst, wenn sie einen hat.
    this.entwurf.set([...this.zeilen(), { name: '', art: 'text', wert: '' }]);
    const i = this.zeilen().length - 1;
    setTimeout(() => document.getElementById(`${this.controlId()}-name-${i}`)?.focus(), 0);
  }

  entfernen(i: number): void {
    const rest = this.zeilen().filter((_z, j) => j !== i);
    this.setze(rest);
    // Befund 8: der Fokus nicht auf `body` — die nächste Zeile, sonst „Eintrag hinzufügen“.
    const ziel = rest.length ? `${this.controlId()}-name-${Math.min(i, rest.length - 1)}` : `${this.controlId()}-neu`;
    setTimeout(() => document.getElementById(ziel)?.focus(), 0);
  }

  /** Review K2c-3 (2), Befund 3: der Knopf liegt im Zweig, den er abbaut — der Fokus nicht auf
   *  `body`, sondern auf die Box bzw. die erste Zeile (ohne Zeilen „Eintrag hinzufügen“). */
  zeigeJson(): void {
    this.alsJson.set(true);
    setTimeout(() => document.getElementById(this.controlId())?.focus(), 0);
  }

  zeigeTabelle(): void {
    this.alsJson.set(false);
    const ziel = this.zeilen().length ? `${this.controlId()}-name-0` : `${this.controlId()}-neu`;
    setTimeout(() => document.getElementById(ziel)?.focus(), 0);
  }

  boxMeldung(meldung: string): void {
    this.boxFehler.set(meldung !== '');
    this.errorChange.emit(meldung);
  }

  private setze(zeilen: TeilZeile[]): void {
    this.entwurf.set(zeilen);
    const ergebnis = wertAus(zeilen);
    if ('fehler' in ergebnis) {
      this.melde(ergebnis.fehler);
      return;
    }
    this.melde(null);
    this.gesendet = JSON.stringify(ergebnis.wert);
    this.valueChange.emit(ergebnis.wert);
  }

  private melde(fehler: ZeilenFehler | null): void {
    const vorher = this.fehler();
    this.fehler.set(fehler);
    if (fehler) this.errorChange.emit(this.fehlerText());
    else if (vorher) this.errorChange.emit('');
  }
}
