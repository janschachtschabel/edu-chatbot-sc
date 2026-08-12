/**
 * The MCP server registry (9-4e) — which tool servers the bot may call.
 *
 * Uses `/config/mcp-servers` rather than the generic area endpoints, and that
 * is the whole reason this is a panel and not a schema form: the GET enriches
 * every server with the tool descriptions its live handshake reported, and the
 * PUT runs the SSRF check on each URL. A schema form would show neither.
 *
 * The PUT replaces the registry, so there is one save for the whole list —
 * per-row saves would be N requests that can half-fail.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal }
  from '@angular/core';

import { describeApiError } from '../core/async-data';
import { StudioApi } from '../core/studio-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

export interface McpServer {
  id: string;
  name: string;
  url: string;
  description: string;
  enabled: boolean;
  tools?: string[];
  /** tool name -> description, from the live server. Absent if it was unreachable. */
  tool_descriptions?: Record<string, string>;
  url_env_var?: string;
  url_readonly?: boolean;
}

interface DiscoveredTool {
  readonly name: string;
  readonly description: string;
}

/**
 * Was die Registry von einem Server erwartet, gegen das, was er wirklich führt.
 *
 * `missing` ist die gefährliche Richtung: diese Werkzeuge werden dem Modell
 * angeboten, der Server kennt sie nicht, und jeder Aufruf endet in
 * `MCP error: …` — ein verbrannter Zug. `extra` ist bloss ein Hinweis.
 */
export function compareToolsets(
  expected: readonly string[], actual: readonly string[],
): { missing: string[]; extra: string[] } {
  const offered = new Set(actual);
  const registered = new Set(expected);
  return {
    missing: expected.filter((name) => !offered.has(name)),
    extra: actual.filter((name) => !registered.has(name)),
  };
}

/**
 * Zwei Adressen für den Vergleich vergleichbar machen. Ohne das Abschneiden des
 * nachgestellten Schrägstrichs griffe der Abgleich daneben und täte still
 * nichts — statt zu sagen, dass er nichts tut.
 */
function sameAddress(a: string, b: string): boolean {
  const cut = (url: string): string => url.trim().replace(/\/+$/, '');
  return cut(a) !== '' && cut(a) === cut(b);
}

@Component({
  selector: 'studio-mcp-registry',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './mcp-registry.component.html',
  styleUrl: './mcp-registry.component.scss',
})
export class McpRegistryComponent {
  private readonly api = inject(StudioApi);
  protected readonly t = inject(StudioLanguageService).t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly servers = signal<readonly McpServer[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal('');
  readonly saving = signal(false);
  readonly saveError = signal('');
  readonly status = signal('');

  readonly discoverUrl = signal('');
  readonly discovering = signal(false);
  readonly discoverError = signal('');
  readonly found = signal<readonly DiscoveredTool[] | null>(null);

  /**
   * Die Adresse, die wirklich befragt wurde — nicht das Eingabefeld, das sich
   * danach weitertippen lässt. Gegen `discoverUrl` verglichen zeigte der
   * Abgleich sonst ein Ergebnis über eine Adresse an, die nie geprüft wurde.
   */
  private readonly checkedUrl = signal('');

  /** Der Registry-Eintrag zur geprüften Adresse — null, wenn sie neu ist. */
  readonly comparedServer = computed(
    () => this.servers().find((s) => sameAddress(s.url, this.checkedUrl())) ?? null,
  );

  /** Erwartung gegen Wirklichkeit; null, solange es nichts zu vergleichen gibt. */
  readonly divergence = computed(() => {
    const tools = this.found();
    const server = this.comparedServer();
    if (!tools || !server) return null;
    return compareToolsets(server.tools ?? [], tools.map((t) => t.name));
  });

  private readonly saved = signal('[]');
  readonly dirty = computed(() => JSON.stringify(this.servers()) !== this.saved());

  /**
   * `save_mcp_servers` skips every entry without an id, so saving a nameless
   * row would answer 200 and drop it — the editor would watch their work
   * vanish with a "Gespeichert." next to it.
   */
  readonly incomplete = computed(() => this.servers().some((s) => !s.id.trim()));

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  private ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.loadError.set('');
    try {
      const servers = await this.api.get<McpServer[]>('/config/mcp-servers');
      this.adopt(servers);
    } catch (err) {
      this.loadError.set(describeApiError(err, this.t));
    } finally {
      this.loading.set(false);
    }
  }

  toolsOf(server: McpServer): { name: string; description: string }[] {
    return (server.tools ?? []).map((name) => ({
      name,
      description: server.tool_descriptions?.[name] ?? '',
    }));
  }

  /** Replace one field of one server — the list is treated as immutable. */
  edit(index: number, patch: Partial<McpServer>): void {
    this.servers.update((list) =>
      list.map((server, i) => (i === index ? { ...server, ...patch } : server)),
    );
    this.status.set('');
  }

  add(): void {
    this.servers.update((list) => [
      ...list,
      { id: '', name: '', url: '', description: '', enabled: false, tools: [] },
    ]);
    this.status.set('');
  }

  remove(index: number): void {
    this.servers.update((list) => list.filter((_, i) => i !== index));
    this.status.set('');
  }

  async save(): Promise<void> {
    if (this.incomplete() || this.saving()) return;
    this.saving.set(true);
    this.saveError.set('');
    this.status.set('');
    try {
      await this.api.put('/config/mcp-servers', { servers: this.servers() });
      // Re-read rather than trust the local copy: the backend strips UI meta,
      // restores the primary if it went missing, and re-enriches descriptions.
      await this.load();
      this.status.set(this.t('editor.saved'));
    } catch (err) {
      this.saveError.set(describeApiError(err, this.t));
    } finally {
      this.saving.set(false);
    }
  }

  async discover(): Promise<void> {
    const url = this.discoverUrl().trim();
    if (!url || this.discovering()) return;
    this.discovering.set(true);
    this.discoverError.set('');
    this.found.set(null);
    this.checkedUrl.set('');
    try {
      const answer = await this.api.post<{ tools: DiscoveredTool[] }>(
        '/config/mcp-servers/discover', null, { url },
      );
      this.found.set(answer.tools ?? []);
      this.checkedUrl.set(url);
    } catch (err) {
      this.discoverError.set(describeApiError(err, this.t));
    } finally {
      this.discovering.set(false);
    }
  }

  private adopt(servers: McpServer[]): void {
    this.servers.set(servers);
    this.saved.set(JSON.stringify(servers));
  }
}
