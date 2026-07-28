import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DecimalPipe, JsonPipe, KeyValuePipe, SlicePipe } from '@angular/common';

import { DebugInfo } from '../grouping/message-types';

/**
 * DebugPanel — das Diagnose-Panel unter dem Chat (Redaktions-/Entwickler-Sicht).
 * Visueller Verbatim-Port des ALT-Blocks (`chat.component.html:422-607` +
 * `.debug-*`-SCSS chat.component.scss:1227-1308), der dort inline im
 * chat.component-Monolithen lag; NEU als eigenständige präsentationale
 * Komponente über dem vollen {@link DebugInfo}-Modell (in diesem Slice aus ALT
 * `api.service.ts` nachgewachsen).
 *
 * Präsentational: liest NUR `debug` (ALT `latestDebug`) + `show` (ALT
 * `showDebug`); keine Logik, keine Emits. Selbst-Gate auf `show && debug` (ALTs
 * `*ngIf="showDebug && latestDebug"`) — der Elternteil (Chat-Shell 8-4)
 * entscheidet, ob es gerendert wird, und reicht die beiden Inputs herein.
 *
 * Kontrollfluss zu Angular-21 übersetzt (`*ngIf`→`@if`, `*ngFor`→`@for track
 * $index`, `else linearTrace`→`@else`); gerendertes DOM + Feld-für-Feld-Ausgabe
 * bleiben identisch zu ALT. `Math` ist als Feld exponiert, weil die
 * Parallel-Trace-Bars ALT-verbatim `Math.max(...)` inline in den Style-Bindings
 * nutzen. Die 6 Sektions-Titel + alle Zeilen sind byte-nah aus ALT.
 *
 * Fidelity-Port-Ausnahme (Datei > 300 Z.): eine kohäsive Diagnose-Ansicht —
 * ein Verantwortungsbereich (das Debug-Objekt rendern). Eine Zerlegung in 6
 * Sektions-Komponenten wäre Over-Engineering und würde vom ALT-Block abweichen.
 * A11y-Sweep (Kontrast der Grau-Töne, ggf. `aria-hidden` auf Emoji) → 8-6.
 */
@Component({
  selector: 'boerdi-debug-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, JsonPipe, KeyValuePipe, SlicePipe],
  styleUrl: './debug-panel.component.scss',
  template: `
    @if (show() && debug(); as d) {
      <div class="debug-panel">
        <!-- ════ 1. Gesprächs-Phase (Conversation Flow) ════ -->
        <div class="debug-section-title">🌀 Gesprächs-Phase</div>
        <div class="debug-row"><span class="debug-label">State:</span> {{ d.state || '–' }}</div>
        @if (d.state_transition) {
          <div class="debug-row">
            <span class="debug-label">Übergang:</span>
            <span [class.debug-warn]="d.state_transition.plausible === false">
              {{ d.state_transition.prev || '(start)' }} → {{ d.state_transition.next }}
            </span>
            @if (d.state_transition.plausible === false) {
              <span class="debug-warn">
                ⚠ implausibel · erwartet: {{ d.state_transition.expected_next_likely.join(', ') }}
              </span>
            }
            @if (d.state_transition.plausible === true) {
              <span class="debug-ok">✓ plausibel</span>
            }
          </div>
        }
        <div class="debug-row"><span class="debug-label">Turn-Typ:</span> {{ d.turn_type || '–' }}</div>

        <!-- ════ 2. Klassifikation (Persona + Intent + Slots + Signale) ════ -->
        <div class="debug-section-title">🎯 Klassifikation</div>
        <div class="debug-row"><span class="debug-label">Persona:</span> {{ d.persona }}</div>
        <div class="debug-row"><span class="debug-label">Intent:</span> {{ d.intent }}</div>
        <div class="debug-row"><span class="debug-label">Signale:</span> {{ d.signals.join(', ') || '–' }}</div>
        <div class="debug-row"><span class="debug-label">Entities:</span> <code>{{ d.entities | json }}</code></div>
        @if (d.confidence !== undefined) {
          <div class="debug-row">
            <span class="debug-label">Confidence:</span> {{ (d.confidence || 0) | number: '1.2-2' }}
          </div>
        }

        <!-- ════ 3. Pattern-Engine (Auswahl + Pipeline) ════ -->
        <div class="debug-section-title">🧩 Pattern-Engine</div>
        <div class="debug-row"><span class="debug-label">Pattern:</span> {{ d.pattern }}</div>
        @if (d.pattern_id_hint) {
          <div class="debug-row">
            <span class="debug-label">LLM-Hint:</span> {{ d.pattern_id_hint }}
            @if (d.llm_engine_match === true) {
              <span class="debug-ok">✓ stimmt mit Engine überein</span>
            }
            @if (d.llm_engine_match === false) {
              <span class="debug-warn">⚠ weicht von Engine ab</span>
            }
          </div>
        }
        @if (d.pattern_reasoning) {
          <div class="debug-row">
            <span class="debug-label">Reasoning:</span> {{ d.pattern_reasoning | slice: 0 : 160
            }}{{ d.pattern_reasoning.length > 160 ? '…' : '' }}
          </div>
        }
        @if (d.phase1_eliminated && d.phase1_eliminated.length) {
          <div class="debug-row">
            <span class="debug-label">Phase 1 eliminiert:</span> {{ d.phase1_eliminated.join(', ') }}
          </div>
        }
        @if (d.phase2_scores) {
          <div class="debug-row">
            <span class="debug-label">Phase 2 Scores:</span>
            @for (entry of d.phase2_scores | keyvalue; track entry.key) {
              <span class="debug-score"> {{ entry.key }}={{ entry.value | number: '1.2-2' }} </span>
            }
          </div>
        }
        @if (d.phase3_modulations['degradation']) {
          <div class="debug-row">
            <span class="debug-label">Degradation:</span>
            <span class="debug-warn">⚠</span>
            fehlende Slots={{ d.phase3_modulations['missing_slots']?.join(', ') || '–' }}
            @if (d.phase3_modulations['blocked_patterns'] && d.phase3_modulations['blocked_patterns'].length) {
              <span> · blockiert={{ d.phase3_modulations['blocked_patterns'].length }} Patterns</span>
            }
          </div>
        }

        <!-- ════ 4. Modulation (Output-Form) ════ -->
        <div class="debug-section-title">🎨 Modulation</div>
        <div class="debug-row">
          <span class="debug-label">Ton/Form:</span>
          Ton={{ d.phase3_modulations['tone'] }}, Formalität={{ d.phase3_modulations['formality'] }}, Länge={{
            d.phase3_modulations['length']
          }}, Detail={{ d.phase3_modulations['detail_level'] }}
          @if (d.phase3_modulations['skip_intro']) { <span> · skip_intro</span> }
          @if (d.phase3_modulations['one_option']) { <span> · one_option</span> }
          @if (d.phase3_modulations['add_sources']) { <span> · add_sources</span> }
        </div>
        <div class="debug-row">
          <span class="debug-label">Response:</span>
          Typ={{ d.phase3_modulations['response_type'] }}, Format={{ d.phase3_modulations['format_primary'] }},
          Follow-up={{ d.phase3_modulations['format_follow_up'] }}, Kacheln={{ d.phase3_modulations['card_text_mode'] }},
          Max={{ d.phase3_modulations['max_items'] }}
        </div>
        @if (d.phase3_modulations['core_rule']) {
          <div class="debug-row">
            <span class="debug-label">Core-Rule:</span> {{ d.phase3_modulations['core_rule'] | slice: 0 : 120
            }}{{ d.phase3_modulations['core_rule'].length > 120 ? '…' : '' }}
          </div>
        }

        <!-- ════ 5. Tools + Wissen ════ -->
        <div class="debug-section-title">🔧 Tools &amp; Wissen</div>
        <div class="debug-row"><span class="debug-label">Tools aufgerufen:</span> {{ d.tools_called.join(', ') || '–' }}</div>
        @if (d.phase3_modulations['tools'] && d.phase3_modulations['tools'].length) {
          <div class="debug-row">
            <span class="debug-label">Pattern-Tools (erlaubt):</span> {{ d.phase3_modulations['tools'].join(', ') }}
          </div>
        }
        <div class="debug-row">
          <span class="debug-label">Quellen:</span> {{ d.phase3_modulations['sources']?.join(', ') || '–' }}
        </div>
        @if (d.phase3_modulations['rag_areas'] && d.phase3_modulations['rag_areas'].length) {
          <div class="debug-row">
            <span class="debug-label">RAG-Areas:</span> {{ d.phase3_modulations['rag_areas'].join(', ') }}
          </div>
        }

        <!-- ════ 6. Safety + Policy + Context (Triple-Schema v2) ════ -->
        <div class="debug-section-title">🛡️ Safety, Policy &amp; Context</div>
        @if (d.safety) {
          <div class="debug-row">
            <span class="debug-label">Safety:</span>
            Risk={{ d.safety.risk_level }}
            @if (d.safety.stages_run && d.safety.stages_run.length) { <span> · stages={{ d.safety.stages_run.join('→') }}</span> }
            @if (d.safety.escalated) { <span> · 🤖 escalated</span> }
            @if (d.safety.flagged_categories && d.safety.flagged_categories.length) { <span> · flagged={{ d.safety.flagged_categories.join(',') }}</span> }
            @if (d.safety.legal_flags && d.safety.legal_flags.length) { <span> · legal={{ d.safety.legal_flags.join(',') }}</span> }
            @if (d.safety.enforced_pattern) { <span> · enforced={{ d.safety.enforced_pattern }}</span> }
            @if (d.safety.blocked_tools && d.safety.blocked_tools.length) { <span> · blocked={{ d.safety.blocked_tools.join(', ') }}</span> }
            @if (d.safety.reasons && d.safety.reasons.length) { <span> · {{ d.safety.reasons.join(', ') }}</span> }
          </div>
        }
        @if (d.outcomes && d.outcomes.length) {
          <div class="debug-row">
            <span class="debug-label">Outcomes:</span>
            @for (o of d.outcomes; track $index) {
              <div class="debug-sub">
                · {{ o.tool }} → {{ o.status }} ({{ o.item_count }} items, {{ o.latency_ms }}ms)@if (o.error) {<span> – {{ o.error }}</span>}
              </div>
            }
          </div>
        }
        @if (d.policy) {
          <div class="debug-row">
            <span class="debug-label">Policy:</span>
            {{ d.policy.allowed ? 'allowed' : 'BLOCKED' }}
            @if (d.policy.matched_rules && d.policy.matched_rules.length) { <span> · rules={{ d.policy.matched_rules.join(', ') }}</span> }
            @if (d.policy.blocked_tools && d.policy.blocked_tools.length) { <span> · blocked={{ d.policy.blocked_tools.join(', ') }}</span> }
            @if (d.policy.required_disclaimers && d.policy.required_disclaimers.length) { <span> · disclaimers={{ d.policy.required_disclaimers.length }}</span> }
          </div>
        }
        @if (d.context) {
          <div class="debug-row">
            <span class="debug-label">Context:</span>
            page={{ d.context.page }}, device={{ d.context.device }}, turn={{ d.context.turn_count }}
          </div>
        }
        @if (d.trace && d.trace.length) {
          <div class="debug-row">
            <span class="debug-label">Trace:</span>
            @for (t of d.trace; track $index) {
              <div class="debug-trace-entry">
                @if (t.data && t.data['parallel'] === true && t.data['tasks']?.length) {
                  <div class="debug-sub debug-parallel-header">⟨ {{ t.label || t.step }} – Gesamt {{ t.duration_ms }}ms ⟩</div>
                  <div class="debug-parallel-stack">
                    @for (task of t.data['tasks']; track $index) {
                      <div
                        class="debug-parallel-task"
                        [style.margin-left.%]="(task.started_at_ms / Math.max(t.duration_ms, 1)) * 100"
                        [style.width.%]="Math.max((task.duration_ms / Math.max(t.duration_ms, 1)) * 100, 2)"
                        [title]="task.label + ' — Start +' + task.started_at_ms + 'ms · Dauer ' + task.duration_ms + 'ms'"
                      >
                        <span class="debug-parallel-task__label">{{ task.label || task.name }}</span>
                        <span class="debug-parallel-task__time">{{ task.duration_ms }}ms</span>
                      </div>
                    }
                  </div>
                } @else {
                  <div class="debug-sub">· [{{ t.step }}] {{ t.label }} – {{ t.duration_ms }}ms</div>
                }
              </div>
            }
          </div>
        }
        <!-- Pattern-Hint (Shadow-Mode telemetry) — LLM-classifier's pattern guess -->
        @if (d.pattern_id_hint) {
          <div class="debug-row">
            <span class="debug-label">LLM-Hint:</span>
            {{ d.pattern_id_hint }}
            @if (d.llm_engine_match === true) { <span style="color:#1f7a39"> ✓ Engine-Match</span> }
            @if (d.llm_engine_match === false) { <span style="color:#ad6f00"> ≠ Engine</span> }
            @if (d.pattern_reasoning) { <span class="debug-sub" style="display:block"> {{ d.pattern_reasoning }}</span> }
          </div>
        }
        <!-- Tie-Breaker (Bonus 2 — selektiver LLM-Hint-Override) -->
        @if (d.phase3_modulations && d.phase3_modulations['tie_breaker']) {
          <div class="debug-row">
            <span class="debug-label">Tie-Breaker:</span>
            @if (d.phase3_modulations['tie_breaker'].applied) {
              <span>
                ⚡ {{ d.phase3_modulations['tie_breaker'].from }} → {{ d.phase3_modulations['tie_breaker'].to }} (gap={{
                  d.phase3_modulations['tie_breaker'].score_gap
                }})
              </span>
            }
            @if (!d.phase3_modulations['tie_breaker'].applied) {
              <span> evaluiert (gap={{ d.phase3_modulations['tie_breaker'].score_gap }}, applied=false) </span>
            }
          </div>
        }
        <!-- Token-Usage + Cache-Hit-Rate (A2.1 + A2.3) -->
        @if (d.token_usage && d.token_usage['calls']) {
          <div class="debug-row">
            <span class="debug-label">Tokens:</span>
            prompt={{ d.token_usage['prompt_tokens'] }}, completion={{ d.token_usage['completion_tokens'] }}, cached={{
              d.token_usage['cached_tokens']
            }}
            @if (d.token_usage['prompt_tokens']) {
              <span> ({{ ((d.token_usage['cached_tokens'] || 0) / d.token_usage['prompt_tokens'] * 100) | number: '1.0-0' }}% cache) </span>
            }
            · {{ d.token_usage['calls'] }} call(s)
          </div>
        }
        @if (d.token_usage && d.token_usage['per_phase']) {
          <div class="debug-row">
            <span class="debug-label">Phasen:</span>
            @for (p of d.token_usage['per_phase'] | keyvalue; track p.key) {
              <div class="debug-sub">
                · {{ p.key }}: prompt={{ p.value.prompt }}, cached={{ p.value.cached
                }}@if (p.value.prompt) {<span> ({{ ((p.value.cached || 0) / p.value.prompt * 100) | number: '1.0-0' }}%)</span>}
              </div>
            }
          </div>
        }
      </div>
    }
  `,
})
export class DebugPanelComponent {
  /** ALT `latestDebug` — der Debug-Block der jüngsten Bot-Antwort (oder null). */
  readonly debug = input<DebugInfo | null>(null);
  /** ALT `showDebug` — Redaktions-/Debug-Toggle. */
  readonly show = input(false);

  /** Für die Parallel-Trace-Bars: ALT nutzt `Math.max(...)` inline in den
   *  Style-Bindings; Templates sehen keine Globals, daher als Feld exponiert. */
  protected readonly Math = Math;
}
