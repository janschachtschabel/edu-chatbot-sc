import type { Catalogue } from '@boerdi/ui';

/**
 * Ein Ausschnitt des Studio-Katalogs, beide Sprachen beieinander.
 *
 * Zusammen und nicht in getrennten `de`-/`en`-Dateien: die Zusage, die hier
 * gehalten werden muss, ist die Schlüsselgleichheit der beiden Sprachen — sie
 * ist beim Schreiben sichtbar, wenn sie zwei Bildschirmzeilen auseinander
 * stehen, und unsichtbar, wenn sie in zwei Dateien stehen.
 */
export interface CataloguePart {
  readonly de: Catalogue;
  readonly en: Catalogue;
}
