/**
 * Vorschau eines UI-Moduls mit den Beispielen seines Manifests (Paket U1-f, Plan §16 F-7).
 *
 * Gerendert wird die ECHTE Komponente aus dem Register von `@boerdi/ui-module` — dieselbe, die
 * das Widget zeigt —, in einem Rahmen mit dem M3-Theme des Widgets (`theme/_m3-theme.scss`), denn
 * das Studio hat die `--mat-sys-*`-Token sonst nicht. Den Host stellt `VorschauModulHost`: nichts
 * verlässt die Seite. Links öffnen nicht (Klick und Mittelklick werden hier abgefangen), alles
 * Übrige sagt die Statuszeile an. Abgefangen wird in der Capture-Phase am Host: ein Modul darf
 * einen Klick anhalten (`wlo-card-tile` ruft `stopPropagation`) — bis zur Bühne bubbelt er dann
 * nie (Review U1-f, Befund 1).
 *
 * Sprache (WCAG 3.1.2, Review U1-f, Befund 5): Beispieltitel, Beispieldaten und die Bühne tragen
 * `lang="de"` — die Beispiele der Manifeste sind deutsch und machen den Text der Bühne aus. Die
 * kurzen Bedienwörter der Module folgen der Studio-Sprache; im englischen Studio stehen sie damit
 * in einem deutsch ausgezeichneten Bereich — bewusst hingenommen (Plan §16, Review U1-f).
 *
 * Je Beispiel (und Zustand) ein eigener Injector: `NgComponentOutlet` erzeugt das Modul dann neu,
 * ein Modul behält keinen Zustand aus dem vorigen Beispiel (aufgeklappte Knoten, gezählte Kacheln).
 * Kennt das Studio das Modul nicht oder passt die Hauptversion nicht (anderer Widget-Stand als
 * das Backend), stehen Hinweis und Beispieldaten da — wie die Textfassung im Widget.
 */
import { NgComponentOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy, Component, computed, DestroyRef, ElementRef, inject, Injector, input,
  linkedSignal,
} from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';

import { MarkdownRenderer } from '@boerdi/ui';
import type { ResultGroupsContext } from '@boerdi/ui/grouping/result-grouping';
import { DE } from '@boerdi/ui/i18n/de';
import { createTranslator } from '@boerdi/ui/i18n/dictionary';
import { EN } from '@boerdi/ui/i18n/en';
import { MODUL_HOST, TREFFERLISTE, UI_MODUL_REGISTER } from '@boerdi/ui-module';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { type UiModulEintrag, vorschauKontext } from './ui-module';
import { VorschauModulHost } from './ui-modul-vorschau-host';

let zaehler = 0;

@Component({
  selector: 'studio-ui-modul-vorschau',
  imports: [NgComponentOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './ui-modul-vorschau.component.html',
  styleUrl: './ui-modul-vorschau.component.scss',
})
export class UiModulVorschauComponent {
  readonly eintrag = input.required<UiModulEintrag>();

  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  private readonly register = inject(UI_MODUL_REGISTER);
  private readonly injector = inject(Injector);
  private readonly sanitizer = inject(DomSanitizer);

  /** Eindeutig je Instanz: zwei Vorschauen auf einer Seite teilen keine Radio-Gruppe. */
  protected readonly gruppe = `umv-beispiel-${++zaehler}`;

  protected readonly sprache = computed<'de' | 'en'>(() => (this.lang.i18n.locale() === 'en' ? 'en' : 'de'));
  protected readonly beispiele = computed(() => this.eintrag().manifest.beispiele ?? []);
  /** Ein anderes Modul beginnt beim ersten Beispiel, offen, als Boxen. */
  protected readonly index = linkedSignal({ source: () => this.eintrag().name, computation: () => 0 });
  protected readonly beantwortet = linkedSignal({ source: () => this.eintrag().name, computation: () => false });
  protected readonly kacheln = linkedSignal({ source: () => this.eintrag().name, computation: () => false });
  /** Eine Ansage gehört zu Modul, Beispiel, Zustand und Darstellung — ein Wechsel räumt sie. */
  protected readonly meldung = linkedSignal({
    source: () => [this.eintrag().name, this.index(), this.beantwortet(), this.kacheln()],
    computation: () => '',
  });

  protected readonly beispiel = computed(() => this.beispiele()[this.index()] ?? null);
  protected readonly mitAntwort = computed(() => !!this.beispiel()?.antwort);
  protected readonly istTrefferliste = computed(() => this.eintrag().name === TREFFERLISTE);

  /** Die Komponente aus dem Register — `null`, wenn das Studio das Modul (in dieser
   *  Hauptversion) nicht kennt. */
  protected readonly komponente = computed(() => {
    const eintrag = this.register[this.eintrag().name];
    return eintrag && eintrag.manifest.version === this.eintrag().manifest.version
      ? eintrag.komponente : null;
  });

  /** Widget-Texte (Trefferboxen, Markdown) in der Sprache des Studios. */
  private readonly widgetT = computed(() =>
    this.sprache() === 'en' ? createTranslator(EN, DE) : createTranslator(DE, DE));

  private readonly renderer = computed(() => {
    const t = this.widgetT();
    return new MarkdownRenderer({
      bypassSecurityTrustHtml: (html) => this.sanitizer.bypassSecurityTrustHtml(html),
      sessionId: () => '',
      isHostTrusted: () => false,
      withBsid: (url) => url ?? '',
      t: (key, params) => t(key, params),
    });
  });

  /** Wie im Studio-Markdown: ohne Sitzung, ohne vertraute Hosts — es gibt kein Gespräch. */
  private readonly trefferKontext = computed<ResultGroupsContext>(() => ({
    withBsid: (url) => url ?? '',
    externalLinkWarning: () => '',
    isTrustedHost: () => false,
    t: this.widgetT(),
  }));

  private readonly host = new VorschauModulHost(
    (key, params) => this.melde(key, params),
    (text) => this.renderer().render(text, 'bot', false),
    () => ({ kontext: this.trefferKontext(), kacheln: this.kacheln(), beschaeftigt: false }),
  );

  protected readonly eingaben = computed(() => {
    const beispiel = this.beispiel();
    if (!beispiel) return null;
    return {
      daten: beispiel.daten,
      kontext: vorschauKontext(this.eintrag().name, this.index(), this.sprache(), beispiel,
        this.beantwortet()),
    };
  });

  /** Neu je Modul, Beispiel, Zustand und Darstellung — dann erzeugt das Outlet das Modul neu. */
  protected readonly modulInjector = computed(() => {
    this.eintrag();
    this.index();
    this.beantwortet();
    this.kacheln();
    return Injector.create({
      providers: [{ provide: MODUL_HOST, useValue: this.host }], parent: this.injector,
    });
  });

  protected readonly datenJson = computed(() => JSON.stringify(this.beispiel()?.daten ?? {}, null, 2));

  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    const klick = (event: Event) => this.abfangen(event as MouseEvent);
    const absenden = (event: Event) => {
      if (this.aufDerBuehne(event)) event.preventDefault();
    };
    host.addEventListener('click', klick, { capture: true });
    host.addEventListener('auxclick', klick, { capture: true });
    host.addEventListener('submit', absenden, { capture: true });
    inject(DestroyRef).onDestroy(() => {
      host.removeEventListener('click', klick, { capture: true });
      host.removeEventListener('auxclick', klick, { capture: true });
      host.removeEventListener('submit', absenden, { capture: true });
    });
  }

  waehle(index: number): void {
    this.index.set(index);
  }

  private aufDerBuehne(event: Event): Element | null {
    const ziel = event.target instanceof Element ? event.target : null;
    return ziel?.closest('.umv-buehne') ? ziel : null;
  }

  /** Klick (auch Tastatur-Enter, der Browser löst dann `click` aus) und Mittelklick auf einen
   *  Link der Bühne öffnen nichts. Ein Formular schickt nichts ab (`submit` oben). */
  private abfangen(event: MouseEvent): void {
    if (event.type === 'auxclick' && event.button !== 1) return;
    const link = this.aufDerBuehne(event)?.closest('a[href]') as HTMLAnchorElement | null;
    if (!link) return;
    event.preventDefault();
    this.melde('uiModule.vorschau.link', { url: link.href });
  }

  private melde(key: string, params: Readonly<Record<string, string>>): void {
    this.meldung.set(this.t(key, { ...params }));
  }
}
