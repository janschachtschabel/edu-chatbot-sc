/**
 * Eine kuratierte Seite als Reiter mit Zählern (Paket 6, S2 — ST-4c).
 *
 * So zeigte ALT die Dimensionen: ein Reiter je Achse, die Zahl daneben, und
 * oben eine Kopfkarte, die alle Achsen mit ihrer Anzahl nennt. NEU stapelte
 * dieselben acht Bereiche als aufklappbare Abschnitte untereinander.
 *
 * - Die Zahlen kommen aus EINEM Abruf (`/config/elements`, wie die Übersicht)
 *   und werden nach jedem Speichern, Anlegen oder Löschen in einem Reiter neu
 *   geholt (`changed`).
 * - Ein Reiter wird beim ersten Öffnen eingehängt und bleibt es: offene
 *   Änderungen überleben den Wechsel, und der Verlassen-Schutz sieht sie
 *   (`dirty`). Verborgen wird mit `hidden`, nicht durch Aushängen.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, signal, viewChildren,
} from '@angular/core';

import { OverviewApi } from '../core/overview-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AreaSectionComponent } from './area-section.component';
import type { CuratedAreaSection } from './curated-views';
import { GroupSectionComponent } from './group-section.component';
import { type ElementCounts, elementCounts } from './overview-cards';
import { TabBarComponent, type TabDef } from './tab-bar.component';

interface Reiter extends TabDef {
  readonly section: CuratedAreaSection;
}

@Component({
  selector: 'studio-curated-tabs',
  imports: [AreaSectionComponent, GroupSectionComponent, TabBarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './curated-tabs.component.html',
  styleUrl: './curated-tabs.component.scss',
})
export class CuratedTabsComponent {
  readonly sections = input.required<readonly CuratedAreaSection[]>();
  /** Der Name der Reiterleiste für Screenreader — der Name der Seite. */
  readonly label = input.required<string>();

  private readonly overview = inject(OverviewApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly counts = signal<ElementCounts | null>(null);
  readonly countsFailed = signal(false);
  private readonly wanted = signal('');
  /** Reiter, die schon offen waren — sie bleiben eingehängt. */
  readonly visited = signal<ReadonlySet<string>>(new Set());
  private zaehlung = 0;

  readonly tabs = computed<readonly Reiter[]>(() => {
    const counts = this.counts();
    return this.sections().map((section) => ({
      id: `ct-${section.area.replace(/[^\w-]/g, '-')}`,
      label: this.t(section.labelKey),
      count: section.count && counts ? counts[section.count] : undefined,
      section,
    }));
  });

  readonly active = computed(() => {
    const ids = this.tabs().map((tab) => tab.id);
    return ids.includes(this.wanted()) ? this.wanted() : (ids[0] ?? '');
  });

  /** Die Zeilen der Kopfkarte: je gezählter Achse „2 Personas — wer fragt". */
  readonly cardRows = computed<readonly string[]>(() => {
    const counts = this.counts();
    if (!counts) return [];
    return this.sections().flatMap((section) => section.count
      ? [this.lang.plural(`curated.card.${section.count}`, counts[section.count])]
      : []);
  });

  private readonly areaSections = viewChildren(AreaSectionComponent);
  private readonly groupSections = viewChildren(GroupSectionComponent);
  /** Für den Verlassen-Schutz der Seite: offene Änderungen in irgendeinem Reiter. */
  readonly dirty = computed(() =>
    [...this.areaSections(), ...this.groupSections()].some((section) => section.dirty()));

  constructor() {
    void this.zaehlen();
  }

  select(id: string): void {
    // Auch der bisher offene Reiter bleibt eingehängt — der erste ist nur über
    // die Vorgabe offen und stünde sonst nicht in `visited`; seine offenen
    // Änderungen gingen beim Wechsel verloren.
    const vorher = this.active();
    this.wanted.set(id);
    this.visited.update((schon) => new Set([...schon, vorher, id]));
  }

  isMounted(id: string): boolean {
    return id === this.active() || this.visited().has(id);
  }

  /** Die Zahlen neu holen. Scheitert das, fehlen nur die Zahlen — die Reiter
   *  arbeiten ohne sie, und die Kopfkarte sagt es. Nur die Antwort des
   *  jüngsten Abrufs zählt (Review Paket 6): zwei schnelle Änderungen hintereinander
   *  ließen sonst die ältere Zahl stehen. */
  async zaehlen(): Promise<void> {
    const mine = ++this.zaehlung;
    try {
      const counts = elementCounts(await this.overview.elements());
      if (mine !== this.zaehlung) return;
      this.counts.set(counts);
      this.countsFailed.set(false);
    } catch {
      if (mine === this.zaehlung) this.countsFailed.set(true);
    }
  }
}
