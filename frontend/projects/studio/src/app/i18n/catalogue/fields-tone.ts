/**
 * Feldtexte (ST-1) der Seite „Dimensionen", Bereich Tonalität
 * (`01-base/tone-modifiers`): die Standard-Tonalität für Personas ohne eigene
 * Angaben. Die Personas selbst pflegen dieselben Werte in ihrer Datei.
 *
 * Schlüsselschema wie in allen `fields-*.ts` (siehe `fields-layer-doc.ts`).
 * Der Lader (`services/config_loader/tone.py`) glättet die Werte, bevor
 * `domain/pattern_engine.phase3_modulate` sie anwendet: Längen-Neigung auf
 * −0,3…+0,3, Anrede auf duzen/siezen/wie_user, Kachelmodus auf
 * minimal/reference/highlight — dasselbe Vokabular wie der Antwort-Prompt
 * (`services/response_prompt_display_blocks.py`). Bis 2026-09-27 ließ der Lader
 * minimal/kurz/explanation/ausfuehrlich durch, und nur minimal fand eine Regel.
 * Wirkt nur auf Antworten der Muster-Engine; die Agent-Schleife nimmt die
 * Anrede aus den Persona-Dateien (`services/agent_kopf.py`), nicht von hier.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_TONE: CataloguePart = {
  de: {
    'feld.ToneModifiersArea.default_modifier.label': 'Standard-Tonalität',
    'feld.ToneModifiersArea.default_modifier.hint':
      'Ton, Länge, Anrede und Kachelmodus für Personas ohne eigene Angaben, etwa eine neue '
      + 'Kennung ohne Persona-Datei. Wirkt nur auf Antworten der Muster-Engine.',
    'feld.ToneModifier.tone.label': 'Ton',
    'feld.ToneModifier.tone.hint':
      'Ton der Antwort, frei formuliert, etwa locker oder sachlich. Ob er dem Ton des Musters '
      + 'vorgeht, regelt „Vorrang vor Muster"; ein erkanntes Signal kann ihn ersetzen. Leer: '
      + 'locker.',
    'feld.ToneModifier.length_bias.label': 'Längen-Neigung',
    'feld.ToneModifier.length_bias.hint':
      'Zahl von −0,3 bis +0,3. Über +0,15 wird die Antwort eine Stufe '
      + 'länger (kurz → mittel → lang), unter −0,15 eine kürzer, dazwischen bleibt sie. Leer: 0.',
    'feld.ToneModifier.formality.label': 'Anrede',
    'feld.ToneModifier.formality.hint':
      'duzen, siezen oder wie_user. wie_user nimmt die Persona-Anrede aus dem Bereich Geräte '
      + '(Seite Anzeige), sonst neutral ohne direkte Anrede. Andere Werte gelten als wie_user.',
    'feld.ToneModifier.card_text_mode.label': 'Kacheltext-Modus',
    'feld.ToneModifier.card_text_mode.hint':
      'Wie der Antworttext mit Material-Kacheln umgeht: minimal (keine Einzeltitel im Text), '
      + 'reference (Materialien nennen, einordnen und verlinken) oder highlight (ein bis zwei '
      + 'begründet hervorheben). explanation gilt als highlight, andere Werte werden zu '
      + 'minimal.',
    'feld.ToneModifier.override.label': 'Vorrang vor Muster',
    'feld.ToneModifier.override.hint':
      'An: Ton und Kachelmodus von hier gehen den Vorgaben des Musters vor. Aus: sie gelten '
      + 'nur, wo das Muster sachlich/neutral bzw. minimal vorgibt. Länge und Anrede wirken immer.',
  },
  en: {
    'feld.ToneModifiersArea.default_modifier.label': 'Default tone',
    'feld.ToneModifiersArea.default_modifier.hint':
      'Tone, length, form of address and card mode for personas without their own settings, '
      + 'such as a new identifier without a persona file. Affects pattern engine answers only.',
    'feld.ToneModifier.tone.label': 'Tone',
    'feld.ToneModifier.tone.hint':
      'Tone of the answer, in free text, such as locker or sachlich. "Override pattern" decides '
      + 'whether it beats the pattern tone; a recognised signal can replace it. Empty: locker.',
    'feld.ToneModifier.length_bias.label': 'Length bias',
    'feld.ToneModifier.length_bias.hint':
      'Number from −0.3 to +0.3. Above +0.15 the answer gets one step longer '
      + '(kurz → mittel → lang), below −0.15 one step shorter, in between it stays. Empty: 0.',
    'feld.ToneModifier.formality.label': 'Form of address',
    'feld.ToneModifier.formality.hint':
      'duzen, siezen or wie_user. wie_user takes the form of address of the persona from the '
      + 'Devices area (Display page), otherwise neutral without direct address. Other values '
      + 'count as wie_user.',
    'feld.ToneModifier.card_text_mode.label': 'Card text mode',
    'feld.ToneModifier.card_text_mode.hint':
      'How the answer text deals with material cards: minimal (no single titles in the text), '
      + 'reference (name, place and link materials) or highlight (single out one or two with a '
      + 'reason). explanation counts as highlight, other values become minimal.',
    'feld.ToneModifier.override.label': 'Override pattern',
    'feld.ToneModifier.override.hint':
      'On: tone and card mode from here take precedence over the pattern defaults. Off: they '
      + 'only apply where the pattern sets sachlich/neutral or minimal. Length and address '
      + 'always apply.',
  },
};
