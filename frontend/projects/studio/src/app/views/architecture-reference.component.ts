/**
 * The architecture reference (9-5f / A5, port of ALT `InfoView.tsx`).
 *
 * ALT hand-rolled the disclosure: a `useState(open)` per section plus a `<button>`
 * that toggled it. Here it is `<details>`/`<summary>`, which is keyboard-operable,
 * announced as expandable, and findable by the browser's in-page search even
 * while collapsed. The styling reuses `_section-shell.scss`, the partial 9-4b
 * already wrote for exactly this shape.
 *
 * The long rows live in `reference-data.ts`. The remaining sections are section
 * components of their own, each with its own reason to change:
 *
 *  - `reference-flow`      — how the elements influence each other + one turn
 *  - `reference-catalogs`  — signals and material types, read LIVE from config
 *  - `reference-knowledge` — RAG/MCP, the topic-page resolver, snapshots
 *  - `reference-widget`    — the widget's public host contract
 *
 * Everything here was checked against NEU before it shipped; where an ALT claim
 * did not survive that check, the correction sits at the data row or in the
 * component that owns the section.
 */
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { ReferenceCatalogsComponent } from './reference-catalogs.component';
import type { SignalElement } from './reference-catalogs';
import {
  INPUT_DIMENSIONS, MODULATION_CONTROL, MODULATION_STYLE, PIPELINE, PROMPT_LAYERS,
  SELECTION_STEPS,
} from './reference-data';
import { ReferenceFlowComponent } from './reference-flow.component';
import { ReferenceKnowledgeComponent } from './reference-knowledge.component';
import { ReferenceWidgetComponent } from './reference-widget.component';
import { RichTextComponent } from './rich-text.component';

@Component({
  selector: 'studio-architecture-reference',
  imports: [
    ReferenceFlowComponent, ReferenceCatalogsComponent, ReferenceKnowledgeComponent,
    ReferenceWidgetComponent, RichTextComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './architecture-reference.component.html',
  styleUrl: './architecture-reference.component.scss',
})
export class ArchitectureReferenceComponent {
  private readonly lang = inject(StudioLanguageService);

  /** Die Prosa dieses Abschnitts (C1-d5a1) aus `i18n/catalogue/reference.ts`. */
  protected readonly t = this.lang.t;

  /** Neun Sätze tragen `<code>` oder `<strong>` mitten im Satz; sie kommen als
   *  Stücke herein und werden von `<studio-rich>` gerendert. */
  protected readonly rich = this.lang.rich;

  /** From the front page's `/config/elements` read — the signal table is data,
   *  not prose, and asking a second time would let the two halves disagree. */
  readonly signals = input<readonly SignalElement[]>([]);

  readonly pipeline = PIPELINE;
  readonly dimensions = INPUT_DIMENSIONS;
  readonly modulationStyle = MODULATION_STYLE;
  readonly modulationControl = MODULATION_CONTROL;
  readonly selection = SELECTION_STEPS;
  readonly layers = PROMPT_LAYERS;
}
