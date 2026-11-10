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
/** AS-7b (Plan 2026-11-09 §5m, F-2): der Weg eines Ablauf-Schritts `seite` — derselbe Knopf, dieselbe
 *  Übergabe der Sitzung. Eigenes Präfix, weil der Widget-Nachlauf des Backends `__guide__`-Chips
 *  außerhalb der Tour zu Links macht. Er hängt nicht am Lotsen-Modus: er ist ein Schritt des Ablaufs. */
export const FUEHRUNG_QR_PREFIX = '__fuehrung__|';

/** Das Präfix eines Lotsen- oder Führungs-Chips — sonst `null`. */
function praefix(qr: string, guideModeActive: boolean): string | null {
  if (typeof qr !== 'string') return null;
  if (qr.startsWith(FUEHRUNG_QR_PREFIX)) return FUEHRUNG_QR_PREFIX;
  return guideModeActive && qr.startsWith(GUIDE_QR_PREFIX) ? GUIDE_QR_PREFIX : null;
}

/** True, wenn der Quick-Reply-String ein Guide-QR (Magic-Prefix) ist —
 *  aber nur solange der Lotsen-Modus aktiv ist (ein Führungs-Chip immer). */
export function isGuideQuickReply(qr: string, guideModeActive: boolean): boolean {
  return praefix(qr, guideModeActive) !== null;
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
  const p = praefix(qr, guideModeActive);
  if (p === null) return qr;
  const rest = qr.slice(p.length);
  const sepIdx = rest.indexOf('|');
  if (sepIdx === -1) return rest.trim() || t('chips.guideFallback');
  const label = rest.slice(0, sepIdx).trim();
  return label || t('chips.guideFallback');
}

/** Extrahiert die URL aus einem Guide-QR-String. URLs dürfen das Trennzeichen
 *  ``|`` nicht enthalten — ist Teil der Konvention. */
export function guideQuickReplyUrl(qr: string, guideModeActive: boolean): string {
  const p = praefix(qr, guideModeActive);
  if (p === null) return '';
  const rest = qr.slice(p.length);
  const sepIdx = rest.indexOf('|');
  if (sepIdx === -1) return '';
  return rest.slice(sepIdx + 1).trim();
}
