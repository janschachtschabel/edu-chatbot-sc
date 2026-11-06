import {
  ChangeDetectionStrategy, Component, computed, effect, type ElementRef, inject, input, signal, untracked, viewChild,
} from '@angular/core';

import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import { NACHLADE_ZIEL, type NachladeElement } from './element-vertrag';
import { hostBruecke } from './host-bruecke';

type Stand = 'laedt' | 'bereit' | 'fehler';

const LADE_TEXT = { de: 'Wird geladen …', en: 'Loading …' } as const;

/**
 * Der gemeinsame Platzhalter für alle nachgeladenen UI-Module (Paket U3-0).
 *
 * Steht im Register an Stelle der Komponente eines Moduls mit `laden: "bei_bedarf"`. Er lädt das
 * Bündel über die Shell (`NACHLADE_ZIEL.laden`), erzeugt danach das Custom Element einmal und
 * reicht ihm bei jeder Änderung Daten, Kontext und den Zustand „beschäftigt“ weiter — dasselbe
 * Element bleibt stehen, damit sein eigener Zustand (etwa eine Auswahl) nicht verloren geht.
 * Scheitert das Laden oder definiert das Bündel das Element nicht, steht die Textfassung des
 * Blocks: eine Antwort bleibt lesbar wie bei einem unbekannten Modul.
 */
@Component({
  selector: 'boerdi-nachlade-platzhalter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @switch (stand()) {
      @case ('laedt') {
        <p class="nachladen__stand" role="status" aria-busy="true">{{ ladeText() }}</p>
      }
      @case ('fehler') {
        <div class="nachladen__text" [innerHTML]="rueckfall()"></div>
      }
    }
    <div #ort class="nachladen__ort"></div>
  `,
  styles: [`
    :host { display: block; }
    .nachladen__stand { margin: 0; color: var(--mat-sys-on-surface-variant); }
  `],
})
export class NachladePlatzhalter {
  readonly daten = input.required<Record<string, unknown>>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);
  private readonly ziel = inject(NACHLADE_ZIEL);
  private readonly bruecke = hostBruecke(this.host);
  private readonly ort = viewChild<ElementRef<HTMLElement>>('ort');
  private element: NachladeElement | null = null;

  protected readonly stand = signal<Stand>('laedt');
  protected readonly ladeText = computed(() => LADE_TEXT[this.kontext().sprache] ?? LADE_TEXT.de);
  protected readonly rueckfall = computed(() => this.host.markdown(this.ziel.text));

  constructor() {
    this.ziel.laden().then(
      () => this.stand.set(customElements.get(this.ziel.element) ? 'bereit' : 'fehler'),
      () => this.stand.set('fehler'),
    );
    effect(() => {
      const ort = this.ort()?.nativeElement;
      if (this.stand() !== 'bereit' || !ort) return;
      const daten = this.daten();
      const kontext = this.kontext();
      const beschaeftigt = this.host.beschaeftigt();
      // Die Zuweisungen außerhalb der Verfolgung: das Element zeichnet sich dabei neu und liest
      // über die Brücke Signale der Shell (`link`, `beschaeftigt`) — die sollen den Effekt nicht
      // erneut auslösen. Er hängt nur an Daten, Kontext und „beschäftigt“.
      untracked(() => this.zuweisen(ort, daten, kontext, beschaeftigt));
    });
  }

  private zuweisen(ort: HTMLElement, daten: Record<string, unknown>, kontext: ModulKontext, beschaeftigt: boolean): void {
    let element = this.element;
    if (!element) {
      element = ort.ownerDocument.createElement(this.ziel.element) as NachladeElement;
      element.host = this.bruecke;
    }
    element.daten = daten;
    element.kontext = kontext;
    element.beschaeftigt = beschaeftigt;
    // Erst mit allen Eigenschaften einhängen: `connectedCallback` sieht schon Daten und Host.
    if (!this.element) {
      this.element = element;
      ort.appendChild(element);
    }
  }
}
