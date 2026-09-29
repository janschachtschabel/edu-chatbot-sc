/**
 * Die Werkzeugliste der Agent-Seite, aufbereitet (ST-8b).
 *
 * Reine Logik, ohne DOM prüfbar. Die Liste selbst baut der Server aus denselben
 * Quellen wie der Zug (`services/agent_tool_overview.py`); hier wird sie nur
 * gruppiert und in Sätze übersetzt.
 */
import type { AgentTool, AgentToolLock } from '../core/agent-center-api.service';
import type { StudioLanguageService } from '../i18n/studio-language.service';

/** Was `lockText` von der Sprache braucht — im Test ohne Angular zu bauen. */
export type LockWords = Pick<StudioLanguageService, 't' | 'plural' | 'listOr'>;

export interface ToolGroup {
  readonly kind: string;
  readonly tools: readonly AgentTool[];
}

/** Lesend vorn: das sind die Werkzeuge, die jeder Zug hat. */
const KIND_ORDER = ['read', 'curation', 'virtual'];

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
    case 'never':
      return w.t('agentTools.lock.never');
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

/** Die Studio-Seite, auf der die Sperre gepflegt wird — `null`, wo es keine gibt. */
export function lockLink(lock: AgentToolLock): string | null {
  switch (lock.code) {
    case 'policy':
      return 'identitaet';
    case 'knowledge_areas':
      return 'wissen';
    default:
      return null;
  }
}
