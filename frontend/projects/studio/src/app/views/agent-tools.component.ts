/**
 * Werkzeuge und Sperren (ST-8b) — welche Werkzeuge der Agent in einem Chat-Zug
 * bekommt und was ihm eines davon nehmen kann.
 *
 * Jede Sperre wird dort gepflegt, wo sie wirkt, und die Zeile verweist auf die Seite dazu.
 * Die festen Sperren des Regex-Gates stehen im Code; die Zeile sagt das, statt einen Ort zu
 * versprechen, an dem man sie ändern könnte. Seit Paket 15 trägt jedes Server-Werkzeug hier
 * seinen Schalter (`werkzeuge_aus` der MCP-Server-Liste, `McpRegistryStore`) — vorher stand er
 * nur im MCP-Panel unter „Wissen“, die Liste hier war lesend.
 *
 * Geladen erst beim Aufklappen, wie der Master-Skill.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import type { AgentTool, AgentToolLock } from '../core/agent-center-api.service';
import { AgentCenterApi } from '../core/agent-center-api.service';
import { AsyncData } from '../core/async-data';
import { McpRegistryStore } from '../core/mcp-registry-store';
import { StudioApi } from '../core/studio-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { STUDIO_VIEWS } from '../studio-views';
import {
  type Schalter, firstSentence, groupTools, lockLink, lockText, schalterFuer,
} from './agent-tools';
import type { CuratedPanelSection } from './curated-views';
import { SaveConflictComponent } from './save-conflict.component';

/** Erlaubnisliste statt zusammengesetztem Schlüssel: eine neue Art kommt roh durch. */
const GROUP_KEYS: ReadonlyMap<string, string> = new Map([
  ['read', 'agentTools.group.read'],
  ['curation', 'agentTools.group.curation'],
  ['external', 'agentTools.group.external'],
  ['virtual', 'agentTools.group.virtual'],
]);

@Component({
  selector: 'studio-agent-tools',
  imports: [RouterLink, SaveConflictComponent],
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
  /** Paket 15: die Server-Liste, deren `werkzeuge_aus` die Schalter schreiben. */
  readonly reg = new McpRegistryStore(inject(StudioApi), this.t);
  readonly dirty = this.reg.dirty;
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

  schalter(tool: AgentTool): Schalter | null {
    return schalterFuer(tool, this.reg.servers());
  }

  /** Bietet der Chatbot das Werkzeug laut (bearbeiteter) Server-Liste an? */
  /** Woher das Werkzeug kommt — ein fremdes nennt seinen Server auch, solange die Liste lädt. */
  herkunft(tool: AgentTool, schalter: Schalter | null): string {
    if (schalter) return schalter.server;
    if (tool.kind === 'virtual') return this.t('agentTools.herkunft.eingebaut');
    if (tool.kind === 'external') return tool.server_id ?? '';
    return this.t('agentTools.herkunft.wlo');
  }

  /** „fest“ nur, wo es stimmt: ohne Server-Liste weiß die Seite nicht, was schaltbar ist. */
  ohneSchalter(tool: AgentTool): string {
    if (tool.kind !== 'virtual' && this.reg.loading()) return this.t('agentTools.schalter.laedt');
    if (tool.kind !== 'virtual' && this.reg.loadError()) {
      return this.t('agentTools.schalter.unbekannt');
    }
    return this.t('agentTools.schalter.fest');
  }

  /** Nach einem Konflikt: Server-Liste und Tabelle — die zeigt, was ein Zug jetzt bekommt. */
  neuLaden(): void {
    void this.reg.load();
    void this.list.reload();
  }

  an(schalter: Schalter): boolean {
    const server = this.reg.servers()[schalter.index];
    return !!server && this.reg.isOffered(server, schalter.name);
  }

  setze(schalter: Schalter, an: boolean): void {
    this.reg.setOffered(schalter.index, schalter.name, an);
  }

  /** Speichern, danach die Tabelle neu: was ein Zug bekommt, hat sich womöglich geändert. */
  async speichern(force = false): Promise<void> {
    await this.reg.save(force);
    if (!this.reg.dirty()) void this.list.reload();
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
    void this.reg.load();
  }
}
