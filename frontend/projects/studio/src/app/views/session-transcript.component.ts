/**
 * One session's conversation (9-5a) — what the person asked and what the bot
 * answered, with the routing decision behind each answer.
 *
 * The debug block is the reason this view exists at all: pattern, intent, state
 * and the tools that ran are how an editor tells "the bot chose the wrong
 * pattern" from "the pattern is worded badly".
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked }
  from '@angular/core';

import { AsyncData } from '../core/async-data';
import { SessionsApi, type SessionMessage } from '../core/sessions-api.service';
import { AsyncStateComponent } from './async-state.component';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { StudioFormat } from '../i18n/studio-format.service';

@Component({
  selector: 'studio-session-transcript',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './session-transcript.component.html',
  styleUrl: './session-transcript.component.scss',
})
export class SessionTranscriptComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = inject(StudioLanguageService).t;

  private readonly api = inject(SessionsApi);

  readonly sessionId = input.required<string>();

  readonly messages = new AsyncData<SessionMessage[]>(() => this.api.messages(this.sessionId()), this.t);
  /** Derived, not mirrored into a second signal — an effect that only copies a
   *  value is a computed with extra steps and one more thing to keep in sync. */
  readonly rows = computed<readonly SessionMessage[]>(() => this.messages.value() ?? []);

  constructor() {
    effect(() => {
      this.sessionId();
      untracked(() => void this.load());
    });
  }

  async load(): Promise<void> {
    await this.messages.reload();
  }

  /** The facts behind one answer, already filtered to what is actually set. */
  facts(message: SessionMessage): { label: string; value: string }[] {
    const debug = message.debug;
    if (!debug) return [];
    const out: { label: string; value: string }[] = [];
    if (debug.pattern) out.push({ label: this.t('st.fact.pattern'), value: debug.pattern });
    if (debug.intent) out.push({ label: this.t('st.fact.intent'), value: debug.intent });
    if (debug.persona) out.push({ label: this.t('st.fact.persona'), value: debug.persona });
    if (debug.state) out.push({ label: this.t('st.fact.state'), value: debug.state });
    if (debug.tools_called?.length) {
      out.push({ label: this.t('st.fact.tools'), value: debug.tools_called.join(', ') });
    }
    if (debug.signals?.length) {
      out.push({ label: this.t('st.fact.signals'), value: debug.signals.join(', ') });
    }
    return out;
  }

  /** Erlaubnisliste statt zusammengesetztem Schlüssel: eine unbekannte Rolle
   *  kommt roh durch, wie schon vor C1-d4e2. */
  roleLabel(role: string): string {
    if (role === 'user') return this.t('st.role.user');
    if (role === 'assistant') return this.t('st.role.assistant');
    return role || this.t('sv.unknown');
  }

  /** Empty for a message the backend stored without one — the template's
   *  `@if` then drops the element instead of rendering an empty span. */
  formatTime(iso: string | undefined): string {
    return iso ? this.fmt.dateTime(iso) : '';
  }
}
