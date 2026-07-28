/**
 * Catches a 401 that happens AFTER the guard let us in (P9-2).
 *
 * The auth cookie lives 30 days, but rotating STUDIO_PASSWORD invalidates every
 * cookie immediately (the token is a pure function of the password — see
 * backend api/studio_auth.py). Without this, an editor mid-edit would just see
 * every save fail with "401" and no way to understand why.
 *
 * The login request itself is excluded: a wrong password is also a 401, and
 * bouncing the login page to the login page would wipe the typed value and the
 * error message.
 */
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { tap } from 'rxjs';

import { SessionStore } from '../auth/session-store';

const LOGIN_PATH = '/studio/api/auth/login';

export const authErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const session = inject(SessionStore);

  return next(req).pipe(
    tap({
      error: (err: unknown) => {
        if (!(err instanceof HttpErrorResponse) || err.status !== 401) return;
        if (req.url.startsWith(LOGIN_PATH)) return;
        session.markSignedOut();
        void router.navigate(['/login'], {
          queryParams: { from: router.url, abgelaufen: 1 },
        });
      },
    }),
  );
};
