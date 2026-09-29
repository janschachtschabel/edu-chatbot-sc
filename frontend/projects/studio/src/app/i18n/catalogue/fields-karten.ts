/**
 * Feldtexte (ST-1) der Seite „Anzeige“, Bereiche `01-base/card-pipeline`
 * (`CardPipelineArea`, `CardPipelineBlock`) und `01-base/widget-modes`
 * (`WidgetModesArea`, `WidgetModesBlock`).
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`. Unbedingt wirken nur die zwei
 * Repositorium-Felder (`services/config_loader/repo_and_cards.py`). Die
 * Nachauswahl (`domain/cards/select.py`) läuft nur mit `CARD_PIPELINE_V2` und auch
 * dann auf dem schon gefundenen Pool (`services/widget_postprocess.py`): darum
 * greift `pool_size` nicht, `llm_curation_pool` und `enable_llm_curation` wertet
 * nach dem Lader niemand aus, und `min_displayed_cards` ändert das Ergebnis
 * rechnerisch nie (es bleibt stets `ordered[:min(len, final)]`).
 * `widget-modes` liest nur der Linklisten-Zweig in `domain/widget_postprocess.py`,
 * den `domain/widget_modes.py` (fest `cards_enabled`) nie öffnet; die ähnlichen
 * `inline_card_links` der Darstellungsregeln wertet gar kein Code aus.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_KARTEN: CataloguePart = {
  de: {
    // ── Trefferauswahl und Links ────────────────────────────────────
    'feld.CardPipelineArea.card_pipeline.label': 'Trefferauswahl und Links',
    'feld.CardPipelineArea.card_pipeline.hint':
      'Wohin Treffer-Links zeigen, und eine Nachauswahl, die gefundene Treffer ordnet und '
      + 'kürzt. Die Nachauswahl läuft nur, wenn die Umgebungsvariable CARD_PIPELINE_V2 gesetzt '
      + 'ist; ab Werk ist sie aus.',
    'feld.CardPipelineBlock.pool_size.label': 'Treffer-Pool',
    'feld.CardPipelineBlock.pool_size.hint':
      'Gedacht: wie viele Treffer die Nachauswahl selbst sucht (5 bis 50, Vorgabe 20). Wird '
      + 'derzeit nicht ausgewertet: Die Nachauswahl nimmt die Treffer, die der Chat schon '
      + 'gefunden hat.',
    'feld.CardPipelineBlock.llm_curation_pool.label': 'Vorlage für das Modell',
    'feld.CardPipelineBlock.llm_curation_pool.hint':
      'Gedacht: wie viele Treffer das Modell zur Auswahl vorgelegt bekommt, höchstens so viele '
      + 'wie der Treffer-Pool; Vorgabe 15. Wird derzeit nicht ausgewertet.',
    'feld.CardPipelineBlock.final_selection_size.label': 'Karten nach der Auswahl',
    'feld.CardPipelineBlock.final_selection_size.hint':
      'Wie viele Karten die Nachauswahl höchstens weitergibt, 1 bis 10, Vorgabe 5; andere Werte '
      + 'setzt der Server auf die nächste Grenze. Gilt nur mit der Umgebungsvariable '
      + 'CARD_PIPELINE_V2.',
    'feld.CardPipelineBlock.enable_llm_curation.label': 'Auswahl durch das Modell',
    'feld.CardPipelineBlock.enable_llm_curation.hint':
      'Gedacht als Schalter, ob das Modell Treffer auswählen darf; Vorgabe an. Wird derzeit '
      + 'nicht ausgewertet: Nichts im Chat fragt den Schalter ab.',
    'feld.CardPipelineBlock.min_displayed_cards.label': 'Mindestzahl Karten',
    'feld.CardPipelineBlock.min_displayed_cards.hint':
      'Gedacht: so viele Karten zeigt die Nachauswahl mindestens, 0 = nicht auffüllen. Wird '
      + 'derzeit nicht ausgewertet: Die Nachauswahl füllt ohnehin bis zur Höchstzahl auf, '
      + 'soweit Treffer da sind.',
    'feld.CardPipelineBlock.known_repo_hosts.label': 'Umzuschreibende Adressen',
    'feld.CardPipelineBlock.known_repo_hosts.hint':
      'Links in Treffern, die mit einer dieser Adressen beginnen (samt https://), zeigen danach '
      + 'auf das geltende Repositorium; andere bleiben. Leer = drei feste '
      + 'openeduhub.net-Adressen.',
    'feld.CardPipelineBlock.repo_base_url.label': 'Repositorium',
    'feld.CardPipelineBlock.repo_base_url.hint':
      'Adresse, auf die Treffer-Links zeigen; muss zu dem passen, was der MCP-Server abfragt. '
      + 'Leer oder ohne http(s):// gilt die Umgebungsvariable REPO_BASE_URL, ab Werk das '
      + 'Staging-Repositorium.',

    // ── Trefferliste im Text ────────────────────────────────────────
    'feld.WidgetModesArea.widget_modes.label': 'Trefferliste im Text',
    'feld.WidgetModesArea.widget_modes.hint':
      'Grenzen einer älteren Darstellung, die Treffer als Linkliste an den Antworttext hängt. '
      + 'Wirkt derzeit nicht, der Server schaltet sie nie ein; die Ergebnisboxen regelt '
      + '„Höchstzahl je Box“.',
    'feld.WidgetModesBlock.cards_inline_link_limit.label': 'Anzahl Treffer-Links',
    'feld.WidgetModesBlock.cards_inline_link_limit.hint':
      'Wie viele Treffer die Linkliste höchstens nennt, 1 bis 6; Vorgabe 5. Wirkt derzeit '
      + 'nicht, weil die Liste nie erscheint; „Anzahl Links“ der Darstellungsregeln wertet gar '
      + 'kein Code aus.',
    'feld.WidgetModesBlock.cards_inline_link_title_max.label': 'Länge der Link-Titel',
    'feld.WidgetModesBlock.cards_inline_link_title_max.hint':
      'Höchstlänge eines Titels in der Linkliste, 30 bis 200 Zeichen; Vorgabe 70, längere '
      + 'enden mit „…“. Wirkt derzeit nicht, weil die Liste nie erscheint; „Titellänge“ der '
      + 'Darstellungsregeln wertet gar kein Code aus.',
  },
  en: {
    // ── Result selection and links ──────────────────────────────────
    'feld.CardPipelineArea.card_pipeline.label': 'Result selection and links',
    'feld.CardPipelineArea.card_pipeline.hint':
      'Where result links point, and a post-selection that orders and trims the results found. '
      + 'The post-selection only runs when the CARD_PIPELINE_V2 environment variable is set; it '
      + 'is off by default.',
    'feld.CardPipelineBlock.pool_size.label': 'Result pool',
    'feld.CardPipelineBlock.pool_size.hint':
      'Intended: how many results the post-selection searches for itself (5 to 50, default '
      + '20). Currently not evaluated: the post-selection takes the results the chat has '
      + 'already found.',
    'feld.CardPipelineBlock.llm_curation_pool.label': 'Shortlist for the model',
    'feld.CardPipelineBlock.llm_curation_pool.hint':
      'Intended: how many results the model is given to choose from, at most as many as the '
      + 'result pool; default 15. Currently not evaluated.',
    'feld.CardPipelineBlock.final_selection_size.label': 'Cards after selection',
    'feld.CardPipelineBlock.final_selection_size.hint':
      'How many cards the post-selection passes on at most, 1 to 10, default 5; the server '
      + 'moves other values to the nearest limit. Only applies with the CARD_PIPELINE_V2 '
      + 'environment variable.',
    'feld.CardPipelineBlock.enable_llm_curation.label': 'Selection by the model',
    'feld.CardPipelineBlock.enable_llm_curation.hint':
      'Intended as the switch for whether the model may pick results; default on. Currently '
      + 'not evaluated: nothing in the chat checks this switch.',
    'feld.CardPipelineBlock.min_displayed_cards.label': 'Minimum cards',
    'feld.CardPipelineBlock.min_displayed_cards.hint':
      'Intended: the post-selection shows at least this many cards, 0 = no filling up. '
      + 'Currently not evaluated: the post-selection fills up to the maximum anyway, as far as '
      + 'results allow.',
    'feld.CardPipelineBlock.known_repo_hosts.label': 'Addresses to rewrite',
    'feld.CardPipelineBlock.known_repo_hosts.hint':
      'Links in results that start with one of these addresses (including https://) then '
      + 'point to the repository in effect; others stay as they are. Empty = three fixed '
      + 'openeduhub.net addresses.',
    'feld.CardPipelineBlock.repo_base_url.label': 'Repository',
    'feld.CardPipelineBlock.repo_base_url.hint':
      'Address that result links point to; must match what the MCP server queries. If empty or '
      + 'without http(s)://, the REPO_BASE_URL environment variable applies, by default the '
      + 'staging repository.',

    // ── Result list in the text ─────────────────────────────────────
    'feld.WidgetModesArea.widget_modes.label': 'Result list in the text',
    'feld.WidgetModesArea.widget_modes.hint':
      'Limits of an older display that appends results to the answer text as a list of links. '
      + 'Currently without effect, the server never switches it on; the result boxes follow '
      + '“Maximum per box”.',
    'feld.WidgetModesBlock.cards_inline_link_limit.label': 'Number of result links',
    'feld.WidgetModesBlock.cards_inline_link_limit.hint':
      'How many results the link list names at most, 1 to 6; default 5. Currently without '
      + 'effect because the list never appears; “Number of links” in the display rules is '
      + 'evaluated by no code at all.',
    'feld.WidgetModesBlock.cards_inline_link_title_max.label': 'Link title length',
    'feld.WidgetModesBlock.cards_inline_link_title_max.hint':
      'Maximum length of a title in the link list, 30 to 200 characters; default 70, longer '
      + 'ones end in “…”. Currently without effect because the list never appears; “Title '
      + 'length” in the display rules is evaluated by no code at all.',
  },
};
