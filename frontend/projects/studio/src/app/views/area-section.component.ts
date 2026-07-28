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
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { ConfigApi } from '../core/config-api.service';
import { AreaDocEditor } from '../schema-form/area-doc-editor';
import { SchemaFormComponent } from '../schema-form/schema-form.component';
import type { CuratedAreaSection } from './curated-views';
import { SafetyLevelComponent } from './safety-level.component';

@Component({
  selector: 'studio-area-section',
  imports: [RouterLink, SafetyLevelComponent, SchemaFormComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './area-section.component.html',
  styleUrl: './area-section.component.scss',
})
export class AreaSectionComponent {
  readonly section = input.required<CuratedAreaSection>();
  /** Whether the panel starts open. Later opening comes from the DOM event. */
  readonly open = input(false);

  private readonly config = inject(ConfigApi);
  readonly editor = new AreaDocEditor(this.config);

  readonly area = computed(() => this.section().area);
  /** Route segments for the raw editor — `/` is a path separator, not a key. */
  readonly rawLink = computed(() => ['/bereich', ...this.area().split('/')]);
  /** Unique per section, so two forms on one page cannot share a field id. */
  readonly idPrefix = computed(() => `cs-${this.area().replace(/[^\w-]/g, '-')}`);
  readonly dirty = this.editor.dirty;

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  /** Load once. Retrying after a failure is the "Erneut versuchen" button. */
  ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.editor.load(this.area());
  }

  reload(): void {
    void this.editor.load(this.area());
  }

  save(): void {
    void this.editor.save(this.area());
  }
}
