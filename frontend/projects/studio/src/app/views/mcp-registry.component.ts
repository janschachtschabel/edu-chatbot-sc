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
import { RouterLink } from '@angular/router';

import { describeApiError } from '../core/async-data';
import {
  type DiscoveredTool, type McpServer, McpRegistryStore,
} from '../core/mcp-registry-store';
import { StudioApi } from '../core/studio-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import { SaveConflictComponent } from './save-conflict.component';

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
  imports: [RouterLink, SaveConflictComponent],
  templateUrl: './mcp-registry.component.html',
  styleUrl: './mcp-registry.component.scss',
})
export class McpRegistryComponent {
  private readonly api = inject(StudioApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  /** Paket 15: dieselbe Logik wie die Seite „Werkzeuge“ (`McpRegistryStore`), aber eine eigene
   *  Instanz — beide schreiben dieselbe Server-Liste, je mit eigener Version und eigenem 409. */
  readonly reg = new McpRegistryStore(this.api, this.t);
  readonly servers = this.reg.servers;
  readonly loading = this.reg.loading;
  readonly loadError = this.reg.loadError;
  readonly saving = this.reg.saving;
  readonly saveError = this.reg.saveError;
  readonly status = this.reg.status;
  readonly conflict = this.reg.conflict;
  readonly dirty = this.reg.dirty;
  readonly incomplete = this.reg.incomplete;

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

  load(): Promise<void> {
    return this.reg.load();
  }

  toolsOf(server: McpServer): { name: string; description: string }[] {
    return (server.tools ?? []).map((name) => ({
      name,
      description: server.tool_descriptions?.[name] ?? '',
    }));
  }

  /** Paket 15: der Kopf einer zugeklappten Server-Zeile — „3 Werkzeuge, 1 aus“. */
  werkzeugZahl(server: McpServer): string {
    const n = (server.tools ?? []).length;
    return this.lang.plural('mcp.werkzeugZahl', n, { aus: (server.werkzeuge_aus ?? []).length });
  }

  isOffered(server: McpServer, name: string): boolean {
    return this.reg.isOffered(server, name);
  }

  hasSwitch(server: McpServer, name: string): boolean {
    return this.reg.hasSwitch(server, name);
  }

  setOffered(index: number, name: string, offered: boolean): void {
    this.reg.setOffered(index, name, offered);
  }

  edit(index: number, patch: Partial<McpServer>): void {
    this.reg.edit(index, patch);
  }

  /** Die eben angelegte Zeile — sie steht offen, bis gespeichert, geladen oder entfernt. */
  readonly neueZeile = signal<number | null>(null);

  add(): void {
    this.reg.add();
    this.neueZeile.set(this.servers().length - 1);
  }

  remove(index: number): void {
    this.reg.remove(index);
    this.neueZeile.set(null);
  }

  async save(force = false): Promise<void> {
    await this.reg.save(force);
    if (!this.reg.saveError() && !this.reg.conflict()) this.neueZeile.set(null);
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
}
