/**
 * TTS-Text-Aufbereitung — Vorlese-Text säubern (`stripMarkdown`) und in
 * Satz-Häppchen zerlegen (`splitSentences`). Verbatim-Port aus ALT
 * `chat/chat-text-utils.ts` (Z. 39–64), KEINE Logik-Änderung.
 *
 * ALTs `chat-text-utils.ts` war ein Grab-Bag; boerdi-chat dekomponiert es
 * nach Verantwortung: `stripLatex` → `markdown/latex.ts` (8-2b),
 * `getLicenseShort` → `cards/license.ts` (8-2f). Diese zwei Helfer werden
 * ausschließlich vom Speech-Cluster (TTS) genutzt und leben daher hier.
 * `formatPhaseLabel` / `_attrIsTrue` folgen mit ihren Konsumenten
 * (Chat-Shell / Element-Definition 8-5).
 */

/** Entfernt Bold/Italic/Links/Header-Marker/Backticks für TTS-Vorlesetext. */
export function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/#{1,6}\s/g, '')
    .replace(/[`~]/g, '');
}

/** Split text into sentence-sized chunks for TTS. */
export function splitSentences(text: string): string[] {
  // Split on sentence-ending punctuation followed by space or end
  const raw = text.match(/[^.!?]+[.!?]+[\s]?|[^.!?]+$/g) || [text];
  // Merge very short fragments (< 20 chars) with the previous sentence
  const merged: string[] = [];
  for (const s of raw) {
    const trimmed = s.trim();
    if (!trimmed) continue;
    if (merged.length > 0 && trimmed.length < 20) {
      merged[merged.length - 1] += ' ' + trimmed;
    } else {
      merged.push(trimmed);
    }
  }
  return merged;
}
