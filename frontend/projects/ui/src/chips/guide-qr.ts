/**
 * Guide-Quick-Reply-Parser (Magic-Prefix ``__guide__|``) — §7 `ui/chips`.
 * Verbatim port of ALT `chat/guide-qr.ts` (behaviour pinned by guide-qr.spec.ts;
 * ALT pinned it via chat.component.spec.ts). No logic change.
 *
 * Magic-prefix für Backend → Frontend Konvention. Backend signalisiert einen
 * "Bring mich hin"-Quick-Reply mit dieser Marker-Form:
 *
 *   __guide__|<Anzeige-Label>|<vollständige URL>
 *
 * Frontend rendert den Eintrag als dunkelblauen Button, Klick navigiert im
 * aktuellen Tab statt eine Folgenachricht zu senden.
 *
 * Pure functions — ``guideModeActive`` (seit Welle E immer ``true``) kommt pro
 * Aufruf als Parameter herein, seit C1-b4 ebenso der Übersetzer.
 */
import type { TranslateFn } from '../i18n/i18n';

/** Marker-Präfix der Guide-QR-Konvention. */
export const GUIDE_QR_PREFIX = '__guide__|';

/** True, wenn der Quick-Reply-String ein Guide-QR (Magic-Prefix) ist —
 *  aber nur solange der Lotsen-Modus aktiv ist. */
export function isGuideQuickReply(qr: string, guideModeActive: boolean): boolean {
  if (!guideModeActive) return false;   // toggle off → never a guide button
  return typeof qr === 'string' && qr.startsWith(GUIDE_QR_PREFIX);
}

/** True if a quick-reply should be hidden entirely. The only reason to hide one
 *  is: it's a Guide-QR (magic-prefix) but the user has Lotsen-Modus disabled —
 *  the link wouldn't make sense. */
export function shouldHideGuideQuickReply(qr: string, guideModeActive: boolean): boolean {
  if (guideModeActive) return false;
  return typeof qr === 'string' && qr.startsWith(GUIDE_QR_PREFIX);
}

/**
 * Extrahiert den Anzeige-Text aus einem Guide-QR-String.
 *
 * @param t Übersetzer (C1-b4) — nur für den Rückfall, wenn das Backend das
 *   Label-Segment leer lässt. Das Label selbst ist Backend-Inhalt und geht nie
 *   durch den Katalog. `t` als letzter Parameter, weil dieses Modul rein ist.
 */
export function guideQuickReplyLabel(qr: string, guideModeActive: boolean, t: TranslateFn): string {
  if (!isGuideQuickReply(qr, guideModeActive)) return qr;
  const rest = qr.slice(GUIDE_QR_PREFIX.length);
  const sepIdx = rest.indexOf('|');
  if (sepIdx === -1) return rest.trim() || t('chips.guideFallback');
  const label = rest.slice(0, sepIdx).trim();
  return label || t('chips.guideFallback');
}

/** Extrahiert die URL aus einem Guide-QR-String. URLs dürfen das Trennzeichen
 *  ``|`` nicht enthalten — ist Teil der Konvention. */
export function guideQuickReplyUrl(qr: string, guideModeActive: boolean): string {
  if (!isGuideQuickReply(qr, guideModeActive)) return '';
  const rest = qr.slice(GUIDE_QR_PREFIX.length);
  const sepIdx = rest.indexOf('|');
  if (sepIdx === -1) return '';
  return rest.slice(sepIdx + 1).trim();
}
