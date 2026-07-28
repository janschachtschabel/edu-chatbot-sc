/**
 * Route guard for everything inside the shell (P9-2).
 *
 * Asks the BFF once and caches the answer in AuthService, so navigating between
 * views does not re-check on every click. A cookie that expires mid-session is
 * caught by the 401 interceptor instead (core/auth-error.interceptor.ts) — the
 * guard covers entry, the interceptor covers drift.
 *
 * `disabled` (503, no STUDIO_PASSWORD) also routes to /login, which then shows
 * the "studio not configured" state rather than a form that cannot succeed.
 */
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const current = auth.state() === 'unknown' ? await auth.refresh() : auth.state();
  if (current === 'signed-in') return true;

  // `from` carries the URL the user actually wanted, so login can return there.
  return router.createUrlTree(['/login'], { queryParams: { from: state.url } });
};
