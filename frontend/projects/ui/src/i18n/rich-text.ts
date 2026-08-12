/**
 * Auszeichnung mitten im Satz (C1-d4b2) — ein Katalog-Text, mehrere Stücke.
 *
 * Sieben Stellen im Studio setzen `<strong>` oder `<code>` INNERHALB eines
 * Satzes. Drei Wege standen zur Wahl:
 *
 *  - **Je Bruchstück ein Eintrag** („Dieser Lauf trägt" + „keine
 *    Gold-Metriken" + „— die Scorecard …"). Genau der Fehler, den C1-d3a beim
 *    Zustands-Streifen abgestellt hat: die Wortstellung gehört der
 *    Übersetzung, nicht dem Template.
 *  - **`innerHTML`** mit Markup im Katalog. Der Baum vermeidet es bewusst, und
 *    ein Katalog wäre damit eine Quelle für Markup — eine Angriffsfläche für
 *    einen Gewinn, den zwei Zeichen auch bringen.
 *  - **Marker im Text, geteilt beim Rendern.** Der Übersetzer sieht den ganzen
 *    Satz mitsamt der Hervorhebung an ihrem Platz und darf sie verschieben.
 *
 * Gewählt ist der dritte. Die Marker sind die aus jedem Editor bekannten:
 * `*so*` hebt hervor, `` `so` `` ist Code.
 *
 * **Geteilt wird der Katalog-Text, eingesetzt wird danach.** Damit kann ein
 * eingesetzter Wert — etwa eine Fehlermeldung des Backends — niemals
 * Auszeichnung erzeugen; sie steht ausschliesslich in der Übersetzung.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import { TranslationParams, einsetzen } from './dictionary';

export type RichKind = 'plain' | 'strong' | 'code';

export interface RichSegment {
  readonly kind: RichKind;
  readonly text: string;
}

/** Ein Stern- oder Backtick-Paar mit mindestens einem Zeichen dazwischen.
 *  Ein Zeichen ohne Partner passt nicht und bleibt damit stehen. */
const MARKIERT = /\*([^*]+)\*|`([^`]+)`/g;

/**
 * Zerlegt einen Katalog-Text in Stücke und setzt in jedes die Platzhalter ein.
 *
 * @param text Text aus dem Katalog, Platzhalter und Marker noch enthalten.
 * @param params Werte der Platzhalter. Ohne sie bleiben die Platzhalter stehen
 *   — dieselbe Regel wie im Wörterbuch-Kern.
 * @returns Die Stücke in Lesereihenfolge; leerer Text ergibt keine Stücke.
 */
export function splitRich(text: string, params?: TranslationParams): readonly RichSegment[] {
  const segments: RichSegment[] = [];
  const push = (kind: RichKind, roh: string): void => {
    if (roh) segments.push({ kind, text: einsetzen(roh, params) });
  };

  let gelesen = 0;
  for (const treffer of text.matchAll(MARKIERT)) {
    push('plain', text.slice(gelesen, treffer.index));
    push(treffer[1] === undefined ? 'code' : 'strong', treffer[1] ?? treffer[2]);
    gelesen = treffer.index + treffer[0].length;
  }
  push('plain', text.slice(gelesen));
  return segments;
}
