/**
 * Web-Component-Attribut-Koerzierung. Custom-Element-Attribute kommen immer als
 * String herein (`emit-guide-suggestion="true"`), im Angular-Consumer aber als
 * echtes `boolean`. `_attrIsTrue` normalisiert beide Formen — leerer String
 * (reines Vorhandensein des Attributs, `<x flag>`) sowie `true`/`1`/`yes` gelten
 * als true.
 *
 * Verbatim aus ALT `chat/chat-text-utils.ts` (kein Standalone-Spec dort).
 * NEU (boerdi-chat): aus 8-5 vorgezogen, weil der host-events-Prereq (8-4S-0a)
 * ihn schon braucht; erster Konsument = host-events, die Element-Definition
 * (8-5) reimportiert ihn von hier.
 */
export function _attrIsTrue(v: boolean | string | undefined): boolean {
  if (v === true) return true;
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase();
    return s === '' || s === 'true' || s === '1' || s === 'yes';
  }
  return false;
}
