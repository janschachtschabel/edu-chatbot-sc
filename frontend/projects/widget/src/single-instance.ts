/**
 * Doppel-Instanz-Guard des Custom Elements (Port von ALT `widget-main.ts:85-113`).
 *
 * Hintergrund (ALT, Welle C Sprint 7, 2026-05-19 — echter Produktionsvorfall):
 * WordPress-Setups wie `wp-test.wirlernenonline.de` zogen sich gelegentlich zwei
 * gestapelte Chatbots, weil das Widget-Snippet sowohl im Theme-Header als auch in
 * einem Content-Block eingebunden war. Statt auf saubere Host-Konfiguration zu
 * hoffen, blendet das Widget jedes zweite und weitere Element aus und warnt.
 *
 * Der `customElements.get`-Guard im Bootstrap deckt das NICHT ab: er verhindert
 * doppelte *Registrierung*, nicht doppelte *Elemente*.
 *
 * Ein MutationObserver ist nötig, weil WordPress-Seiten Tags dynamisch einfügen
 * (Lazy-Loading, AJAX-Reload von Layout-Blöcken) — ein einmaliger Check beim
 * Bootstrap käme zu früh.
 *
 * Eigene Datei (nicht in `widget-main.ts`): dort läuft der Bootstrap als
 * Top-Level-Seiteneffekt, ein Import in Tests würde eine echte Angular-App
 * starten. So bleibt die Regel testbar.
 */

/** Attribut, mit dem ein ausgeblendetes Duplikat markiert ist (idempotent). */
export const DUPLICATE_FLAG = 'boerdiDuplicateHidden';

/** Alle Duplikate außer dem ersten ausblenden. Idempotent — mehrfache Aufrufe
 *  (der Observer feuert pro Mutation) blenden nicht doppelt aus und warnen nur
 *  einmal je Element. */
export function enforceSingleInstance(elementName = 'boerdi-chat'): number {
  const all = document.querySelectorAll(elementName);
  if (all.length <= 1) return 0;
  let hidden = 0;
  for (let i = 1; i < all.length; i++) {
    const el = all[i] as HTMLElement;
    if (el.dataset[DUPLICATE_FLAG] === '1') continue;
    el.dataset[DUPLICATE_FLAG] = '1';
    el.style.display = 'none';
    hidden++;
    console.warn(
      '[BOERDi Widget] Duplicate <boerdi-chat> hidden — nur die erste Instanz rendert.',
      el,
    );
  }
  return hidden;
}

/** Guard scharf machen: einmal sofort prüfen, dann auf DOM-Inserts hören.
 *  Gibt den Observer zurück (oder `null`, wenn die Umgebung keinen hat). */
export function watchSingleInstance(elementName = 'boerdi-chat'): MutationObserver | null {
  enforceSingleInstance(elementName);
  if (typeof MutationObserver === 'undefined' || !document.body) return null;
  const mo = new MutationObserver(() => enforceSingleInstance(elementName));
  mo.observe(document.body, { childList: true, subtree: true });
  return mo;
}
