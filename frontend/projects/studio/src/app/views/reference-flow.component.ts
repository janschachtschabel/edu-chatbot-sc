/**
 * Two sections of the architecture reference (A5-Rest): how the elements
 * influence each other, and one turn walked through end to end.
 *
 * Own component rather than more rows in the hull: the hull describes the
 * static architecture (which layers exist, what each holds), these two describe
 * a single run through it — and the hull was already at 252 lines.
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { EXAMPLE_FLOW, INFLUENCES } from './reference-flow-data';
import { RichTextComponent } from './rich-text.component';

@Component({
  selector: 'studio-reference-flow',
  imports: [RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-flow.component.html',
  styleUrl: './reference-flow.component.scss',
})
export class ReferenceFlowComponent {
  private readonly lang = inject(StudioLanguageService);

  /** Die Prosa dieses Abschnitts (C1-d5c1) aus `i18n/catalogue/reference-flow.ts`. */
  protected readonly t = this.lang.t;

  /** Nur ein Satz traegt Auszeichnung: die zitierte Beispiel-Nachricht. */
  protected readonly rich = this.lang.rich;

  readonly influences = INFLUENCES;
  readonly flow = EXAMPLE_FLOW;
}
