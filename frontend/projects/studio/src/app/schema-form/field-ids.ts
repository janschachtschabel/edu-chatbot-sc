/**
 * Bezeichner für ein Formularfeld: die `id` im Dokument und der Schlüssel eines
 * neuen Karten-Eintrags.
 *
 * Zwei reine Funktionen, herausgelöst aus `schema-field.component.ts` — die
 * Komponente war über die 300-Zeilen-Schwelle gewachsen, und keine der beiden
 * hat mit dem Zeichnen zu tun.
 */

/**
 * Injective enough for an `id`: unsafe characters are ESCAPED, not collapsed.
 * `\w` is ASCII-only, so a collapsing sanitizer mapped `größe` and `gr_e` — and
 * `a b` and `a_b` — onto one id, and `<label for>` then bound to whichever
 * control rendered first.
 */
export function safeIdPart(part: string | number): string {
  return String(part).replace(/[^\w.-]/g, (char) => `_${char.codePointAt(0)!.toString(36)}_`);
}

/** Der erste freie Schlüssel einer Karte: `stem`, sonst `stem_2`, `stem_3` …
 *  Ohne Stamm `neuer_eintrag`; beim Duplizieren (ST-3) `<schlüssel>_kopie`. */
export function nextFreeKey(existing: readonly string[], stem = 'neuer_eintrag'): string {
  const taken = new Set(existing);
  if (!taken.has(stem)) return stem;
  for (let n = 2; ; n += 1) {
    const candidate = `${stem}_${n}`;
    if (!taken.has(candidate)) return candidate;
  }
}
