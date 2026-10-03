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
import { AREA_SCHEMAS } from "../schema-form/area-schemas.fixture";
import { AreaSectionComponent } from "./area-section.component";
import type { CuratedAreaSection } from "./curated-views";

const AREA = "01-base/welcome-config";
const DATA_URL = `/studio/api/config/data/${AREA}`;
const SECTION: CuratedAreaSection = {
  area: AREA,
  labelKey: "curated.begruessung.welcome.label",
  hintKey: "curated.begruessung.welcome.hint",
};

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<AreaSectionComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

/** Nebenbei-Abrufe (Wirkungs-Marke, Kataloge) duldsam beantworten. */
function settle(http: HttpTestingController): void {
  http.match("/studio/api/config/effects").forEach((r) => r.flush({}));
  http.match("/studio/api/config/choices").forEach((r) => r.flush({}));
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(AreaSectionComponent);
  fixture.componentRef.setInput("section", SECTION);
  fixture.componentRef.setInput("open", true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  settle(http);
  http.expectOne(`/studio/api/config/schema/${AREA}`).flush(AREA_SCHEMAS[AREA]);
  http.expectOne(DATA_URL).flush({
    area: AREA, data: { welcome: { greeting: "Moin" } }, type: "yaml", version: 2,
  });
  await tick();
  await fixture.whenStable();
  settle(http);
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

/**
 * Paket 4, D5 (externes Audit F14): Auch die Abschnitte der kuratierten
 * Ansichten speichern gegen ihre Version und zeigen nach einem 409 den
 * Hinweis — derselbe Editor-Kern wie im Bereichs-Editor.
 */
describe("AreaSectionComponent — Konflikt beim Speichern (Paket 4, D5)", () => {
  it("zeigt den Hinweis, behält den Entwurf und lädt auf Wunsch neu", async () => {
    const h = await mount();
    h.fixture.componentInstance.editor.setDoc({ welcome: { greeting: "Mein Entwurf" } });
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".cs-save")?.click();
    await h.fixture.whenStable();
    const put = h.http.expectOne(DATA_URL);
    expect(put.request.body.expected_version).toBe(2);
    put.flush(
      { detail: { message: "x", version: 3, updated_by: "restore",
                  updated_at: "2026-10-03T20:41:00+00:00" } },
      { status: 409, statusText: "Conflict" });
    await tick();
    await h.fixture.whenStable();

    const hinweis = h.el.querySelector("studio-save-conflict");
    expect(hinweis?.textContent).toContain("Wiederherstellung");
    expect(h.fixture.componentInstance.editor.doc()).toEqual({
      welcome: { greeting: "Mein Entwurf" },
    });

    const neu = [...h.el.querySelectorAll<HTMLButtonElement>("studio-save-conflict button")]
      .find((b) => b.textContent?.includes("Neu laden"));
    neu!.click();
    await h.fixture.whenStable();
    h.http.expectOne(`/studio/api/config/schema/${AREA}`).flush(AREA_SCHEMAS[AREA]);
    h.http.expectOne(DATA_URL).flush({
      area: AREA, data: { welcome: { greeting: "Wiederhergestellt" } }, type: "yaml", version: 3,
    });
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector("studio-save-conflict")).toBeNull();
  });
});
