/**
 * Die kuratierten Seiten für den Betrieb (9-4b): Anzeige, Datenschutz, Wissen,
 * Agent.
 *
 * Aus `curated-views.ts` herausgelöst (Paket 6), das über 300 Zeilen stand; die
 * Regeln für diese Daten stehen dort im Kopf. Die Reihenfolge der Seiten und
 * ihrer Abschnitte ist unverändert.
 */
import type { CuratedView } from './curated-views';

export const BETRIEB_SEITEN: readonly CuratedView[] = [
  {
    slug: 'anzeige',
    introKey: 'curated.anzeige.intro',
    sections: [
      {
        area: '01-base/display-rules',
        labelKey: 'curated.anzeige.display.label',
        hintKey: 'curated.anzeige.display.hint',
      },
      // ST-9: welche Treffer überhaupt zu Karten werden, und die Links darin.
      {
        area: '01-base/card-pipeline',
        labelKey: 'curated.anzeige.cardPipeline.label',
        hintKey: 'curated.anzeige.cardPipeline.hint',
      },
      {
        area: '01-base/widget-modes',
        labelKey: 'curated.anzeige.widgetModes.label',
        hintKey: 'curated.anzeige.widgetModes.hint',
      },
      {
        area: '01-base/header-nav',
        labelKey: 'curated.anzeige.header.label',
        hintKey: 'curated.anzeige.header.hint',
      },
      {
        area: '01-base/device-config',
        labelKey: 'curated.anzeige.devices.label',
        hintKey: 'curated.anzeige.devices.hint',
      },
    ],
  },
  {
    slug: 'datenschutz',
    introKey: 'curated.datenschutz.intro',
    sections: [
      {
        area: '01-base/privacy-config',
        labelKey: 'curated.datenschutz.privacy.label',
        hintKey: 'curated.datenschutz.privacy.hint',
      },
      {
        area: '01-base/quality-log-config',
        labelKey: 'curated.datenschutz.qualityLog.label',
        hintKey: 'curated.datenschutz.qualityLog.hint',
      },
      {
        // Paket 8 (A): what the `retention_days` fields (conversations, safety log,
        // quality log) mean right now.
        panel: 'retention',
        labelKey: 'curated.datenschutz.retention.label',
        hintKey: 'curated.datenschutz.retention.hint',
      },
      {
        panel: 'privacy-purge',
        labelKey: 'curated.datenschutz.purge.label',
        hintKey: 'curated.datenschutz.purge.hint',
      },
    ],
  },
  {
    slug: 'wissen',
    introKey: 'curated.wissen.intro',
    sections: [
      {
        panel: 'rag-areas',
        labelKey: 'curated.wissen.areas.label',
        hintKey: 'curated.wissen.areas.hint',
      },
      {
        panel: 'rag-ingest',
        labelKey: 'curated.wissen.ingest.label',
        hintKey: 'curated.wissen.ingest.hint',
      },
      {
        // Describes the areas the panel above lists — only useful together,
        // which is why this config sits between them and not on its own page.
        area: '05-knowledge/rag-config',
        labelKey: 'curated.wissen.ragConfig.label',
        hintKey: 'curated.wissen.ragConfig.hint',
      },
      {
        // Paket 7 (P4): read since ever by `rag/retrieval`, editable only now.
        area: '01-base/rag-retrieval',
        labelKey: 'curated.wissen.retrieval.label',
        hintKey: 'curated.wissen.retrieval.hint',
      },
      {
        panel: 'mcp-registry',
        labelKey: 'curated.wissen.mcp.label',
        hintKey: 'curated.wissen.mcp.hint',
      },
    ],
  },
  {
    // Umschalter und Probelauf auf EINER Seite: wer die Maschine umstellt, will
    // sehen, was sie tut, und wer einen Lauf startet, will wissen, unter welchen
    // Deckeln er läuft. Getrennt wären es zwei Seiten, zwischen denen man
    // hin- und herspringt, um eine einzige Frage zu beantworten.
    slug: 'agent',
    introKey: 'curated.agent.intro',
    sections: [
      {
        area: '01-base/engine',
        labelKey: 'curated.agent.engine.label',
        hintKey: 'curated.agent.engine.hint',
      },
      {
        // ST-8d: the start of a turn's chain as the model reads it — our own
        // rules first, then the master skill below, then what each turn adds.
        panel: 'agent-prompt',
        labelKey: 'curated.agent.prompt.label',
        hintKey: 'curated.agent.prompt.hint',
      },
      {
        // AG-2: lives in the repository, shown here read-only (user decision
        // 2026-09-26) — a panel because its source is `/api/master-skill`.
        panel: 'master-skill',
        labelKey: 'curated.agent.masterSkill.label',
        hintKey: 'curated.agent.masterSkill.hint',
      },
      {
        // ST-8b: what the loop gets and what can take a tool away — read-only,
        // each lock stays where it is maintained.
        panel: 'agent-tools',
        labelKey: 'curated.agent.tools.label',
        hintKey: 'curated.agent.tools.hint',
      },
      {
        // ST-8c: which skills a collection approves — its registry document,
        // fetched on request (one MCP call per collection).
        panel: 'agent-skills',
        labelKey: 'curated.agent.skills.label',
        hintKey: 'curated.agent.skills.hint',
      },
      {
        // ST-8e (AG-4 part A): a conversation over the real chat path with the
        // agent engine — the task tester below drives `/api/agent` instead.
        panel: 'agent-probe',
        labelKey: 'curated.agent.probe.label',
        hintKey: 'curated.agent.probe.hint',
      },
      {
        panel: 'agent-tester',
        labelKey: 'curated.agent.tester.label',
        hintKey: 'curated.agent.tester.hint',
      },
    ],
  },
];
