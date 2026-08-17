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
import { SeedPanelComponent } from "./seed-panel.component";

const SEED = "/studio/api/config/seed";

interface Harness {
  fixture: ComponentFixture<SeedPanelComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const LEER = {
  available: true,
  area_count: 0,
  neu: [],
  gleich: [],
  abweichend: [],
  nur_in_db: [],
};

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(status: Record<string, unknown>): Promise<Harness> {
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
  const fixture = TestBed.createComponent(SeedPanelComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne(SEED).flush(status);
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

describe("SeedPanelComponent", () => {
  it("sagt es, wenn das Abbild keinen Auslieferungsstand mitbringt", async () => {
    const h = await mount({ ...LEER, available: false });
    expect(text(h)).toContain("bringt keinen Auslieferungsstand mit");
    // Beide Knöpfe hätten nichts zu holen; angeboten würden sie nur ein 404
    // erzeugen.
    expect(button(h, "Fehlende nachziehen").disabled).toBe(true);
    expect(button(h, "Alles auf Auslieferungsstand").disabled).toBe(true);
  });

  it("zeigt die vier Zahlen, an denen die Entscheidung hängt", async () => {
    const h = await mount({
      available: true,
      area_count: 35,
      neu: ["01-base/neu"],
      gleich: new Array(30).fill(0).map((_, i) => `g/${i}`),
      abweichend: ["01-base/engine", "01-base/welcome-config"],
      nur_in_db: ["01-base/eigenbau"],
    });
    expect(text(h)).toContain("Bereiche im Abbild: 35");
    expect(text(h)).toContain("unverändert: 30");
    // Die Beschriftung steht vor der Zahl, damit auch „1" grammatisch stimmt —
    // „1 fehlen in der Datenbank" wäre falsch gewesen.
    expect(text(h)).toContain("fehlend: 1");
    expect(text(h)).toContain("abweichend: 2");
    expect(text(h)).toContain("nur in der Datenbank: 1");
  });

  it("nennt die Namen der Bereiche, die gelöscht würden", async () => {
    // Die Zahl allein reicht für den scharfen Knopf nicht: „1 nur in der
    // Datenbank" sagt nicht, ob das eine Altlast oder gepflegte Arbeit ist.
    const h = await mount({
      ...LEER,
      area_count: 1,
      nur_in_db: ["01-base/eigenbau"],
    });
    expect(text(h)).toContain("01-base/eigenbau");
  });

  it("hält den harmlosen Knopf aus, wenn nichts fehlt", async () => {
    const h = await mount({
      ...LEER,
      area_count: 35,
      gleich: ["a"],
      abweichend: ["b"],
    });
    expect(button(h, "Fehlende nachziehen").disabled).toBe(true);
    // Der scharfe darf hier, denn „b" weicht ab.
    expect(button(h, "Alles auf Auslieferungsstand").disabled).toBe(false);
  });

  it("zieht Fehlendes ohne Rückfrage nach und meldet die Zahl", async () => {
    const h = await mount({ ...LEER, area_count: 3, neu: ["a", "b"] });
    await click(h, "Fehlende nachziehen");
    const req = h.http.expectOne(`${SEED}/apply`);
    expect(req.request.body).toEqual({ mode: "missing" });
    req.flush({ written: 2, deleted: 0, snapshot_id: null });
    await settle(h);
    expect(text(h)).toContain("2 Bereiche nachgezogen");
    // Die Zählung muss danach stimmen, sonst zeigt die Karte Arbeit an, die
    // schon getan ist.
    h.http.expectOne(SEED).flush(LEER);
  });

  it("fragt vor dem scharfen Lauf zurück und nennt beide Folgen", async () => {
    const h = await mount({
      ...LEER,
      area_count: 2,
      abweichend: ["a"],
      nur_in_db: ["b"],
    });
    await click(h, "Alles auf Auslieferungsstand");
    h.http.expectNone(`${SEED}/apply`);
    expect(text(h)).toContain("überschrieben");
    expect(text(h)).toContain("gelöscht");
    // Der Rückweg gehört in die Rückfrage, nicht erst in die Erfolgsmeldung.
    expect(text(h)).toContain("Schnappschuss");

    await click(h, "Ja, herstellen");
    const req = h.http.expectOne(`${SEED}/apply`);
    expect(req.request.body).toEqual({ mode: "exact" });
    req.flush({ written: 1, deleted: 1, snapshot_id: "snap-abc" });
    await settle(h);
    expect(text(h)).toContain("Geschrieben: 1, gelöscht: 1");
    h.http.expectOne(SEED).flush(LEER);
  });

  it("liest auch nach einem Fehlschlag neu, statt eine tote Zählung zu zeigen", async () => {
    // Ein abgelehnter Lauf (kein Platz für den Schnappschuss) darf die Karte
    // nicht in ihrem alten Zustand einfrieren.
    const h = await mount({ ...LEER, area_count: 1, nur_in_db: ["b"] });
    await click(h, "Alles auf Auslieferungsstand");
    await click(h, "Ja, herstellen");
    h.http
      .expectOne(`${SEED}/apply`)
      .flush({ detail: "Snapshot-Limit erreicht (max 50)" }, { status: 400, statusText: "Bad Request" });
    await settle(h);
    expect(text(h)).toContain("Snapshot-Limit");
    h.http.expectOne(SEED).flush(LEER);
  });
});
