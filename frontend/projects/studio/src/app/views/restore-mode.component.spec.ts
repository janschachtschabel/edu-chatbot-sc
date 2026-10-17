// @vitest-environment jsdom
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { RestoreModeComponent } from "./restore-mode.component";

async function mount(): Promise<ComponentFixture<RestoreModeComponent>> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  const fixture = TestBed.createComponent(RestoreModeComponent);
  await fixture.whenStable();
  return fixture;
}

function radio(f: ComponentFixture<RestoreModeComponent>, wert: string): HTMLInputElement {
  return (f.nativeElement as HTMLElement).querySelector<HTMLInputElement>(
    `input[type="radio"][value="${wert}"]`,
  )!;
}

describe("RestoreModeComponent", () => {
  it("steht ohne Zutun auf „ergänzend“ und nennt beide Folgen", async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const f = await mount();
    expect(radio(f, "merge").checked).toBe(true);
    expect(radio(f, "exact").checked).toBe(false);
    const text = (f.nativeElement as HTMLElement).textContent ?? "";
    expect(text).toContain("bleiben, wie sie sind");
    // Die Folge von „exakt" steht da, BEVOR jemand sie wählt — nicht erst danach.
    expect(text).toContain("werden gelöscht");
    expect(text).toContain("Snapshot");
  });

  it("ist eine beschriftete Gruppe, jede Wahl mit eigenem Etikett", async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const f = await mount();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector("fieldset > legend")?.textContent).toContain(
      "nicht in der Sicherung",
    );
    for (const wert of ["merge", "exact"]) {
      expect(radio(f, wert).closest("label")).not.toBeNull();
    }
  });

  it("nennt jeden Knopf kurz und hängt die Folge als Beschreibung an (Review C-11)", async () => {
    // Der ganze Folgesatz stand im Namen des Knopfs — bei jedem Fokus vorgelesen.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const f = await mount();
    const el = f.nativeElement as HTMLElement;
    const text = (id: string | null) => el.querySelector(`#${id}`)?.textContent?.trim();
    const exakt = radio(f, "exact");
    expect(text(exakt.getAttribute("aria-labelledby"))).toBe("Exakt");
    expect(text(exakt.getAttribute("aria-describedby"))).toContain("werden gelöscht");
    const ergaenzend = radio(f, "merge");
    expect(text(ergaenzend.getAttribute("aria-labelledby"))).toBe("Ergänzend (Vorgabe)");
    expect(text(ergaenzend.getAttribute("aria-describedby"))).toContain("bleiben, wie sie sind");
  });

  it("meldet die Wahl nach oben", async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const f = await mount();
    radio(f, "exact").click();
    await f.whenStable();
    expect(f.componentInstance.mode()).toBe("exact");
    radio(f, "merge").click();
    await f.whenStable();
    expect(f.componentInstance.mode()).toBe("merge");
  });

  it("folgt einer Wahl von außen", async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const f = await mount();
    f.componentRef.setInput("mode", "exact");
    await f.whenStable();
    expect(radio(f, "exact").checked).toBe(true);
  });

  it("teilt den Gruppennamen mit keiner zweiten Rückfrage", async () => {
    // Drei Panels können zugleich eine Rückfrage offen haben; teilten sich ihre
    // Knöpfe einen Namen, schaltete eine Wahl im einen die im anderen ab.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const a = await mount();
    const b = await mount();
    expect(radio(a, "merge").name).not.toBe("");
    expect(radio(a, "merge").name).not.toBe(radio(b, "merge").name);
  });
});
