/**
 * Login (P9-2). Port of ALT `studio/src/app/login/page.tsx` with four fixes:
 *
 *  1. the input has a real `<label for>` — ALT's only accessible name was the
 *     placeholder, so a screen reader announced "Passwort, Eingabefeld" with no
 *     indication of what the field belonged to;
 *  2. the error sits in a live region, so a failed attempt is announced;
 *  3. distinct messages per cause — ALT showed "Falsches Passwort" for every
 *     non-2xx, so a 500 or a rate-limit read as a typo;
 *  4. the `?from=` redirect is validated (see redirect-target.ts) — ALT assigned
 *     it to `window.location.href` unchecked, an off-site redirect primitive.
 */
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { StudioApiError } from '../core/studio-api-error';
import { AuthService } from './auth.service';
import { safeRedirectTarget } from './redirect-target';

@Component({
  selector: 'studio-login',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly password = signal('');
  readonly busy = signal(false);
  readonly error = signal('');
  /** 503 — no password configured; the form is pointless and stays hidden. */
  readonly disabled = signal(false);
  /** Arrived here from the 401 interceptor rather than by choice. */
  readonly expired = signal(false);

  ngOnInit(): void {
    const params = new URLSearchParams(window.location.search);
    this.expired.set(params.get('abgelaufen') === '1');
    // Someone already signed in (or a studio with the gate off) should not be
    // asked to log in again — refresh() also surfaces the 'disabled' state.
    void this.auth.refresh().then((state) => {
      if (state === 'disabled') this.disabled.set(true);
      else if (state === 'signed-in') void this.goToTarget();
    });
  }

  onPassword(event: Event): void {
    this.password.set((event.target as HTMLInputElement).value);
    // Clear a stale failure as soon as the user starts fixing it, rather than
    // leaving a red message next to a field they have already changed.
    if (this.error()) this.error.set('');
  }

  async submit(event?: Event): Promise<void> {
    event?.preventDefault();
    if (this.busy() || !this.password()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await this.auth.login(this.password());
      await this.goToTarget();
    } catch (err) {
      this.error.set(messageFor(err));
    } finally {
      this.busy.set(false);
    }
  }

  private goToTarget(): Promise<boolean> {
    const from = new URLSearchParams(window.location.search).get('from');
    return this.router.navigateByUrl(safeRedirectTarget(from));
  }
}

function messageFor(err: unknown): string {
  if (!(err instanceof StudioApiError)) return 'Unerwarteter Fehler. Bitte erneut versuchen.';
  switch (err.status) {
    case 401:
      return 'Falsches Passwort.';
    case 429:
      return 'Zu viele Versuche. Bitte eine Minute warten.';
    case 503:
      return 'Das Studio ist nicht eingerichtet (kein Passwort konfiguriert).';
    case 0:
      return 'Backend nicht erreichbar. Läuft der Server?';
    default:
      return `Anmeldung fehlgeschlagen (Fehler ${err.status}).`;
  }
}
