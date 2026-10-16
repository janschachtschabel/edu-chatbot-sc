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
import { type SaveConflict, StudioApiError } from '../core/studio-api-error';
import { StudioApi } from '../core/studio-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import { SaveConflictComponent } from './save-conflict.component';

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
  /** Paket 7 (S5): Werkzeuge, die das Modell nicht bekommt — der GET liefert die
   *  wirksame Liste (Vorgabe: `search_skill`), gespeichert wird sie so. */
  werkzeuge_aus?: string[];
  /** Nur diese Werkzeuge kennt der Chatbot; nur sie tragen einen Schalter. */
  werkzeuge_im_katalog?: string[];
  /** Paket 11 (E): übernommene Werkzeuge eines weiteren Servers. */
  tool_schemas?: DiscoveredTool[];
  /** Paket 11: Katalog-Werkzeuge, die der Server laut Live-Abfrage nicht führt. */
  werkzeuge_fehlen_am_server?: string[];
}

interface DiscoveredTool {
  readonly name: string;
  readonly description: string;
  readonly input_schema?: Record<string, unknown>;
  readonly read_only?: boolean;
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
  imports: [SaveConflictComponent],
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
  /** The stored version (Paket 4, D5), from `X-Config-Version`; a save asserts it. */
  readonly version = signal<number | null>(null);
  /** Set by a 409: someone saved since. The draft stays until reload or force. */
  readonly conflict = signal<SaveConflict | null>(null);

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

  /**
   * Das Ergebnis des Abgleichs als ein Satz, für die dauerhafte Live-Region
   * (Paket 4b, B2). Sichtbar steht es weiter bei seinen Listen: Die Absätze
   * dort entstehen mit dem Abruf und würden nicht angesagt. Meldet der Server
   * kein Werkzeug, steht das sichtbar davor — und so auch hier (Paket 4c, B1).
   */
  readonly abgleichAnsage = computed(() => {
    const tools = this.found();
    if (this.discoverError() || !tools) return '';
    const vorweg = tools.length === 0 ? `${this.t('mcp.discover.none')} ` : '';
    if (!this.comparedServer()) return vorweg + this.t('mcp.compare.unregistered');
    const diff = this.divergence();
    if (!diff) return '';
    return vorweg + (diff.missing.length > 0
      ? `${this.t('mcp.compare.missing')} ${diff.missing.join(', ')}`
      : this.t('mcp.compare.match'));
  });

  /**
   * Paket 11 (E): die geprüften Werkzeuge in den eingetragenen Server übernehmen — nicht beim
   * WLO-Server, dessen Katalog fest im Chatbot steht (seine Adresse kommt aus der Umgebung).
   */
  readonly canAdopt = computed(() => {
    const server = this.comparedServer();
    return !!server && !server.url_readonly && (this.found()?.length ?? 0) > 0;
  });

  adoptTools(): void {
    const server = this.comparedServer();
    const tools = this.found();
    if (!server || server.url_readonly || !tools) return;
    const index = this.servers().indexOf(server);
    this.edit(index, {
      tools: tools.map((t) => t.name),
      tool_schemas: tools.map((t) => ({
        name: t.name, description: t.description,
        input_schema: t.input_schema ?? {}, read_only: t.read_only === true,
      })),
    });
    this.status.set(this.t('mcp.adopt.done'));
  }

  /** Der Server führt das Werkzeug derzeit nicht — eingeschaltet scheiterte jeder Aufruf. */
  fehltAmServer(server: McpServer, name: string): boolean {
    return (server.werkzeuge_fehlen_am_server ?? []).includes(name);
  }

  /** Übernommen, aber schreibend — warum es keinen Schalter trägt. */
  isWriting(server: McpServer, name: string): boolean {
    return (server.tool_schemas ?? []).some((t) => t.name === name && t.read_only !== true);
  }

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
      const { body, version } = await this.api.getVersioned<McpServer[]>('/config/mcp-servers');
      this.adopt(body);
      this.version.set(version);
      this.conflict.set(null);
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

  /** Paket 7 (S5): bietet der Chatbot dieses Werkzeug dem Modell an? */
  isOffered(server: McpServer, name: string): boolean {
    return !(server.werkzeuge_aus ?? []).includes(name);
  }

  /** Ein Schalter nur, wo er wirkt: bei Werkzeugen, die der Chatbot kennt. */
  hasSwitch(server: McpServer, name: string): boolean {
    return (server.werkzeuge_im_katalog ?? []).includes(name);
  }

  setOffered(index: number, name: string, offered: boolean): void {
    const aus = new Set(this.servers()[index]?.werkzeuge_aus ?? []);
    if (offered) aus.delete(name);
    else aus.add(name);
    this.edit(index, { werkzeuge_aus: [...aus].sort() });
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

  /**
   * `force`: „Trotzdem speichern" after a conflict — against exactly the
   * version the conflict reported, not unconditionally (Paket 4, D5).
   */
  async save(force = false): Promise<void> {
    if (this.incomplete() || this.saving()) return;
    this.saving.set(true);
    this.saveError.set('');
    this.status.set('');
    try {
      const conflict = this.conflict();
      const expected = force && conflict ? conflict.version : this.version();
      await this.api.put('/config/mcp-servers', {
        servers: this.servers(),
        ...(expected === null ? {} : { expected_version: expected }),
      });
      // Re-read rather than trust the local copy: the backend strips UI meta,
      // restores the primary if it went missing, and re-enriches descriptions.
      await this.load();
      this.status.set(this.t('editor.saved'));
    } catch (err) {
      if (err instanceof StudioApiError && err.status === 409) {
        this.conflict.set(err.conflict ?? { version: null, updatedBy: null, updatedAt: null });
      } else {
        this.saveError.set(describeApiError(err, this.t));
      }
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
