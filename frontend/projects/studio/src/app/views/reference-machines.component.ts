/**
 * Architektur-Referenz, erster Abschnitt: die beiden Maschinen (Paket 6, S3 —
 * Rest von ST-5). Was beide teilen, wo sie sich trennen, wer wählt — und live,
 * welche Maschine diese Anlage vorgibt (aus `/config/effects`, das die Shell
 * bei jedem Seitenwechsel holt).
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { EffectsApi } from '../core/effects-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { RichTextComponent } from './rich-text.component';

/** Die Zeilen der Gegenüberstellung — je eine Katalog-Gruppe `rm.row.<id>`. */
const ROWS = ['classify', 'steer', 'tools', 'flow', 'write'] as const;

/**
 * Die 13 Knoten von `graph/build.py` in ihrer Reihenfolge, je ein Satz
 * `rm.node.<id>`. `frueh`: der Knoten kann den Zug beenden (er setzt
 * `early_response`) — nur diese drei; der Seitenkontext läuft immer weiter.
 */
const GRAPH: readonly { readonly id: string; readonly frueh?: true }[] = [
  { id: 'setup' }, { id: 'tour', frueh: true }, { id: 'page_context_enrich' },
  { id: 'context_greeting', frueh: true }, { id: 'persist_user' },
  { id: 'preflight', frueh: true }, { id: 'assess' }, { id: 'safety_log' }, { id: 'merge' },
  { id: 'route' }, { id: 'respond' }, { id: 'assemble' }, { id: 'persist' },
];

@Component({
  selector: 'studio-reference-machines',
  imports: [RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-machines.component.html',
  styleUrl: './reference-machines.component.scss',
})
export class ReferenceMachinesComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly rich = this.lang.rich;

  private readonly effects = inject(EffectsApi).effects;

  /** Der Satz zur Vorgabe dieser Anlage; leer, solange sie nicht bekannt ist —
   *  dann sagt die Seite nichts, statt zu raten. */
  readonly currentKey = computed(() => {
    const effects = this.effects();
    return effects ? `rm.current.${effects.engine}` : '';
  });

  readonly rows = ROWS;
  readonly graph = GRAPH;
}
