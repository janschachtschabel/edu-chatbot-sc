/**
 * Prüffehler des Servers am Feld (ST-2e): ein Satz je pydantic-Fehlerart,
 * `validation.<art>`, und die Zusammenfassung über dem Formular.
 *
 * Die Platzhalter heißen wie die Einträge in `ctx` (`ge`, `le`, `gt`, `lt`,
 * `expected`) — `core/field-problems.ts` reicht sie unverändert durch, Zahlen
 * lokal formatiert. Eine Art ohne eigenen Satz nennt die Meldung des Servers
 * (`validation.other`), statt sie zu verschweigen.
 */
import type { CataloguePart } from './catalogue-part';

export const VALIDATION: CataloguePart = {
  de: {
    'editor.invalidFields': 'Nicht gespeichert, bitte prüfen — {fields}.',
    'schemaForm.problemsElsewhere': 'Weitere Meldungen ohne eigenes Feld: {list}',
    'validation.greater_than_equal': 'Mindestens {ge}.',
    'validation.less_than_equal': 'Höchstens {le}.',
    'validation.greater_than': 'Muss größer als {gt} sein.',
    'validation.less_than': 'Muss kleiner als {lt} sein.',
    'validation.int_parsing': 'Bitte eine ganze Zahl eingeben.',
    'validation.int_type': 'Bitte eine ganze Zahl eingeben.',
    'validation.int_from_float': 'Bitte eine ganze Zahl ohne Nachkommastellen eingeben.',
    'validation.float_parsing': 'Bitte eine Zahl eingeben.',
    'validation.float_type': 'Bitte eine Zahl eingeben.',
    'validation.string_type': 'Hier gehört ein Text hin.',
    'validation.bool_parsing': 'Hier gehört „an" oder „aus" hin.',
    'validation.bool_type': 'Hier gehört „an" oder „aus" hin.',
    'validation.literal_error': 'Erlaubt sind nur diese Werte: {expected}.',
    'validation.missing': 'Dieses Feld muss ausgefüllt sein.',
    'validation.list_type': 'Hier wird eine Liste erwartet.',
    'validation.dict_type': 'Hier werden Einträge mit Schlüsseln erwartet.',
    'validation.model_type': 'Hier werden Einträge mit Schlüsseln erwartet.',
    'validation.string_pattern_mismatch': 'Das Format passt nicht.',
    'validation.other': 'Der Server lehnt den Wert ab: {msg}',
  },
  en: {
    'editor.invalidFields': 'Not saved, please check — {fields}.',
    'schemaForm.problemsElsewhere': 'Further messages without a field of their own: {list}',
    'validation.greater_than_equal': 'At least {ge}.',
    'validation.less_than_equal': 'At most {le}.',
    'validation.greater_than': 'Must be greater than {gt}.',
    'validation.less_than': 'Must be less than {lt}.',
    'validation.int_parsing': 'Please enter a whole number.',
    'validation.int_type': 'Please enter a whole number.',
    'validation.int_from_float': 'Please enter a whole number without decimals.',
    'validation.float_parsing': 'Please enter a number.',
    'validation.float_type': 'Please enter a number.',
    'validation.string_type': 'This needs a text.',
    'validation.bool_parsing': 'This needs "on" or "off".',
    'validation.bool_type': 'This needs "on" or "off".',
    'validation.literal_error': 'Only these values are allowed: {expected}.',
    'validation.missing': 'This field must be filled in.',
    'validation.list_type': 'A list is expected here.',
    'validation.dict_type': 'Entries with keys are expected here.',
    'validation.model_type': 'Entries with keys are expected here.',
    'validation.string_pattern_mismatch': 'The format does not match.',
    'validation.other': 'The server refuses the value: {msg}',
  },
};
