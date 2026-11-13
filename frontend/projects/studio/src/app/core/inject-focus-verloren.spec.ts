// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { fokusVerloren } from './inject-focus';

/** R3-g: der Fokus geht nur dann auf die Statuszeile, wenn er verloren ging. */
describe('fokusVerloren', () => {
  it('auf body oder einem gesperrten Knopf: verloren; auf einem Feld: nicht', () => {
    expect(fokusVerloren(document.body)).toBe(true);
    expect(fokusVerloren(null)).toBe(true);
    const knopf = document.createElement('button');
    knopf.disabled = true;
    expect(fokusVerloren(knopf)).toBe(true);
    const feld = document.createElement('input');
    expect(fokusVerloren(feld)).toBe(false);
  });
});
