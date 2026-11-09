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
      '*Auf Abruf:* im Muster-Modus, wenn das Pattern `sources: ["rag"]` führt und das '
      + 'Modell `query_knowledge` aufruft; in der Agent-Schleife über `wissen_suchen`.',
    'rk.rag.ingest': '*Einspielen:* im Studio als Datei, Webadresse oder Freitext.',

    'rk.mcp.title': 'MCP — externe Werkzeuge',
    /** Ohne Zahl (Paket 6, S3): die frühere Konstante 12 stimmte längst nicht
     *  mehr, und die aktuelle Liste samt Sperren zeigt die Agent-Seite live. */
    'rk.mcp.text':
      'Externe Server — allen voran WLO edu-sharing — stellen Werkzeuge bereit, die das '
      + 'Modell bei Bedarf aufruft. Die aktuelle Liste samt Sperren steht auf der Seite '
      + '„Agent & Maschine“ unter „Werkzeuge und Sperren“.',
    'rk.mcp.access':
      '*Zugang:* im Muster-Modus nur, wenn das Pattern `sources: ["mcp"]` führt; die '
      + 'Agent-Schleife bekommt den ganzen Katalog ohne gesperrte Werkzeuge. Kuratierende '
      + '(schreibende) Werkzeuge nur mit Schreibrecht — im Muster-Modus zudem nur, wenn das '
      + 'Pattern sie ausdrücklich nennt.',
    'rk.mcp.contract':
      '*Antworten:* verbindlich ist der strukturierte Teil (`structuredContent`) — '
      + 'Fehlercodes, Bestätigungsschlüssel, Stand eines Plans; der Text ist Rückfall. '
      + 'Vorausgesetzt ist der MCP-Stand vom 07.11.2026.',
    'rk.mcp.write':
      '*Schreiben:* immer zweistufig — Vorschau, dann das Ja der Person. Material wird '
      + 'mit einer Bestätigung angelegt und einsortiert; Sammlungsbäume und viele '
      + 'Aufnahmen laufen als Plan unter einer Bestätigung, große Pläne setzt der Knopf '
      + '„Plan fortsetzen“ fort.',
    /** Plan 2026-11-07 (Stabilität der MCP-Anbindung, CB-2…CB-9). */
    'rk.mcp.stability':
      '*Überlast und Ausfall:* der Chatbot bleibt unter dem Budget des Servers (eigenes '
      + 'Budget per Client-Schlüssel, Wächter `MCP_BUDGET_RPM`). „Ausgelastet“ heißt: nichts '
      + 'lief — eine offene Freigabe bleibt liegen. Antwortet der Server mehrmals nicht, '
      + 'scheitern Aufrufe 30 s lang sofort, bis `/ready` wieder antwortet. Geht die Antwort '
      + 'eines bestätigten Schreibaufrufs verloren, holt der Chatbot sie mit demselben '
      + 'Schlüssel nach, ohne doppelt zu schreiben.',
    'rk.mcp.login':
      '*Anmeldung:* geprüft über `/auth/status`. Kann der Server gerade nicht prüfen, gilt die '
      + 'letzte Bestätigung derselben Person 30 Minuten weiter (`AUTH_GRACE_S`). Ticket- und '
      + 'Widget-Anmeldungen laufen nach 12 Stunden ab — das Widget tauscht das Ticket dann neu '
      + 'bzw. bietet die Anmeldung vorher an. „Abmelden“ beendet den Zugang am Server.',
    'rk.mcp.blockable': '*Sperrbar:* Safety oder Policy können einzelne Werkzeuge ausschließen.',
    'rk.mcp.speculative':
      '*Spekulativ (Muster-Modus):* bei passenden Intents startet die Suche parallel '
      + 'zur Antwort, statt auf sie zu warten.',
    'rk.mcp.note':
      '`query_knowledge` gehört nicht dazu: es ist der Einstieg in den '
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

    'rk.snap.title': 'Snapshots und eigener Grundstand',
    'rk.snap.intro':
      'Ein Snapshot friert die *Konfigurationsbereiche* ein — und nur diese. '
      + 'Gespräche, Auswertungen und RAG-Inhalte gehören nicht dazu; ein '
      + 'Rückspielen lässt sie unberührt.',
    'rk.snap.link': 'Bedient wird das alles in der Sicherung',
    'rk.snap.snapshots': 'Snapshots',
    'rk.snap.rows': 'Liegen als Zeilen in `config_snapshots`, nicht als Dateien.',
    'rk.snap.limit': 'Bis zu 50 Stück; das Anlegen darüber hinaus lehnt der Server ab.',
    'rk.snap.restore':
      'Wiederherstellen *ergänzt* in der Vorgabe: jeder Bereich aus dem Snapshot '
      + 'überschreibt seinen aktuellen Stand, Bereiche außerhalb bleiben stehen. Wahlweise '
      + '*exakt*: dann fallen diese weg, nach einem Snapshot des Stands davor.',
    'rk.snap.download': 'Herunterladen liefert dieselbe ZIP fürs eigene Archiv.',

    'rk.factory.title': 'Eigener Grundstand',
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
      '*On demand:* in pattern mode when the pattern carries `sources: ["rag"]` and the '
      + 'model calls `query_knowledge`; in the agent loop through `wissen_suchen`.',
    'rk.rag.ingest': '*Ingesting:* in the studio as a file, a web address or free text.',

    'rk.mcp.title': 'MCP — external tools',
    'rk.mcp.text':
      'External servers — WLO edu-sharing first of all — provide tools that the model '
      + 'calls when needed. The current list including blocks is on the page “Agent & '
      + 'engine” under “Tools and locks”.',
    'rk.mcp.access':
      '*Access:* in pattern mode only when the pattern carries `sources: ["mcp"]`; the '
      + 'agent loop gets the whole catalogue minus blocked tools. Curation (writing) tools '
      + 'only with write permission — in pattern mode also only when the pattern names them '
      + 'explicitly.',
    'rk.mcp.contract':
      '*Answers:* the structured part (`structuredContent`) is binding — error codes, '
      + 'confirmation keys, the state of a plan; the text is the fallback. The MCP state of '
      + '2026-11-07 is required.',
    'rk.mcp.write':
      '*Writing:* always two steps — preview, then the person says yes. Material is created '
      + 'and filed under one confirmation; collection trees and many additions run as a plan '
      + 'under one confirmation, and the “Continue” button carries on with large plans.',
    'rk.mcp.stability':
      '*Load and outages:* the chatbot stays below the server budget (own budget via a client '
      + 'key, guard `MCP_BUDGET_RPM`). “Busy” means nothing ran — an open approval stays. If '
      + 'the server fails to answer several times, calls fail at once for 30 s until `/ready` '
      + 'answers again. If the answer to a confirmed write is lost, the chatbot fetches it '
      + 'again with the same key, without writing twice.',
    'rk.mcp.login':
      '*Sign-in:* checked via `/auth/status`. If the server cannot check right now, the last '
      + 'confirmation of the same person stays valid for 30 minutes (`AUTH_GRACE_S`). Ticket '
      + 'and widget sign-ins expire after 12 hours — the widget then exchanges the ticket '
      + 'again or offers to sign in beforehand. “Sign out” ends the access at the server.',
    'rk.mcp.blockable': '*Blockable:* safety or policy can exclude individual tools.',
    'rk.mcp.speculative':
      '*Speculative (pattern mode):* for matching intents the search starts in parallel '
      + 'with the answer instead of waiting for it.',
    'rk.mcp.note':
      '`query_knowledge` is not one of them: it is the entry point into the RAG '
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

    'rk.snap.title': 'Snapshots and own baseline',
    'rk.snap.intro':
      'A snapshot freezes the *configuration areas* — and only those. '
      + 'Conversations, analytics and RAG content are not part of it; restoring one '
      + 'leaves them untouched.',
    'rk.snap.link': 'All of this is operated in the backup view',
    'rk.snap.snapshots': 'Snapshots',
    'rk.snap.rows': 'They live as rows in `config_snapshots`, not as files.',
    'rk.snap.limit': 'Up to 50 of them; the server refuses to create any beyond that.',
    'rk.snap.restore':
      'Restoring *adds* by default: every area from the snapshot overwrites its current '
      + 'state, areas outside it stay as they are. Optionally *exact*: those are deleted, '
      + 'after a snapshot of the state before.',
    'rk.snap.download': 'Downloading yields the same ZIP for your own archive.',

    'rk.factory.title': 'Own baseline',
    'rk.factory.one': 'Exactly one per installation — the row with the id `factory`.',
    'rk.factory.from': 'It arises from the current live state or from an uploaded ZIP.',
    'rk.factory.reset': '“Reset” plays it back in, again only the configuration.',

    'rk.snap.note':
      'A full database image is not covered by this — that belongs to the server’s '
      + 'operational backup, not to the studio.',
  },
};
