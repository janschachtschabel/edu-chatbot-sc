// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginComponent } from './login.component';

const SESSION = '/studio/api/auth/session';
const LOGIN = '/studio/api/auth/login';

interface Harness {
  fixture: ComponentFixture<LoginComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

/** Drain the microtask queue; zoneless whenStable() does not await our promises. */
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

/**
 * Boot the component with the given query string on the page URL, and answer the
 * ngOnInit session probe with `session`.
 */
async function mount(search = '', session: [object, number] = [{
  authenticated: false, open: false,
}, 200]): Promise<Harness> {
  window.history.replaceState({}, '', `/studio/login${search}`);
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideRouter([{ path: '**', children: [] }]),
      provideHttpClient(),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(LoginComponent);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  const [body, status] = session;
  http.expectOne(SESSION).flush(body, { status, statusText: 'x' });
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

function type({ el }: Harness, value: string): void {
  const input = el.querySelector<HTMLInputElement>('#studio-password');
  if (!input) throw new Error('Passwortfeld fehlt');
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

/** Submit, answer with `status`, and settle — the promise is awaited for real. */
async function submit(h: Harness, status: number, body: object = { detail: 'x' }): Promise<void> {
  const pending = h.fixture.componentInstance.submit();
  h.http.expectOne(LOGIN).flush(body, { status, statusText: 'x' });
  await pending;
  await tick();
  await h.fixture.whenStable();
}

describe('LoginComponent', () => {
  beforeEach(() => {
    TestBed.resetTestingModule();
  });

  it('labels the password field properly', async () => {
    const h = await mount();
    const label = h.el.querySelector<HTMLLabelElement>('label[for="studio-password"]');
    const input = h.el.querySelector<HTMLInputElement>('#studio-password');
    // ALT had no <label> at all — the placeholder was the accessible name
    // (login/page.tsx:61-76), and it disappears as soon as the user types.
    expect(label?.textContent?.trim()).toBe('Passwort');
    expect(input?.getAttribute('autocomplete')).toBe('current-password');
    expect(input?.type).toBe('password');
  });

  it('is submittable with Enter — the native form event is wired', async () => {
    const h = await mount();
    type(h, 'richtig');
    await h.fixture.whenStable();
    // requestSubmit() is what Enter in a single-field form triggers.
    h.el.querySelector<HTMLFormElement>('form')?.requestSubmit();
    h.http.expectOne(LOGIN).flush({ ok: true, open: false });
    await tick();
  });

  it('announces a wrong password in a live region and keeps the typed value', async () => {
    const h = await mount();
    type(h, 'falsch');
    await h.fixture.whenStable();
    await submit(h, 401);

    const error = h.el.querySelector('#pw-error');
    expect(error?.getAttribute('role')).toBe('alert');
    expect(error?.textContent).toContain('Falsches Passwort');
    const input = h.el.querySelector<HTMLInputElement>('#studio-password');
    expect(input?.value).toBe('falsch'); // never cleared on failure
    expect(input?.getAttribute('aria-invalid')).toBe('true');
    expect(input?.getAttribute('aria-describedby')).toBe('pw-error');
  });

  it('distinguishes the failure causes ALT collapsed into one string', async () => {
    for (const [status, expected] of [[429, 'Zu viele Versuche'], [500, 'Fehler 500']] as const) {
      TestBed.resetTestingModule();
      const h = await mount();
      type(h, 'x');
      await h.fixture.whenStable();
      await submit(h, status);
      expect(h.el.querySelector('#pw-error')?.textContent).toContain(expected);
    }
  });

  it('clears a stale error as soon as the user edits the field', async () => {
    const h = await mount();
    type(h, 'falsch');
    await h.fixture.whenStable();
    await submit(h, 401);
    expect(h.el.querySelector('#pw-error')?.textContent).toContain('Falsches');

    type(h, 'falsch2');
    await h.fixture.whenStable();
    expect(h.el.querySelector('#pw-error')?.textContent?.trim()).toBe('');
  });

  it('hides the form entirely when the studio is not configured (503)', async () => {
    const h = await mount('', [{ detail: 'disabled' }, 503]);
    // A form that cannot succeed is worse than an explanation.
    expect(h.el.querySelector('#studio-password')).toBeNull();
    expect(h.el.textContent).toContain('STUDIO_PASSWORD');
  });

  it('redirects to the validated target after a successful login', async () => {
    const h = await mount('?from=%2Fpatterns');
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl');
    type(h, 'richtig');
    await h.fixture.whenStable();
    await submit(h, 200, { ok: true, open: false });

    expect(navigate).toHaveBeenCalledWith('/patterns');
  });

  it('ignores an off-site ?from= — the ALT open redirect', async () => {
    const h = await mount('?from=https%3A%2F%2Fevil.example');
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl');
    type(h, 'richtig');
    await h.fixture.whenStable();
    await submit(h, 200, { ok: true, open: false });

    expect(navigate).toHaveBeenCalledWith('/uebersicht');
  });

  it('explains itself when the session expired mid-work', async () => {
    const h = await mount('?abgelaufen=1&from=%2Fpatterns');
    expect(h.el.querySelector('#pw-hint')?.textContent).toContain('Sitzung ist abgelaufen');
  });

  it('does not ask an already-signed-in user to log in again', async () => {
    window.history.replaceState({}, '', '/studio/login?from=%2Fsessions');
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([{ path: '**', children: [] }]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    const fixture = TestBed.createComponent(LoginComponent);
    const http = TestBed.inject(HttpTestingController);
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl');
    await fixture.whenStable();

    http.expectOne(SESSION).flush({ authenticated: true, open: false });
    await tick();

    expect(navigate).toHaveBeenCalledWith('/sessions');
  });
});
