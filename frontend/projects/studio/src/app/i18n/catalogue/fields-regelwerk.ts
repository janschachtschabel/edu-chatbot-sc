/**
 * Feldtexte (ST-1) der Seite „Identität & Schutz“, Bereich `01-base/policy`
 * (Regelwerk). Ausgewertet in `domain/policy.py`: `match` und `effect` sind freie
 * Objekte, gelesen werden darin `persona`, `intent`, `message_regex` bzw.
 * `block_tools`, `disclaimer`, `disclaimer_en`. `description` ist nur beschreibend.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_REGELWERK: CataloguePart = {
  de: {
    'feld.PolicyArea.rules.label': 'Regeln',
    'feld.PolicyArea.rules.hint':
      'Regeln der Organisation, im Chat geprüft: passt eine, sperrt sie Werkzeuge oder hängt '
      + 'einen Hinweis an die Antwort. Die Antwort selbst blockiert keine Regel.',
    'feld.PolicyRule.id.label': 'Kennung',
    'feld.PolicyRule.id.hint':
      'Eindeutiger Name der Regel, etwa pol-no-personal-data-search. Erscheint im Debug-Block '
      + 'unter den getroffenen Regeln.',
    'feld.PolicyRule.description.label': 'Beschreibung',
    'feld.PolicyRule.description.hint':
      'Wozu die Regel dient, für die Redaktion. Nur beschreibend.',
    'feld.PolicyRule.match.label': 'Bedingung',
    'feld.PolicyRule.match.hint':
      'Wann die Regel greift: persona (etwa P-RED), intent (etwa I01), message_regex '
      + '(Suchmuster auf die kleingeschriebene Nachricht; ungültig = greift nie). Alles '
      + 'Angegebene muss passen; ohne Angabe greift sie immer.',
    'feld.PolicyRule.effect.label': 'Wirkung',
    'feld.PolicyRule.effect.hint':
      'Was geschieht: block_tools sperrt die genannten Werkzeuge, disclaimer hängt einen '
      + 'Hinweis kursiv an die Antwort, disclaimer_en ist seine englische Fassung (leer = der '
      + 'deutsche).',
  },
  en: {
    'feld.PolicyArea.rules.label': 'Rules',
    'feld.PolicyArea.rules.hint':
      'Rules of the organisation, checked in the chat: if one matches, it blocks tools or '
      + 'adds a notice to the answer. No rule blocks the answer itself.',
    'feld.PolicyRule.id.label': 'Identifier',
    'feld.PolicyRule.id.hint':
      'Unique name of the rule, such as pol-no-personal-data-search. Appears in the debug '
      + 'block among the matched rules.',
    'feld.PolicyRule.description.label': 'Description',
    'feld.PolicyRule.description.hint':
      'What the rule is for, for the editorial team. Descriptive only.',
    'feld.PolicyRule.match.label': 'Condition',
    'feld.PolicyRule.match.hint':
      'When the rule applies: persona (such as P-RED), intent (such as I01), message_regex '
      + '(pattern on the lower-cased message; invalid = never applies). Everything given must '
      + 'match; with nothing given, it always applies.',
    'feld.PolicyRule.effect.label': 'Effect',
    'feld.PolicyRule.effect.hint':
      'What happens: block_tools blocks the listed tools, disclaimer adds a notice in italics '
      + 'to the answer, disclaimer_en is its English version (empty = the German one).',
  },
};
