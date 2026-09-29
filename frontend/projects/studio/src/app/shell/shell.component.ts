/**
 * The studio shell: header, navigation, content outlet (P9-2).
 *
 * ALT held all of this in `page.tsx` together with the 17 views and their state.
 * Here it is chrome only — views arrive through the router outlet.
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, inject, signal, viewChild,
} from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { EffectsApi } from '../core/effects-api.service';
import { LanguageSwitcherComponent } from '../i18n/language-switcher.component';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { NAV_GROUPS } from '../studio-views';
import { BackupToolsComponent } from './backup-tools.component';
import { StatusIndicatorComponent } from './status-indicator.component';

@Component({
  selector: 'studio-shell',
  imports: [
    RouterLink, RouterLinkActive, RouterOutlet,
    StatusIndicatorComponent, LanguageSwitcherComponent, BackupToolsComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  /** Übersetzen im Template (C1-d1). Liest das Sprach-Signal im Aufruf, also
   *  rendert die Hülle beim Umschalten von selbst neu — seit C1-d2 auch die
   *  Beschriftungen der Navigation, die nur noch Katalog-Schlüssel liefert. */
  protected readonly t = inject(StudioLanguageService).t;

  readonly navGroups = NAV_GROUPS;
  /** Drawer state; only has an effect below the 60rem breakpoint. */
  readonly navOpen = signal(false);
  readonly loggingOut = signal(false);
  /** No password configured — "Abmelden" would be meaningless. */
  readonly gateOpen = this.auth.gateOpen;

  /** The `<main>` landmark — where focus goes after the router swaps the view. */
  private readonly mainRef = viewChild<ElementRef<HTMLElement>>('main');
  private readonly backupTools = viewChild(BackupToolsComponent);
  private readonly effects = inject(EffectsApi);
  /** The first activation is the page loading, not a navigation the user made. */
  private viewActivatedOnce = false;

  /**
   * Move focus into the content region on a route change.
   *
   * Without it the focus stays on the sidebar link a keyboard or screen-reader
   * user just activated while the view swaps underneath them: nothing is
   * announced, and the next Tab continues through the navigation rather than
   * through the page they asked for. The skip link covers WCAG 2.4.1, so this
   * closes the remaining best-practice gap (audit 2026-08-12).
   *
   * Driven by the outlet's `(activate)` output rather than `router.events`
   * on purpose: the whole frontend holds zero RxJS subscriptions, and one
   * focus hook does not earn the first one.
   */
  onViewActivated(): void {
    // Auch beim ersten Laden: die Wirkungs-Zuordnung (ST-5) samt Vorgabe-
    // Maschine frisch, die Meldung der Kopfzeilen-Werkzeuge (ST-9) weg.
    void this.effects.refresh();
    this.backupTools()?.dismiss();
    if (!this.viewActivatedOnce) {
      this.viewActivatedOnce = true;
      return;
    }
    this.mainRef()?.nativeElement.focus();
  }

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
