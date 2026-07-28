/**
 * The Sessions dashboard (9-5a): which conversations exist, and what was said.
 *
 * ALT's version made the whole card a `<div onClick>` with two nested buttons
 * calling `stopPropagation` — not reachable by keyboard at all. Here the row
 * title is a `<button>` and the two destructive actions are siblings, so
 * nothing nests and Tab order follows what the eye sees.
 *
 * Both destructive actions ask first. They are easy to confuse — "Verlauf
 * leeren" keeps the session and its analytics, "Löschen" takes everything —
 * so the confirmation names which one is armed.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal, viewChild }
  from '@angular/core';

import { AsyncData, describeApiError } from '../core/async-data';
import { germanDateTime } from '../core/format';
import { SessionsApi, type SessionRow } from '../core/sessions-api.service';
import { AsyncStateComponent } from './async-state.component';
import { SessionTranscriptComponent } from './session-transcript.component';

/** Which destructive action is armed, for which session. */
interface Armed {
  readonly id: string;
  readonly kind: 'delete' | 'clear';
}

@Component({
  selector: 'studio-sessions',
  imports: [AsyncStateComponent, SessionTranscriptComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './sessions.component.html',
  styleUrl: './sessions.component.scss',
})
export class SessionsComponent {
  private readonly api = inject(SessionsApi);

  readonly sessions = new AsyncData<SessionRow[]>(() => this.api.list());
  readonly rows = computed(() => this.sessions.value() ?? []);

  readonly selected = signal('');
  readonly armed = signal<Armed | null>(null);
  /** Present only while a session is selected — hence the optional call. */
  private readonly transcript = viewChild(SessionTranscriptComponent);
  readonly working = signal(false);
  readonly actionError = signal('');
  readonly status = signal('');

  constructor() {
    void this.sessions.reload();
  }

  reload(): void {
    void this.sessions.reload();
  }

  select(id: string): void {
    this.selected.set(this.selected() === id ? '' : id);
  }

  isArmed(id: string, kind: Armed['kind']): boolean {
    const armed = this.armed();
    return armed !== null && armed.id === id && armed.kind === kind;
  }

  arm(id: string, kind: Armed['kind']): void {
    this.actionError.set('');
    this.armed.set({ id, kind });
  }

  disarm(): void {
    this.armed.set(null);
  }

  async confirm(): Promise<void> {
    const armed = this.armed();
    if (!armed || this.working()) return;
    this.working.set(true);
    this.actionError.set('');
    try {
      if (armed.kind === 'delete') {
        await this.api.deleteSession(armed.id);
        if (this.selected() === armed.id) this.selected.set('');
        this.status.set('Session gelöscht.');
      } else {
        await this.api.clearMessages(armed.id);
        // The selection stays: closing the panel of the conversation someone is
        // reading is not feedback, it is a disappearance. The transcript
        // re-reads instead and shows that it is now empty.
        this.transcript()?.load();
        this.status.set('Gesprächsverlauf geleert.');
      }
      this.armed.set(null);
      await this.sessions.reload();
    } catch (err) {
      this.actionError.set(describeApiError(err));
    } finally {
      this.working.set(false);
    }
  }

  formatTime(iso: string): string {
    return germanDateTime(iso);
  }
}
