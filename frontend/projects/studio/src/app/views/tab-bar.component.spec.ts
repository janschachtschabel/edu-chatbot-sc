// @vitest-environment jsdom
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { TabBarComponent, type TabDef } from './tab-bar.component';

const TABS: readonly TabDef[] = [
  { id: 'eins', label: 'Eins' },
  { id: 'zwei', label: 'Zwei' },
  { id: 'drei', label: 'Drei' },
];

@Component({
  selector: 'studio-tab-host',
  imports: [TabBarComponent],
  template: `
    <studio-tab-bar
      [tabs]="tabs"
      [active]="active()"
      label="Auswertung"
      (tabChange)="active.set($event)"
    />
    @for (tab of tabs; track tab.id) {
      <section [id]="'panel-' + tab.id" role="tabpanel" [attr.aria-labelledby]="'tab-' + tab.id"
               [hidden]="active() !== tab.id">{{ tab.label }}-Inhalt</section>
    }
  `,
})
class HostComponent {
  readonly tabs = TABS;
  readonly active = signal('eins');
}

let fixture: ComponentFixture<HostComponent>;
let el: HTMLElement;

function tabs(): HTMLButtonElement[] {
  return Array.from(el.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
}

async function press(key: string): Promise<void> {
  (document.activeElement as HTMLElement).dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true }),
  );
  await fixture.whenStable();
}

describe('TabBarComponent', () => {
  beforeEach(async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(HostComponent);
    el = fixture.nativeElement as HTMLElement;
    document.body.appendChild(el); // focus() only works for a connected element
    await fixture.whenStable();
  });

  it('names the tablist and marks exactly one tab selected', () => {
    expect(el.querySelector('[role="tablist"]')!.getAttribute('aria-label')).toBe('Auswertung');
    const selected = tabs().filter((t) => t.getAttribute('aria-selected') === 'true');
    expect(selected).toHaveLength(1);
    expect(selected[0].textContent).toContain('Eins');
  });

  it('points every tab at a panel that exists', () => {
    for (const tab of tabs()) {
      const id = tab.getAttribute('aria-controls')!;
      // An aria-controls pointing nowhere is the defect this component exists
      // to prevent; the panels live in the caller, so the contract is the ids.
      expect(el.querySelector(`#${id}`)).not.toBeNull();
    }
  });

  it('keeps only the selected tab in the tab sequence (roving tabindex)', () => {
    expect(tabs().map((t) => t.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
  });

  it('selects with the arrow keys and takes the focus along', async () => {
    tabs()[0].focus();
    await press('ArrowRight');

    expect(fixture.componentInstance.active()).toBe('zwei');
    expect(document.activeElement).toBe(tabs()[1]);
    expect(tabs().map((t) => t.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
  });

  it('wraps around at both ends', async () => {
    tabs()[0].focus();
    await press('ArrowLeft');
    expect(fixture.componentInstance.active()).toBe('drei');

    await press('ArrowRight');
    expect(fixture.componentInstance.active()).toBe('eins');
  });

  it('jumps to the first and last tab with Home and End', async () => {
    tabs()[0].focus();
    await press('End');
    expect(fixture.componentInstance.active()).toBe('drei');

    await press('Home');
    expect(fixture.componentInstance.active()).toBe('eins');
  });

  it('leaves other keys to the browser', async () => {
    tabs()[0].focus();
    await press('Tab');
    expect(fixture.componentInstance.active()).toBe('eins');
  });

  it('selects on click', async () => {
    tabs()[2].click();
    await fixture.whenStable();
    expect(fixture.componentInstance.active()).toBe('drei');
  });
});

/**
 * A caller may decline the switch — the area editor refuses while the document
 * has unsaved changes (B4). The tab bar must then leave the focus where it is:
 * a focused tab that is `aria-selected="false"` tells a screen reader the panel
 * changed when it did not.
 */
@Component({
  selector: 'studio-tab-host-refusing',
  imports: [TabBarComponent],
  template: `
    <studio-tab-bar [tabs]="tabs" [active]="active()" label="Ansicht" (tabChange)="refuse()" />
  `,
})
class RefusingHostComponent {
  readonly tabs = TABS;
  readonly active = signal('eins');
  asked = 0;
  refuse(): void {
    this.asked += 1;
  }
}

describe('TabBarComponent — der Aufrufer lehnt ab', () => {
  let refusing: ComponentFixture<RefusingHostComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    refusing = TestBed.createComponent(RefusingHostComponent);
    host = refusing.nativeElement as HTMLElement;
    document.body.appendChild(host);
    await refusing.whenStable();
  });

  it('keeps the focus on the selected tab when the change is refused', async () => {
    const buttons = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    buttons[0].focus();

    buttons[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    await refusing.whenStable();

    expect(refusing.componentInstance.asked).toBe(1); // the caller was asked …
    expect(refusing.componentInstance.active()).toBe('eins'); // … and said no
    expect(document.activeElement).toBe(buttons[0]);
  });
});
