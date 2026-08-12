/**
 * Die Wissensbasis (C1-d3c): die Bereiche, ihre Dokumente und das Einlesen.
 *
 * Drei Ansichten teilen sich mehrere Einträge — `rag.chunks` zählt Abschnitte
 * in allen dreien, `rag.delete`/`rag.deleting` gehören zu beiden Löschwegen.
 * Getrennte Einträge je Ansicht könnten voneinander abdriften, ohne dass es
 * jemandem auffällt.
 *
 * Die Ja-Antwort der Rückfrage hiess bis C1-d4b `rag.confirmYes` und stand
 * gleichlautend noch einmal in `backup.ts`; sie ist jetzt `action.confirmDelete`
 * in `shared.ts` — sie gehört keiner Ansicht.
 */
import type { CataloguePart } from './catalogue-part';

export const KNOWLEDGE: CataloguePart = {
  de: {
    // ── Geteilt zwischen Bereichen und Dokumenten ───────────────────
    /** Zählt Abschnitte in Bereichsliste, Dokumentliste und Einlese-Ergebnis. */
    'rag.chunks.one': '{count} Abschnitt',
    'rag.chunks.other': '{count} Abschnitte',
    'rag.delete': 'Löschen',
    'rag.deleting': 'Wird gelöscht …',

    // ── Wissensbereiche ─────────────────────────────────────────────
    'rag.areas.loading': 'Die Wissensbereiche werden geladen …',
    /** Der Satz nannte bis C1-d3c den Nachbar-Abschnitt beim Namen. Diese
     *  Beschriftung ist Daten aus `curated-views.ts` und dort noch deutsch —
     *  im englischen Satz stünde sie als Verweis auf eine Überschrift, die
     *  anders lautet. Deshalb örtlich statt namentlich. */
    'rag.areas.empty':
      'Noch keine Wissensbereiche. Ein Bereich entsteht mit dem ersten Dokument — '
      + 'im Abschnitt darunter eines hochladen.',
    'rag.areas.documents.one': '{count} Dokument',
    'rag.areas.documents.other': '{count} Dokumente',
    'rag.areas.openDocs': 'Dokumente',
    'rag.areas.openDocsFor': 'Dokumente von {area}',
    'rag.areas.deleteFor': 'Löschen — Bereich {area}',
    /** Der GANZE Satz beugt sich, nicht nur das Substantiv: „geht" gegen
     *  „gehen". Ein Bereich mit einem einzigen Abschnitt ist der Normalfall
     *  nach dem ersten kurzen Dokument. */
    'rag.areas.confirmDelete.one':
      'Wirklich löschen? Der eine Abschnitt von „{area}“ geht verloren — das '
      + 'lässt sich nicht rückgängig machen.',
    'rag.areas.confirmDelete.other':
      'Wirklich löschen? Alle {count} Abschnitte von „{area}“ gehen verloren — '
      + 'das lässt sich nicht rückgängig machen.',
    'rag.areas.deleted': 'Bereich „{area}“ gelöscht.',

    // ── Dokumente eines Bereichs ────────────────────────────────────
    'rag.docs.loading': 'Die Dokumente werden geladen …',
    'rag.docs.empty':
      'In „{area}“ liegen keine Dokumente mehr. Der Bereich verschwindet mit dem '
      + 'nächsten Neuladen.',
    'rag.docs.noSource': 'ohne Quelle',
    'rag.docs.showText': 'Volltext anzeigen',
    'rag.docs.hideText': 'Volltext ausblenden',
    'rag.docs.showTextFor': 'Volltext anzeigen — {title}',
    'rag.docs.hideTextFor': 'Volltext ausblenden — {title}',
    'rag.docs.deleteFor': 'Löschen — {title}',
    'rag.docs.confirmDelete': 'Wirklich löschen? Das Dokument muss danach neu eingelesen werden.',
    'rag.docs.textLoading': 'Der Volltext wird geladen …',
    'rag.docs.chunksOf': 'Abschnitte von {title}',
    'rag.docs.chunkNo': 'Abschnitt {number}',

    // ── Einlesen ────────────────────────────────────────────────────
    'rag.ingest.sourceLegend': 'Quelle',
    'rag.ingest.source.file': 'Datei',
    'rag.ingest.source.url': 'Webseite',
    'rag.ingest.source.text': 'Text',
    'rag.ingest.area': 'Wissensbereich (Pflicht)',
    'rag.ingest.areaHelp':
      'Ein vorhandener Bereich oder ein neuer Name — der Bereich entsteht mit '
      + 'diesem Dokument.',
    'rag.ingest.title': 'Titel (optional)',
    'rag.ingest.fileHelp':
      'PDF, DOCX, PPTX, XLSX, HTML, Markdown oder Text. Große Dateien lehnt der '
      + 'Server ab, statt am Speicher zu scheitern.',
    'rag.ingest.url': 'Adresse der Webseite',
    'rag.ingest.urlHelp': 'Öffentlich erreichbare Adresse — interne Adressen weist der Server ab.',
    'rag.ingest.busy': 'Wird eingelesen …',
    'rag.ingest.go': 'Einlesen',
    'rag.ingest.missing': 'Es fehlt noch: {what}.',
    /** Glieder einer Aufzählung, keine Satzteile: verbunden werden sie von
     *  `StudioLanguageService.list()` über `Intl.ListFormat`, nicht von einem
     *  übersetzten Binder. */
    'rag.ingest.need.area': 'ein Wissensbereich',
    'rag.ingest.need.file': 'eine Datei',
    'rag.ingest.need.url': 'eine Adresse',
    'rag.ingest.need.text': 'der Text',
    'rag.ingest.done.one': '„{title}“ liegt jetzt in „{area}“ — {count} Abschnitt.',
    'rag.ingest.done.other': '„{title}“ liegt jetzt in „{area}“ — {count} Abschnitte.',
    /** Rückfall, wenn kein Titel eingetragen wurde. */
    'rag.ingest.untitled': 'Dokument',
    'rag.ingest.previewTitle': 'Anfang des eingelesenen Textes',

    // ── Fehlschläge des Einlesens ───────────────────────────────────
    'rag.error.unreadable': 'Die Datei oder Adresse konnte nicht gelesen werden.',
    'rag.error.tooLarge': 'Die Datei ist größer als das Upload-Limit des Servers.',
  },

  en: {
    'rag.chunks.one': '{count} section',
    'rag.chunks.other': '{count} sections',
    'rag.delete': 'Delete',
    'rag.deleting': 'Deleting …',

    'rag.areas.loading': 'Loading the knowledge areas …',
    'rag.areas.empty':
      'No knowledge areas yet. An area comes into being with its first document — '
      + 'upload one in the section below.',
    'rag.areas.documents.one': '{count} document',
    'rag.areas.documents.other': '{count} documents',
    'rag.areas.openDocs': 'Documents',
    'rag.areas.openDocsFor': 'Documents of {area}',
    'rag.areas.deleteFor': 'Delete — area {area}',
    'rag.areas.confirmDelete.one':
      'Really delete? The single section of “{area}” is lost — this cannot be undone.',
    'rag.areas.confirmDelete.other':
      'Really delete? All {count} sections of “{area}” are lost — this cannot be undone.',
    'rag.areas.deleted': 'Area “{area}” deleted.',

    'rag.docs.loading': 'Loading the documents …',
    'rag.docs.empty':
      'There are no documents left in “{area}”. The area disappears on the next reload.',
    'rag.docs.noSource': 'no source',
    'rag.docs.showText': 'Show full text',
    'rag.docs.hideText': 'Hide full text',
    'rag.docs.showTextFor': 'Show full text — {title}',
    'rag.docs.hideTextFor': 'Hide full text — {title}',
    'rag.docs.deleteFor': 'Delete — {title}',
    'rag.docs.confirmDelete': 'Really delete? The document has to be ingested again afterwards.',
    'rag.docs.textLoading': 'Loading the full text …',
    'rag.docs.chunksOf': 'Sections of {title}',
    'rag.docs.chunkNo': 'Section {number}',

    'rag.ingest.sourceLegend': 'Source',
    'rag.ingest.source.file': 'File',
    'rag.ingest.source.url': 'Web page',
    'rag.ingest.source.text': 'Text',
    'rag.ingest.area': 'Knowledge area (required)',
    'rag.ingest.areaHelp':
      'An existing area or a new name — the area comes into being with this document.',
    'rag.ingest.title': 'Title (optional)',
    'rag.ingest.fileHelp':
      'PDF, DOCX, PPTX, XLSX, HTML, Markdown or text. The server rejects large '
      + 'files rather than running out of memory.',
    'rag.ingest.url': 'Address of the web page',
    'rag.ingest.urlHelp': 'A publicly reachable address — internal ones are refused by the server.',
    'rag.ingest.busy': 'Ingesting …',
    'rag.ingest.go': 'Ingest',
    'rag.ingest.missing': 'Still missing: {what}.',
    'rag.ingest.need.area': 'a knowledge area',
    'rag.ingest.need.file': 'a file',
    'rag.ingest.need.url': 'an address',
    'rag.ingest.need.text': 'the text',
    'rag.ingest.done.one': '“{title}” now lies in “{area}” — {count} section.',
    'rag.ingest.done.other': '“{title}” now lies in “{area}” — {count} sections.',
    'rag.ingest.untitled': 'Document',
    'rag.ingest.previewTitle': 'Beginning of the ingested text',

    'rag.error.unreadable': 'The file or address could not be read.',
    'rag.error.tooLarge': 'The file is larger than the server’s upload limit.',
  },
};
