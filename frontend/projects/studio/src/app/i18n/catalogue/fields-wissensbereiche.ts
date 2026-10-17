/**
 * Feldtexte (ST-1) der Seite „Wissen“, Bereich `05-knowledge/rag-config` — je
 * Wissensbereich ein Eintrag (`RagAreaDef`). `mode` steuert die Muster-Engine
 * (`domain/route_head.py`, `services/tool_loop_messages.py`), `agent` allein die
 * Agent-Schleife (`services/agent_knowledge.py`); `description` lesen beide. Ein
 * Eintrag ganz ohne `mode` fällt schon im Lader weg (`services/config_loader/rag.py`),
 * in beiden Maschinen; „nicht gesetzt“ im Studio schreibt dagegen einen leeren Wert.
 *
 * Dazu `01-base/rag-retrieval` (Paket 7, P4): die Werte der Wissenssuche
 * (`services/rag/retrieval.get_retrieval_settings`) für beide Maschinen.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_WISSENSBEREICHE: CataloguePart = {
  de: {
    'feld.RagAreaDef.mode.label': 'Abrufart',
    'feld.RagAreaDef.mode.hint':
      'Muster-Engine: always = wird vor der Antwort vorab durchsucht; on-demand = nur auf '
      + 'Abruf des Modells. Beides nur in Mustern, die den Bereich nennen oder ohne eigene '
      + 'Liste Wissen (rag) anfordern. Nicht gesetzt: nur in Mustern, die den Bereich '
      + 'ausdrücklich nennen.',
    'feld.RagAreaDef.description.label': 'Beschreibung',
    'feld.RagAreaDef.description.hint':
      'Kurzbeschreibung des Bereichs. Beide Maschinen zeigen sie dem Modell im '
      + 'Wissenswerkzeug; danach wählt es, welchen Bereich es durchsucht.',
    'feld.RagAreaDef.agent.label': 'Für die Agent-Schleife',
    'feld.RagAreaDef.agent.hint':
      'Darf die Agent-Schleife diesen Bereich durchsuchen? Aus nimmt ihn nur dort heraus; in '
      + 'der Muster-Engine gilt die Abrufart. Ohne Eintrag an.',
    'feld.RagRetrievalArea.retrieval.label': 'Wissenssuche',
    'feld.RagRetrievalArea.retrieval.hint':
      'Werte für jede Suche in den Wissensbereichen, in beiden Maschinen.',
    'feld.RagAbruf.top_k.label': 'Treffer je Suche',
    'feld.RagAbruf.top_k.hint':
      'Wie viele Abschnitte eine Suche höchstens liefert, 1 bis 50. Leer = Vorgabe 10. '
      + 'Umgebung: RAG_TOP_K.',
    'feld.RagAbruf.min_score.label': 'Mindestähnlichkeit',
    'feld.RagAbruf.min_score.hint':
      'Abschnitte unter dieser Ähnlichkeit (0 bis 1) fallen weg. Leer = Vorgabe 0,30. '
      + 'Umgebung: RAG_MIN_SCORE.',
    'feld.RagAbruf.max_chars_per_area.label': 'Zeichen je Bereich',
    'feld.RagAbruf.max_chars_per_area.hint':
      'Höchstens so viel Text eines Bereichs kommt in den Prompt; 0 = ohne Grenze. '
      + 'Leer = Vorgabe 3000. Umgebung: RAG_MAX_CHARS_PER_AREA.',
  },
  en: {
    'feld.RagAreaDef.mode.label': 'Retrieval mode',
    'feld.RagAreaDef.mode.hint':
      'Pattern engine: always = searched in advance before the answer; on-demand = only when '
      + 'the model asks. Both only in patterns that name the area, or request knowledge (rag) '
      + 'without a list of their own. Not set: only in patterns that name the area explicitly.',
    'feld.RagAreaDef.description.label': 'Description',
    'feld.RagAreaDef.description.hint':
      'Short description of the area. Both engines show it to the model in the knowledge '
      + 'tool; the model uses it to choose which area to search.',
    'feld.RagAreaDef.agent.label': 'For the agent loop',
    'feld.RagAreaDef.agent.hint':
      'May the agent loop search this area? Off removes it only there; in the pattern engine '
      + 'the retrieval mode applies. Without an entry, on.',
    'feld.RagRetrievalArea.retrieval.label': 'Knowledge search',
    'feld.RagRetrievalArea.retrieval.hint':
      'Values for every search in the knowledge areas, in both engines.',
    'feld.RagAbruf.top_k.label': 'Hits per search',
    'feld.RagAbruf.top_k.hint':
      'How many passages a search returns at most, 1 to 50. Empty = default 10. '
      + 'Environment: RAG_TOP_K.',
    'feld.RagAbruf.min_score.label': 'Minimum similarity',
    'feld.RagAbruf.min_score.hint':
      'Passages below this similarity (0 to 1) are dropped. Empty = default 0.30. '
      + 'Environment: RAG_MIN_SCORE.',
    'feld.RagAbruf.max_chars_per_area.label': 'Characters per area',
    'feld.RagAbruf.max_chars_per_area.hint':
      'At most this much text of one area goes into the prompt; 0 = no limit. '
      + 'Empty = default 3000. Environment: RAG_MAX_CHARS_PER_AREA.',
  },
};
