// @vitest-environment jsdom
import { signal } from '@angular/core';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CONFIRM_LEAVE, unsavedChangesGuard } from './unsaved-changes.guard';

/** The guard only reads `dirty`; the router arguments are irrelevant to it. */
function run(dirty: boolean): unknown {
  const guard = unsavedChangesGuard as unknown as (c: { dirty: () => boolean }) => unknown;
  return guard({ dirty: signal(dirty) });
}

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
    expect(confirm).toHaveBeenCalledWith(CONFIRM_LEAVE);
  });

  it('stays on the page when the answer is no', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    // the editor refuses a TAB switch while dirty; leaving the view entirely
    // discarded the same edits silently, which is the larger loss
    expect(run(true)).toBe(false);
  });
});
