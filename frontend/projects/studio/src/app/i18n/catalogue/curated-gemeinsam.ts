/**
 * Paket 15: Texte der gemeinsamen Seiten „Zielgruppen“, „Werkzeuge“ und „Skills“
 * (`views/curated-pages-gemeinsam.ts`).
 */
import type { CataloguePart } from './catalogue-part';

export const CURATED_GEMEINSAM: CataloguePart = {
  de: {
    'curated.zielgruppen.intro':
      'Wie der Chatbot wen anspricht — in beiden Modi. Die übrigen Persona-Einstellungen '
      + '(Erkennung, Ton, Muster) stehen unter Muster › Dimensionen.',
    'curated.zielgruppen.rueckfall.label': 'Rückfall der Anrede',
    'curated.zielgruppen.rueckfall.hint':
      'Gilt, wenn eine Zielgruppe „wie die Person schreibt“ trägt und die Person noch nichts '
      + 'geschrieben hat.',
    'curated.werkzeuge.intro':
      'Alle Werkzeuge, die ein Zug bekommen kann — eingebaute, die des WLO-Servers und die '
      + 'weiterer MCP-Server — mit Herkunft und dem, was eines sperren kann. Gilt in beiden Modi.',
    'curated.wissen.reiter.rag': 'Wissensbereiche',
    'curated.anzeige.reiter.chat': 'Im Chat',
    'curated.anzeige.reiter.karten': 'Karten',
    'curated.anzeige.reiter.kopfzeile': 'Kopfzeile',
    'curated.anzeige.reiter.geraete': 'Geräte',
    'curated.fuehrung.reiter.tour': 'Website-Tour',
    'curated.fuehrung.reiter.lotse': 'Lotse',
    'curated.fuehrung.reiter.regeln': 'Lotsen-Regeln',
    'curated.wissen.reiter.mcp': 'MCP-Server',
    'curated.skills.intro':
      'Der Master-Skill, nach dem der Agent arbeitet, die Skills einer Sammlung und die '
      + 'Skill-Brücke, die freigegebene Skills auch Muster-Zügen mitgibt.',
  },
  en: {
    'curated.zielgruppen.intro':
      'How the chatbot addresses whom — in both modes. The other persona settings '
      + '(detection, tone, patterns) are under Patterns › Dimensions.',
    'curated.zielgruppen.rueckfall.label': 'Fallback form of address',
    'curated.zielgruppen.rueckfall.hint':
      'Applies when an audience is set to “as the person writes” and the person has not '
      + 'written yet.',
    'curated.werkzeuge.intro':
      'Every tool a turn can get — built-in ones, those of the WLO server and those of further '
      + 'MCP servers — with their origin and what can lock one. Applies in both modes.',
    'curated.wissen.reiter.rag': 'Knowledge areas',
    'curated.anzeige.reiter.chat': 'In the chat',
    'curated.anzeige.reiter.karten': 'Cards',
    'curated.anzeige.reiter.kopfzeile': 'Header',
    'curated.anzeige.reiter.geraete': 'Devices',
    'curated.fuehrung.reiter.tour': 'Website tour',
    'curated.fuehrung.reiter.lotse': 'Guide',
    'curated.fuehrung.reiter.regeln': 'Guide rules',
    'curated.wissen.reiter.mcp': 'MCP servers',
    'curated.skills.intro':
      'The master skill the agent works by, a collection’s skills and the skill bridge that '
      + 'also gives approved skills to pattern turns.',
  },
};
