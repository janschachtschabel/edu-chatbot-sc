// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService,
} from '../i18n/studio-language.service';
import { CONFIRM_LEAVE_KEY, unsavedChangesGuard } from './unsaved-changes.guard';

/**
 * The guard only reads `dirty`; the router arguments are irrelevant to it.
 *
 * It DOES need an injection context, though: since C1-d3a it translates the
 * question rather than reading a module constant, and a constant would have
 * frozen in whichever language was active when the module loaded. Angular runs
 * a `CanDeactivateFn` in an injection context, so `inject()` is legal there —
 * and running it outside one, as this helper used to, no longer works.
 */
function run(dirty: boolean): unknown {
  const guard = unsavedChangesGuard as unknown as (c: { dirty: () => boolean }) => unknown;
  return TestBed.runInInjectionContext(() => guard({ dirty: signal(dirty) }));
}

beforeEach(() => {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
});

afterEach(() => vi.restoreAllMocks());

describe('unsavedChangesGuard', () => {
  it('lets a clean view go without bothering anyone', () => {
    const confirm = vi.spyOn(window, 'confirm');
    expect(run(false)).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
  });

  it('asks before discarding unsaved changes', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    expect(run(true)).toBe(true);
    expect(confirm).toHaveBeenCalledWith(TestBed.inject(StudioLanguageService).t(CONFIRM_LEAVE_KEY));
  });

  it('stellt die Rückfrage in der aktiven Sprache', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    TestBed.inject(StudioLanguageService).toggle();
    run(true);
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('unsaved changes'));
  });

  it('stays on the page when the answer is no', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    // the editor refuses a TAB switch while dirty; leaving the view entirely
    // discarded the same edits silently, which is the larger loss
    expect(run(true)).toBe(false);
  });
});
