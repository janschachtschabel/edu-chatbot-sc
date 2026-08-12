import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import { ActionState } from './action-state';
import { StudioApiError } from './studio-api-error';

/** Siehe `async-data.spec.ts`: ein echter Katalog, weil die Frage lautet, was
 *  ein Leser sieht. */
function catalogue(): { i18n: I18n; t: I18n['t'] } {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  return { i18n, t: (key, params) => i18n.t(key, params) };
}

const de = (): I18n['t'] => catalogue().t;

/** A promise plus the handles to settle it from the test. */
function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (err: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('ActionState', () => {
  it('nennt die laufende Aktion beim Namen, damit nur ihr Knopf arbeitet', async () => {
    const state = new ActionState(de());
    const gate = deferred<string>();

    const pending = state.run('backup', () => gate.promise);
    expect(state.isRunning('backup')).toBe(true);
    expect(state.isRunning('restore')).toBe(false);
    expect(state.busy()).toBe(true);

    gate.resolve('Fertig.');
    await pending;
    expect(state.isRunning('backup')).toBe(false);
    expect(state.busy()).toBe(false);
  });

  it('zeigt die Erfolgsmeldung der Aktion', async () => {
    const state = new ActionState(de());
    await expect(state.run('create', async () => '3 Bereiche gesichert.')).resolves.toBe(true);
    expect(state.message()).toEqual({ kind: 'ok', text: '3 Bereiche gesichert.' });
  });

  it('zeigt den Satz des Backends, nicht die Transport-Hülle', async () => {
    const state = new ActionState(de());
    const failed = state.run('create', () =>
      Promise.reject(new StudioApiError(400, 'Snapshot-Limit erreicht (max 50).', '/x')));

    await expect(failed).resolves.toBe(false);
    expect(state.message()).toEqual({
      kind: 'error', text: 'Snapshot-Limit erreicht (max 50).',
    });
    // A failed action must not leave the page looking busy.
    expect(state.busy()).toBe(false);
  });

  it('meldet einen Fehler ohne Backend-Satz in der aktiven Sprache', async () => {
    // C1-d4a. „Sicherung" und „Werksstand" sind seit C1-d3b übersetzt, ihre
    // Fehlermeldung kam bis hierher aber aus `describeApiError` und war
    // deutsch — ein deutscher Satz mitten auf einer englischen Seite.
    const { i18n, t } = catalogue();
    i18n.setLocale('en');
    const state = new ActionState(t);

    await state.run('create', () => Promise.reject(new StudioApiError(0, '', '/x')));
    expect(state.message()).toEqual({ kind: 'error', text: 'Backend unreachable.' });
  });

  it('räumt die alte Meldung ab, sobald die nächste Aktion startet', async () => {
    const state = new ActionState(de());
    await state.run('create', async () => 'Snapshot angelegt.');

    const gate = deferred<string>();
    const pending = state.run('delete', () => gate.promise);
    // Otherwise "Snapshot angelegt." would still stand while a delete runs, and
    // would sit next to its failure afterwards.
    expect(state.message()).toBeNull();

    gate.reject(new StudioApiError(404, 'Snapshot not found', '/x'));
    await pending;
    expect(state.message()).toEqual({ kind: 'error', text: 'Snapshot not found' });
  });
});
