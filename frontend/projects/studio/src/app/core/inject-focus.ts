/**
 * Fokus nach dem nächsten Rendern — für Panels mit Rückfrage (Paket 9, V8).
 *
 * Das Muster stammt aus „Gespräche löschen“ (Paket 4b): beim Scharfschalten auf
 * „Abbrechen“, danach zurück auf den Knopf, der die Rückfrage öffnete. Schließt
 * sich eine Rückfrage, verschwindet der fokussierte Knopf mit ihr — ohne neues
 * Ziel fiele der Fokus auf `<body>`, und wer mit der Tastatur arbeitet, stünde
 * wieder am Seitenanfang (WCAG 2.4.3).
 *
 * - `afterNextRender`: das Ziel entsteht oft erst mit dem nächsten Rendern.
 * - Mehrere Selektoren sind eine Rückfallkette: das erste Ziel, das es gibt und
 *   das nicht gesperrt ist — fehlt die Zeile nach dem Löschen oder hat der Knopf
 *   nichts mehr zu tun, die Überschrift des Panels (`tabindex="-1"`).
 * - In einer zerstörten Ansicht wirft `afterNextRender` (NG0911, Review Paket 7
 *   MINOR 17): wer die Seite während eines Laufs verlässt, bekommt keinen Fokus.
 *
 * Im Injektionskontext aufrufen, als Feld der Komponente.
 */
import { DestroyRef, ElementRef, Injector, afterNextRender, inject } from '@angular/core';

export type FocusAfterRender = (...selectors: string[]) => void;

/** Paket R3-g: ging der Fokus verloren (auf `body` oder einem gesperrten Element)? Nach dem
 *  Speichern sind „Speichern“/„Verwerfen“ gesperrt — wer inzwischen woanders arbeitet, bleibt dort. */
export function fokusVerloren(aktiv: Element | null): boolean {
  if (!aktiv || aktiv === document.body || aktiv === document.documentElement) return true;
  return (aktiv as HTMLButtonElement).disabled === true;
}

/** `nurWennVerloren` (Paket R3-g, WCAG 2.4.3): nur springen, wenn der Fokus verloren ging —
 *  für die Statuszeile nach dem Speichern. */
export function injectFocus(optionen: { readonly nurWennVerloren?: boolean } = {}): FocusAfterRender {
  const host = inject<ElementRef<HTMLElement>>(ElementRef);
  const injector = inject(Injector);
  const destroyRef = inject(DestroyRef);
  return (...selectors) => {
    if (destroyRef.destroyed) return;
    afterNextRender(() => {
      if (optionen.nurWennVerloren && !fokusVerloren(document.activeElement)) return;
      for (const selector of selectors) {
        const target = host.nativeElement.querySelector<HTMLElement>(selector);
        if (target && !target.matches(':disabled')) {
          target.focus();
          return;
        }
      }
    }, { injector });
  };
}
