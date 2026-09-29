/**
 * Probelauf im Chat (ST-8e, AG-4 Teil A) — ein Gespräch mit der Agent-Schleife
 * über den echten Chat-Weg, mit Dauer, Token und Spur je Zug.
 *
 * Der Auftrags-Tester darunter fährt `/api/agent`, den Endpunkt der
 * Gastanwendungen, mit eigenem Prompt — er zeigt nicht, was der Agent im Chat
 * tut (Plan §2.4). Hier geht jeder Zug durch `POST /api/chat` mit
 * `X-Boerdi-Engine: agent`, wie ein Widget mit `engine="agent"`: Safety,
 * Master-Skill, Nutzungsbuchung und der Verlauf der Sitzung.
 *
 * Die Dauer misst der Browser um die Anfrage herum — sie ist das, was eine
 * Person im Widget wartet. Runden und Token kommen aus dem Debug-Block der
 * Antwort und stehen in derselben Komponente wie unter Sessions.
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, inject, input,
  signal, viewChild,
} from '@angular/core';

import { describeApiError } from '../core/async-data';
import { ChatProbeApi, newProbeSession } from '../core/chat-probe-api.service';
import type { TraceDebug } from '../core/sessions-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AgentTraceComponent } from './agent-trace.component';
import type { CuratedPanelSection } from './curated-views';

interface ProbeTurn {
  readonly message: string;
  readonly answer: string;
  readonly durationMs: number;
  readonly debug: TraceDebug | undefined;
  readonly cards: number;
  readonly documents: readonly string[];
}

@Component({
  selector: 'studio-agent-probe',
  imports: [AgentTraceComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-probe.component.html',
  styleUrl: './agent-probe.component.scss',
})
export class AgentProbeComponent {
  private readonly api = inject(ChatProbeApi);
  private readonly lang = inject(StudioLanguageService);
  private readonly injector = inject(Injector);
  protected readonly t = this.lang.t;
  protected readonly list = this.lang.list;
  protected readonly fmt = inject(StudioFormat);

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  private readonly messageField = viewChild<ElementRef<HTMLTextAreaElement>>('messageField');

  readonly locales = ['de', 'en'] as const;
  readonly locale = signal<'de' | 'en'>('de');
  readonly sessionId = signal(newProbeSession());
  readonly message = signal('');
  readonly fieldError = signal('');
  readonly running = signal(false);
  readonly error = signal('');
  readonly status = signal('');
  readonly turns = signal<readonly ProbeTurn[]>([]);

  onMessage(event: Event): void {
    this.message.set((event.target as HTMLTextAreaElement).value);
  }

  onLocale(event: Event): void {
    const wert = (event.target as HTMLSelectElement).value;
    if (wert === 'de' || wert === 'en') this.locale.set(wert);
  }

  async send(): Promise<void> {
    if (this.running()) return;
    const nachricht = this.message().trim();
    if (!nachricht) {
      this.fieldError.set(this.t('agentProbe.error.empty'));
      return;
    }
    this.fieldError.set('');
    this.error.set('');
    this.status.set('');
    this.running.set(true);
    const start = performance.now();
    try {
      const antwort = await this.api.turn(this.sessionId(), nachricht, this.locale());
      const durationMs = performance.now() - start;
      this.turns.update((bisher) => [...bisher, {
        message: nachricht,
        answer: antwort.content ?? '',
        durationMs,
        debug: antwort.debug,
        cards: antwort.cards?.length ?? 0,
        documents: (antwort.inline_documents ?? []).map((d) => d.title ?? '').filter(Boolean),
      }]);
      // Erst nach Erfolg leeren: ein gescheiterter Zug behält, was geschrieben war.
      this.message.set('');
      this.status.set(this.t('agentProbe.done', { duration: this.fmt.seconds(durationMs) }));
    } catch (err) {
      this.error.set(describeApiError(err, this.t));
    } finally {
      this.running.set(false);
      // Der Knopf war gesperrt und hat den Fokus verloren; weiter geht es im Feld.
      afterNextRender(() => this.messageField()?.nativeElement.focus(), { injector: this.injector });
    }
  }

  reset(): void {
    if (this.running()) return;
    this.sessionId.set(newProbeSession());
    this.turns.set([]);
    this.error.set('');
    this.fieldError.set('');
    this.status.set(this.t('agentProbe.started'));
  }
}
