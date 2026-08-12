/**
 * The three states a read-only view has besides "here is the data" (9-5a):
 * loading, failed, empty — in that precedence, in one place.
 *
 * The precedence is the reason this is a component and not a snippet. Written
 * out by hand in each view it drifted: a retry that still showed the old alert
 * looks like it failed again, and an empty list shown over an error claims the
 * data is gone when only the request was.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-async-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './async-state.component.html',
  styleUrl: './async-state.component.scss',
})
export class AsyncStateComponent {
  protected readonly t = inject(StudioLanguageService).t;

  /**
   * WHAT is being loaded — a bare noun ("Sessions", "Lauf"), no article.
   *
   * Until C1-d3a the template read `{{ label() }} werden geladen …`, so callers
   * passed a sentence subject ("Die Sessions", "Der Lauf") and the verb stayed
   * here in the plural: six of the 21 call sites rendered ungrammatical German.
   * The whole sentence is now one catalogue entry with `{label}` in it.
   */
  readonly label = input.required<string>();
  readonly loading = input(false);
  readonly error = input('');
  readonly empty = input(false);
  /** Says what would be here and how it gets here — never just "keine Daten".
   *  Already-rendered text, translated by the view that owns it. */
  readonly emptyText = input('');

  readonly retry = output<void>();

  readonly shown = computed<'loading' | 'error' | 'empty' | 'none'>(() => {
    if (this.loading()) return 'loading';
    if (this.error()) return 'error';
    if (this.empty()) return 'empty';
    return 'none';
  });
}
