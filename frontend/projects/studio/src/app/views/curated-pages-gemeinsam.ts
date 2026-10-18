/**
 * Gemeinsame Seiten aus dem Nutzer-Rundgang vom 2026-10-17 (Paket 15): Zielgruppen, Werkzeuge
 * und Skills gelten in beiden Modi — vorher standen sie verteilt (Anrede auf „Rolle & Grenzen“,
 * der Rückfall unter „Anzeige“, Werkzeuge doppelt im MCP-Panel und auf der Agent-Seite, die
 * Skills auf der Agent- und der Patterns-Seite).
 */
import type { CuratedView } from './curated-views';

export const GEMEINSAME_SEITEN: readonly CuratedView[] = [
  {
    slug: 'zielgruppen',
    introKey: 'curated.zielgruppen.intro',
    sections: [
      {
        // Zielgruppe → du/Sie gilt für beide Maschinen und bleibt in den Personas
        // (Entscheid 2026-08-18/-21/-28); hier nur die Anrede, die übrigen Persona-Felder
        // stehen unter Muster › Dimensionen.
        panel: 'anrede',
        labelKey: 'curated.agentRolle.anrede.label',
        hintKey: 'curated.agentRolle.anrede.hint',
      },
      {
        // Der Rückfall, wenn eine Persona keine Anrede trägt (`agent_kopf`, Muster-Weg).
        area: '01-base/device-config',
        felder: ['persona_formality'],
        labelKey: 'curated.zielgruppen.rueckfall.label',
        hintKey: 'curated.zielgruppen.rueckfall.hint',
      },
    ],
  },
  {
    slug: 'werkzeuge',
    introKey: 'curated.werkzeuge.intro',
    sections: [
      {
        // ST-8b: was ein Zug bekommt und was ein Werkzeug wegnehmen kann.
        panel: 'agent-tools',
        labelKey: 'curated.agent.tools.label',
        hintKey: 'curated.agent.tools.hint',
      },
    ],
  },
  {
    slug: 'skills',
    introKey: 'curated.skills.intro',
    sections: [
      {
        // AG-2: lebt im Repositorium, hier lesend (Nutzer-Entscheid 2026-09-26).
        panel: 'master-skill',
        labelKey: 'curated.agent.masterSkill.label',
        hintKey: 'curated.agent.masterSkill.hint',
      },
      {
        // ST-8c: welche Skills eine Sammlung freigibt — Registry-Dokument und Suche.
        panel: 'agent-skills',
        labelKey: 'curated.agent.skills.label',
        hintKey: 'curated.agent.skills.hint',
      },
      {
        // Paket 14 (E-6): die Skill-Brücke der Muster-Maschine — ein Feld aus `01-base/engine`.
        area: '01-base/engine',
        felder: ['muster_skills'],
        zuerstIn: 'pattern',
        labelKey: 'curated.patterns.skillBruecke.label',
        hintKey: 'curated.patterns.skillBruecke.hint',
      },
    ],
  },
];
