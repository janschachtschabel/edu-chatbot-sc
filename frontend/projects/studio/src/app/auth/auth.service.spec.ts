// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { AuthService } from './auth.service';

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  it('starts in "unknown" — nothing is assumed before asking', () => {
    expect(auth.state()).toBe('unknown');
    expect(auth.signedIn()).toBe(false);
  });

  it('becomes signed-in on an authenticated session', async () => {
    const done = auth.refresh();
    http.expectOne('/studio/api/auth/session').flush({ authenticated: true, open: false });
    expect(await done).toBe('signed-in');
    expect(auth.signedIn()).toBe(true);
    expect(auth.gateOpen()).toBe(false);
  });

  it('reports a 503 as "disabled", NOT as "signed-out"', async () => {
    // The difference decides whether the login form is worth showing at all: a
    // studio without STUDIO_PASSWORD is closed fail-closed, so no password works.
    const done = auth.refresh();
    http.expectOne('/studio/api/auth/session')
      .flush({ detail: 'Studio is disabled' }, { status: 503, statusText: 'Service Unavailable' });
    expect(await done).toBe('disabled');
  });

  it('reports a 401 as signed-out', async () => {
    const done = auth.refresh();
    http.expectOne('/studio/api/auth/session')
      .flush({ detail: 'Studio login required' }, { status: 401, statusText: 'Unauthorized' });
    expect(await done).toBe('signed-out');
  });

  it('remembers the open gate so the shell can hide "Abmelden"', async () => {
    const done = auth.refresh();
    http.expectOne('/studio/api/auth/session').flush({ authenticated: true, open: true });
    await done;
    expect(auth.gateOpen()).toBe(true);
  });

  it('signs in and propagates the failure otherwise', async () => {
    const ok = auth.login('richtig');
    const req = http.expectOne('/studio/api/auth/login');
    expect(req.request.body).toEqual({ password: 'richtig' });
    req.flush({ ok: true, open: false });
    await ok;
    expect(auth.signedIn()).toBe(true);

    const bad = auth.login('falsch');
    http.expectOne('/studio/api/auth/login')
      .flush({ detail: 'Wrong password' }, { status: 401, statusText: 'Unauthorized' });
    await expect(bad).rejects.toThrow();
  });

  it('drops the cached state even when logout itself fails', async () => {
    const signedIn = auth.refresh();
    http.expectOne('/studio/api/auth/session').flush({ authenticated: true, open: false });
    await signedIn;

    const done = auth.logout();
    http.expectOne('/studio/api/auth/logout').error(new ProgressEvent('error'));
    await done.catch(() => undefined);
    // Otherwise the guard would keep waving through a session the user ended.
    expect(auth.state()).toBe('signed-out');
  });
});
