import { describe, expect, it } from 'vitest';

import { splitRich } from './rich-text';

/**
 * Auszeichnung MITTEN im Satz (C1-d4b2).
 *
 * Der Bedarf ist gemessen: sieben Stellen im Studio setzen `<strong>` oder
 * `<code>` innerhalb eines Satzes. Je Bruchstück ein Katalog-Eintrag wäre
 * derselbe Fehler wie beim Zustands-Streifen vor C1-d3a — die Wortstellung
 * gehört der Übersetzung, nicht dem Template. `innerHTML` scheidet aus.
 *
 * Zwei Regeln tragen alles Weitere:
 *
 * 1. **Geteilt wird der KATALOG-Text, eingesetzt wird danach.** Ein Wert, der
 *    selbst einen Stern trägt, kann so keine Auszeichnung erzeugen — die
 *    Auszeichnung steht ausschliesslich in der Übersetzung.
 * 2. **Ein Zeichen ohne Partner bleibt stehen.** Ein halb geschriebener
 *    Marker ist sichtbar falsch statt still verschluckt.
 */
describe('splitRich', () => {
  it('gibt Text ohne Marker als ein einziges Stück zurück', () => {
    expect(splitRich('Nur ein Satz.')).toEqual([
      { kind: 'plain', text: 'Nur ein Satz.' },
    ]);
  });

  it('zeichnet einen Stern-Abschnitt als hervorgehoben aus', () => {
    expect(splitRich('Dieser Lauf trägt *keine Gold-Metriken* — sagt sie.')).toEqual([
      { kind: 'plain', text: 'Dieser Lauf trägt ' },
      { kind: 'strong', text: 'keine Gold-Metriken' },
      { kind: 'plain', text: ' — sagt sie.' },
    ]);
  });

  it('zeichnet einen Backtick-Abschnitt als Code aus', () => {
    expect(splitRich('eine falsche `REPO_BASE_URL` scheitert')).toEqual([
      { kind: 'plain', text: 'eine falsche ' },
      { kind: 'code', text: 'REPO_BASE_URL' },
      { kind: 'plain', text: ' scheitert' },
    ]);
  });

  it('kennt beide Auszeichnungen in einem Satz', () => {
    expect(splitRich('*A* und `B`')).toEqual([
      { kind: 'strong', text: 'A' },
      { kind: 'plain', text: ' und ' },
      { kind: 'code', text: 'B' },
    ]);
  });

  it('setzt Platzhalter ein — auch innerhalb der Auszeichnung', () => {
    expect(splitRich('harte Quote *{rate}* ({ok}/{total})', { rate: '83 %', ok: 10, total: 12 }))
      .toEqual([
        { kind: 'plain', text: 'harte Quote ' },
        { kind: 'strong', text: '83 %' },
        { kind: 'plain', text: ' (10/12)' },
      ]);
  });

  it('lässt einen Wert mit Stern KEINE Auszeichnung erzeugen', () => {
    // Der eingesetzte Wert kann fremd sein (eine Backend-Fehlermeldung). Weil
    // erst geteilt und dann eingesetzt wird, bleibt er ein einziges Stück Text.
    expect(splitRich('*Fehler:* {message}', { message: 'sagt *nichts*' })).toEqual([
      { kind: 'strong', text: 'Fehler:' },
      { kind: 'plain', text: ' sagt *nichts*' },
    ]);
  });

  it('lässt ein Zeichen ohne Partner stehen', () => {
    expect(splitRich('3 * 4 = 12')).toEqual([
      { kind: 'plain', text: '3 * 4 = 12' },
    ]);
  });

  it('lässt einen Platzhalter ohne Wert stehen — wie der Wörterbuch-Kern', () => {
    expect(splitRich('Lauf {id}')).toEqual([
      { kind: 'plain', text: 'Lauf {id}' },
    ]);
  });

  it('gibt für leeren Text nichts zurück statt eines leeren Stücks', () => {
    expect(splitRich('')).toEqual([]);
  });
});
