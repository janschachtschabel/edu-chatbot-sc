/**
 * Feldtexte (ST-1) der Seite „Wissen“, Bereich `05-knowledge/rag-config` — je
 * Wissensbereich ein Eintrag (`RagAreaDef`). `mode` steuert die Muster-Engine
 * (`domain/route_head.py`, `services/tool_loop_messages.py`), `agent` allein die
 * Agent-Schleife (`services/agent_knowledge.py`); `description` lesen beide. Ein
 * Eintrag ganz ohne `mode` fällt schon im Lader weg (`services/config_loader/rag.py`),
 * in beiden Maschinen; „nicht gesetzt“ im Studio schreibt dagegen einen leeren Wert.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_WISSENSBEREICHE: CataloguePart = {
  de: {
    'feld.RagAreaDef.mode.label': 'Abrufart',
    'feld.RagAreaDef.mode.hint':
      'Muster-Engine: always = wird vor der Antwort vorab durchsucht; on-demand = nur auf '
      + 'Abruf des Modells und nur in Mustern, die Wissen anfordern. Nicht gesetzt: nur in '
      + 'Mustern, die den Bereich ausdrücklich nennen.',
    'feld.RagAreaDef.description.label': 'Beschreibung',
    'feld.RagAreaDef.description.hint':
      'Kurzbeschreibung des Bereichs. Beide Maschinen zeigen sie dem Modell im '
      + 'Wissenswerkzeug; danach wählt es, welchen Bereich es durchsucht.',
    'feld.RagAreaDef.agent.label': 'Für die Agent-Schleife',
    'feld.RagAreaDef.agent.hint':
      'Darf die Agent-Schleife diesen Bereich durchsuchen? Aus nimmt ihn nur dort heraus; in '
      + 'der Muster-Engine gilt die Abrufart. Ohne Eintrag an.',
  },
  en: {
    'feld.RagAreaDef.mode.label': 'Retrieval mode',
    'feld.RagAreaDef.mode.hint':
      'Pattern engine: always = searched in advance before the answer; on-demand = only when '
      + 'the model asks, and only in patterns that request knowledge. Not set: only in '
      + 'patterns that name the area explicitly.',
    'feld.RagAreaDef.description.label': 'Description',
    'feld.RagAreaDef.description.hint':
      'Short description of the area. Both engines show it to the model in the knowledge '
      + 'tool; the model uses it to choose which area to search.',
    'feld.RagAreaDef.agent.label': 'For the agent loop',
    'feld.RagAreaDef.agent.hint':
      'May the agent loop search this area? Off removes it only there; in the pattern engine '
      + 'the retrieval mode applies. Without an entry, on.',
  },
};
