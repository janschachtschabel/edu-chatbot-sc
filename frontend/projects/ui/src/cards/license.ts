/**
 * Kompakte Lizenz-Anzeige für das Footer-Badge auf dem Vorschaubild.
 * "CC BY-SA 4.0" → "CC BY-SA", "Custom"/"Individuelle Lizenz" → "©",
 * sonstige werden gekürzt.
 *
 * Verbatim-Port aus ALT `chat/chat-text-utils.ts` (dort im Text-Helfer-
 * Sammelfile). NEU trennt die eine card-sichtbare Funktion als eigenständige
 * Datei heraus — einziger Konsument ist das WloCard-Tile-Lizenzbadge. Der
 * Rest von chat-text-utils folgt mit der Chat-Shell (8-4).
 */
export function getLicenseShort(license: string): string {
  if (!license) return '';
  const l = license.trim();
  // C12: CC0 ist eine Public-Domain-Dedication mit eigenem Kürzel — der
  // ``^cc\b``-Match unten greift bei "CC0" NICHT (kein Word-Boundary
  // zwischen 'c' und '0'), sonst fiele "CC0" fälschlich auf "PD" durch.
  if (/^cc\s*0\b/i.test(l)) return 'CC0';
  if (/^cc\b/i.test(l)) {
    // "CC BY-SA 4.0" → "CC BY-SA"
    return l.replace(/\s*\d(\.\d+)?\s*$/, '').toUpperCase();
  }
  if (/individuelle|custom|copyright/i.test(l)) return '©';
  if (/public\s*domain|gemeinfrei|cc\s*0|pdm/i.test(l)) return 'PD';
  if (l.length > 12) return 'Lizenz';
  return l;
}
