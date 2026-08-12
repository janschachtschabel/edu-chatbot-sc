/**
 * Der Referenz-Abschnitt „Wissensquellen" (C1-d5b1): RAG, MCP, die
 * Themenseiten-Auflösung und die Snapshots.
 *
 * Nicht zu verwechseln mit `knowledge.ts` — das ist die Wissensbasis-VERWALTUNG
 * (Bereiche anlegen, Dokumente einlesen). Hier steht die Erklärung derselben
 * Sache in der Referenz. Zwei Ansichten, zwei Gründe zur Änderung.
 *
 * **Der Verweis auf die Sicherung trägt eine vollständige Wortgruppe**
 * (`rk.snap.link`). Das ist das Muster aus C1-d4a: dort stand „und einen Lauf
 * starten" ausserhalb des Links — ein Satz aus zwei Bruchstücken und ein
 * Verweis, der sein Ziel nur halb nennt. `rich()` kennt `strong` und `code`,
 * aber keinen Verweis; einen Satz um ein `<a>` herum zu schneiden hiesse, die
 * Wortstellung dem Template zu überlassen statt der Übersetzung.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE_KNOWLEDGE: CataloguePart = {
  de: {
    'rk.title': 'Wissensquellen: RAG und MCP',

    'rk.rag.title': 'RAG — eigenes Wissen',
    'rk.rag.text':
      'Hochgeladene Dokumente werden in Abschnitte zerlegt, als Vektoren in '
      + 'Postgres abgelegt und per Kosinus-Ähnlichkeit (pgvector) gesucht.',
    'rk.rag.always': '*Immer an:* der Bereich wird bei jeder Nachricht als Kontext eingefügt.',
    'rk.rag.onDemand':
      '*Auf Abruf:* nur wenn das Pattern `sources: ["rag"]` führt und das Modell '
      + '`query_knowledge` aufruft.',
    'rk.rag.ingest': '*Einspielen:* im Studio als Datei, Webadresse oder Freitext.',

    'rk.mcp.title': 'MCP — externe Werkzeuge',
    /** Die Anzahl ist heute die Konstante 12 in der Komponente. Trotzdem beide
     *  Formen: eine Zahl, die aus dem Code kommt, kann sich ändern, und die
     *  Einzahl wäre dann still falsch — dieselbe Regel wie in C1-d3a. */
    'rk.mcp.text.one':
      'Ein externer Server (WLO edu-sharing) stellt {count} Werkzeug bereit, das '
      + 'das Modell bei Bedarf aufruft.',
    'rk.mcp.text.other':
      'Ein externer Server (WLO edu-sharing) stellt {count} Werkzeuge bereit, die '
      + 'das Modell bei Bedarf aufruft.',
    'rk.mcp.access': '*Zugang:* nur wenn das Pattern `sources: ["mcp"]` führt.',
    'rk.mcp.blockable': '*Sperrbar:* Safety oder Policy können einzelne Werkzeuge ausschließen.',
    'rk.mcp.speculative':
      '*Spekulativ:* bei passenden Intents startet die Suche parallel zur Antwort, '
      + 'statt auf sie zu warten.',
    'rk.mcp.note':
      '`query_knowledge` zählt hier nicht mit: es ist der Einstieg in den '
      + 'RAG-Bestand, kein MCP-Werkzeug.',

    'rk.page.title': 'Themenseiten-Auflösung (ergänzt Schicht 6)',
    'rk.page.text':
      'Steckt das Widget auf einer WLO-Themenseite, einer Sammlung oder einer '
      + 'edu-sharing-Ansicht, löst `page_context` die Seite beim ersten Turn über '
      + 'MCP auf (`get_node_details`, bei einem Slug zuerst '
      + '`search_wlo_topic_pages`) und legt Titel, Fächer, Bildungsstufen und '
      + 'Schlagworte als Block in den Prompt.',
    'rk.page.ttl':
      '*Gültigkeit:* 30 Minuten bei erfolgreicher Auflösung, 2 Minuten nach einem '
      + 'Fehlschlag — damit ein kurzer MCP-Ausfall nicht eine halbe Stunde nachwirkt.',
    'rk.page.detected':
      '*Erkannt werden* `node_id`, `collection_id`, `topic_page_slug` und '
      + '`subject_slug`; welche URL-Formen und Meta-Angaben darauf führen, steht im '
      + 'Kopf von `page-context-detector.ts`.',
    'rk.page.effect':
      '*Wirkung:* „Worum geht es hier?" lässt sich ohne Rückfrage beantworten, der '
      + 'Seitentitel dient als voreingestelltes Thema.',

    'rk.snap.title': 'Snapshots und Werkseinstellungen',
    'rk.snap.intro':
      'Ein Snapshot friert die *Konfigurationsbereiche* ein — und nur diese. '
      + 'Gespräche, Auswertungen und RAG-Inhalte gehören nicht dazu; ein '
      + 'Rückspielen lässt sie unberührt.',
    'rk.snap.link': 'Bedient wird das alles in der Sicherung',
    'rk.snap.snapshots': 'Snapshots',
    'rk.snap.rows': 'Liegen als Zeilen in `config_snapshots`, nicht als Dateien.',
    'rk.snap.limit': 'Bis zu 50 Stück; das Anlegen darüber hinaus lehnt der Server ab.',
    'rk.snap.restore':
      'Wiederherstellen *ergänzt*: jeder Bereich aus dem Snapshot überschreibt '
      + 'seinen aktuellen Stand, Bereiche außerhalb bleiben stehen.',
    'rk.snap.download': 'Herunterladen liefert dieselbe ZIP fürs eigene Archiv.',

    'rk.factory.title': 'Werksstand',
    'rk.factory.one': 'Genau einer je Installation — die Zeile mit der Kennung `factory`.',
    'rk.factory.from': 'Entsteht aus dem aktuellen Live-Stand oder aus einer hochgeladenen ZIP.',
    'rk.factory.reset': '„Zurücksetzen" spielt ihn wieder ein, ebenfalls nur die Konfiguration.',

    'rk.snap.note':
      'Ein vollständiges Datenbank-Abbild ist damit nicht abgedeckt — das gehört '
      + 'zur Betriebs-Sicherung des Servers, nicht ins Studio.',
  },

  en: {
    'rk.title': 'Knowledge sources: RAG and MCP',

    'rk.rag.title': 'RAG — knowledge of your own',
    'rk.rag.text':
      'Uploaded documents are split into sections, stored as vectors in Postgres '
      + 'and searched by cosine similarity (pgvector).',
    'rk.rag.always': '*Always on:* the area is inserted as context with every message.',
    'rk.rag.onDemand':
      '*On demand:* only when the pattern carries `sources: ["rag"]` and the model '
      + 'calls `query_knowledge`.',
    'rk.rag.ingest': '*Ingesting:* in the studio as a file, a web address or free text.',

    'rk.mcp.title': 'MCP — external tools',
    'rk.mcp.text.one':
      'An external server (WLO edu-sharing) provides {count} tool, which the model '
      + 'calls when needed.',
    'rk.mcp.text.other':
      'An external server (WLO edu-sharing) provides {count} tools, which the model '
      + 'calls when needed.',
    'rk.mcp.access': '*Access:* only when the pattern carries `sources: ["mcp"]`.',
    'rk.mcp.blockable': '*Blockable:* safety or policy can exclude individual tools.',
    'rk.mcp.speculative':
      '*Speculative:* for matching intents the search starts in parallel with the '
      + 'answer instead of waiting for it.',
    'rk.mcp.note':
      '`query_knowledge` does not count here: it is the entry point into the RAG '
      + 'store, not an MCP tool.',

    'rk.page.title': 'Topic-page resolution (extends layer 6)',
    'rk.page.text':
      'When the widget sits on a WLO topic page, a collection or an edu-sharing '
      + 'view, `page_context` resolves the page on the first turn through MCP '
      + '(`get_node_details`, for a slug first `search_wlo_topic_pages`) and puts '
      + 'the title, subjects, educational levels and keywords into the prompt as a '
      + 'block.',
    'rk.page.ttl':
      '*Validity:* 30 minutes after a successful resolution, 2 minutes after a '
      + 'failure — so that a brief MCP outage does not linger for half an hour.',
    'rk.page.detected':
      '*Recognised are* `node_id`, `collection_id`, `topic_page_slug` and '
      + '`subject_slug`; which URL forms and meta fields lead to them is written at '
      + 'the top of `page-context-detector.ts`.',
    'rk.page.effect':
      '*Effect:* “What is this about?” can be answered without asking back, and the '
      + 'page title serves as the preselected topic.',

    'rk.snap.title': 'Snapshots and factory settings',
    'rk.snap.intro':
      'A snapshot freezes the *configuration areas* — and only those. '
      + 'Conversations, analytics and RAG content are not part of it; restoring one '
      + 'leaves them untouched.',
    'rk.snap.link': 'All of this is operated in the backup view',
    'rk.snap.snapshots': 'Snapshots',
    'rk.snap.rows': 'They live as rows in `config_snapshots`, not as files.',
    'rk.snap.limit': 'Up to 50 of them; the server refuses to create any beyond that.',
    'rk.snap.restore':
      'Restoring *adds*: every area from the snapshot overwrites its current state, '
      + 'areas outside it stay as they are.',
    'rk.snap.download': 'Downloading yields the same ZIP for your own archive.',

    'rk.factory.title': 'Factory state',
    'rk.factory.one': 'Exactly one per installation — the row with the id `factory`.',
    'rk.factory.from': 'It arises from the current live state or from an uploaded ZIP.',
    'rk.factory.reset': '“Reset” plays it back in, again only the configuration.',

    'rk.snap.note':
      'A full database image is not covered by this — that belongs to the server’s '
      + 'operational backup, not to the studio.',
  },
};
