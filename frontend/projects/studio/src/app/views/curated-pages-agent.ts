/**
 * Die kuratierten Seiten des Agent-Arbeitsbereichs (Paket 14): Rolle & Grenzen und Prompt &
 * Probelauf. Die Agent-Übersicht ist eine eigene Ansicht; Werkzeuge, Skills und die Anrede je
 * Zielgruppe stehen seit Paket 15 auf gemeinsamen Seiten (`curated-pages-gemeinsam.ts`).
 *
 * Was hier steht, liest die Agent-Schleife tatsächlich (`services/agent_kopf.py`, Code-Lesart
 * 2026-10-17): Rolle und Schutzregeln, die Leitplanken-Tabelle, die Grenzen der Schleife,
 * Sicherheitsstufe und Werkzeug-Policy, dazu die beiden Schutzantworten — Krisen- und
 * Drohungs-Züge beantwortet auch unter der Agent-Schleife der Muster-Weg (SF-1).
 *
 * Leitplanken, Sicherheit und Regelwerk stehen auch auf „Identität“ im Muster-Arbeitsbereich:
 * dasselbe Dokument, versioniert gespeichert; man ist immer nur in einem Arbeitsbereich.
 */
import type { CuratedView } from './curated-views';

export const AGENT_SEITEN: readonly CuratedView[] = [
  {
    slug: 'agent-rolle',
    introKey: 'curated.agentRolle.intro',
    sections: [
      {
        // Paket 15: Rolle, Schutzregeln und die Grenzen der Schleife in EINEM Abschnitt — zwei
        // Abschnitte desselben Dokuments auf einer Seite schickten sich beim Speichern
        // gegenseitig ins 409. Die Grenzen standen vorher auf „Werkzeuge & Skills“.
        area: '01-base/engine',
        felder: ['agent_rolle', 'agent'],
        labelKey: 'curated.agentRolle.rolle.label',
        hintKey: 'curated.agentRolle.rolle.hint',
      },
      {
        area: '01-base/guardrails',
        labelKey: 'curated.agentRolle.guardrails.label',
        hintKey: 'curated.agentRolle.guardrails.hint',
      },
      {
        area: '01-base/safety-config',
        labelKey: 'curated.agentRolle.safety.label',
        hintKey: 'curated.agentRolle.safety.hint',
        feature: 'safety-level',
      },
      {
        area: '01-base/policy',
        labelKey: 'curated.agentRolle.policy.label',
        hintKey: 'curated.agentRolle.policy.hint',
      },
      {
        area: '03-patterns',
        kind: 'group',
        dokumente: ['M01', 'M02'],
        // Paket 15: was eine Schutzantwort ausmacht. Routing-Felder (wann, Auslöser, Quellen)
        // wirken hier nicht — das Sicherheits-Tor erzwingt M01/M02 —, sie stehen unter Patterns.
        felder: [
          'body', 'frontmatter.core_rule', 'frontmatter.default_tone',
          'frontmatter.default_length', 'frontmatter.quick_replies_mode',
          'frontmatter.forbidden_phrases',
        ],
        labelKey: 'curated.agentRolle.schutz.label',
        hintKey: 'curated.agentRolle.schutz.hint',
      },
    ],
  },
  {
    slug: 'agent-prompt',
    introKey: 'curated.agentPrompt.intro',
    sections: [
      {
        // ST-8d: the start of a turn's chain as the model reads it — our own
        // rules first, then the master skill below, then what each turn adds.
        panel: 'agent-prompt',
        labelKey: 'curated.agent.prompt.label',
        hintKey: 'curated.agent.prompt.hint',
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
