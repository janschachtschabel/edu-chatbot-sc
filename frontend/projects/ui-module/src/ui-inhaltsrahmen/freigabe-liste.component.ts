import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, input, signal } from '@angular/core';

import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import {
  anzahlTreffer, type FreigabeDaten, gruppen, PROBLEME_SICHTBAR, SEITE, sichtbar, TEXTE_FREIGABE,
} from './freigabe';

let naechsteKennung = 0;

/**
 * Paket N4: der Rumpf der Freigabe-Box im Inhaltsrahmen (Art `schreib_vorschau` mit `freigabe`).
 * Kompakt: Kopfzeile, ein Satz, Probleme des MCP getrennt; die Liste eingeklappt (Disclosure),
 * aufgeklappt nach Ordner gruppiert, ab mehr als {@link SEITE} Einträgen mit Filterfeld und
 * seitenweise. „Freigeben“/„Abbrechen“ gehen als Direktaktion über den Host (`auftrag`); danach —
 * oder nur lesend (nächster Zug, Verlauf) — bleibt eine Zeile als Quittung (`role="status"`).
 */
@Component({
  selector: 'ui-freigabe-liste',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './freigabe-liste.component.scss',
  template: `
    @if (quittung(); as zeile) {
      <p class="freigabe__quittung" role="status" tabindex="-1">{{ zeile }}</p>
    } @else {
      <p class="freigabe__kopf">{{ kopf() }}</p>
      @if (freigabe().metadaten) {
        <p class="freigabe__satz">{{ t().satz }}</p>
      }
      @if (freigabe().probleme.length) {
        <div class="freigabe__probleme">
          <p>{{ t().probleme(freigabe().probleme.length) }}</p>
          <ul [id]="problemeId">
            @for (p of problemeGezeigt(); track $index) {
              <li><bdi>{{ p.titel }}</bdi> – {{ t().grund(p.grund) }}</li>
            }
          </ul>
          @if (freigabe().probleme.length > problemeSichtbar) {
            <button type="button" class="freigabe__auf" [attr.aria-expanded]="alleProbleme()"
                    [attr.aria-controls]="problemeId" (click)="alleProbleme.set(!alleProbleme())">
              {{ t().alleZeigen(freigabe().probleme.length) }}
            </button>
          }
        </div>
      }
      @if (freigabe().eintraege.length) {
        <button type="button" class="freigabe__auf" [attr.aria-expanded]="offen()"
                [attr.aria-controls]="offen() ? listeId : null" (click)="offen.set(!offen())">
          {{ t().liste(freigabe().eintraege.length) }}
        </button>
        @if (offen()) {
          <div class="freigabe__liste" [id]="listeId">
            @if (mitFilter()) {
              <label class="freigabe__filter-label" [for]="filterId">{{ t().filter }}</label>
              <input type="search" class="freigabe__filter" [id]="filterId" [value]="filter()"
                     [attr.aria-describedby]="trefferId" (input)="filtern($event)" />
              <p class="freigabe__treffer" [id]="trefferId" aria-live="polite">
                {{ t().treffer(gezeigt().length, treffer()) }}
              </p>
            }
            @for (g of gruppiert(); track g.ordner) {
              <div class="freigabe__gruppe" [attr.data-ordner]="g.ordner">
                <p class="freigabe__ordner">{{ g.ordner || t().ohneOrdner }}</p>
                <ul>
                  @for (e of g.eintraege; track $index) {
                    <li class="freigabe__eintrag"><bdi>{{ e.titel }}</bdi></li>
                  }
                </ul>
              </div>
            }
            @if (gezeigt().length < treffer()) {
              <button type="button" class="freigabe__mehr" (click)="seiten.set(seiten() + 1)">{{ t().mehr }}</button>
            }
          </div>
        }
      }
      @if (hinweis()) {
        <p class="freigabe__hinweis" role="status">{{ hinweis() }}</p>
      }
      <div class="freigabe__knoepfe">
        <button type="button" class="freigabe__knopf freigabe__knopf--haupt" [disabled]="sendet()"
                (click)="entscheiden('freigeben')">{{ t().freigeben }}</button>
        <button type="button" class="freigabe__knopf" [disabled]="sendet()"
                (click)="entscheiden('verwerfen')">{{ t().abbrechen }}</button>
      </div>
    }
  `,
})
export class FreigabeListe {
  readonly freigabe = input.required<FreigabeDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly kennung = ++naechsteKennung;
  protected readonly listeId = `freigabe-liste-${this.kennung}`;
  protected readonly filterId = `freigabe-filter-${this.kennung}`;
  protected readonly trefferId = `freigabe-treffer-${this.kennung}`;
  protected readonly problemeId = `freigabe-probleme-${this.kennung}`;
  protected readonly problemeSichtbar = PROBLEME_SICHTBAR;
  protected readonly alleProbleme = signal(false);

  protected readonly offen = signal(false);
  protected readonly filter = signal('');
  protected readonly seiten = signal(1);
  protected readonly sendet = signal(false);
  protected readonly hinweis = signal('');
  private readonly entschieden = signal<'freigeben' | 'verwerfen' | null>(null);

  protected readonly t = computed(() => TEXTE_FREIGABE[this.kontext().sprache]);
  protected readonly mitFilter = computed(() => this.freigabe().eintraege.length > SEITE);
  protected readonly gezeigt = computed(() => sichtbar(this.freigabe().eintraege, this.filter(), this.seiten()));
  protected readonly treffer = computed(() => anzahlTreffer(this.freigabe().eintraege, this.filter()));
  protected readonly gruppiert = computed(() => gruppen(this.gezeigt()));
  protected readonly problemeGezeigt = computed(() =>
    (this.alleProbleme() ? this.freigabe().probleme : this.freigabe().probleme.slice(0, PROBLEME_SICHTBAR)));
  /** Review N4 (7): beim Metadaten-Flow „N Materialien werden erschlossen“, sonst neutral mit dem
   *  Flow — die Zahl nur, wenn es Einträge gibt. */
  protected readonly kopf = computed(() => {
    const f = this.freigabe();
    return f.metadaten === false ? this.t().kopfFlow(f.flow ?? '', f.anzahl) : this.t().kopf(f.anzahl);
  });

  /** Die eine Zeile nach der Entscheidung bzw. im Verlauf — sonst `null` (die ganze Box). Review N4
   *  (2): neutral „Entscheidung gesendet“ — was daraus wurde (gestartet, abgelaufen, nicht mehr
   *  offen, abgelehnt), sagt die Antwort darunter. */
  protected readonly quittung = computed(() => {
    const t = this.t();
    const wahl = this.entschieden();
    if (wahl) return t.gesendet(wahl);
    return this.kontext().nurLesen ? t.vorbei(this.freigabe().anzahl) : null;
  });

  protected filtern(ereignis: Event): void {
    this.filter.set((ereignis.target as HTMLInputElement).value);
    this.seiten.set(1);
  }

  protected async entscheiden(schritt: 'freigeben' | 'verwerfen'): Promise<void> {
    if (this.sendet() || this.host.beschaeftigt?.()) return;
    this.sendet.set(true);
    this.hinweis.set('');
    try {
      const f = this.freigabe();
      const antwort = await this.host.auftrag({ schritt, ablauf: f.ablauf, freigabe: f.id });
      if (antwort['gesendet'] === true) {
        this.entschieden.set(schritt);
        // Die Knöpfe verschwinden — der Fokus geht auf die Quittung statt verloren (WCAG 2.4.3)
        setTimeout(() => this.element.nativeElement.querySelector<HTMLElement>('.freigabe__quittung')?.focus());
      }
      else this.hinweis.set(this.t().fehlgeschlagen);
    } catch {
      this.hinweis.set(this.t().fehlgeschlagen);
    } finally {
      this.sendet.set(false);
    }
  }
}
