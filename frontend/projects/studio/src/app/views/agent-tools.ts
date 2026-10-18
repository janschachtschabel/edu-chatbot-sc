/**
 * Die Werkzeugliste der Agent-Seite, aufbereitet (ST-8b).
 *
 * Reine Logik, ohne DOM prüfbar. Die Liste selbst baut der Server aus denselben
 * Quellen wie der Zug (`services/agent_tool_overview.py`); hier wird sie nur
 * gruppiert und in Sätze übersetzt.
 */
import type { AgentTool, AgentToolLock } from '../core/agent-center-api.service';
import type { Engine } from '../core/effects-api.service';
import type { McpServer } from '../core/mcp-registry-store';
import type { StudioLanguageService } from '../i18n/studio-language.service';
import { heimatSeite } from './area-homes';

/** Was `lockText` von der Sprache braucht — im Test ohne Angular zu bauen. */
export type LockWords = Pick<StudioLanguageService, 't' | 'plural' | 'listOr'>;

export interface ToolGroup {
  readonly kind: string;
  readonly tools: readonly AgentTool[];
}

/** Lesend vorn: das sind die Werkzeuge, die jeder Zug hat. */
const KIND_ORDER = ['read', 'curation', 'external', 'virtual'];

export function groupTools(tools: readonly AgentTool[]): ToolGroup[] {
  const kinds = [...KIND_ORDER, ...new Set(tools.map((t) => t.kind).filter((k) => !KIND_ORDER.includes(k)))];
  return kinds
    .map((kind) => ({ kind, tools: tools.filter((t) => t.kind === kind) }))
    .filter((group) => group.tools.length > 0);
}

/**
 * Der erste Satz einer Werkzeug-Beschreibung.
 *
 * Ein Satz endet an `.`, `!` oder `?` vor einem Großbuchstaben — so trennen
 * „z.B. 'welche …'" und „(max. 50)" nicht. Ein Absatz endet ihn ebenfalls.
 */
export function firstSentence(text: string): string {
  const absatz = text.split(/\n\s*\n/)[0];
  const ende = /[.!?](?=\s+[A-ZÄÖÜ])/.exec(absatz);
  return (ende ? absatz.slice(0, ende.index + 1) : absatz).trim();
}

/**
 * Anlass im Regex-Gate → Katalog-Schlüssel; ein unbekannter kommt roh durch. Nur
 * persönliche Daten: Krise und Drohung nehmen keine einzelnen Werkzeuge, dann
 * antwortet das Schutzmuster statt der Schleife (Hinweis über der Tabelle).
 */
const SIGNAL_KEYS: ReadonlyMap<string, string> = new Map([
  ['pii', 'agentTools.signal.pii'],
]);

/** Wann das Werkzeug fehlt, als Satz. Ein unbekannter Code kommt roh durch. */
export function lockText(lock: AgentToolLock, w: LockWords): string {
  switch (lock.code) {
    case 'hidden':
      return w.t('agentTools.lock.hidden');
    case 'needs_access':
      return w.t('agentTools.lock.needsAccess');
    case 'tool_mode':
      return w.t('agentTools.lock.toolMode', { modes: w.listOr(lock.modes ?? []) });
    case 'safety_fixed': {
      const signals = (lock.signals ?? []).map((s) => {
        const key = SIGNAL_KEYS.get(s);
        return key ? w.t(key) : s;
      });
      return w.t('agentTools.lock.safetyFixed', { signals: w.listOr(signals) });
    }
    case 'policy': {
      const rules = lock.rules ?? [];
      return w.plural('agentTools.lock.policy', rules.length, { rules: w.listOr(rules) });
    }
    case 'knowledge_areas':
      return w.t('agentTools.lock.knowledgeAreas');
    case 'host_schema':
      return w.t('agentTools.lock.hostSchema');
    default:
      return lock.code;
  }
}

/** Die Studio-Seite, auf der die Sperre gepflegt wird — `null`, wo es keine gibt. Die Seite
 *  „Werkzeuge“ ist gemeinsam: das Regelwerk steht je Arbeitsbereich woanders (Review PR #18). */
export function lockLink(lock: AgentToolLock, ansicht: Engine): string | null {
  switch (lock.code) {
    case 'policy':
      return heimatSeite('01-base/policy', ansicht);
    case 'knowledge_areas':
      return 'wissen';
    default:
      return null;
  }
}

/** Wo ein Werkzeug an- und abgeschaltet wird: Server (Index in der Liste), Name dort, Anzeige. */
export interface Schalter {
  readonly index: number;
  readonly name: string;
  readonly server: string;
}

/** Wie `fremdwerkzeuge._PRIMARY_ID` im Backend. */
const WLO_SERVER_ID = 'wlo-mcp';

/**
 * Paket 15: der Schalter eines Werkzeugs — `werkzeuge_aus` des Servers, dessen Katalog es
 * führt. Fremde Werkzeuge heißen im Zug `server__werkzeug`. Eingebaute (virtuelle) und
 * Werkzeuge ohne Katalog-Eintrag tragen keinen: dort wirkt ein Schalter nicht.
 */
export function schalterFuer(tool: AgentTool, servers: readonly McpServer[]): Schalter | null {
  if (tool.kind === 'virtual') return null;
  // Fremd: Server und Originalname aus der Zeile; WLO: nur am WLO-Server — ein fremder Server
  // mit gleichnamigem Werkzeug ist ein anderer Namensraum (Review-Runde 2).
  const fremd = tool.kind === 'external';
  const serverId = fremd ? tool.server_id : WLO_SERVER_ID;
  const name = fremd ? tool.tool : tool.name;
  if (!serverId || !name) return null;
  const index = servers.findIndex((s) => s.id === serverId
    && (s.werkzeuge_im_katalog ?? []).includes(name));
  if (index < 0) return null;
  return { index, name, server: servers[index].name || servers[index].id };
}

/** Paket 16, C7: woher ein Werkzeug kommt — nach Art, unabhängig davon, ob es einen Schalter
 *  trägt (das Schreibwerkzeug hat keinen und kommt doch vom WLO-MCP). */
export type HerkunftArt = 'eingebaut' | 'wlo' | 'fremd';

export interface Herkunft {
  readonly art: HerkunftArt;
  /** Anzeigename des Servers; seine Kennung, solange die Server-Liste fehlt. */
  readonly server: string;
  readonly host: string;
}

export function herkunftVon(tool: AgentTool, servers: readonly McpServer[]): Herkunft {
  if (tool.kind === 'virtual') return { art: 'eingebaut', server: '', host: '' };
  const art: HerkunftArt = tool.kind === 'external' ? 'fremd' : 'wlo';
  const id = art === 'fremd' ? tool.server_id ?? '' : WLO_SERVER_ID;
  const eintrag = servers.find((s) => s.id === id);
  return { art, server: eintrag ? eintrag.name || eintrag.id : id, host: hostVon(eintrag?.url) };
}

function hostVon(url: string | undefined): string {
  if (!url) return '';
  try {
    return new URL(url).host;
  } catch {
    // Eine noch nicht gespeicherte, halbe Eingabe im MCP-Panel — dann eben ohne Host.
    return '';
  }
}
