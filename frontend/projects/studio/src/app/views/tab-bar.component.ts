/**
 * An ARIA tablist (9-5c).
 *
 * The panels stay with the caller — only the tab strip is shared, because only
 * the strip has semantics worth getting right once: a roving tabindex, arrow
 * keys that move the focus along with the selection, and an `aria-controls`
 * that resolves. The contract is the ids: tab `x` controls `#panel-x` and is
 * itself `#tab-x`, so the caller labels its panel with `aria-labelledby`.
 *
 * Selection follows the arrow keys (automatic activation). That is the pattern
 * the APG recommends when switching panels is cheap; every panel here is
 * already-loaded data — except that the caller may *decline* a switch, which is
 * what `focusActive` below is about.
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, computed, inject,
  input, output,
} from '@angular/core';

export interface TabDef {
  /** Also the id suffix: `#tab-<id>` controls `#panel-<id>`. */
  readonly id: string;
  readonly label: string;
}

@Component({
  selector: 'studio-tab-bar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="tb" role="tablist" [attr.aria-label]="label()">
      @for (tab of tabs(); track tab.id) {
        <button
          type="button"
          role="tab"
          class="tb-tab"
          [id]="'tab-' + tab.id"
          [class.tb-tab--on]="tab.id === active()"
          [attr.aria-selected]="tab.id === active()"
          [attr.aria-controls]="'panel-' + tab.id"
          [attr.tabindex]="tab.id === active() ? 0 : -1"
          (keydown)="onKey($event)"
          (click)="tabChange.emit(tab.id)"
        >{{ tab.label }}</button>
      }
    </div>
  `,
  styleUrl: './tab-bar.component.scss',
})
export class TabBarComponent {
  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly injector = inject(Injector);

  readonly tabs = input.required<readonly TabDef[]>();
  readonly active = input.required<string>();
  /** Names the tablist for screen readers ("Auswertung", not "Tabs"). */
  readonly label = input.required<string>();

  readonly tabChange = output<string>();

  private readonly index = computed(() =>
    this.tabs().findIndex((tab) => tab.id === this.active()));

  onKey(event: KeyboardEvent): void {
    const count = this.tabs().length;
    if (count === 0) return;
    const current = Math.max(this.index(), 0);

    let next: number;
    switch (event.key) {
      case 'ArrowRight': next = (current + 1) % count; break;
      case 'ArrowLeft': next = (current - 1 + count) % count; break;
      case 'Home': next = 0; break;
      case 'End': next = count - 1; break;
      default: return;
    }
    event.preventDefault();
    this.tabChange.emit(this.tabs()[next].id);
    this.focusActive();
  }

  /**
   * The roving tabindex means the selected tab is the only tabbable one, so the
   * focus has to be carried over explicitly or it lands on the body.
   *
   * Focuses whichever tab is active *now* — not the one the key asked for. A
   * caller may decline the switch (the area editor does, while the document has
   * unsaved changes), and then the focus has to stay put: a focused tab that is
   * `aria-selected="false"` announces a panel change that never happened.
   *
   * `afterNextRender`, not a microtask: `active` is an input, so it carries the
   * caller's answer only after the change detection this emit triggers — in a
   * microtask it still reads the value from before the key press.
   */
  private focusActive(): void {
    afterNextRender(() => {
      const index = this.index();
      if (index < 0) return;
      const el = (this.host.nativeElement as HTMLElement)
        .querySelectorAll<HTMLButtonElement>('[role="tab"]')[index];
      el?.focus();
    }, { injector: this.injector });
  }
}
