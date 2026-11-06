/**
 * Styles von `<boerdi-ui-fortschritt>` (Paket K1b) für den Shadow Root — nur M3-Tokens, Radien aus der
 * M3-Skala (`check:tokens`, `check:radii`). Knöpfe mindestens 32 px hoch, Fokus immer sichtbar; der
 * unbestimmte Balken steht still, wenn die Person weniger Bewegung wünscht.
 */
export const FORTSCHRITT_STIL = `
:host { display: block; color: var(--mat-sys-on-surface); }
.f {
  display: flex; flex-direction: column; gap: 8px; min-width: 0;
  border: 1px solid var(--mat-sys-outline-variant); border-radius: var(--mat-sys-corner-small);
  padding: 10px 12px 12px; background: var(--mat-sys-surface); font-size: .82rem; line-height: 1.4;
}
.f:focus-visible { outline: 2px solid var(--mat-sys-primary); outline-offset: 2px; }
.f p, .f h3 { margin: 0; }
.f__titel { font-size: .86rem; font-weight: 600; }
.f__stand { font-weight: 600; }
.f__zeit { color: var(--mat-sys-on-surface-variant); }
progress { width: 100%; height: 4px; accent-color: var(--mat-sys-primary); }
.f__knoepfe { display: flex; flex-wrap: wrap; gap: 8px; }
button {
  font: inherit; min-height: 32px; border: 1px solid var(--mat-sys-outline);
  border-radius: var(--mat-sys-corner-full); padding: 4px 14px; background: var(--mat-sys-surface);
  color: var(--mat-sys-primary); cursor: pointer;
}
button[aria-disabled="true"] { cursor: not-allowed; opacity: .6; }
button:focus-visible { outline: 2px solid var(--mat-sys-primary); outline-offset: 2px; }
.f__unsichtbar { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
[hidden] { display: none !important; }
@media (prefers-reduced-motion: reduce) {
  /* Querschnitts-Review FE-6: der unbestimmte Balken zeichnet der Browser selbst und animiert ihn —
   * bei reduzierter Bewegung eine ruhige Spur; den Stand sagt der Satz daneben. */
  progress:not([value]) {
    -webkit-appearance: none; appearance: none; border: 0; height: 4px;
    border-radius: var(--mat-sys-corner-full); background: var(--mat-sys-surface-container-highest);
  }
  progress:not([value])::-webkit-progress-bar { background: transparent; }
  progress:not([value])::-moz-progress-bar { animation: none; background: transparent; }
}
`;
