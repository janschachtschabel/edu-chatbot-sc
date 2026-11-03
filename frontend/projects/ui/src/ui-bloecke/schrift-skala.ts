/**
 * Schriftskala der Inhalte von UI-Modulen aus den Anzeige-Regeln einer Nachricht
 * (`inline_documents.font_size_percent`, Studio „Dokument-Boxen“). Übernommen aus der früheren
 * Dokument-Box (`inlineDocFontSize`, ALT-Port): auf 70–100 % geklammert, Vorgabe 85 %;
 * `parseInt` fängt Zeichenketten, NaN oder Fehlendes → Vorgabe.
 */
export function schriftProzent(displayRules: Record<string, unknown> | null | undefined): number {
  const raw = (displayRules as any)?.['inline_documents']?.['font_size_percent'];
  const n = typeof raw === 'number' ? raw : parseInt(raw, 10);
  if (!Number.isFinite(n)) return 85;
  return Math.max(70, Math.min(100, n));
}
