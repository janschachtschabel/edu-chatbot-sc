import { describe, expect, it } from 'vitest';

import { createTranslator } from './dictionary';

/**
 * Wörterbuch-Kern (C1-a). Zwei Regeln tragen alles Weitere:
 *
 * 1. **Rückfall je Schlüssel, nicht je Katalog.** Ein unvollständiger
 *    englischer Katalog darf nicht die ganze Oberfläche auf Deutsch kippen —
 *    und ein fehlender Text darf erst recht nicht leer bleiben.
 * 2. **Ein unbekannter Schlüssel ist sichtbar.** Er kommt als Schlüssel
 *    zurück; eine leere Zeichenkette wäre ein stiller Ausfall in der
 *    Oberfläche, den niemand meldet.
 */

const DE = {
  'widget.open': 'Chat öffnen',
  'widget.close': 'Schließen',
  'print.cardsUsed': 'Verwendete Inhalte ({count})',
};

const EN = {
  'widget.open': 'Open chat',
  // 'widget.close' fehlt bewusst — genau der Rückfall-Fall.
  'print.cardsUsed': 'Sources used ({count})',
};

describe('createTranslator', () => {
  it('liefert den Text der aktiven Sprache', () => {
    expect(createTranslator(EN, DE)('widget.open')).toBe('Open chat');
  });

  it('fällt JE SCHLÜSSEL auf Deutsch zurück, nicht je Katalog', () => {
    const t = createTranslator(EN, DE);
    expect(t('widget.close')).toBe('Schließen');
    // Der Rest des englischen Katalogs bleibt davon unberührt.
    expect(t('widget.open')).toBe('Open chat');
  });

  it('gibt einen unbekannten Schlüssel sichtbar zurück statt leer', () => {
    expect(createTranslator(EN, DE)('widget.gibtsNicht')).toBe('widget.gibtsNicht');
  });

  it('setzt Platzhalter ein', () => {
    // Beleg für den Bedarf: `print-utils.ts` baut „Verwendete Inhalte (3)".
    expect(createTranslator(DE, DE)('print.cardsUsed', { count: 3 }))
      .toBe('Verwendete Inhalte (3)');
    expect(createTranslator(EN, DE)('print.cardsUsed', { count: 3 }))
      .toBe('Sources used (3)');
  });

  it('lässt einen Platzhalter ohne Wert stehen, statt "undefined" zu schreiben', () => {
    // Ein sichtbares {count} ist ein Fehlerhinweis; „undefined" liest sich wie Inhalt.
    expect(createTranslator(DE, DE)('print.cardsUsed')).toBe('Verwendete Inhalte ({count})');
  });

  it('ist auf Deutsch ein reiner Durchreicher — die Standardsprache kostet nichts', () => {
    const t = createTranslator(DE, DE);
    expect(t('widget.close')).toBe('Schließen');
  });
});
