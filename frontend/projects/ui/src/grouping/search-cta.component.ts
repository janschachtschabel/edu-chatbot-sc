import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import {
  groupedSearchTerm, groupedSearchUrl, ResultGroupsContext, searchCtaTooltip,
} from './result-grouping';
import { ChatMessage } from './message-types';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';

/**
 * Der Absprung aus dem Chat in die vollständige WLO-Suche — mit genau den
 * Filtern, die der Bot für diesen Turn benutzt hat (die URL kommt fertig aus
 * den `queryMetas`, siehe `groupedSearchUrl`).
 *
 * Bis U6b (2026-08-09) stand dieser Block inline in `result-groups`. Seit U2b
 * zeigt der große Modus statt der Gruppen-Boxen das Kachelraster und verlor
 * damit den Knopf — obwohl die Darstellungsform nichts darüber aussagt, ob
 * jemand weitersuchen will. Deshalb hier als eigene Komponente: EIN Block,
 * zwei Verwender (`result-groups` und `card-list`), kein zweiter Wortlaut.
 *
 * Das gerenderte DOM ist unverändert gegenüber dem Inline-Block — die Klassen
 * heißen weiter `result-group--cta`, damit die Bestandstests und die geerbte
 * Optik (ALT chat.component.scss) exakt gleich bleiben. `:host` ist
 * layout-transparent, damit der Anker direkt im Flex-Fluss des Elternteils
 * hängt wie zuvor.
 */
@Component({
  selector: 'boerdi-search-cta',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './search-cta.component.scss',
  template: `
    @if (searchUrl(); as url) {
      <a
        class="result-group result-group--cta"
        [href]="url"
        [attr.target]="searchTargetSelf() ? '_self' : '_blank'"
        rel="noopener noreferrer"
        [attr.title]="searchTooltip()"
      >
        <span class="result-group__cta-icon" [innerHTML]="searchIcon | safeSvg"></span>
        <span class="result-group__cta-text">
          @if (searchTerm(); as q) {
            <strong>{{ ctx().t('groups.cta.withTerm', { term: q }) }}</strong>
          } @else {
            <strong>{{ ctx().t('groups.cta.all') }}</strong>
          }
          <span class="result-group__cta-sub">{{ ctx().t('groups.cta.sub') }}</span>
        </span>
        <span class="result-group__cta-arrow" [innerHTML]="arrowIcon | safeSvg"></span>
      </a>
    }
  `,
})
export class SearchCtaComponent {
  /** Die Nachricht, aus deren `queryMetas` Ziel und Suchbegriff kommen. */
  readonly message = input.required<ChatMessage>();
  /** bsid-Rewrite + Trusted-Host-Prüfung der Shell (ALT `_groupingCtx`). */
  readonly ctx = input.required<ResultGroupsContext>();

  protected readonly searchIcon = ICONS.search;
  protected readonly arrowIcon = ICONS.chevron_right;

  protected readonly searchUrl = computed(() => groupedSearchUrl(this.message(), this.ctx()));
  protected readonly searchTerm = computed(() => groupedSearchTerm(this.message()));
  protected readonly searchTooltip = computed(() => searchCtaTooltip(this.message(), this.ctx()));

  /** ALT `ChatComponent.isTrustedSearchUrl` — `_self` bei same-origin oder
   *  trusted Host, sonst `_blank`. `window.location` = Widget-Host-Seite. */
  protected readonly searchTargetSelf = computed(() => {
    const url = this.searchUrl();
    if (!url) return false;
    try {
      const u = new URL(url, window.location.href);
      if (u.origin === window.location.origin) return true;
      return this.ctx().isTrustedHost(u.hostname.toLowerCase());
    } catch {
      return false;
    }
  });
}
