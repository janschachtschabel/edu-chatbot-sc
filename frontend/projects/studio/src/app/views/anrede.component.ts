/**
 * Anrede je Zielgruppe (Paket 14, C2) — das Panel „Anrede“, seit Paket 15 auf „Zielgruppen“.
 *
 * Der Agent-Kopf liest aus jeder Persona nur `label` und `formality` (`services/agent_kopf.py`).
 * Die Zuordnung Zielgruppe → du/Sie gilt für beide Maschinen und bleibt in den Persona-Dokumenten
 * (Entscheid 2026-08-18/-21/-28); dieses Panel zeigt deshalb nur diese beiden Felder und
 * speichert je Zeile das GANZE Dokument, bedingt auf seine Version — wie jeder Abschnitt, mit
 * derselben Konflikt-Komponente nach einem 409. Eine ungespeicherte Wahl zählt für den
 * Verlassen-Schutz der Seite (`dirty`).
 *
 * Geladen erst beim Aufklappen: eine Liste (`/config/elements`) und je Persona ihr Dokument.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked,
} from '@angular/core';

import { describeApiError } from '../core/async-data';
import { type AreaDocument, ConfigApi, saveCondition } from '../core/config-api.service';
import { OverviewApi } from '../core/overview-api.service';
import { type SaveConflict, StudioApiError } from '../core/studio-api-error';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import { SaveConflictComponent } from './save-conflict.component';

/** Die Werte von `formality`, die der Agent-Kopf kennt (`agent_kopf._ANREDE`). */
export const ANREDEN = ['siezen', 'duzen', 'wie_user', 'neutral'] as const;

interface Zeile {
  readonly area: string;
  readonly kennung: string;
  readonly name: string;
  readonly doc: AreaDocument | null;
  readonly gewaehlt: string;
  readonly busy: boolean;
  readonly gespeichert: boolean;
  readonly fehler: string;
  readonly konflikt: SaveConflict | null;
}

interface PersonaEintrag {
  readonly id?: string;
  readonly label?: string;
  readonly file?: string;
}

function formality(doc: AreaDocument | null): string {
  const fm = doc?.data['frontmatter'] as Record<string, unknown> | undefined;
  return typeof fm?.['formality'] === 'string' ? fm['formality'] : '';
}

@Component({
  selector: 'studio-anrede',
  imports: [SaveConflictComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './anrede.component.html',
  styleUrl: './anrede.component.scss',
})
export class AnredeComponent {
  private readonly config = inject(ConfigApi);
  private readonly overview = inject(OverviewApi);
  protected readonly t = inject(StudioLanguageService).t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly zeilen = signal<readonly Zeile[]>([]);
  readonly laedt = signal(false);
  readonly listenFehler = signal('');
  readonly anreden = ANREDEN;

  readonly geladen = computed(() => !this.laedt() && !this.listenFehler());
  readonly dirty = computed(() => this.zeilen().some((zeile) => this.geaendert(zeile)));

  private gestartet = false;

  constructor() {
    effect(() => {
      if (this.open()) untracked(() => this.ensureLoaded());
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  private ensureLoaded(): void {
    if (this.gestartet) return;
    this.gestartet = true;
    void this.laden();
  }

  async laden(): Promise<void> {
    this.laedt.set(true);
    this.listenFehler.set('');
    try {
      const personas = ((await this.overview.elements()).personas ?? []) as PersonaEintrag[];
      const zeilen = personas.filter((p) => p.file).map((p) => ({
        area: String(p.file).replace(/\.md$/, ''),
        kennung: String(p.id ?? ''),
        name: String(p.label || p.id || ''),
      }));
      const docs = await Promise.all(zeilen.map((z) => this.config.data(z.area)));
      this.zeilen.set(zeilen.map((z, i) => ({
        ...z, doc: docs[i], gewaehlt: formality(docs[i]),
        busy: false, gespeichert: false, fehler: '', konflikt: null,
      })));
    } catch (err) {
      this.listenFehler.set(describeApiError(err, this.t));
    } finally {
      this.laedt.set(false);
    }
  }

  geaendert(zeile: Zeile): boolean {
    return zeile.gewaehlt !== formality(zeile.doc);
  }

  /** Ein unbekannter Wert (alter Stand) bleibt sichtbar, statt still „Sie“ zu zeigen. */
  unbekannt(zeile: Zeile): boolean {
    return !(ANREDEN as readonly string[]).includes(zeile.gewaehlt);
  }

  waehle(area: string, wert: string): void {
    this.aendere(area, { gewaehlt: wert, gespeichert: false, fehler: '' });
  }

  /** `force` nach einem Konflikt: gegen genau die gemeldete Version (wie `AreaDocEditor`). */
  async speichern(zeile: Zeile, force = false): Promise<void> {
    if (!zeile.doc || zeile.busy) return;
    const version = force && zeile.konflikt ? zeile.konflikt.version : zeile.doc.version;
    this.aendere(zeile.area, { busy: true, fehler: '' });
    const fm = (zeile.doc.data['frontmatter'] ?? {}) as Record<string, unknown>;
    try {
      const doc = await this.config.saveData(
        zeile.area, { ...zeile.doc.data, frontmatter: { ...fm, formality: zeile.gewaehlt } },
        saveCondition(version));
      this.aendere(zeile.area, { doc, gewaehlt: formality(doc), gespeichert: true, konflikt: null });
    } catch (err) {
      if (err instanceof StudioApiError && err.status === 409) {
        this.aendere(zeile.area, {
          konflikt: err.conflict ?? { version: null, updatedBy: null, updatedAt: null },
        });
      } else {
        this.aendere(zeile.area, { fehler: describeApiError(err, this.t) });
      }
    } finally {
      this.aendere(zeile.area, { busy: false });
    }
  }

  async neuLaden(zeile: Zeile): Promise<void> {
    try {
      const doc = await this.config.data(zeile.area);
      this.aendere(zeile.area, {
        doc, gewaehlt: formality(doc), fehler: '', konflikt: null, gespeichert: false,
      });
    } catch (err) {
      this.aendere(zeile.area, { fehler: describeApiError(err, this.t) });
    }
  }

  private aendere(area: string, teil: Partial<Zeile>): void {
    this.zeilen.update((alle) => alle.map((z) => (z.area === area ? { ...z, ...teil } : z)));
  }
}
