/**
 * One session's conversation (9-5a) — what the person asked and what the bot
 * answered, with the routing decision behind each answer.
 *
 * The debug block is the reason this view exists at all: pattern, intent, state
 * and the tools that ran are how an editor tells "the bot chose the wrong
 * pattern" from "the pattern is worded badly". Since ST-8a each answer also
 * shows its engine, tokens and — in agent mode — the rounds of the loop; since
 * Paket 18C/D its error number and its turn record (tool calls with arguments,
 * rewrites), and a search hit (`fokus`) jumps to its message.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked }
  from '@angular/core';

import { AsyncData } from '../core/async-data';
import { injectFocus } from '../core/inject-focus';
import { SessionsApi, TRANSCRIPT_LIMIT, type SessionMessage } from '../core/sessions-api.service';
import { AgentTraceComponent } from './agent-trace.component';
import { AsyncStateComponent } from './async-state.component';
import { ZugakteComponent } from './zugakte.component';
import { fehlernummer } from './zugakte';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { StudioFormat } from '../i18n/studio-format.service';

@Component({
  selector: 'studio-session-transcript',
  imports: [AgentTraceComponent, AsyncStateComponent, ZugakteComponent],
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
  /** The message an error-number search led to (Paket 18C/D): highlighted and
   *  focused once it is loaded — focus moves the view there, too. One object per
   *  search; a reload of the same transcript does not jump again. */
  readonly fokus = input<{ readonly messageId: number } | null>(null);

  readonly messages = new AsyncData<SessionMessage[]>(() => this.api.messages(this.sessionId()), this.t);
  /** Derived, not mirrored into a second signal — an effect that only copies a
   *  value is a computed with extra steps and one more thing to keep in sync. */
  readonly rows = computed<readonly SessionMessage[]>(() => this.messages.value() ?? []);

  /** Die Suche führte zu einer Nachricht außerhalb der geladenen 200 (Review 2026-10-30): bis
   *  dahin hieß es „gefunden, geöffnet“, und nichts war markiert. */
  readonly fokusFehlt = computed(() => {
    const ziel = this.fokus();
    const geladen = this.messages.value();
    // Erst nach fertigem Laden (Review 18G-5): `value()` ist bis dahin `null` bzw. noch der
    // Verlauf der vorigen Sitzung — der Hinweis blitzte sonst bei jedem Öffnen auf.
    return !!ziel && geladen !== null && !this.messages.loading() && !this.messages.error()
      && !geladen.some((m) => m.id === ziel.messageId);
  });
  protected readonly limit = TRANSCRIPT_LIMIT;

  private readonly focus = injectFocus();
  private fokussiert: object | null = null;

  constructor() {
    effect(() => {
      this.sessionId();
      // Paket 19 (N-39): eine andere Sitzung — der Verlauf der vorigen gilt nicht mehr.
      untracked(() => {
        this.messages.clear();
        void this.load();
      });
    });
    effect(() => {
      const ziel = this.fokus();
      if (ziel && ziel !== this.fokussiert && this.rows().some((m) => m.id === ziel.messageId)) {
        this.fokussiert = ziel;
        untracked(() => this.focus(`#st-msg-${ziel.messageId}`));
      }
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
    const nummer = message.role === 'assistant' ? fehlernummer(message.trace_id) : '';
    if (nummer) out.push({ label: this.t('st.fact.errorNumber'), value: nummer });
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
