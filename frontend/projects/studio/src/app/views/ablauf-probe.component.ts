/**
 * Paket AS-8b (Plan 2026-11-09 §5n, P-9): „Ablauf ausprobieren“ — ein Abschnitt der Vorschau.
 *
 * Ablauf wählen (auch ausgeschaltete, erkennbar mit „(aus)“), Startdaten als JSON (optional) und
 * „Ablauf starten“. Die Vorschau baut daraufhin ein neues Widget mit dem Attribut `probe` und
 * startet den Ablauf über `element.startAblauf(id, daten)` (`widget-preview.component.ts`; nicht
 * über Attribute, Browser-Abnahme AS-8, B-1). Das Backend lässt die Probe nur mit Studio-Anmeldung
 * zu und schreibt dabei nichts (AS-8a).
 *
 * Zustände der Liste: laden, leer (Hinweis auf „Abläufe“), Fehler (mit neuem Versuch). Ungültige
 * Startdaten stehen am Feld (`aria-invalid`, `aria-describedby`); der Text bleibt stehen.
 */
import {
  ChangeDetectionStrategy, Component, type ElementRef, computed, effect, inject, input, output, signal,
  untracked, viewChild,
} from '@angular/core';

import { type AblaufZeile, AblaufApi } from '../core/ablauf-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { type StartdatenFehler, startdatenPruefen } from './probe-start';

/** Was die Vorschau starten soll; `null` = Probe beenden. */
export interface ProbeStart {
  readonly ablauf: string;
  readonly daten: string | null;
}

type Liste =
  | { readonly art: 'laden' }
  | { readonly art: 'fehler' }
  | { readonly art: 'da'; readonly zeilen: readonly AblaufZeile[] };

@Component({
  selector: 'studio-ablauf-probe',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './ablauf-probe.component.scss',
  template: `
    <section class="op-panel" aria-labelledby="ap-probe-titel">
      <h2 class="op-title" id="ap-probe-titel">{{ t('preview.probe.title') }}</h2>
      <p class="op-lead">{{ t('preview.probe.lead') }}</p>

      @switch (liste().art) {
        @case ('laden') { <p class="op-lead" role="status">{{ t('preview.probe.laden') }}</p> }
        @case ('fehler') {
          <p class="op-msg op-msg--error" role="alert">⚠ {{ t('preview.probe.listeFehler') }}</p>
          <div class="op-actions">
            <button type="button" class="op-btn" (click)="laden()">{{ t('async.retry') }}</button>
          </div>
        }
        @case ('da') {
          @if (zeilen().length === 0) {
            <p class="op-lead">{{ t('preview.probe.leer') }}</p>
          } @else {
            <form class="ap-probe-form" (submit)="starte($event)" novalidate>
              @if (unbekannt(); as kennung) {
                <p class="ap-probe-hilfe" role="status">{{ t('preview.probe.unbekannt', { kennung }) }}</p>
              }
              <label class="op-label" for="ap-probe-ablauf">{{ t('preview.probe.ablauf') }}</label>
              <select id="ap-probe-ablauf" class="op-input" [value]="gewaehlt()"
                (change)="gewaehlt.set($any($event.target).value)">
                @for (z of zeilen(); track z.id) {
                  <option [value]="z.id" [selected]="z.id === gewaehlt()">{{ titelMitStand(z) }}</option>
                }
              </select>

              <label class="op-label" for="ap-probe-daten">{{ t('preview.probe.daten') }}</label>
              <textarea #datenFeld id="ap-probe-daten" class="op-input ap-probe-daten" rows="3" spellcheck="false"
                autocomplete="off" [value]="daten()" (input)="aendern($any($event.target).value)"
                [attr.aria-invalid]="fehler() ? 'true' : null"
                [attr.aria-describedby]="fehler() ? 'ap-probe-hilfe ap-probe-fehler' : 'ap-probe-hilfe'">
              </textarea>
              <p class="ap-probe-hilfe" id="ap-probe-hilfe">{{ t('preview.probe.datenHilfe') }}</p>
              @if (fehler(); as f) {
                <p class="op-msg op-msg--error" id="ap-probe-fehler">⚠ {{ t('preview.probe.fehler.' + f) }}</p>
              }

              <div class="op-actions">
                <button #startKnopf type="submit" class="op-btn op-btn--primary">{{ t('preview.probe.starten') }}</button>
                @if (aktiv()) {
                  <button type="button" class="op-btn" (click)="beenden()">{{ t('preview.probe.beenden') }}</button>
                }
              </div>
            </form>
          }
        }
      }
      <!-- eine bleibende Region: sie sagt, welche Probe gerade im Widget läuft -->
      <p class="ap-probe-stand" role="status">
        @if (aktivTitel(); as titel) { {{ t('preview.probe.laeuft', { titel }) }} }
      </p>
    </section>
  `,
})
export class AblaufProbeComponent {
  private readonly api = inject(AblaufApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  /** Kennung aus `?ablauf=` (Knopf am Ablauf) — wählt ihn vor. */
  readonly vorauswahl = input<string | null>(null);
  /** Die Kennung der Probe, die gerade im Widget läuft — sonst `null`. */
  readonly aktiv = input<string | null>(null);
  readonly starten = output<ProbeStart | null>();

  readonly liste = signal<Liste>({ art: 'laden' });
  readonly gewaehlt = signal('');
  readonly daten = signal('');
  readonly fehler = signal<StartdatenFehler | null>(null);
  private readonly datenFeld = viewChild<ElementRef<HTMLTextAreaElement>>('datenFeld');
  private readonly startKnopf = viewChild<ElementRef<HTMLButtonElement>>('startKnopf');

  readonly zeilen = computed(() => {
    const l = this.liste();
    return l.art === 'da' ? l.zeilen : [];
  });
  /** Eine Kennung aus der Adresse, die es (noch) nicht gibt — etwa ein ungespeicherter Ablauf. */
  readonly unbekannt = computed(() => {
    const wunsch = this.vorauswahl();
    const zeilen = this.zeilen();
    return wunsch && zeilen.length && !zeilen.some((z) => z.id === wunsch) ? wunsch : null;
  });
  readonly aktivTitel = computed(() => {
    const id = this.aktiv();
    const z = id ? this.zeilen().find((x) => x.id === id) : undefined;
    return id ? (z ? this.titel(z) : id) : null;
  });

  constructor() {
    void this.laden();
    // die Vorauswahl gilt, sobald die Liste da ist — und nur für einen Ablauf, den es gibt
    effect(() => {
      const wunsch = this.vorauswahl();
      const zeilen = this.zeilen();
      untracked(() => {
        if (!zeilen.length) return;
        const passend = wunsch && zeilen.some((z) => z.id === wunsch);
        if (passend) this.gewaehlt.set(wunsch);
        else if (!zeilen.some((z) => z.id === this.gewaehlt())) this.gewaehlt.set(zeilen[0].id);
      });
    });
  }

  async laden(): Promise<void> {
    this.liste.set({ art: 'laden' });
    try {
      this.liste.set({ art: 'da', zeilen: (await this.api.liste()).filter((z) => z.lesbar) });
    } catch (err) {
      console.error('[Studio] Abläufe für die Probe nicht geladen:', err);
      this.liste.set({ art: 'fehler' });
    }
  }

  titel(z: AblaufZeile): string {
    return z.titel[this.lang.i18n.locale()] || z.titel['de'] || z.id;
  }

  titelMitStand(z: AblaufZeile): string {
    return z.aktiv ? this.titel(z) : this.t('preview.probe.aus', { titel: this.titel(z) });
  }

  aendern(text: string): void {
    this.daten.set(text);
    if (this.fehler()) this.fehler.set(null);   // erst beim nächsten Start neu prüfen
  }

  starte(event: Event): void {
    event.preventDefault();
    const ablauf = this.gewaehlt();
    if (!ablauf) return;
    const geprueft = startdatenPruefen(this.daten());
    if (!geprueft.ok) {
      this.fehler.set(geprueft.fehler);
      // Review AS-8b, Befund 4: dorthin, wo der Fehler steht — das Feld liest ihn mit vor
      this.datenFeld()?.nativeElement.focus();
      return;
    }
    this.fehler.set(null);
    this.starten.emit({ ablauf, daten: geprueft.json });
  }

  beenden(): void {
    this.starten.emit(null);
    // Review AS-8b, Befund 3: der Knopf verschwindet gleich — der Fokus bleibt in der Form
    this.startKnopf()?.nativeElement.focus();
  }
}
