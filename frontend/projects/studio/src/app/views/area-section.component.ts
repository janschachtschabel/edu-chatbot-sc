/**
 * One config area as a disclosure panel inside a curated view (9-4b).
 *
 * `<details>`/`<summary>` on purpose: an accordion built from divs needs
 * `aria-expanded`, `aria-controls`, a button role and its own key handling —
 * four things to get wrong. The native element brings all of them, and it
 * keeps working when the stylesheet does not load.
 *
 * A section loads the first time it is opened, not on arrival: a page with
 * five areas would otherwise fire ten requests for the one section the editor
 * came for. Closing and reopening does NOT reload — that would throw away
 * unsaved edits, and the disclosure triangle is not a "discard" control.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ConfigApi } from '../core/config-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AreaDocEditor } from '../schema-form/area-doc-editor';
import { SchemaFormComponent } from '../schema-form/schema-form.component';
import type { CuratedAreaSection, Hinweis } from './curated-views';
import { EffectBadgeComponent } from './effect-badge.component';
import { feldAusschnitt } from './feld-ausschnitt';
import { SafetyLevelComponent } from './safety-level.component';
import { SaveConflictComponent } from './save-conflict.component';

@Component({
  selector: 'studio-area-section',
  imports: [
    EffectBadgeComponent, RouterLink, SafetyLevelComponent, SaveConflictComponent,
    SchemaFormComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './area-section.component.html',
  styleUrl: './area-section.component.scss',
})
export class AreaSectionComponent {
  readonly section = input.required<CuratedAreaSection>();
  /** Whether the panel starts open. Later opening comes from the DOM event. */
  readonly open = input(false);
  /** After a successful save — a tabbed page counts again (ST-4c, Paket 6). */
  readonly changed = output<void>();

  private readonly config = inject(ConfigApi);
  protected readonly t = inject(StudioLanguageService).t;
  readonly editor = new AreaDocEditor(this.config, this.t);

  readonly area = computed(() => this.section().area);
  /** Paket 14 (B1) / 15: der Feld-Ausschnitt dieser Seite; `null` = alle Felder. */
  readonly felder = computed(() => feldAusschnitt(this.editor.schema(), this.section()));
  /** Route segments for the raw editor — `/` is a path separator, not a key. */
  readonly rawLink = computed(() => ['/bereich', ...this.area().split('/')]);
  /** Review-Runde 2: die Seite, auf der der Abschnitt steht — der Editor führt dorthin zurück
   *  (ein Bereich kann auf mehreren Seiten stehen; die erste wäre oft die falsche). */
  readonly rawQuery = (() => {
    const seite = inject(ActivatedRoute, { optional: true })?.snapshot?.routeConfig?.path;
    return seite ? { von: seite } : null;
  })();
  /** Unique per section, so two forms on one page cannot share a field id. */
  readonly idPrefix = computed(() => `cs-${this.area().replace(/[^\w-]/g, '-')}`);
  /** Auch ein nicht lesbarer Feld-Entwurf ist ungespeicherte Arbeit (Review-Runde 2). */
  readonly dirty = this.editor.verwerfbar;
  /** Paket 15: Hinweise des Abschnitts zum aktuellen Entwurf (`CuratedAreaSection.hinweise`). */
  readonly hinweise = computed(() => this.section().hinweise?.(this.editor.doc()) ?? []);

  hinweisText(hinweis: Hinweis): string {
    return typeof hinweis === 'string' ? this.t(hinweis) : this.t(hinweis.key, hinweis.params);
  }

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  /** Load once. Retrying after a failure is the `async.retry` button. */
  ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.editor.load(this.area());
  }

  reload(): void {
    void this.editor.load(this.area());
  }

  /** `force`: „Trotzdem speichern" after a conflict (Paket 4, D5). */
  save(force = false): void {
    void this.editor.save(this.area(), { force }).then((saved) => {
      if (saved) this.changed.emit();
    });
  }
}
