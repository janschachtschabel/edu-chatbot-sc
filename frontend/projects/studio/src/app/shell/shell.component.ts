/**
 * The studio shell: header, navigation, content outlet (P9-2).
 *
 * ALT held all of this in `page.tsx` together with the 17 views and their state.
 * Here it is chrome only — views arrive through the router outlet.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { NAV_GROUPS } from '../studio-views';
import { StatusIndicatorComponent } from './status-indicator.component';

@Component({
  selector: 'studio-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, StatusIndicatorComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly navGroups = NAV_GROUPS;
  /** Drawer state; only has an effect below the 60rem breakpoint. */
  readonly navOpen = signal(false);
  readonly loggingOut = signal(false);
  /** No password configured — "Abmelden" would be meaningless. */
  readonly gateOpen = this.auth.gateOpen;

  toggleNav(): void {
    this.navOpen.update((open) => !open);
  }

  /** After following a nav link the drawer has done its job. */
  closeNavOnNarrow(): void {
    this.navOpen.set(false);
  }

  async logout(): Promise<void> {
    this.loggingOut.set(true);
    try {
      await this.auth.logout();
      await this.router.navigate(['/login']);
    } finally {
      this.loggingOut.set(false);
    }
  }
}
