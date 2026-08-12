// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { FactoryPanelComponent } from "./factory-panel.component";

const FACTORY = "/studio/api/config/factory";

interface Harness {
  fixture: ComponentFixture<FactoryPanelComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(
  status: Record<string, unknown> = { exists: false },
): Promise<Harness> {
  TestBed.resetTestingModule();
  // Siehe backup.component.spec.ts — jsdom meldet `en-US`.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(FactoryPanelComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne(FACTORY).flush(status);
  await settle(h);
  return h;
}

const text = (h: Harness): string => h.el.textContent ?? "";

function button(h: Harness, label: string): HTMLButtonElement {
  const match = Array.from(h.el.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").trim().startsWith(label),
  );
  if (!match)
    throw new Error(
      `Kein Knopf "${label}" — vorhanden: ${Array.from(
        h.el.querySelectorAll("button"),
      )
        .map((b) => b.textContent?.trim())
        .join(" | ")}`,
    );
  return match;
}

async function click(h: Harness, label: string): Promise<void> {
  button(h, label).click();
  await settle(h);
}

describe("FactoryPanelComponent", () => {
  beforeEach(() => {
    Object.assign(URL, {
      createObjectURL: vi.fn(() => "blob:x"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("sagt, dass kein Werksstand da ist, statt leere Felder zu zeigen", async () => {
    const h = await mount({ exists: false });
    expect(text(h)).toContain("Kein Werksstand gesichert");
    // Two of the four actions need a stored baseline; offering them anyway would
    // only produce a 404 ("Kein Factory-Stand gesetzt").
    expect(button(h, "Zurücksetzen").disabled).toBe(true);
    expect(button(h, "Herunterladen").disabled).toBe(true);
  });

  it("zeigt Datum und Bezeichnung des gesicherten Standes", async () => {
    const h = await mount({
      exists: true,
      created_at: "2026-07-20T09:30:00Z",
      label: "Auslieferung",
    });
    // `germanDateTime` is the shared de-DE formatter (6 views): "20.7.2026, 11:30:00".
    expect(text(h)).toContain("20.7.2026");
    expect(text(h)).toContain("Auslieferung");
    expect(button(h, "Zurücksetzen").disabled).toBe(false);
  });

  it("fragt vor dem Überschreiben des Werksstands zurück", async () => {
    const h = await mount({
      exists: true,
      created_at: "2026-07-20T09:30:00Z",
      label: "alt",
    });
    await click(h, "Aus Live-Stand sichern");
    h.http.expectNone(`${FACTORY}/save`);
    expect(text(h)).toContain("überschrieben");

    await click(h, "Ja, Werksstand ersetzen");
    h.http
      .expectOne(`${FACTORY}/save`)
      .flush({ status: "saved", id: "factory" });
    await settle(h);
    // The card must show the NEW date, so the status is re-read.
    h.http.expectOne(FACTORY).flush({
      exists: true,
      created_at: "2026-07-26T12:00:00Z",
      label: "factory",
    });
    await settle(h);
    expect(text(h)).toContain("26.7.2026");
  });

  it("nennt beim Zurücksetzen die echte Folge und meldet die Zahl der Bereiche", async () => {
    const h = await mount({
      exists: true,
      created_at: "2026-07-20T09:30:00Z",
      label: "x",
    });
    await click(h, "Zurücksetzen");
    // ALT warned that the database, sessions, memory, quality logs and RAG
    // chunks would be replaced. `_apply_config` writes config areas and nothing
    // else, so that warning would be a false claim here.
    expect(text(h)).not.toMatch(/Datenbank|Sessions|RAG/);
    expect(text(h)).toContain("Konfigurationsbereiche");

    await click(h, "Ja, zurücksetzen");
    h.http
      .expectOne(`${FACTORY}/restore`)
      .flush({ status: "restored", areas: 35 });
    await settle(h);
    expect(text(h)).toContain("35");
  });

  it("lädt einen Werksstand erst nach Rückfrage hoch", async () => {
    // Same consequence as "Aus Live-Stand sichern": the stored baseline is
    // replaced and the old one is gone. Both are confirmed, so the rule is
    // "everything that destroys something asks", with the download as the one
    // action that destroys nothing.
    const h = await mount({ exists: false });
    expect(button(h, "Hochladen").disabled).toBe(true);

    const file = new File(["PK"], "factory.zip");
    h.fixture.componentInstance.onFile({
      target: { files: [file] },
    } as unknown as Event);
    await settle(h);
    await click(h, "Hochladen");
    h.http.expectNone(`${FACTORY}/upload`);

    await click(h, "Ja, übernehmen");
    const req = h.http.expectOne(`${FACTORY}/upload`);
    expect((req.request.body as FormData).get("file")).toBe(file);
    req.flush({ status: "saved", id: "factory" });
    await settle(h);
    h.http
      .expectOne(FACTORY)
      .flush({ exists: true, created_at: "2026-07-26T12:00:00Z", label: "f" });
  });
});
