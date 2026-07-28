/**
 * The widget-embedding section of the architecture reference (9-5f / A5).
 *
 * Its own component, not a block in the host template, because it documents a
 * different thing for a different reason: the public host contract of
 * `<boerdi-chat>` (§5.5) rather than the prompt architecture. Data in
 * `widget-contract-data.ts`, pinned from the widget project's own spec.
 */
import { ChangeDetectionStrategy, Component } from '@angular/core';

import {
  EMBED_SAMPLE, HOST_ATTRIBUTES, HOST_EVENTS, HOST_OUTPUTS,
} from './widget-contract-data';

@Component({
  selector: 'studio-reference-widget',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-widget.component.html',
  styleUrl: './reference-widget.component.scss',
})
export class ReferenceWidgetComponent {
  readonly attributes = HOST_ATTRIBUTES;
  readonly events = HOST_EVENTS;
  readonly outputs = HOST_OUTPUTS.join(', ');
  readonly embedSample = EMBED_SAMPLE;

  /** True on the first row of an attribute group, so the group is named once. */
  isGroupStart(index: number): boolean {
    return index === 0 || this.attributes[index - 1].group !== this.attributes[index].group;
  }
}
