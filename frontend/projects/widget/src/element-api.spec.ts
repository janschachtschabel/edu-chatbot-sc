import { describe, expect, it } from 'vitest';

import { FORWARDED_METHODS, NgElementLike, componentOf, patchElementApi } from './element-api';

/**
 * Element-JS-API (8-5h). ALT hatte für den Methoden-Patch keinen Test (der lag
 * als Top-Level-Code in `main.ts`); hier ist er eine eigene Regel und damit
 * pinnbar — inklusive des Falls, den eine Host-Seite garantiert irgendwann
 * trifft: API-Aufruf, bevor das Element aufgewertet ist.
 */
class FakeElement implements NgElementLike {
  _ngElementStrategy?: { componentRef?: { instance?: Record<string, unknown> } | null };
}

function upgraded(instance: Record<string, unknown>): FakeElement {
  const el = new FakeElement();
  el._ngElementStrategy = { componentRef: { instance } };
  return el;
}

describe('element-api', () => {
  it('bietet beide Kontext-Wege an: ergänzen UND ersetzen', () => {
    // Befund der Plugin-Entwickler (2026-08-14): eine Seitenleiste kann den
    // Kontext nicht per Attribut nachreichen (nur in `ngOnInit` gelesen) und
    // auch nicht per URL-Wächter (die Adresse der Leiste ändert sich nie).
    // `updateContext` MERGT — ein Host aus der Erkennung und die IDs des
    // vorigen Tabs überleben damit jeden Wechsel. Der ersetzende Weg existierte
    // im Code, war aber von außen nicht erreichbar.
    expect(FORWARDED_METHODS).toContain('updateContext');
    expect(FORWARDED_METHODS).toContain('replaceContext');
  });

  it('reicht den Auftrag von außen durch', () => {
    // Nutzer-Entscheid 2026-08-14: ein Gastgeber soll den Chat auf ein Thema
    // starten können. Bis dahin gab es dafür nur `/api/agent` — also einen Weg
    // OHNE Chat-Fenster, und genau das war die Lücke.
    expect(FORWARDED_METHODS).toContain('startTask');
  });

  it('reicht alle §5.5-Methoden an die Komponenten-Instanz durch', () => {
    patchElementApi(FakeElement.prototype);
    const calls: string[] = [];
    const instance: Record<string, unknown> = {};
    for (const name of FORWARDED_METHODS) {
      instance[name] = (...args: unknown[]) => { calls.push(`${name}(${args.join(',')})`); return name; };
    }
    const el = upgraded(instance) as FakeElement & Record<string, (...a: unknown[]) => unknown>;

    for (const name of FORWARDED_METHODS) {
      expect(el[name]()).toBe(name);
    }
    expect(calls).toEqual(FORWARDED_METHODS.map(n => `${n}()`));
  });

  it('reicht Argumente durch und behält `this` = Komponenten-Instanz', () => {
    patchElementApi(FakeElement.prototype);
    const instance = {
      seen: null as unknown,
      updateContext(ctx: unknown) { (this as { seen: unknown }).seen = ctx; },
    };
    const el = upgraded(instance as unknown as Record<string, unknown>) as FakeElement & {
      updateContext: (c: unknown) => void;
    };
    el.updateContext({ thema: 'eiszeit' });
    expect(instance.seen).toEqual({ thema: 'eiszeit' });
  });

  it('vor dem Upgrade (keine Instanz) ist jeder Aufruf ein No-Op, keine Exception', () => {
    patchElementApi(FakeElement.prototype);
    const el = new FakeElement() as FakeElement & Record<string, () => unknown>;
    for (const name of FORWARDED_METHODS) {
      expect(() => el[name]()).not.toThrow();
      expect(el[name]()).toBeUndefined();
    }
    // Auch ein halb aufgebauter Strategy-Zustand darf nicht werfen.
    el._ngElementStrategy = { componentRef: null };
    expect(el['openChatbot']()).toBeUndefined();
    expect(componentOf(el)).toBeUndefined();
  });

  it('überschreibt keine bereits vorhandene Methode gleichen Namens', () => {
    class WithOwn implements NgElementLike {
      _ngElementStrategy?: { componentRef?: { instance?: Record<string, unknown> } | null };
      openChatbot(): string { return 'eigene'; }
    }
    patchElementApi(WithOwn.prototype);
    expect(new WithOwn().openChatbot()).toBe('eigene');
  });
});
