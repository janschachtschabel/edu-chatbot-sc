/**
 * Styles von `<boerdi-ui-strukturabgleich>` (Paket U4) für den Shadow Root — nur M3-Tokens
 * (`--mat-sys-*`), Radien aus der M3-Skala; `check:tokens` und `check:radii` lesen diese Datei mit.
 * Die Art steht immer als Wort im Etikett, nie nur als Farbe. Links mindestens 24 px hoch (WCAG 2.5.8),
 * Fokus sichtbar.
 */
export const ABGLEICH_STIL = `
:host { display: block; color: var(--mat-sys-on-surface); container-type: inline-size; }
.a {
  display: flex; flex-direction: column; gap: 8px; min-width: 0;
  border: 1px solid var(--mat-sys-outline-variant); border-radius: var(--mat-sys-corner-small);
  padding: 10px 12px 12px; background: var(--mat-sys-surface); font-size: .82rem; line-height: 1.4;
}
.a p { margin: 0; }
.a__titel { margin: 0; font-size: .86rem; font-weight: 600; }
.a__unter { color: var(--mat-sys-on-surface-variant); }
.a__zahlen { font-weight: 600; }
.a__liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.a__zeile { display: grid; grid-template-columns: 6.5em minmax(0, 1fr); gap: 2px 8px; align-items: baseline; }
.a__liste--e2 { margin-top: 4px; padding-inline-start: 14px; border-inline-start: 1px solid var(--mat-sys-outline-variant); }
.a__art {
  justify-self: start; padding: 0 6px; border-radius: var(--mat-sys-corner-extra-small);
  border: 1px solid var(--mat-sys-outline-variant); font-size: .74rem; white-space: nowrap;
}
.a__art--vorhanden { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); }
.a__art--aehnlich { background: var(--mat-sys-surface-container-high); color: var(--mat-sys-on-surface); }
.a__art--neu { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
.a__art--luecke { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
.a__art--ungewiss { background: var(--mat-sys-surface); color: var(--mat-sys-on-surface-variant); border-style: dashed; }
.a__name { overflow-wrap: anywhere; }
.a__wlo { grid-column: 2; color: var(--mat-sys-on-surface-variant); overflow-wrap: anywhere; }
a { color: var(--mat-sys-primary); display: inline-block; min-height: 24px; }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--mat-sys-primary); outline-offset: 2px; }
details { border-top: 1px solid var(--mat-sys-outline-variant); padding-top: 6px; }
summary { cursor: pointer; min-height: 24px; font-weight: 600; }
.a__hinweis { color: var(--mat-sys-on-surface-variant); font-size: .78rem; }
@container (max-width: 360px) {
  .a__zeile { grid-template-columns: minmax(0, 1fr); }
  .a__wlo { grid-column: 1; }
}
`;
