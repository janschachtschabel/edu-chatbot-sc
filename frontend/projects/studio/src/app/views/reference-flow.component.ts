/**
 * Two sections of the architecture reference (A5-Rest): how the elements
 * influence each other, and one turn walked through end to end.
 *
 * Own component rather than more rows in the hull: the hull describes the
 * static architecture (which layers exist, what each holds), these two describe
 * a single run through it — and the hull was already at 252 lines.
 */
import { ChangeDetectionStrategy, Component } from '@angular/core';

import { EXAMPLE_FLOW, INFLUENCES } from './reference-flow-data';

@Component({
  selector: 'studio-reference-flow',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-flow.component.html',
  styleUrl: './reference-flow.component.scss',
})
export class ReferenceFlowComponent {
  readonly influences = INFLUENCES;
  readonly flow = EXAMPLE_FLOW;
}
