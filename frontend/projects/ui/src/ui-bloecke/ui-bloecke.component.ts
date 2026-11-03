import { NgComponentOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy, Component, computed, inject, Injector, input, type Type,
} from '@angular/core';
import type { SafeHtml } from '@angular/platform-browser';

import { MODUL_HOST, UI_MODUL_REGISTER, type ModulKontext, type UiBlock } from '@boerdi/ui-module';

import type { GroupingContext } from '../grouping/result-grouping';
import type { TranslateFn } from '../i18n/i18n';
import { BlockModulHost } from './block-modul-host';
import { blockDarstellbar } from './modul-darstellbar';
import { schriftProzent } from './schrift-skala';
import { type ShellAntworten, type ShellTreffer, WidgetModulHost } from './widget-modul-host';

interface Darstellung {
  readonly block: UiBlock;
  /** `null` = Textfassung (Modul fehlt oder Version passt nicht). */
  readonly komponente: Type<unknown> | null;
  readonly eingaben: { daten: Record<string, unknown>; kontext: ModulKontext };
  /** Eigener Modul-Host des Blocks (U1-d1); `undefined` bei der Textfassung. */
  readonly injector: Injector | undefined;
}

/**
 * Der eine Platzhalter für alle UI-Module einer Antwort (Paket U1-a).
 *
 * Je Block das registrierte Modul, in der Reihenfolge der Antwort. Fehlt das Modul im Register,
 * passt die Hauptversion nicht oder fehlen die Daten, steht die Textfassung — so bleibt eine Antwort lesbar, wenn
 * Backend und eingebettetes Widget verschieden alt sind. Beantwortete und veraltete Blöcke
 * bekommen `nurLesen`. Den Modul-Host stellt dieser Platzhalter bereit (mit den Seams der Shell:
 * Übersetzer, Markdown-Renderer); Module sehen nur ihn.
 *
 * Seit U1-d1 je Block einen eigenen (`BlockModulHost` über den Injector des Outlets): mit der
 * Block-Kennung und nur den Fähigkeiten aus dem Manifest. Der Injector bleibt je Block derselbe,
 * solange Kennung und Modul gleich sind — ein neuer erzeugte das Modul neu, und eigener Zustand
 * (etwa „mehr anzeigen“ der Trefferliste) ginge verloren.
 */
@Component({
  selector: 'boerdi-ui-bloecke',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgComponentOutlet],
  styleUrl: './ui-bloecke.component.scss',
  // Ein Platz ohne Blöcke nimmt keinen Raum ein (Rand und Lücke des Hosts).
  host: { '[hidden]': '!darstellungen().length', '[class.ui-bloecke--unten]': 'platz() === "unten"' },
  template: `
    @for (d of darstellungen(); track d.block.block_id) {
      <div class="ui-block" [attr.data-modul]="d.block.modul">
        @if (d.komponente) {
          <ng-container *ngComponentOutlet="d.komponente; inputs: d.eingaben; injector: d.injector" />
        } @else {
          <div class="ui-block__text" [innerHTML]="renderMarkdown()(d.block.text ?? '')"></div>
        }
      </div>
    }
  `,
})
export class UiBloeckeComponent {
  readonly bloecke = input.required<readonly UiBlock[]>();
  readonly sprache = input.required<'de' | 'en'>();
  /** Render-Seam der Shell: fertig sanitisierter Markdown (wie bei den Bot-Antworten). */
  readonly renderMarkdown = input.required<(content: string) => SafeHtml>();
  /** Übersetzer der Shell — für die Sprachauszeichnung der Druckansicht. */
  readonly translate = input.required<TranslateFn>();
  /** Anzeige-Regeln der Nachricht; `inline_documents.font_size_percent` setzt die Schriftskala. */
  readonly displayRules = input<Record<string, unknown> | null>(null);
  /** Link-Regeln der Shell (`render.groupingCtx`) für `host.link()`. */
  readonly verweise = input.required<Pick<GroupingContext, 'withBsid' | 'externalLinkWarning'>>();
  /** `oben` vor den Trefferboxen, `unten` danach (`darstellung.platz` im Manifest). Module
   *  ohne Angabe und unbekannte Module (Textfassung) stehen oben. */
  readonly platz = input<'oben' | 'unten'>('oben');
  /** Trefferdarstellung der Shell für die Trefferliste (U1-c2). */
  readonly treffer = input.required<ShellTreffer>();
  /** Die Nachricht, zu der diese Blöcke gehören (für Aktionen wie „mehr laden“). */
  readonly nachrichtId = input.required<string>();
  /** Antwort-Weg der Shell für abfragende Module (U1-d1). */
  readonly antworten = input.required<ShellAntworten>();

  private readonly register = inject(UI_MODUL_REGISTER);
  private readonly injector = inject(Injector);
  /** Der gemeinsame Host mit den Seams der Shell; Module sehen nur ihren `BlockModulHost`. */
  private readonly basis = new WidgetModulHost(this);
  private readonly hosts = new Map<string, Injector>();

  /** Der Injector eines Blocks — einmal je Kennung und Modul angelegt. */
  private blockInjector(block: UiBlock): Injector {
    const schluessel = `${block.block_id} ${block.modul}`;
    let injector = this.hosts.get(schluessel);
    if (!injector) {
      const host = new BlockModulHost(this.basis, block.block_id,
        this.register[block.modul]?.manifest.faehigkeiten);
      injector = Injector.create({ providers: [{ provide: MODUL_HOST, useValue: host }], parent: this.injector });
      this.hosts.set(schluessel, injector);
    }
    return injector;
  }

  private readonly schriftSkala = computed(() => schriftProzent(this.displayRules()) / 100);

  protected readonly darstellungen = computed<Darstellung[]>(() =>
    this.bloecke()
      .filter((block) => (this.register[block.modul]?.manifest.darstellung?.platz ?? 'oben') === this.platz())
      .map((block) => {
      // Ohne Daten (alter Verlauf) bekäme das Modul nichts zu zeigen — dann die Textfassung. Dieselbe
      // Regel lesen die Tore der Shell (`modul-darstellbar.ts`).
      const passt = blockDarstellbar(block, this.register);
      return {
        block,
        komponente: passt ? this.register[block.modul].komponente : null,
        injector: passt ? this.blockInjector(block) : undefined,
        eingaben: {
          daten: block.daten ?? {},
          kontext: {
            blockId: block.block_id,
            sprache: this.sprache(),
            nurLesen: block.status === 'beantwortet' || block.status === 'veraltet',
            antwort: block.antwort ?? null,
            schriftSkala: this.schriftSkala(),
            anzeigeRegeln: this.displayRules(),
          },
        },
      };
    }),
  );
}
