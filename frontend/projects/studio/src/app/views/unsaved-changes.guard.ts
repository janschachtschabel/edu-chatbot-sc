/**
 * Refuse to leave a view with unsaved changes without asking (9-3, review).
 *
 * The area editor already refuses to switch its own tabs while dirty — but
 * clicking a sidebar link discarded the same edits silently, which made the tab
 * refusal read as arbitrary friction rather than as protection.
 */
import { DestroyRef, Signal, inject } from '@angular/core';
import { CanDeactivateFn } from '@angular/router';

import { StudioLanguageService } from '../i18n/studio-language.service';

export interface HasUnsavedChanges {
  readonly dirty: Signal<boolean>;
}

/** Katalog-Schlüssel der Rückfrage. Kein fertiger Text mehr: eine Konstante
 *  auf Modulebene wäre einmal beim Laden in der damaligen Sprache gebaut und
 *  bliebe darin stehen — derselbe Fall wie der Dokumenttitel in C1-d2. */
export const CONFIRM_LEAVE_KEY = 'guard.confirmLeave';

/** Läuft im Injektionskontext, deshalb ist `inject()` hier erlaubt. */
export const unsavedChangesGuard: CanDeactivateFn<HasUnsavedChanges> = (component) =>
  !component.dirty() || window.confirm(inject(StudioLanguageService).t(CONFIRM_LEAVE_KEY));

/**
 * The same protection for leaving the whole app — the router guard above only
 * sees in-app navigation, not a reload or a closed tab. Call from a component
 * constructor (it uses `inject`).
 */
export function warnOnUnload(isDirty: () => boolean): void {
  const warn = (event: BeforeUnloadEvent): void => {
    if (isDirty()) event.preventDefault();
  };
  window.addEventListener('beforeunload', warn);
  inject(DestroyRef).onDestroy(() => window.removeEventListener('beforeunload', warn));
}
