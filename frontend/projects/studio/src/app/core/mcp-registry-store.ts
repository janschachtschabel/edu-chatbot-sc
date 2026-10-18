/**
 * Die MCP-Server-Liste als Zustand (Paket 15): laden, bearbeiten, speichern — die Logik des
 * Panels „MCP-Server“ (Wissen) und der Seite „Werkzeuge“, deren Schalter dieselbe Liste
 * schreiben. Je Komponente eine eigene Instanz; die Version schützt beide (409).
 *
 * Aus `views/mcp-registry.component.ts` gelöst, verhaltensgleich. `/config/mcp-servers` statt
 * des generischen Bereichs-Endpunkts: der GET reichert jeden Server mit den Live-Beschreibungen
 * an, der PUT prüft jede Adresse (SSRF). Der PUT ersetzt die ganze Liste — ein Speichern für
 * alles, sonst wären es N Anfragen, die halb scheitern können.
 */
import { computed, signal } from '@angular/core';

import type { Translate } from '../i18n/studio-language.service';
import { describeApiError } from './async-data';
import { type SaveConflict, StudioApiError } from './studio-api-error';
import type { StudioApi } from './studio-api.service';

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

export interface DiscoveredTool {
  readonly name: string;
  readonly description: string;
  readonly input_schema?: Record<string, unknown>;
  readonly read_only?: boolean;
}

export class McpRegistryStore {
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

  private readonly saved = signal('[]');
  readonly dirty = computed(() => JSON.stringify(this.servers()) !== this.saved());

  /**
   * `save_mcp_servers` skips every entry without an id, so saving a nameless
   * row would answer 200 and drop it — the editor would watch their work
   * vanish with a "Gespeichert." next to it.
   */
  readonly incomplete = computed(() => this.servers().some((s) => !s.id.trim()));

  constructor(private readonly api: StudioApi, private readonly t: Translate) {}

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

  /** Paket 15: den gespeicherten Stand zurückholen (Seite „Werkzeuge“). */
  discard(): void {
    this.servers.set(JSON.parse(this.saved()) as McpServer[]);
    this.conflict.set(null);
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

  private adopt(servers: McpServer[]): void {
    this.servers.set(servers);
    this.saved.set(JSON.stringify(servers));
  }
}
