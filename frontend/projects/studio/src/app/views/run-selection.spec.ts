import { describe, expect, it } from 'vitest';

import { MAX_COMPARE, RunSelection } from './run-selection';

describe('RunSelection (ST-7c)', () => {
  it('merkt sich gewählte Läufe in der Reihenfolge der Wahl', () => {
    const wahl = new RunSelection();
    wahl.toggle('r2');
    wahl.toggle('r1');
    expect(wahl.ids()).toEqual(['r2', 'r1']);
    expect(wahl.has('r1')).toBe(true);
    expect(wahl.count()).toBe(2);
  });

  it('nimmt einen Lauf beim zweiten Klick wieder heraus', () => {
    const wahl = new RunSelection();
    wahl.toggle('r1');
    wahl.toggle('r1');
    expect(wahl.ids()).toEqual([]);
  });

  it('bleibt unter der Obergrenze des Servers', () => {
    const wahl = new RunSelection();
    for (let i = 0; i < MAX_COMPARE + 3; i++) wahl.toggle(`r${i}`);
    expect(wahl.count()).toBe(MAX_COMPARE);
    expect(wahl.full()).toBe(true);
    // Abwählen geht immer.
    wahl.toggle('r0');
    expect(wahl.count()).toBe(MAX_COMPARE - 1);
  });

  it('vergisst gelöschte Läufe und leert sich auf Zuruf', () => {
    const wahl = new RunSelection();
    wahl.toggle('r1');
    wahl.toggle('r2');
    wahl.remove('r1');
    expect(wahl.ids()).toEqual(['r2']);
    wahl.clear();
    expect(wahl.count()).toBe(0);
  });
});
