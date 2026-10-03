// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { RagEmbedMissingComponent } from "./rag-embed-missing.component";

const tick = (): Promise<unknown> =>
  new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<RagEmbedMissingComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(RagEmbedMissingComponent);
  await fixture.whenStable();
  return {
    fixture,
    el: fixture.nativeElement as HTMLElement,
    http: TestBed.inject(HttpTestingController),
  };
}

async function nachholen(h: Harness): Promise<void> {
  h.el.querySelector<HTMLButtonElement>("button")?.click();
  await h.fixture.whenStable();
}

async function antwort(h: Harness, body: object, status = 200): Promise<void> {
  h.http
    .expectOne("/studio/api/rag/embed")
    .flush(body, { status, statusText: status === 200 ? "OK" : "Error" });
  await tick();
  await h.fixture.whenStable();
}

const live = (h: Harness): string =>
  h.el.querySelector('[aria-live="polite"]')?.textContent?.trim() ?? "";

/**
 * Paket 4, C2 (externes Audit F06): Ein Import, bei dem Vektoren fehlten,
 * meldet sie jetzt. Die Suche findet solche Abschnitte erst nach dem Nachholen
 * (`POST /api/rag/embed`) — das Studio rief diesen Weg bisher nie.
 */
describe("RagEmbedMissingComponent", () => {
  it("bietet das Nachholen an", async () => {
    // Die Zahl steht in der angesagten Ergebniszeile des Imports
    // (``rag-ingest.component.spec.ts``), nicht hier.
    const { el } = await mount();
    expect(el.querySelector("button")?.textContent).toContain("nachholen");
  });

  it("die Statusmeldung steht leer im DOM, bevor etwas passiert", async () => {
    // Eine Live-Region, die erst mit ihrem Text entsteht, sagen Screenreader
    // oft nicht an (Audit 2026-09-29, F-M6).
    const h = await mount();
    expect(h.el.querySelector('[aria-live="polite"]')).not.toBeNull();
    expect(live(h)).toBe("");
  });

  it("sperrt den Knopf, solange es läuft", async () => {
    const h = await mount();
    await nachholen(h);
    const knopf = h.el.querySelector<HTMLButtonElement>("button");
    expect(knopf?.disabled).toBe(true);
    expect(knopf?.textContent).toContain("Wird nachgeholt");
    await antwort(h, { status: "ok", embedded: 2, total: 2 });
  });

  it("holt nach, meldet es und hat dann nichts mehr zu tun", async () => {
    const h = await mount();
    await nachholen(h);
    await antwort(h, { status: "ok", embedded: 2, total: 2 });
    expect(live(h)).toContain("2 Abschnitte nachgeholt");
    expect(h.el.querySelector("button")).toBeNull();
  });

  it("ein Teilerfolg lässt den Knopf für einen neuen Versuch stehen", async () => {
    const h = await mount();
    await nachholen(h);
    await antwort(h, { status: "ok", embedded: 1, total: 2 });
    expect(live(h)).toContain("1 von 2");
    expect(h.el.querySelector<HTMLButtonElement>("button")?.disabled).toBe(false);
  });

  it("ein Fehler steht als Meldung da, und der Knopf bleibt", async () => {
    const h = await mount();
    await nachholen(h);
    await antwort(h, { detail: "kaputt" }, 500);
    expect(h.el.querySelector('[role="alert"]')).not.toBeNull();
    expect(h.el.querySelector<HTMLButtonElement>("button")?.disabled).toBe(false);
  });
});
