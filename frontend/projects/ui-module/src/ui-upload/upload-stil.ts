/**
 * Styles von `<boerdi-ui-upload>` (Paket U3-1a) für den Shadow Root — nur M3-Tokens (`--mat-sys-*`,
 * sie erben in den Shadow Root), Radien aus der M3-Skala; `check:tokens` und `check:radii` lesen diese
 * Datei mit. Aussehen wie der Baum-Kern (`_baum/_baum.scss`), dort SCSS und für Komponenten; ein
 * nachgeladenes Element hat keinen SCSS-Schritt.
 *
 * Nutzertest 2026-11-05: je Datei ein festes Raster (Name · Größe · Rolle) statt umbrechender
 * Flex-Zeilen; „Ignorieren“ als schlanker Text-Knopf in der Ordnerzeile; eine Hilfslinie je Ebene.
 * Wird das Modul schmal (Container-Abfrage), rückt das Rollen-Feld geordnet unter den Namen.
 * Bedienelemente mindestens 28 px hoch (WCAG 2.5.8 verlangt 24 px), Fokus immer sichtbar.
 */
export const UPLOAD_STIL = `
:host { display: block; color: var(--mat-sys-on-surface); container-type: inline-size; }
.u {
  position: relative; display: flex; flex-direction: column; gap: 10px; min-width: 0;
  border: 1px solid var(--mat-sys-outline-variant); border-radius: var(--mat-sys-corner-small);
  padding: 10px 12px 12px; background: var(--mat-sys-surface); font-size: .82rem; line-height: 1.4;
}
.u p { margin: 0; }
.u__titel { margin: 0; font-size: .86rem; font-weight: 600; }
.u__befund { font-weight: 600; }
.u__ablage {
  border: 1px dashed var(--mat-sys-outline); border-radius: var(--mat-sys-corner-small);
  padding: 14px 12px; text-align: center; color: var(--mat-sys-on-surface-variant);
}
.u__ablage--ueber { border-style: solid; border-color: var(--mat-sys-primary); background: var(--mat-sys-surface-container); }
.u__knoepfe { display: flex; flex-wrap: wrap; gap: 8px; }
button, select { font: inherit; }
button {
  min-height: 32px; border: 1px solid var(--mat-sys-outline); border-radius: var(--mat-sys-corner-full);
  padding: 4px 14px; background: var(--mat-sys-surface); color: var(--mat-sys-primary); cursor: pointer;
}
button.u__haupt { background: var(--mat-sys-primary); border-color: var(--mat-sys-primary); color: var(--mat-sys-on-primary); }
button:disabled { cursor: not-allowed; opacity: .6; }
button:focus-visible, select:focus-visible { outline: 2px solid var(--mat-sys-primary); outline-offset: 2px; }
select {
  min-height: 28px; max-width: 100%; border: 1px solid var(--mat-sys-outline-variant);
  border-radius: var(--mat-sys-corner-extra-small); background: var(--mat-sys-surface);
  color: var(--mat-sys-on-surface); padding: 2px 4px; font-size: .78rem;
}
.u__baum, .u__gruppe { list-style: none; margin: 0; padding: 0; }
.u__gruppe {
  margin-inline-start: 7px; padding-inline-start: clamp(8px, 4%, 18px);
  border-inline-start: 1px solid var(--mat-sys-outline-variant);
}
.u__ordner {
  display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center;
  column-gap: 8px; min-height: 32px;
}
.u__ordner > .u__auf {
  min-width: 0; min-height: 28px; border: none; border-radius: var(--mat-sys-corner-extra-small);
  padding: 2px 4px; background: transparent; color: var(--mat-sys-on-surface); text-align: start;
  overflow-wrap: break-word; font-weight: 600;
}
.u__ordner > .u__zahl { white-space: nowrap; }
.u__ordner > .u__leise {
  min-height: 28px; border: none; padding: 2px 6px; background: transparent; white-space: nowrap;
  font-size: .78rem; text-decoration: underline; text-underline-offset: 2px;
}
.u__datei {
  display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(7.5em, auto);
  align-items: center; column-gap: 10px; row-gap: 2px; min-height: 32px; padding-block: 1px;
}
.u__name { min-width: 0; overflow-wrap: anywhere; }
.u__zahl, .u__hinweis { color: var(--mat-sys-on-surface-variant); }
.u__datei > .u__zahl { white-space: nowrap; font-variant-numeric: tabular-nums; text-align: end; }
.u__datei--ignoriert .u__name { color: var(--mat-sys-on-surface-variant); text-decoration: line-through; }
.u__warnungen { margin: 0; padding-inline-start: 1.2em; }
.u__fehler { color: var(--mat-sys-error); }
.u__fortschritt { width: 100%; height: 6px; accent-color: var(--mat-sys-primary); }
.u__wlo {
  display: flex; flex-direction: column; gap: 8px; padding-top: 10px;
  border-top: 1px solid var(--mat-sys-outline-variant);
}
.u__wlo > .u__titel { font-size: .84rem; }
.u__ergebnis { max-height: 18em; overflow-y: auto; border-radius: var(--mat-sys-corner-extra-small); }
.u__ergebnis:focus-visible { outline: 2px solid var(--mat-sys-primary); outline-offset: 2px; }
.u__ergebnis-liste { list-style: none; margin: 0; padding: 0; }
.u__eintrag {
  display: grid; grid-template-columns: 1.4em minmax(0, 1fr) auto; align-items: baseline;
  column-gap: 8px; row-gap: 2px; padding-block: 3px;
}
.u__eintrag > .u__zahl { text-align: end; }
.u__eintrag > .u__link { grid-column: 2 / -1; justify-self: start; color: var(--mat-sys-primary); }
.u__link:focus-visible { outline: 2px solid var(--mat-sys-primary); outline-offset: 2px; }
.u__symbol { font-weight: 700; text-align: center; }
.u__eintrag--failed .u__symbol, .u__eintrag--failed > .u__zahl { color: var(--mat-sys-error); }
.u__unsichtbar { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@container (max-width: 340px) {
  .u__eintrag { grid-template-columns: 1.4em minmax(0, 1fr); }
  .u__eintrag > .u__zahl { grid-column: 2; text-align: start; }
  .u__datei { grid-template-columns: minmax(0, 1fr) auto; }
  .u__datei > select { grid-column: 1 / -1; justify-self: start; }
}
@container (max-width: 280px) {
  .u__ordner { grid-template-columns: minmax(0, 1fr) auto; }
  .u__ordner > .u__leise { grid-column: 1 / -1; justify-self: start; }
}
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
