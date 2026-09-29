/**
 * Feldtexte (ST-1) der vier Schichtdokumente: Grundpersona, Leitplanken,
 * Fachregeln, Plattformwissen. Alle vier nutzen dasselbe Modell, darum stehen
 * ihre Texte einmal hier und nicht je Bereich.
 *
 * Schlüsselschema aller `fields-*.ts`: `feld.<Modell>.<feld>.{label,hint}` —
 * `<Modell>` ist der pydantic-Klassenname, wie ihn das Schema als `title`
 * führt (Entwurf: Plan 2026-09-26 §9.3). Ein Hilfetext sagt, was das Feld
 * WIRKT. Wo der Code ein Feld nicht auswertet, sagt er genau das: die
 * Kopfangaben hier stammen aus dem Schichtmodell des ALT und steuern nichts —
 * `services/config_loader/personas.py` liest bei Grundpersona und Leitplanken
 * nur den Text, bei den Fachdokumenten die ganze Datei als Prompttext.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_LAYER_DOC: CataloguePart = {
  de: {
    'feld.LayerDocArea.frontmatter.label': 'Kopfangaben',
    'feld.LayerDocArea.frontmatter.hint':
      'Beschreibende Angaben zum Dokument. Bei Fachregeln und Plattformwissen stehen sie '
      + 'wörtlich mit im Prompt, bei Grundpersona und Leitplanken zählt nur der Text.',
    'feld.LayerDocArea.body.label': 'Text',
    'feld.LayerDocArea.body.hint':
      'Die Anweisung selbst, in Markdown. Diesen Text liest das Modell in jedem Zug, in '
      + 'dem das Dokument gilt.',
    'feld.LayerDocFrontmatter.element.label': 'Art',
    'feld.LayerDocFrontmatter.element.hint':
      'Art des Bausteins, etwa persona, rule, domain oder knowledge. Nur beschreibend.',
    'feld.LayerDocFrontmatter.variant.label': 'Untertyp',
    'feld.LayerDocFrontmatter.variant.hint':
      'Genauere Einordnung, etwa base, guardrail oder platform. Nur beschreibend.',
    'feld.LayerDocFrontmatter.id.label': 'Kennung',
    'feld.LayerDocFrontmatter.id.hint':
      'Name des Bausteins, etwa persona.base. Eindeutig halten, damit Verweise lesbar '
      + 'bleiben; der Code wertet die Kennung nicht aus.',
    'feld.LayerDocFrontmatter.layer.label': 'Schicht',
    'feld.LayerDocFrontmatter.layer.hint':
      'Schicht aus dem Aufbau der Vorlage: 1 = Grundlage, 2 = Fachwissen. Die Reihenfolge '
      + 'im Prompt legt der Code fest, nicht diese Zahl.',
    'feld.LayerDocFrontmatter.priority.label': 'Priorität',
    'feld.LayerDocFrontmatter.priority.hint':
      'Gewicht aus der Vorlage, höher heißt wichtiger. Wird derzeit nicht ausgewertet.',
    'feld.LayerDocFrontmatter.always_active.label': 'Immer aktiv',
    'feld.LayerDocFrontmatter.always_active.hint':
      'Markiert Bausteine, die in jedem Zug gelten. Nur beschreibend: Grundpersona und '
      + 'Leitplanken lädt der Code ohnehin immer.',
    'feld.LayerDocFrontmatter.version.label': 'Version',
    'feld.LayerDocFrontmatter.version.hint':
      'Stand des Textes, frei gepflegt (etwa 4.0.0). Hilft beim Abgleich mit der Redaktion.',
  },
  en: {
    'feld.LayerDocArea.frontmatter.label': 'Header',
    'feld.LayerDocArea.frontmatter.hint':
      'Descriptive details about the document. For domain rules and platform knowledge '
      + 'they go into the prompt verbatim; for the base persona and guardrails only the '
      + 'text counts.',
    'feld.LayerDocArea.body.label': 'Text',
    'feld.LayerDocArea.body.hint':
      'The instruction itself, in Markdown. The model reads this text in every turn the '
      + 'document applies to.',
    'feld.LayerDocFrontmatter.element.label': 'Kind',
    'feld.LayerDocFrontmatter.element.hint':
      'Kind of building block, such as persona, rule, domain or knowledge. Descriptive only.',
    'feld.LayerDocFrontmatter.variant.label': 'Subtype',
    'feld.LayerDocFrontmatter.variant.hint':
      'Finer classification, such as base, guardrail or platform. Descriptive only.',
    'feld.LayerDocFrontmatter.id.label': 'Identifier',
    'feld.LayerDocFrontmatter.id.hint':
      'Name of the building block, such as persona.base. Keep it unique so references stay '
      + 'readable; the code does not evaluate it.',
    'feld.LayerDocFrontmatter.layer.label': 'Layer',
    'feld.LayerDocFrontmatter.layer.hint':
      'Layer from the template structure: 1 = foundation, 2 = domain knowledge. The code '
      + 'sets the order in the prompt, not this number.',
    'feld.LayerDocFrontmatter.priority.label': 'Priority',
    'feld.LayerDocFrontmatter.priority.hint':
      'Weight from the template, higher means more important. Currently not evaluated.',
    'feld.LayerDocFrontmatter.always_active.label': 'Always active',
    'feld.LayerDocFrontmatter.always_active.hint':
      'Marks building blocks that apply in every turn. Descriptive only: the code always '
      + 'loads the base persona and the guardrails anyway.',
    'feld.LayerDocFrontmatter.version.label': 'Version',
    'feld.LayerDocFrontmatter.version.hint':
      'Version of the text, maintained by hand (such as 4.0.0). Helps when comparing '
      + 'with the editorial team.',
  },
};
