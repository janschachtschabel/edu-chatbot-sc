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
import { germanDateTime } from '../core/format';
import { SessionsApi, type SessionMessage } from '../core/sessions-api.service';
import { AsyncStateComponent } from './async-state.component';

@Component({
  selector: 'studio-session-transcript',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './session-transcript.component.html',
  styleUrl: './session-transcript.component.scss',
})
export class SessionTranscriptComponent {
  private readonly api = inject(SessionsApi);

  readonly sessionId = input.required<string>();

  readonly messages = new AsyncData<SessionMessage[]>(() => this.api.messages(this.sessionId()));
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
    if (debug.pattern) out.push({ label: 'Muster', value: debug.pattern });
    if (debug.intent) out.push({ label: 'Intent', value: debug.intent });
    if (debug.persona) out.push({ label: 'Persona', value: debug.persona });
    if (debug.state) out.push({ label: 'Zustand', value: debug.state });
    if (debug.tools_called?.length) {
      out.push({ label: 'Werkzeuge', value: debug.tools_called.join(', ') });
    }
    if (debug.signals?.length) out.push({ label: 'Signale', value: debug.signals.join(', ') });
    return out;
  }

  roleLabel(role: string): string {
    if (role === 'user') return 'Nutzerin/Nutzer';
    if (role === 'assistant') return 'BOERDi';
    return role || 'unbekannt';
  }

  /** Empty for a message the backend stored without one — the template's
   *  `@if` then drops the element instead of rendering an empty span. */
  formatTime(iso: string | undefined): string {
    return iso ? germanDateTime(iso) : '';
  }
}
