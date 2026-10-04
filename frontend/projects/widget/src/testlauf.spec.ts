import { describe, expect, it } from 'vitest';

/**
 * Hält fest, dass die Unit-Tests unter fester Zeitzone laufen (`vitest-base.config.ts`,
 * Paket 4 V1). Ohne sie hingen datumsabhängige Specs von der Rechnerzeit ab: die CI
 * rechnet in UTC, ein Rechner in Deutschland in Europe/Berlin.
 */
describe('Testlauf', () => {
  it('rechnet in UTC', () => {
    expect(new Date(0).getTimezoneOffset()).toBe(0);
  });
});
