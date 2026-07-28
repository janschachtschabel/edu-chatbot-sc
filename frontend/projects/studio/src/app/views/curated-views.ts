/**
 * What each curated config view puts on one page (9-4b).
 *
 * ALT built one hand-written React component per view — ~6 300 TSX lines that
 * mostly re-implemented "load an area, show its fields, save it". 9-3 already
 * renders any area from its schema, so what is left is genuinely editorial:
 * WHICH areas belong to one job, in what order, and what each is for. That is
 * data, so it lives here as data.
 *
 * Two rules this file must keep:
 *   - a FILE key addresses one document and gets a plain form section;
 *     `03-patterns` and `04-personas` address a folder and must be marked
 *     `kind: 'group'`, which renders a picker plus the form of one document.
 *   - the section order is the reading order of the page. The first section is
 *     open on arrival; the rest load when they are opened.
 *
 * Areas no view lists stay reachable through „Alle Bereiche" (9-3) — that
 * escape hatch is why this list may stay editorial instead of exhaustive.
 */

export interface CuratedAreaSection {
  /** Config area key, exactly as the registry spells it. */
  readonly area: string;
  /** `group` = the key is a folder of documents (`03-patterns`). */
  readonly kind?: 'file' | 'group';
  /** Heading for the section — what the editor is changing, not the filename. */
  readonly label: string;
  /** One line on what this area decides. */
  readonly hint: string;
  /**
   * Something the generated form alone cannot do for this area. Every value
   * gets its own branch in the section template rather than a plugin mechanism
   * nobody asked for:
   *  - `safety-level` — the picker §5.6 names, shown above the form.
   *  - `pattern-tabs` — ALT's five field tabs (A7). A pattern document carries
   *    21 head fields plus the instruction text; in one fieldset that is a
   *    wall. The cut itself lives in `pattern-field-tabs.ts`.
   */
  readonly feature?: 'safety-level' | 'pattern-tabs';
}

/**
 * A panel that is NOT a config document (9-4e). "Wissen" needs three: the
 * knowledge areas live in the database, ingesting a document is an upload, and
 * the MCP registry has endpoints of its own that add live tool descriptions and
 * an SSRF check on write. None of the three can be a schema form, and all three
 * belong on the same page as the config that describes them.
 */
export interface CuratedPanelSection {
  readonly panel: 'rag-areas' | 'rag-ingest' | 'mcp-registry';
  readonly label: string;
  readonly hint: string;
}

export type CuratedSection = CuratedAreaSection | CuratedPanelSection;

/** Narrows the union — a panel has no area key and no schema. */
export function isAreaSection(section: CuratedSection): section is CuratedAreaSection {
  return 'area' in section;
}

export interface CuratedView {
  /** Route slug — must be a `paket: '9-4'` entry in STUDIO_VIEWS. */
  readonly slug: string;
  /** Lead paragraph: what this page is for, in the editor's language. */
  readonly intro: string;
  readonly sections: readonly CuratedSection[];
}

export const CURATED_VIEWS: readonly CuratedView[] = [
  {
    slug: 'begruessung',
    intro:
      'Der erste Eindruck im Widget: die Begrüßungsblase und die Chips darunter. '
      + 'Ein Chip kann die Web-Tour starten — dafür muss „tour_reply" wörtlich einem '
      + 'der Quick-Replies entsprechen.',
    sections: [
      {
        area: '01-base/welcome-config',
        label: 'Begrüßung & Start-Chips',
        hint: 'Begrüßungstext, Quick-Replies und der Chip, der die Web-Tour startet.',
      },
    ],
  },
  {
    slug: 'kontext-aktionen',
    intro:
      'Was Boerdi anbietet, wenn er von selbst auf einer Seite auftaucht — je nach '
      + 'Seitentyp (Sammlung, Inhalt, Themenseite) eine eigene Ansprache und eigene Pills.',
    sections: [
      {
        area: '01-base/context-actions',
        label: 'Proaktive Begrüßung & Pills',
        hint: 'An/aus, Melde-Adresse, Ansprache und Pills je Seitentyp, Kuratier-Prompt.',
      },
    ],
  },
  {
    slug: 'identitaet',
    intro:
      'Wer Boerdi ist und wo seine Grenzen liegen. Das Sicherheitslevel ganz oben '
      + 'entscheidet, welche Prüfungen überhaupt laufen — alles Weitere feilt daran.',
    sections: [
      {
        area: '01-base/safety-config',
        label: 'Sicherheit',
        feature: 'safety-level',
        hint: 'Stufe, Presets, Krisen- und PII-Begriffe, Schwellen und Rate-Limits.',
      },
      {
        area: '01-base/base-persona',
        label: 'Grundpersona',
        hint: 'Haltung, Stimme und Selbstverständnis in jeder Antwort.',
      },
      {
        area: '01-base/guardrails',
        label: 'Leitplanken',
        hint: 'Was Boerdi nicht tut, und wie er das sagt.',
      },
      {
        area: '01-base/policy',
        label: 'Regelwerk',
        hint: 'Regeln, die Muster und Werkzeuge je Situation erlauben oder sperren.',
      },
    ],
  },
  {
    slug: 'domain-wissen',
    intro:
      'Was Boerdi über die Plattform und ihre Inhalte weiß. Diese Texte gehen als '
      + 'Systemwissen in jede Antwort ein — je konkreter, desto weniger rät das Modell.',
    sections: [
      {
        area: '02-domain/domain-rules',
        label: 'Domänen-Regeln',
        hint: 'Fachliche Leitplanken für Antworten in dieser Domäne.',
      },
      {
        area: '02-domain/wlo-plattform-wissen',
        label: 'Plattform-Wissen',
        hint: 'Wie WirLernenOnline aufgebaut ist: Bereiche, Begriffe, Wege.',
      },
      {
        area: '01-base/website-tour',
        label: 'Web-Tour',
        hint: 'Stationen der geführten Tour, ihre Gruppen und Einstiege.',
      },
    ],
  },
  {
    slug: 'material-formate',
    intro:
      'Welche Materialarten Boerdi erzeugen kann und woran er erkennt, dass jemand '
      + 'eine davon möchte.',
    sections: [
      {
        area: '05-canvas/material-types',
        label: 'Material-Typen',
        hint: 'Die erzeugbaren Formate mit Beschreibung und Vorlage.',
      },
      {
        area: '05-canvas/type-aliases',
        label: 'Bezeichnungen',
        hint: 'Alltagswörter, die auf einen Typ zeigen („Test" → Quiz).',
      },
      {
        area: '05-canvas/create-triggers',
        label: 'Auslöser: neu erstellen',
        hint: 'Formulierungen, die als Auftrag zum Erstellen gelten.',
      },
      {
        area: '05-canvas/edit-triggers',
        label: 'Auslöser: überarbeiten',
        hint: 'Formulierungen, die sich auf ein bestehendes Dokument beziehen.',
      },
      {
        area: '05-canvas/persona-priorities',
        label: 'Vorrang je Persona',
        hint: 'Welche Typen für welche Zielgruppe zuerst vorgeschlagen werden.',
      },
    ],
  },
  {
    slug: 'patterns',
    intro:
      'Die Gesprächsmuster: je ein Dokument mit Kopfdaten und Anweisungstext. '
      + 'Welches Muster greift, entscheidet der LLM-Hint — hier steht, was es dann tut.',
    sections: [
      {
        area: '03-patterns',
        kind: 'group',
        label: 'Gesprächsmuster',
        hint: 'Auslöser, Abgrenzung, Ton, Werkzeuge und Anweisungstext je Muster.',
        feature: 'pattern-tabs',
      },
    ],
  },
  {
    slug: 'dimensionen',
    intro:
      'Die Achsen, an denen Boerdi ein Gespräch einordnet.',
    sections: [
      {
        area: '04-personas',
        kind: 'group',
        label: 'Personas',
        hint: 'Zielgruppen mit Ansprache, Zielen und typischen Anliegen.',
      },
      {
        area: '04-intents/intents',
        label: 'Intents',
        hint: 'Absichten, die der Klassifikator unterscheidet.',
      },
      {
        area: '04-states/states',
        label: 'Gesprächszustände',
        hint: 'Phasen eines Dialogs und die erlaubten Übergänge.',
      },
      {
        area: '04-entities/entities',
        label: 'Entitäten',
        hint: 'Erkannte Größen wie Fach oder Bildungsstufe, mit Beispielen.',
      },
      {
        area: '04-signals/signal-modulations',
        label: 'Signale',
        hint: 'Feine Hinweise im Text, die die Antwort nachjustieren.',
      },
      {
        area: '01-base/tone-modifiers',
        label: 'Tonalität',
        hint: 'Wie sich die Ansprache je Persona verschiebt.',
      },
    ],
  },
  {
    slug: 'anzeige',
    intro:
      'Wie Ergebnisse im Widget erscheinen: welche Boxen, wie viele Einträge, '
      + 'welche Kopfzeilen-Links — und was kleine Geräte davon abweichend bekommen.',
    sections: [
      {
        area: '01-base/display-rules',
        label: 'Darstellungsregeln',
        hint: 'Boxen, Grenzen und Textlängen der Ergebnisdarstellung.',
      },
      {
        area: '01-base/header-nav',
        label: 'Kopfzeilen-Navigation',
        hint: 'Die Links, die das Widget oben anbietet.',
      },
      {
        area: '01-base/device-config',
        label: 'Geräte',
        hint: 'Abweichende Grenzen für kleine Bildschirme.',
      },
    ],
  },
  {
    slug: 'datenschutz',
    intro:
      'Was mitgeschrieben wird und wie lange. Weniger Logging heißt weniger '
      + 'Auswertung — die Analyse-Ansichten zeigen dann entsprechend weniger.',
    sections: [
      {
        area: '01-base/privacy-config',
        label: 'Datenschutz',
        hint: 'Welche Inhalte überhaupt gespeichert werden dürfen.',
      },
      {
        area: '01-base/quality-log-config',
        label: 'Qualitäts-Logging',
        hint: 'Umfang der Protokolle, aus denen die Analyse gespeist wird.',
      },
    ],
  },
  {
    slug: 'wissen',
    intro:
      'Woher der Bot Wissen holt: eigene Dokumente (RAG) und die MCP-Server, über '
      + 'die er WirLernenOnline durchsucht. Ein Wissensbereich entsteht mit dem '
      + 'ersten Dokument darin — angelegt wird er nicht, er wird befüllt.',
    sections: [
      {
        panel: 'rag-areas',
        label: 'Wissensbereiche',
        hint: 'Was aktuell in der Datenbank liegt, mit Dokumenten und Abschnitten.',
      },
      {
        panel: 'rag-ingest',
        label: 'Dokumente hinzufügen',
        hint: 'Datei, Webseite oder Text einlesen und in einen Bereich legen.',
      },
      {
        // Describes the areas the panel above lists — only useful together,
        // which is why this config sits between them and not on its own page.
        area: '05-knowledge/rag-config',
        label: 'Bereichs-Einstellungen',
        hint: '„always" legt einen Bereich in jeden Prompt, „on-demand" nur bei Bedarf.',
      },
      {
        panel: 'mcp-registry',
        label: 'MCP-Server',
        hint: 'Werkzeug-Server, die der Bot im Gespräch aufrufen darf.',
      },
    ],
  },
];

export function curatedView(slug: string): CuratedView | undefined {
  return CURATED_VIEWS.find((view) => view.slug === slug);
}
