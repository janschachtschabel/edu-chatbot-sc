// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { AreasComponent } from "./areas.component";

const FILES = "/studio/api/config/files";

interface Harness {
  fixture: ComponentFixture<AreasComponent>;
  el: HTMLElement;
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

async function mount(
  response: object = [
    {
      path: "01-base/welcome-config.yaml",
      full_path: "x",
      name: "welcome-config.yaml",
      type: "yaml",
    },
    {
      path: "01-base/policy.yaml",
      full_path: "x",
      name: "policy.yaml",
      type: "yaml",
    },
    {
      path: "03-patterns/m01-krisen.md",
      full_path: "x",
      name: "m01-krisen.md",
      type: "md",
    },
  ],
  status = 200,
): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
  // Zusagen unten brauchen deshalb die oberste Sprachquelle.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideRouter([{ path: "**", children: [] }]),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(AreasComponent);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne(FILES).flush(response, { status, statusText: "x" });
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

function links(el: HTMLElement): HTMLAnchorElement[] {
  return Array.from(el.querySelectorAll("a.ar-link"));
}

describe("AreasComponent", () => {
  it("lists every area the backend reports", async () => {
    const h = await mount();
    expect(links(h.el)).toHaveLength(3);
    expect(h.el.textContent).toContain("3 Bereiche");
  });

  it("links to the generic editor with the extension stripped", async () => {
    const h = await mount();
    const hrefs = links(h.el).map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/bereich/01-base/welcome-config");
    expect(hrefs).toContain("/bereich/03-patterns/m01-krisen");
  });

  it("groups by folder, folders and entries sorted", async () => {
    const h = await mount();
    const folders = Array.from(h.el.querySelectorAll(".ar-folder")).map(
      (n) => n.textContent,
    );
    expect(folders).toEqual(["01-base", "03-patterns"]);
    const first = Array.from(
      h.el.querySelectorAll(".ar-group")[0].querySelectorAll(".ar-name"),
    );
    expect(first.map((n) => n.textContent)).toEqual([
      "policy",
      "welcome-config",
    ]);
  });

  it("says what to do when nothing is imported yet", async () => {
    const h = await mount([]);
    expect(h.el.textContent).toContain("boerdi import-config");
    expect(links(h.el)).toHaveLength(0);
  });

  it("offers a retry when the list cannot be loaded", async () => {
    const h = await mount({ detail: "boom" }, 500);
    const alert = h.el.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("konnte nicht geladen werden");
    expect(alert?.querySelector("button")).not.toBeNull();
  });
});
