/**
 * Die Spur eines Zugs (ST-8a) — unter jeder Antwort im Sitzungs-Verlauf und
 * unter jedem Zug des Chat-Probelaufs auf der Agent-Seite (8e).
 *
 * Oben die Kennzahlen, die man beim Überfliegen braucht: Maschine, Token, Ende,
 * geholter Skill. Die Runden stehen eingeklappt darunter — ein Verlauf mit
 * zwanzig Zügen soll ein Verlauf bleiben und kein Protokoll.
 *
 * Ein Zug vor jeder Maschine (Tour, Kontext-Begrüßung, Direktaktionen: `engine`
 * leer, AG-1) ohne gebuchte Token zeigt nichts. „Maschine unbekannt" wäre dort
 * falsch: es gab keine.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { TraceDebug } from '../core/sessions-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { type TraceCall, readTokens, readTrace, stopReasonLabel } from './agent-trace';
import { engineLabel } from './engine-label';

interface Fact {
  readonly label: string;
  readonly value: string;
}

@Component({
  selector: 'studio-agent-trace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-trace.component.html',
  styleUrl: './agent-trace.component.scss',
})
export class AgentTraceComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly fmt = inject(StudioFormat);

  readonly debug = input<TraceDebug | undefined>(undefined);

  readonly trace = computed(() => readTrace(this.debug()?.trace));

  readonly facts = computed<readonly Fact[]>(() => {
    const debug = this.debug();
    const out: Fact[] = [];
    if (debug?.engine) {
      out.push({ label: this.t('trace.engine'), value: engineLabel(debug.engine, this.t) });
    }
    const tokens = readTokens(debug?.token_usage);
    if (tokens) {
      out.push({
        label: this.t('trace.tokens'),
        value: this.t('trace.tokens.value', {
          prompt: this.fmt.whole(tokens.prompt),
          cached: this.fmt.whole(tokens.cached),
          completion: this.fmt.whole(tokens.completion),
        }),
      });
    }
    const { stop, skills } = this.trace();
    if (stop) {
      out.push({
        label: this.t('trace.end'),
        value: this.t('trace.end.value', {
          reason: stop.reason ? stopReasonLabel(stop.reason, this.t) : this.t('trace.stop.unknown'),
          rounds: this.lang.plural('trace.rounds', stop.rounds),
          duration: this.fmt.seconds(stop.durationMs),
        }),
      });
    }
    for (const skill of skills) out.push({ label: this.t('trace.skill'), value: skill.title });
    return out;
  });

  readonly visible = computed(() => this.facts().length > 0 || this.trace().rounds.length > 0);

  /** `name (arg1, arg2)` — Bezeichner, deshalb ohne Übersetzung. */
  callText(call: TraceCall): string {
    return call.args.length ? `${call.name} (${call.args.join(', ')})` : call.name;
  }
}
