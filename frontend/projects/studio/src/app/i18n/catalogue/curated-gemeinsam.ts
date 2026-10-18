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
      + 'geschrieben hat. Zeilen für Zielgruppen mit fester Anrede (Sie oder du) wirken nicht.',
    'curated.werkzeuge.intro':
      'Alle Werkzeuge, die ein Zug bekommen kann — eingebaute, die des WLO-Servers und die '
      + 'weiterer MCP-Server — mit Herkunft und dem, was eines sperren kann. Gilt in beiden Modi.',
    'curated.wissen.reiter.rag': 'Wissensbereiche',
    'curated.anzeige.reiter.chat': 'Im Chat',
    'curated.anzeige.reiter.karten': 'Karten',
    'curated.anzeige.reiter.kopfzeile': 'Kopfzeile',
    'curated.anzeige.reiter.geraete': 'Geräte',
    'curated.fuehrung.reiter.tour': 'Website-Tour',
    'curated.schutz.reiter.sicherheit': 'Sicherheit',
    'curated.schutz.reiter.rolle': 'Rolle & Grenzen',
    'curated.schutz.reiter.persona': 'Grundpersona',
    'curated.schutz.reiter.regeln': 'Leitplanken & Regeln',
    'curated.schutz.reiter.schutz': 'Schutzantworten',
    'curated.sprung.safetyLogs': 'Was die Sicherheitsstufe ausgelöst hat: Safety-Logs ansehen',
    'curated.agentRolle.gruppe.rolle': 'Rolle',
    'curated.agentRolle.gruppe.schutzregeln': 'Schutzregeln',
    'curated.agentRolle.gruppe.grenzen': 'Grenzen der Schleife',
    'curated.agentRolle.gruppe.anonym': 'Engere Grenzen ohne Anmeldung',
    'curated.fuehrung.gruppe.start': 'Start & Auslöser',
    'curated.fuehrung.gruppe.texte': 'Texte',
    'curated.fuehrung.gruppe.website': 'Website & Pfade',
    'curated.fuehrung.gruppe.gruppen': 'Besuchergruppen',
    'curated.fuehrung.gruppe.links': 'Linklisten',
    'curated.fuehrung.gruppe.schritte': 'Schritte',
    'curated.fuehrung.gruppe.doku': 'Doku (ohne Wirkung)',
    'curated.kontextAktionen.gruppe.technik': 'Technik',
    'curated.kontextAktionen.gruppe.begruessung': 'Begrüßung je Seitenart (DE)',
    'curated.kontextAktionen.gruppe.begruessungEn': 'Begrüßung je Seitenart (EN)',
    'curated.kontextAktionen.gruppe.pills': 'Pills je Seitenart',
    'curated.kontextAktionen.gruppe.dublette': 'Seite schon in WLO (DE)',
    'curated.kontextAktionen.gruppe.dubletteEn': 'Seite schon in WLO (EN)',
    'curated.kontextAktionen.gruppe.ki': 'KI-Anweisung „Sammlung kuratieren“ (intern)',
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
      + 'written yet. Rows for audiences with a fixed form of address have no effect.',
    'curated.werkzeuge.intro':
      'Every tool a turn can get — built-in ones, those of the WLO server and those of further '
      + 'MCP servers — with their origin and what can lock one. Applies in both modes.',
    'curated.wissen.reiter.rag': 'Knowledge areas',
    'curated.anzeige.reiter.chat': 'In the chat',
    'curated.anzeige.reiter.karten': 'Cards',
    'curated.anzeige.reiter.kopfzeile': 'Header',
    'curated.anzeige.reiter.geraete': 'Devices',
    'curated.fuehrung.reiter.tour': 'Website tour',
    'curated.schutz.reiter.sicherheit': 'Safety',
    'curated.schutz.reiter.rolle': 'Role & limits',
    'curated.schutz.reiter.persona': 'Base persona',
    'curated.schutz.reiter.regeln': 'Guardrails & rules',
    'curated.schutz.reiter.schutz': 'Protective answers',
    'curated.sprung.safetyLogs': 'What the safety level triggered: open the safety logs',
    'curated.agentRolle.gruppe.rolle': 'Role',
    'curated.agentRolle.gruppe.schutzregeln': 'Safeguard rules',
    'curated.agentRolle.gruppe.grenzen': 'Loop limits',
    'curated.agentRolle.gruppe.anonym': 'Tighter limits without sign-in',
    'curated.fuehrung.gruppe.start': 'Start & triggers',
    'curated.fuehrung.gruppe.texte': 'Texts',
    'curated.fuehrung.gruppe.website': 'Website & paths',
    'curated.fuehrung.gruppe.gruppen': 'Visitor groups',
    'curated.fuehrung.gruppe.links': 'Link lists',
    'curated.fuehrung.gruppe.schritte': 'Steps',
    'curated.fuehrung.gruppe.doku': 'Documentation (no effect)',
    'curated.kontextAktionen.gruppe.technik': 'Technical',
    'curated.kontextAktionen.gruppe.begruessung': 'Greeting per page type (DE)',
    'curated.kontextAktionen.gruppe.begruessungEn': 'Greeting per page type (EN)',
    'curated.kontextAktionen.gruppe.pills': 'Pills per page type',
    'curated.kontextAktionen.gruppe.dublette': 'Page already in WLO (DE)',
    'curated.kontextAktionen.gruppe.dubletteEn': 'Page already in WLO (EN)',
    'curated.kontextAktionen.gruppe.ki': 'AI instruction “curate collection” (internal)',
    'curated.fuehrung.reiter.lotse': 'Guide',
    'curated.fuehrung.reiter.regeln': 'Guide rules',
    'curated.wissen.reiter.mcp': 'MCP servers',
    'curated.skills.intro':
      'The master skill the agent works by, a collection’s skills and the skill bridge that '
      + 'also gives approved skills to pattern turns.',
  },
};
