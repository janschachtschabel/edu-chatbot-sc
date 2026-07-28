// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { AsyncData } from './async-data';
import { StudioApiError } from './studio-api-error';

/** A fetch whose resolution this test controls. */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void } {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

describe('AsyncData', () => {
  it('starts empty and idle — nothing is fetched until asked', () => {
    let calls = 0;
    const data = new AsyncData(async () => { calls += 1; return [1]; });
    expect(data.value()).toBeNull();
    expect(data.loading()).toBe(false);
    expect(data.error()).toBe('');
    expect(calls).toBe(0);
  });

  it('publishes the result and clears the loading flag', async () => {
    const data = new AsyncData(async () => ['a']);
    const done = data.reload();
    expect(data.loading()).toBe(true);
    await done;
    expect(data.value()).toEqual(['a']);
    expect(data.loading()).toBe(false);
    expect(data.error()).toBe('');
  });

  it('keeps the last good value when a refresh fails', async () => {
    // A table that empties itself on a failed refresh tells the reader the data
    // is gone. It is not — the request is.
    const fail = { now: false };
    const data = new AsyncData(async () => {
      if (fail.now) throw new StudioApiError(500, 'Serverfehler', '/x');
      return ['alt'];
    });
    await data.reload();
    fail.now = true;
    await data.reload();

    expect(data.value()).toEqual(['alt']);
    expect(data.error()).toBe('Serverfehler');
    expect(data.loading()).toBe(false);
  });

  it('clears a previous error once a reload succeeds', async () => {
    const fail = { now: true };
    const data = new AsyncData(async () => {
      if (fail.now) throw new StudioApiError(500, 'kaputt', '/x');
      return ['ok'];
    });
    await data.reload();
    expect(data.error()).toBe('kaputt');

    fail.now = false;
    await data.reload();
    expect(data.error()).toBe('');
    expect(data.value()).toEqual(['ok']);
  });

  it('lets the NEWER request win, whatever order the answers arrive in', async () => {
    // Double-click "Aktualisieren" and the first response can land last. Without
    // the guard the view then shows data it already replaced.
    const first = deferred<string[]>();
    const second = deferred<string[]>();
    const queue = [first.promise, second.promise];
    const data = new AsyncData(() => queue.shift() as Promise<string[]>);

    const a = data.reload();
    const b = data.reload();
    second.resolve(['neu']);
    await b;
    first.resolve(['alt']);
    await a;

    expect(data.value()).toEqual(['neu']);
    expect(data.loading()).toBe(false);
  });

  it('lets a newer FAILURE not be overwritten by an older success either', async () => {
    const first = deferred<string[]>();
    const second = deferred<string[]>();
    const queue = [first.promise, second.promise];
    const data = new AsyncData(() => queue.shift() as Promise<string[]>);

    const a = data.reload();
    const b = data.reload();
    second.reject(new StudioApiError(0, 'Backend nicht erreichbar.', '/x'));
    await b;
    first.resolve(['alt']);
    await a;

    expect(data.value()).toBeNull();
    expect(data.error()).toBe('Backend nicht erreichbar.');
  });

  it('describes an unexpected throw without leaking its internals', async () => {
    const data = new AsyncData(async () => { throw new TypeError('x.y is not a function'); });
    await data.reload();
    expect(data.error()).toBe('Unerwarteter Fehler.');
  });

  it('reports emptiness only once something was actually loaded', async () => {
    const data = new AsyncData<string[]>(async () => []);
    expect(data.isEmpty()).toBe(false); // nothing loaded yet is not "empty"
    await data.reload();
    expect(data.isEmpty()).toBe(true);
  });

  it('treats a non-list payload as never empty', async () => {
    const data = new AsyncData(async () => ({ total: 0 }));
    await data.reload();
    expect(data.isEmpty()).toBe(false);
  });

  it('survives being reloaded while a reload is already running', async () => {
    const gate = deferred<string[]>();
    const data = new AsyncData(() => gate.promise);
    const a = data.reload();
    const b = data.reload();
    gate.resolve(['x']);
    await Promise.all([a, b]);
    await tick();
    expect(data.loading()).toBe(false);
  });
});
