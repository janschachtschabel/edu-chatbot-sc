/**
 * LaTeX→Unicode text cleanup (§7 `ui/markdown` helper). Verbatim port of the
 * `stripLatex` half of ALT `chat/chat-text-utils.ts` — converts the LaTeX
 * fragments the LLM occasionally emits despite the anti-LaTeX prompt
 * (`\frac12`, `\frac{1}{2}`, `\sqrt{2}`, `$x^2$`) into readable Unicode. Used by
 * the markdown renderer and (later) the print views. No logic change.
 */

// Unicode-Brüche für die häufigsten Werte aus Mathe-Materialien.
const _UNI_FRAC: Record<string, string> = {
  '1/2': '½', '1/3': '⅓', '2/3': '⅔', '1/4': '¼', '3/4': '¾',
  '1/5': '⅕', '2/5': '⅖', '3/5': '⅗', '4/5': '⅘',
  '1/6': '⅙', '5/6': '⅚', '1/7': '⅐',
  '1/8': '⅛', '3/8': '⅜', '5/8': '⅝', '7/8': '⅞',
  '1/9': '⅑', '1/10': '⅒',
};

export function stripLatex(text: string): string {
  const fr = (n: string, d: string): string =>
    _UNI_FRAC[`${n}/${d}`] || `${n}⁄${d}`;
  return text
    .replace(/\\frac\s*\{\s*(\d+)\s*\}\s*\{\s*(\d+)\s*\}/g, (_m, n, d) => fr(n, d))
    .replace(/\\frac\s*(\d)\s*(\d)/g, (_m, n, d) => fr(n, d))
    .replace(/\\sqrt\s*\{\s*([^}]+?)\s*\}/g, (_m, x) => `√${x}`)
    .replace(/\$([^$\n]+?)\$/g, '$1');
}
