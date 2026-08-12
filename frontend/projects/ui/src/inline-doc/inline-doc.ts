/**
 * Reine Helfer für die Inline-Document-Box (Lernpfade M09 / KI-Materialien M10
 * / Edits M11). Verbatim-Port der ALT-`ChatComponent`-Methoden
 * `inlineDocFontSize` / `inlineDocIcon` / `inlineDocFallbackLabel`
 * (chat.component.ts). Icons aus dem geteilten `ui/icons`-Set.
 */
import { ICONS } from '../icons/icons';
import type { TranslateFn } from '../i18n/i18n';

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
    // Vorgeschlagene, noch nicht ausgeführte Änderung an WLO — bewusst nicht
    // `check`: ein Haken behauptete, sie sei schon geschehen.
    case 'schreib_vorschau': return ICONS.edit_note;
    default:            return ICONS.description;
  }
}

/** Fallback-Label wenn das Backend keinen `title` liefert. `t` als Parameter
 *  (C1-b3), damit das Modul rein bleibt; die Schlüssel tragen den Backend-`kind`
 *  im Namen, die Zuordnung bleibt also ablesbar. */
export function inlineDocFallbackLabel(kind: string, t: TranslateFn): string {
  switch ((kind || '').toLowerCase()) {
    case 'lernpfad':    return t('inlineDoc.kind.lernpfad');
    case 'ki_material': return t('inlineDoc.kind.ki_material');
    case 'edit':        return t('inlineDoc.kind.edit');
    case 'bericht':     return t('inlineDoc.kind.bericht');
    case 'remix':       return t('inlineDoc.kind.remix');
    default:            return t('inlineDoc.kind.fallback');
  }
}
