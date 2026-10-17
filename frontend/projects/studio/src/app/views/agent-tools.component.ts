/**
 * Werkzeuge und Sperren (ST-8b) — welche Werkzeuge der Agent in einem Chat-Zug
 * bekommt und was ihm eines davon nehmen kann.
 *
 * Nur lesend: jede Sperre wird dort gepflegt, wo sie wirkt, und die Zeile
 * verweist auf die Seite dazu. Die festen Sperren des Regex-Gates stehen im Code;
 * die Zeile sagt das, statt einen Ort zu versprechen, an dem man sie ändern könnte.
 *
 * Geladen erst beim Aufklappen, wie der Master-Skill.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import type { AgentToolLock } from '../core/agent-center-api.service';
import { AgentCenterApi } from '../core/agent-center-api.service';
import { AsyncData } from '../core/async-data';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { STUDIO_VIEWS } from '../studio-views';
import { firstSentence, groupTools, lockLink, lockText } from './agent-tools';
import type { CuratedPanelSection } from './curated-views';

/** Erlaubnisliste statt zusammengesetztem Schlüssel: eine neue Art kommt roh durch. */
const GROUP_KEYS: ReadonlyMap<string, string> = new Map([
  ['read', 'agentTools.group.read'],
  ['curation', 'agentTools.group.curation'],
  ['external', 'agentTools.group.external'],
  ['virtual', 'agentTools.group.virtual'],
]);

@Component({
  selector: 'studio-agent-tools',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-tools.component.html',
  styleUrl: './agent-tools.component.scss',
})
export class AgentToolsComponent {
  private readonly api = inject(AgentCenterApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly list = new AsyncData(() => this.api.tools(), this.t);
  readonly groups = computed(() => groupTools(this.list.value()?.tools ?? []));
  readonly summary = computed(() => {
    const tools = this.list.value()?.tools ?? [];
    return this.lang.plural('agentTools.summary', tools.length, {
      offered: tools.filter((tool) => tool.offered).length,
    });
  });

  protected readonly firstSentence = firstSentence;
  protected readonly lockLink = lockLink;

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) untracked(() => this.ensureLoaded());
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  lockText(lock: AgentToolLock): string {
    return lockText(lock, this.lang);
  }

  groupLabel(kind: string): string {
    const key = GROUP_KEYS.get(kind);
    return key ? this.t(key) : kind;
  }

  groupHint(kind: string): string {
    const key = GROUP_KEYS.get(kind);
    return key ? this.t(`${key}.hint`) : '';
  }

  pageLabel(slug: string): string {
    const view = STUDIO_VIEWS.find((v) => v.slug === slug);
    return this.t('agentTools.pageLink', { page: view ? this.t(view.labelKey) : slug });
  }

  private ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.list.reload();
  }
}
