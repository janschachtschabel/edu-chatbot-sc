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
import type { OriginScope } from '../core/origin-scope';
import { SessionsApi, type SessionRow } from '../core/sessions-api.service';
import { AsyncStateComponent } from './async-state.component';
import { OriginScopeComponent } from './origin-scope.component';
import { SessionTranscriptComponent } from './session-transcript.component';
import { type ZugZiel, ZugSucheComponent } from './zug-suche.component';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { StudioFormat } from '../i18n/studio-format.service';

/** Which destructive action is armed, for which session. */
interface Armed {
  readonly id: string;
  readonly kind: 'delete' | 'clear';
}

@Component({
  selector: 'studio-sessions',
  imports: [AsyncStateComponent, OriginScopeComponent, SessionTranscriptComponent, ZugSucheComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './sessions.component.html',
  styleUrl: './sessions.component.scss',
})
export class SessionsComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;

  private readonly api = inject(SessionsApi);

  /** ST-9: nach Herkunft — serverseitig, die Liste kappt bei 100. */
  // Vorgabe Produktion (Studio-Rundgang 2026-10-18); die anderen bleiben wählbar.
  readonly scope = signal<OriginScope>('production');

  readonly sessions = new AsyncData<SessionRow[]>(() => this.api.list(this.scope()), this.t);
  readonly rows = computed(() => this.sessions.value() ?? []);

  /** Bis C1-d4e2 stand die deutsche Mehrzahl-Regel in der Vorlage. */
  turnCount(count: number): string {
    return this.lang.plural('sv.turns', count);
  }

  readonly selected = signal('');
  /** The message an error-number search led to (Paket 18C/D) — cleared by a
   *  plain pick, so the highlight never outlives the search that set it. A fresh
   *  object per search: the same number searched twice jumps again. */
  readonly fokus = signal<{ readonly messageId: number } | null>(null);
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

  setScope(scope: OriginScope): void {
    if (scope === this.scope()) return;
    this.scope.set(scope);
    this.reload();
  }

  select(id: string): void {
    this.fokus.set(null);
    this.selected.set(this.selected() === id ? '' : id);
  }

  /** A search hit: open its session — also one outside the filtered list — at
   *  the message. */
  open(ziel: ZugZiel): void {
    this.selected.set(ziel.sessionId);
    this.fokus.set({ messageId: ziel.messageId });
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
        this.status.set(this.t('sv.deleted'));
      } else {
        await this.api.clearMessages(armed.id);
        // The selection stays: closing the panel of the conversation someone is
        // reading is not feedback, it is a disappearance. The transcript
        // re-reads instead and shows that it is now empty.
        this.transcript()?.load();
        this.status.set(this.t('sv.cleared'));
      }
      this.armed.set(null);
      await this.sessions.reload();
    } catch (err) {
      this.actionError.set(describeApiError(err, this.t));
    } finally {
      this.working.set(false);
    }
  }

  formatTime(iso: string): string {
    return this.fmt.dateTime(iso);
  }
}
