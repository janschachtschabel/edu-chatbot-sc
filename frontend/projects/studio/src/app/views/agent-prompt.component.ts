/**
 * Was das Modell zuerst liest (ST-8d) — der Anfang der Kette eines Chat-Zugs
 * im Agent-Modus, aus `GET /api/agent-center/prompt`.
 *
 * Eine nummerierte Folge, weil die Reihenfolge die Aussage ist: eigene Regeln
 * vor fremdem Text (AG-3), Stabiles vor Wechselndem (Prompt-Cache). Kopf und
 * Master-Skill stehen im Wortlaut da — als reiner Text, wie im Master-Skill-Panel.
 * Was je Zug folgt, hängt an Seite, Einbettung und Verlauf; dort steht, wann es
 * erscheint, statt eines erfundenen Beispiels.
 *
 * Geladen erst beim Aufklappen und neu, wenn die Widget-Sprache wechselt: sie
 * steht im Kopf als Rückfall-Sprache.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked,
} from '@angular/core';

import { AgentCenterApi, type PromptChainItem } from '../core/agent-center-api.service';
import { AsyncData } from '../core/async-data';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

/** Erlaubnisliste: ein neues Glied des Backends kommt mit seiner Kennung durch. */
const STEPS: ReadonlySet<string> = new Set([
  'head', 'master_skill', 'result_schema', 'host_capabilities', 'page_rules',
  'host_instruction', 'skill_hints', 'page_data', 'history', 'prefetch', 'last_shown', 'message',
]);
const SKILL_STATES: ReadonlySet<string> = new Set(['off', 'no_node', 'failed']);

@Component({
  selector: 'studio-agent-prompt',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-prompt.component.html',
  styleUrl: './agent-prompt.component.scss',
})
export class AgentPromptComponent {
  private readonly api = inject(AgentCenterApi);
  private readonly lang = inject(StudioLanguageService);
  private readonly fmt = inject(StudioFormat);
  protected readonly t = this.lang.t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly locales = ['de', 'en'] as const;
  readonly locale = signal<'de' | 'en'>('de');
  readonly preview = new AsyncData(() => this.api.prompt(this.locale()), this.t);
  readonly toolsLine = computed(() => {
    const tools = this.preview.value()?.tools;
    return tools
      ? this.lang.plural('agentPrompt.tools', tools.count, { chars: this.fmt.whole(tools.chars) })
      : '';
  });

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) untracked(() => this.ensureLoaded());
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  onLocale(event: Event): void {
    const wert = (event.target as HTMLInputElement).value;
    if (wert !== 'de' && wert !== 'en') return;
    this.locale.set(wert);
    void this.preview.reload();
  }

  name(item: PromptChainItem): string {
    return STEPS.has(item.id) ? this.t(`agentPrompt.step.${item.id}`) : item.id;
  }

  /** Wann ein Glied je Zug erscheint — leer für Kopf, Master-Skill und Unbekanntes. */
  when(item: PromptChainItem): string {
    return STEPS.has(item.id) && item.id !== 'head' && item.id !== 'master_skill'
      ? this.t(`agentPrompt.when.${item.id}`)
      : '';
  }

  /** Länge, beim Master-Skill mit Prüfsumme — oder warum er fehlt. */
  meta(item: PromptChainItem): string {
    if (item.id === 'master_skill' && !item.text) {
      const state = item.state ?? '';
      return SKILL_STATES.has(state)
        ? this.t(`agentPrompt.skill.${state}`, { error: item.error ?? '' })
        : state;
    }
    if (item.text === undefined) return '';
    const chars = this.lang.plural('agentPrompt.chars', item.chars ?? 0, {
      n: this.fmt.whole(item.chars ?? 0),
    });
    const sum = (item.sha256 ?? '').slice(0, 12);
    return sum ? this.t('agentPrompt.checksum', { chars, sum }) : chars;
  }

  private ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.preview.reload();
  }
}
