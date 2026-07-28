// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { waitForElement } from './widget-element-loader';

describe('waitForElement', () => {
  it('ist fertig, sobald das Element registriert ist', async () => {
    customElements.define('wp-probe-a', class extends HTMLElement {});
    await expect(waitForElement('wp-probe-a', 5_000)).resolves.toBeUndefined();
  });

  it('wartet auf eine Registrierung, die erst noch kommt', async () => {
    const waiting = waitForElement('wp-probe-b', 5_000);
    customElements.define('wp-probe-b', class extends HTMLElement {});
    await expect(waiting).resolves.toBeUndefined();
  });

  it('gibt auf, statt ewig Fortschritt zu behaupten', async () => {
    // `widget-main.ts` fängt einen gescheiterten Bootstrap selbst ab und loggt
    // ihn nur — ohne Frist bliebe die Vorschau für immer im Ladezustand.
    await expect(waitForElement('wp-probe-nie', 5)).rejects.toThrow('wurde nicht registriert');
  });
});
