// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import {
  Component,
  provideZonelessChangeDetection,
} from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { Router, provideRouter } from "@angular/router";
import { beforeEach, describe, expect, it } from "vitest";

import { SessionStore } from "../auth/session-store";
import {
  STUDIO_LOCALE_STORAGE_KEY,
  StudioLanguageService,
} from "../i18n/studio-language.service";
import { STUDIO_VIEWS } from "../studio-views";
import { ShellComponent } from "./shell.component";

/**
 * The a11y properties asserted here are all things ALT lacked (page.tsx:350-446):
 * nav items were `<button onClick>` with no href and no `aria-current`, there was
 * no skip link, and the status dot was an empty span with no live region.
 */
/** Stands in for a real view: the outlet needs something to activate. */
@Component({
  standalone: true,
  template: "<p>Ansicht</p>",
})
class StubViewComponent {}

describe("ShellComponent", () => {
  let fixture: ComponentFixture<ShellComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.resetTestingModule();
    // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund), und der
    // Browser ist im Studio die zweitstärkste Quelle. Ohne diese Zeile stünde
    // die Hülle hier auf Englisch und jede deutsche Zusage unten schlüge fehl.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        // Real routes for every slug, so nav clicks actually navigate — that is
        // what makes routerLinkActive/aria-current observable here. Each one
        // carries a stub component: a componentless route activates nothing in
        // the outlet, so `(activate)` — and with it the focus move on a view
        // change — would never fire.
        provideRouter(
          STUDIO_VIEWS.map((v) => ({
            path: v.slug,
            component: StubViewComponent,
          })),
        ),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    fixture = TestBed.createComponent(ShellComponent);
    http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it("renders every view as a real link, not a button", () => {
    // `Array.from`, not spread: the workspace tsconfig lib is ES2022+dom without
    // dom.iterable, so a NodeList is not iterable here.
    const links = Array.from(
      el.querySelectorAll<HTMLAnchorElement>(".nav-item"),
    );
    expect(links).toHaveLength(STUDIO_VIEWS.length);
    for (const link of links) {
      // A real href is what makes middle-click, open-in-new-tab and the browser
      // status bar work — ALT's buttons had none.
      expect(link.getAttribute("href")).toMatch(/^\/[a-z-]+$/);
    }
  });

  it("exposes the grouped structure with headings inside a labelled nav", () => {
    const nav = el.querySelector("nav");
    expect(nav?.getAttribute("aria-label")).toBe("Konfigurationsbereiche");
    const titles = Array.from(el.querySelectorAll(".nav-group-title"), (h) =>
      h.textContent?.trim(),
    );
    expect(titles).toEqual(["Konfiguration", "Auswertung", "System"]);
    // Lists, so a screen reader announces "3 of 16".
    expect(el.querySelectorAll(".nav-list").length).toBe(4);
  });

  it("has a skip link that targets the main landmark", () => {
    const skip = el.querySelector<HTMLAnchorElement>("a.skip");
    expect(skip?.textContent?.trim()).toBe("Zum Inhalt springen");
    const target = skip?.getAttribute("href")?.replace("#", "");
    expect(el.querySelector(`#${target}`)?.tagName).toBe("MAIN");
  });

  it("marks no nav item as current while no view is open", () => {
    expect(el.querySelector('[aria-current="page"]')).toBeNull();
  });

  it("announces the backend status in a live region", () => {
    const status = el.querySelector('[role="status"]');
    expect(status).not.toBeNull();
    // Third state: neither "Verbunden" nor "Offline" before the first answer.
    expect(status?.textContent).toContain("Verbindung wird geprüft");
    http.expectOne("/studio/api/health").flush({ status: "ok" });
  });

  it("toggles the narrow-screen drawer with an honest aria-expanded", async () => {
    const toggle = el.querySelector<HTMLButtonElement>(".nav-toggle");
    expect(toggle?.getAttribute("aria-expanded")).toBe("false");
    expect(toggle?.getAttribute("aria-controls")).toBe("studio-nav");

    toggle?.click();
    await fixture.whenStable();
    expect(el.querySelector(".nav-toggle")?.getAttribute("aria-expanded")).toBe(
      "true",
    );

    // Following a link closes it again, so the content is not left behind a drawer.
    el.querySelector<HTMLAnchorElement>(".nav-item")?.click();
    await fixture.whenStable();
    expect(el.querySelector(".nav-toggle")?.getAttribute("aria-expanded")).toBe(
      "false",
    );
  });

  it("marks the open view with aria-current, not just a CSS class", async () => {
    el.querySelector<HTMLAnchorElement>(".nav-item")?.click();
    await fixture.whenStable();

    const current = Array.from(el.querySelectorAll('[aria-current="page"]'));
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toContain(
      TestBed.inject(StudioLanguageService).t(STUDIO_VIEWS[0].labelKey),
    );
    // ALT conveyed the active state through the `active` class alone, so a
    // screen reader had no way to know where it was.
    expect(current[0].classList.contains("nav-item--active")).toBe(true);
  });

  it('hides "Abmelden" when no password guards the studio', async () => {
    // `.logout`, nicht `.header-tools button`: seit C1-d1 steht der
    // Sprach-Umschalter als erster Knopf in denselben Werkzeugen.
    expect(el.querySelector(".header-tools .logout")?.textContent).toContain(
      "Abmelden",
    );

    TestBed.inject(SessionStore).set("signed-in", true);
    await fixture.whenStable();
    // A logout button that cannot log anyone out is worse than none.
    expect(el.querySelector(".header-tools .logout")).toBeNull();
  });

  it("makes the brand a link — ALT put the click handler on the <h1>", () => {
    const brand = el.querySelector("h1.brand a");
    expect(brand?.getAttribute("href")).toBe("/");
  });

  it("trägt den Sprach-Umschalter in der Kopfzeile — auch ohne Passwort-Gate", async () => {
    // Er darf NICHT im `@if (!gateOpen())`-Zweig stehen: ein Studio ohne
    // Passwort hätte sonst gar keine Sprachwahl.
    expect(
      el.querySelector(".header-tools studio-language-switcher"),
    ).not.toBeNull();

    TestBed.inject(SessionStore).set("signed-in", true);
    await fixture.whenStable();
    expect(
      el.querySelector(".header-tools studio-language-switcher"),
    ).not.toBeNull();
  });

  it("holt die Texte der Hülle aus dem Katalog, nicht aus dem Markup", async () => {
    TestBed.inject(StudioLanguageService).toggle();
    await fixture.whenStable();

    const holen = (sel: string) => el.querySelector(sel)?.textContent?.trim();
    expect(holen("a.skip")).toBe("Skip to content");
    expect(holen(".nav-toggle")).toBe("Navigation");
    expect(holen(".header-tools .logout")).toBe("Sign out");
    expect(el.querySelector("nav")?.getAttribute("aria-label")).toBe(
      "Configuration areas",
    );
  });

  it("übersetzt auch die Navigation selbst — nicht nur den Rahmen (C1-d2)", async () => {
    expect(el.querySelector(".nav-label")?.textContent?.trim()).toBe(
      "Übersicht",
    );

    TestBed.inject(StudioLanguageService).toggle();
    await fixture.whenStable();

    expect(el.querySelector(".nav-label")?.textContent?.trim()).toBe(
      "Overview",
    );
    expect(el.querySelector(".nav-desc")?.textContent?.trim()).toBe(
      "Start, architecture & status",
    );
    const titel = Array.from(el.querySelectorAll(".nav-group-title"), (h) =>
      h.textContent?.trim(),
    );
    expect(titel).toEqual(["Configuration", "Monitoring", "System"]);
  });

  it("zieht den Fokus beim Ansichtswechsel in den Inhaltsbereich (Audit 2026-08-12)", async () => {
    // Ohne diesen Umzug bleibt der Fokus auf dem gerade aktivierten
    // Seitenleisten-Link, während die Ansicht darunter wechselt: Tastatur- und
    // Screenreader-Nutzende bekommen nichts angesagt und tabben anschließend
    // weiter durch die Navigation statt durch die Seite, die sie wollten.
    const router = TestBed.inject(Router);
    const main = el.querySelector<HTMLElement>("#studio-main");
    expect(main).not.toBeNull();

    await router.navigate([STUDIO_VIEWS[0].slug]);
    await fixture.whenStable();
    // Der erste Aufschlag ist das Laden der Seite, keine Navigation des
    // Nutzers — da darf der Fokus nicht wegspringen.
    expect(document.activeElement).not.toBe(main);

    await router.navigate([STUDIO_VIEWS[1].slug]);
    await fixture.whenStable();
    expect(document.activeElement).toBe(main);
  });
});
