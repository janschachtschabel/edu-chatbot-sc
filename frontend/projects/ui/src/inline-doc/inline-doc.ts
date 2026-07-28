/**
 * Reine Helfer für die Inline-Document-Box (Lernpfade M09 / KI-Materialien M10
 * / Edits M11). Verbatim-Port der ALT-`ChatComponent`-Methoden
 * `inlineDocFontSize` / `inlineDocIcon` / `inlineDocFallbackLabel`
 * (chat.component.ts). Icons aus dem geteilten `ui/icons`-Set.
 */
import { ICONS } from '../icons/icons';

/** Klammert die Inline-Document-Schriftgröße aus den Display-Rules
 *  (`inline_documents.font_size_percent`) auf [70,100], Default 85. Verbatim
 *  aus ALT — `parseInt` fängt String-Werte, NaN/fehlend → Default. */
export function inlineDocFontSize(displayRules: Record<string, unknown> | null | undefined): number {
  const raw = (displayRules as any)?.['inline_documents']?.['font_size_percent'];
  const n = typeof raw === 'number' ? raw : parseInt(raw, 10);
  if (!Number.isFinite(n)) return 85;
  return Math.max(70, Math.min(100, n));
}

/** Inline-SVG-Icon für die Inline-Document-Header-Zeile nach `kind`. */
export function inlineDocIcon(kind: string): string {
  switch ((kind || '').toLowerCase()) {
    case 'lernpfad':    return ICONS.route;
    case 'ki_material': return ICONS.article;
    case 'edit':        return ICONS.edit;
    case 'bericht':     return ICONS.description;
    case 'remix':       return ICONS.refresh;
    default:            return ICONS.description;
  }
}

/** Fallback-Label wenn das Backend keinen `title` liefert. */
export function inlineDocFallbackLabel(kind: string): string {
  switch ((kind || '').toLowerCase()) {
    case 'lernpfad':    return 'Lernpfad';
    case 'ki_material': return 'Material';
    case 'edit':        return 'Bearbeitete Version';
    case 'bericht':     return 'Bericht';
    case 'remix':       return 'Remix';
    default:            return 'Inhalt';
  }
}
