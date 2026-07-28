import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DUPLICATE_FLAG, enforceSingleInstance, watchSingleInstance } from './single-instance';

/**
 * Doppel-Instanz-Guard (8-5h-Nachtrag). ALT hatte dafür keinen Test — der Code
 * lag als Top-Level-Block in `widget-main.ts`. Hier ist er eine eigene Regel und
 * damit pinnbar, inklusive des Falls, der ihn überhaupt nötig gemacht hat:
 * ein zweites Element, das erst NACH dem Bootstrap ins DOM kommt.
 *
 * `x-boerdi-test` statt `boerdi-chat` als Elementname: der Test soll keine
 * echte Custom-Element-Definition brauchen.
 */
const NAME = 'x-boerdi-test';

function add(): HTMLElement {
  const el = document.createElement(NAME);
  document.body.appendChild(el);
  return el;
}

describe('enforceSingleInstance', () => {
  beforeEach(() => { document.body.innerHTML = ''; vi.spyOn(console, 'warn').mockImplementation(() => {}); });
  afterEach(() => vi.restoreAllMocks());

  it('eine einzelne Instanz bleibt unangetastet', () => {
    const el = add();
    expect(enforceSingleInstance(NAME)).toBe(0);
    expect(el.style.display).toBe('');
  });

  it('blendet jedes zweite und weitere Element aus und warnt', () => {
    const first = add(), second = add(), third = add();
    expect(enforceSingleInstance(NAME)).toBe(2);
    expect(first.style.display).toBe('');
    expect(second.style.display).toBe('none');
    expect(third.style.display).toBe('none');
    expect(second.dataset[DUPLICATE_FLAG]).toBe('1');
    expect(console.warn).toHaveBeenCalledTimes(2);
  });

  it('ist idempotent — der Observer feuert pro Mutation, warnt aber nur einmal', () => {
    add(); add();
    expect(enforceSingleInstance(NAME)).toBe(1);
    expect(enforceSingleInstance(NAME)).toBe(0);
    expect(console.warn).toHaveBeenCalledTimes(1);
  });
});

describe('watchSingleInstance', () => {
  beforeEach(() => { document.body.innerHTML = ''; vi.spyOn(console, 'warn').mockImplementation(() => {}); });
  afterEach(() => vi.restoreAllMocks());

  it('fängt ein NACH dem Bootstrap eingefügtes Duplikat (WordPress-Fall)', async () => {
    add();
    const mo = watchSingleInstance(NAME);
    const late = add();          // z.B. per AJAX nachgeladener Layout-Block
    await new Promise(r => setTimeout(r));   // MutationObserver ist ein Microtask
    expect(late.style.display).toBe('none');
    mo?.disconnect();
  });
});
