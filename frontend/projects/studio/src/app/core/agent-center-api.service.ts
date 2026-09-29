/**
 * Die Agent-Steuerzentrale, wie das Studio sie liest (ST-8): `/api/agent-center`.
 *
 * Nur lesend. Die Routen stehen neben `/api/master-skill` und nicht unter
 * `/api/agent`, der sich mit `AGENT_OPEN` ohne Anmeldung öffnen lässt.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

/**
 * Wann ein Werkzeug fehlt (`services/agent_tool_overview.py`). `code` sagt, welche
 * Stelle es nimmt; die übrigen Felder tragen die Werte dazu.
 */
export interface AgentToolLock {
  readonly code: string;
  /** `tool_mode`: die Werte des Einbettungs-Attributs, die es nehmen. */
  readonly modes?: readonly string[];
  /** `safety_fixed`: `crisis` | `threat` | `pii`. */
  readonly signals?: readonly string[];
  /** `policy`: die Kennungen der Regeln. */
  readonly rules?: readonly string[];
}

export interface AgentTool {
  readonly name: string;
  /** `read` | `curation` | `virtual`. */
  readonly kind: string;
  /** Was das Modell über das Werkzeug liest. */
  readonly description: string;
  /** Bekommt ein gewöhnlicher Chat-Zug im Agent-Modus es? */
  readonly offered: boolean;
  readonly locks: readonly AgentToolLock[];
}

export interface AgentToolList {
  readonly tools: readonly AgentTool[];
}

/** Ein freigegebener Skill (`services/agent_skill_directory.py`). Fremd
 *  beschriebener Text aus dem Repositorium — als reiner Text zeigen. */
export interface SkillEntry {
  readonly node_id: string;
  readonly title: string;
  readonly description: string;
  readonly keywords: readonly string[];
  readonly context: string;
  readonly url: string;
  /** Der md-editor des Repositoriums — auf das Original, nie auf einen Verweis (Paket F). */
  readonly edit_url: string;
}

/**
 * Skills per Suchbegriff (`GET /api/agent-center/skills/search`, Paket F3).
 * `available: false`: der MCP-Server bietet `search_skill` nicht an — dann über
 * die Sammlungs-ID suchen. `truncated`: so viele Treffer wie erbeten (Server
 * ohne Gesamtzahl) — die Liste kann gekappt sein.
 */
export interface SkillSearch {
  readonly query: string;
  readonly available: boolean;
  readonly entries: readonly SkillEntry[];
  readonly truncated?: boolean;
}

export interface SkillDirectory {
  readonly collection_id: string;
  /** `null`, wenn die Sammlung kein Registry-Dokument führt; `reason` sagt warum. */
  readonly registry: { readonly node_id: string; readonly title: string; readonly url: string } | null;
  readonly entries: readonly SkillEntry[];
  /** Im Dokument genannt, im Repositorium nicht gefunden. */
  readonly unresolved: readonly { readonly node_id: string; readonly title: string }[];
  /** `collection_not_found` | `no_registry` | `unreadable` — vom MCP-Server. */
  readonly reason: string | null;
  /** Die Suche oder die Liste wurde gekappt: womöglich unvollständig. */
  readonly truncated: boolean;
}

/**
 * Ein Glied der Kette eines Chat-Zugs (`services/agent_prompt_preview.py`).
 * `head` und `master_skill` tragen ihren Wortlaut; die Glieder danach hängen am
 * einzelnen Zug und kommen nur als Kennung.
 */
export interface PromptChainItem {
  readonly id: string;
  readonly text?: string | null;
  readonly chars?: number;
  /** Nur `master_skill`: `on` | `off` | `no_node` | `failed`. */
  readonly state?: string;
  readonly node_id?: string;
  readonly sha256?: string | null;
  readonly error?: string | null;
}

export interface PromptPreview {
  readonly locale: string;
  readonly chain: readonly PromptChainItem[];
  /** Die Werkzeug-Beschreibungen gehen jede Runde mit — Zahl und Umfang. */
  readonly tools: { readonly count: number; readonly chars: number };
}

@Injectable({ providedIn: 'root' })
export class AgentCenterApi {
  private readonly api = inject(StudioApi);

  tools(): Promise<AgentToolList> {
    return this.api.get<AgentToolList>('/agent-center/tools');
  }

  skills(collection: string): Promise<SkillDirectory> {
    return this.api.get<SkillDirectory>('/agent-center/skills', { collection });
  }

  searchSkills(q: string): Promise<SkillSearch> {
    return this.api.get<SkillSearch>('/agent-center/skills/search', { q });
  }

  prompt(locale: string): Promise<PromptPreview> {
    return this.api.get<PromptPreview>('/agent-center/prompt', { locale });
  }
}
