/**
 * The studio's front page (9-5f / A5, port of ALT `HomeOverview.tsx` + the
 * `homeTab` split of `page.tsx:447-470`).
 *
 * ALT's home was two tabs — "Übersicht" and "Architektur & Referenz" — and the
 * view registry says the same thing ("Start, Architektur & Status"), which is why
 * the reference is a tab here and not a route of its own. It mounts on first
 * visit, like every other panel in 9-5.
 *
 * Three ALT behaviours are deliberately not ported:
 *
 *  - **No offline banner.** ALT took a `backendOnline` prop and painted a red
 *    card. In NEU the shell header polls `/health` and owns that state
 *    (`status-indicator.component.ts`); a second display could contradict it,
 *    and each panel here reports its own failure anyway.
 *  - **No swallowed failures.** ALT's four fetches sat in one
 *    `Promise.allSettled` whose rejections were dropped, so a broken endpoint
 *    looked like "no data" forever. Each read is its own `AsyncData` (9-5a rule)
 *    and the strip shows what failed.
 *  - **No quick-action row.** Of ALT's three buttons, two duplicated cards on
 *    this very page (Evaluation, Material-Formate) and the third opened the
 *    snapshot dialog, which is A6 and does not exist yet. It comes back with A6.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AsyncData } from '../core/async-data';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { OverviewApi } from '../core/overview-api.service';
import { ArchitectureReferenceComponent } from './architecture-reference.component';
import type { SignalElement } from './reference-catalogs';
import {
  LAYER_CARDS, OPS_CARDS, type ElementsPayload, type LayerCard, elementCounts, figureText,
  viewOf, visibleTags,
} from './overview-cards';
import { RichTextComponent } from './rich-text.component';
import { StatusStripComponent } from './status-strip.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';

/** Reiter-Kennung → Katalog-Schlüssel. Ausgeschriebene Paare statt
 *  `'overview.tab.' + id`: ein zur Laufzeit gebauter Schlüssel gäbe bei einem
 *  Tippfehler den Schlüssel selbst als Reiter-Beschriftung aus. */
const TAB_KEYS: readonly { readonly id: string; readonly labelKey: string }[] = [
  { id: 'uebersicht', labelKey: 'overview.tab.uebersicht' },
  { id: 'referenz', labelKey: 'overview.tab.referenz' },
];

@Component({
  selector: 'studio-overview',
  imports: [
    TabBarComponent, RouterLink, ArchitectureReferenceComponent, RichTextComponent,
    StatusStripComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './overview.component.html',
  styleUrl: './overview.component.scss',
})
export class OverviewComponent {
  private readonly api = inject(OverviewApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  /** Die vier Erklär-Karten am Fuss der Seite tragen `<code>` und `<strong>`
   *  mitten im Satz (C1-d5d). */
  protected readonly rich = this.lang.rich;

  /** Errechnet und nicht konstant: eine Modul-Konstante fröre die Beschriftung
   *  in der Sprache ein, die beim Laden des Moduls galt (C1-d3a). */
  readonly tabs = computed<readonly TabDef[]>(() =>
    TAB_KEYS.map((tab) => ({ id: tab.id, label: this.t(tab.labelKey) })));
  readonly active = signal(TAB_KEYS[0].id);
  private readonly visited = signal<ReadonlySet<string>>(new Set([TAB_KEYS[0].id]));
  readonly shows = computed(() => {
    const seen = this.visited();
    return (id: string): boolean => seen.has(id);
  });

  readonly layers = LAYER_CARDS;
  readonly ops = OPS_CARDS;

  readonly elements = new AsyncData<ElementsPayload>(() => this.api.elements(), this.t);


  readonly counts = computed(() => elementCounts(this.elements.value()));

  /** The same payload, for the reference tab's live signal table (A5-Rest). */
  readonly signals = computed<readonly SignalElement[]>(
    () => (this.elements.value()?.signals ?? []) as readonly SignalElement[]);

  constructor() {
    // Rundgang 3: Modell, Grundstand und letzten Lauf lädt die Statusleiste selbst.
    void this.elements.reload();
  }

  select(id: string): void {
    this.active.set(id);
    if (!this.visited().has(id)) {
      this.visited.update((seen) => new Set(seen).add(id));
    }
  }

  label(slug: string): string {
    return this.lang.t(viewOf(slug).labelKey);
  }

  desc(slug: string): string {
    return this.lang.t(viewOf(slug).descKey);
  }

  headline(card: LayerCard): string {
    return this.t(card.headlineKey);
  }

  primary(card: LayerCard): string {
    return figureText(card.primary, this.counts(), this.t);
  }

  tags(card: LayerCard): readonly string[] {
    return visibleTags(card, this.counts(), this.t);
  }
}
