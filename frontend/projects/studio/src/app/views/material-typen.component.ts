/**
 * Materialformate (Paket 14, D3) — das Panel „Materialtypen“: Liste links, Detail rechts.
 *
 * Wie im alten Studio (`CanvasFormatsEditor.tsx`): Filter nach Kategorie, ein Eintrag je Typ,
 * Speichern der ganzen Liste. Neu sind Suche, die gerenderte Vorschau der Vorlage mit den
 * Querbezügen (Aliase, Vorrang) und das versionierte Speichern über den Bereichs-Endpunkt —
 * ein fremder Stand kommt als 409 und erscheint in der Konflikt-Komponente wie überall: der
 * Entwurf bleibt, „Neu laden“ verwirft ihn, „Trotzdem speichern“ schreibt gegen die gemeldete
 * Version (Plan §5.4).
 *
 * Ein ungespeicherter Entwurf sperrt die Liste: ein Wechsel verlöre ihn sonst ohne Rückfrage.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked,
} from '@angular/core';

import { describeApiError } from '../core/async-data';
import { type AreaDocument, ConfigApi, saveCondition } from '../core/config-api.service';
import { injectFocus } from '../core/inject-focus';
import { type MaterialTyp, pruefe } from '../core/material-types';
import { type SaveConflict, StudioApiError } from '../core/studio-api-error';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import {
  type DetailReiter, type FeldAenderung, MaterialTypDetailComponent,
} from './material-typ-detail.component';
import { SaveConflictComponent } from './save-conflict.component';

const TYPEN = '05-canvas/material-types';
const ALIASE = '05-canvas/type-aliases';
const VORRANG = '05-canvas/persona-priorities';
const NEU = '__neu__';
const LEER: MaterialTyp = { id: '', label: '', label_en: '', emoji: '', category: '', structure: '' };

type Filter = 'alle' | 'didaktisch' | 'analytisch';

@Component({
  selector: 'studio-material-typen',
  imports: [MaterialTypDetailComponent, SaveConflictComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './material-typen.component.html',
  styleUrl: './material-typen.component.scss',
})
export class MaterialTypenComponent {
  private readonly config = inject(ConfigApi);
  protected readonly t = inject(StudioLanguageService).t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly doc = signal<AreaDocument | null>(null);
  readonly aliase = signal<Readonly<Record<string, string>>>({});
  readonly analytisch = signal<readonly string[]>([]);
  readonly laedt = signal(false);
  readonly ladeFehler = signal('');

  readonly filter = signal<Filter>('alle');
  readonly suche = signal('');
  readonly gewaehlt = signal('');
  readonly entwurf = signal<MaterialTyp | null>(null);
  readonly reiter = signal<DetailReiter>('mf-vorschau');
  readonly versucht = signal(false);
  readonly busy = signal(false);
  readonly fehler = signal('');
  readonly konflikt = signal<SaveConflict | null>(null);
  /** Was der Konflikt unterbrach — „Trotzdem speichern“ wiederholt genau das. */
  private unterbrochen: 'speichern' | 'loeschen' | null = null;
  readonly meldung = signal('');
  readonly loeschFrage = signal(false);
  /** Review PR #18 (WCAG 2.4.3): die Knöpfe der Rückfrage verschwinden mit ihr. */
  private readonly focus = injectFocus();

  fragLoeschen(): void {
    this.loeschFrage.set(true);
    this.focus('.mf-frage .mf-abbrechen');
  }

  abbrechenLoeschen(): void {
    this.loeschFrage.set(false);
    this.focus('.mf-loeschen');
  }

  readonly typen = computed<readonly MaterialTyp[]>(
    () => (this.doc()?.data['material_types'] as MaterialTyp[] | undefined) ?? []);

  readonly anzahl = computed(() => ({
    alle: this.typen().length,
    didaktisch: this.typen().filter((t) => t.category === 'didaktisch').length,
    analytisch: this.typen().filter((t) => t.category === 'analytisch').length,
  }));
  readonly filterwerte: readonly Filter[] = ['alle', 'didaktisch', 'analytisch'];

  readonly liste = computed(() => {
    const filter = this.filter();
    const suche = this.suche().trim().toLowerCase();
    return this.typen()
      .filter((t) => filter === 'alle' || t.category === filter)
      .filter((t) => !suche || t.id.includes(suche) || t.label.toLowerCase().includes(suche));
  });

  readonly neu = computed(() => this.gewaehlt() === NEU);
  private readonly original = computed(
    () => (this.neu() ? LEER : this.typen().find((t) => t.id === this.gewaehlt()) ?? null));

  readonly dirty = computed(() => {
    const entwurf = this.entwurf();
    return !!entwurf && JSON.stringify(entwurf) !== JSON.stringify(this.original());
  });

  readonly pruefung = computed(() => {
    const entwurf = this.entwurf();
    return entwurf ? pruefe(this.typen(), entwurf, this.neu() ? null : this.gewaehlt()) : [];
  });
  readonly sichtbareFehler = computed(() => (this.versucht() ? this.pruefung() : []));

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
    this.ladeFehler.set('');
    try {
      const [typen, aliase, vorrang] = await Promise.all(
        [TYPEN, ALIASE, VORRANG].map((area) => this.config.data(area)));
      this.doc.set(typen);
      this.aliase.set((aliase.data['aliases'] as Record<string, string> | undefined) ?? {});
      this.analytisch.set((vorrang.data['analytical_personas'] as string[] | undefined) ?? []);
      this.zuruecksetzen(this.typen().some((t) => t.id === this.gewaehlt()) ? this.gewaehlt() : '');
    } catch (err) {
      this.ladeFehler.set(describeApiError(err, this.t));
    } finally {
      this.laedt.set(false);
    }
  }

  /** Die Abschnitte „Aliase“ und „Vorrang“ stehen auf derselben Seite (Review PR #18): nach
   *  ihrem Speichern liest die Liste beide neu — der Typen-Entwurf bleibt dabei unberührt. */
  async nebenbereicheNeu(): Promise<void> {
    if (!this.gestartet) return;
    try {
      const [aliase, vorrang] = await Promise.all(
        [ALIASE, VORRANG].map((area) => this.config.data(area)));
      this.aliase.set((aliase.data['aliases'] as Record<string, string> | undefined) ?? {});
      this.analytisch.set((vorrang.data['analytical_personas'] as string[] | undefined) ?? []);
    } catch (err) {
      this.meldung.set(describeApiError(err, this.t));
    }
  }

  waehle(id: string): void {
    if (this.dirty()) return;
    this.zuruecksetzen(id);
    this.reiter.set(id === NEU ? 'mf-bearbeiten' : 'mf-vorschau');
    this.meldung.set('');
  }

  aendere({ feld, wert }: FeldAenderung): void {
    this.entwurf.update((e) => (e ? { ...e, [feld]: wert } : e));
  }

  neuAnlegen(): void {
    this.waehle(NEU);
  }

  verwerfen(): void {
    this.zuruecksetzen(this.neu() ? '' : this.gewaehlt());
  }

  private zuruecksetzen(id: string): void {
    this.gewaehlt.set(id);
    const original = id === NEU ? LEER : this.typen().find((t) => t.id === id) ?? null;
    this.entwurf.set(original ? { ...original } : null);
    this.versucht.set(false);
    this.fehler.set('');
    this.konflikt.set(null);
    this.loeschFrage.set(false);
  }

  async speichern(): Promise<void> {
    const entwurf = this.entwurf();
    if (!entwurf || this.busy()) return;
    this.versucht.set(true);
    if (this.pruefung().length > 0) {
      // Die Fehler stehen am Formular — von der Vorschau aus bliebe der Klick sonst stumm.
      this.reiter.set('mf-bearbeiten');
      return;
    }
    const liste = this.neu() ? [...this.typen(), entwurf]
      : this.typen().map((t) => (t.id === this.gewaehlt() ? entwurf : t));
    if (await this.schreibe(liste, 'speichern')) {
      this.zuruecksetzen(entwurf.id);
      this.meldung.set(this.t('materialFormate.gespeichert'));
    }
  }

  async loeschen(): Promise<void> {
    const id = this.gewaehlt();
    if (await this.schreibe(this.typen().filter((t) => t.id !== id), 'loeschen')) {
      this.zuruecksetzen('');
      this.meldung.set(this.t('materialFormate.geloescht'));
      this.focus('.mf-neu');
    }
  }

  /** Nach einem Konflikt: dieselbe Aktion gegen die gemeldete Version. */
  async erzwingen(): Promise<void> {
    const konflikt = this.konflikt();
    const aktion = this.unterbrochen;
    if (!konflikt || !aktion) return;
    this.doc.update((doc) => (doc ? { ...doc, version: konflikt.version } : doc));
    await (aktion === 'speichern' ? this.speichern() : this.loeschen());
  }

  private async schreibe(
    liste: readonly MaterialTyp[], aktion: 'speichern' | 'loeschen',
  ): Promise<boolean> {
    const doc = this.doc();
    if (!doc) return false;
    this.busy.set(true);
    this.fehler.set('');
    try {
      this.doc.set(await this.config.saveData(TYPEN, { ...doc.data, material_types: liste },
        saveCondition(doc.version)));
      this.konflikt.set(null);
      this.unterbrochen = null;
      return true;
    } catch (err) {
      if (err instanceof StudioApiError && err.status === 409) {
        this.konflikt.set(err.conflict ?? { version: null, updatedBy: null, updatedAt: null });
        this.unterbrochen = aktion;
      } else {
        this.fehler.set(describeApiError(err, this.t));
      }
      return false;
    } finally {
      this.busy.set(false);
      this.loeschFrage.set(false);
    }
  }

  neuLaden(): void {
    this.entwurf.set(null);
    void this.laden();
  }
}
