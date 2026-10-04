// @vitest-environment jsdom
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import type { SaveConflict } from "../core/studio-api-error";
import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { SaveConflictComponent } from "./save-conflict.component";

interface Harness {
  fixture: ComponentFixture<SaveConflictComponent>;
  el: HTMLElement;
}

async function mount(conflict: SaveConflict, busy = false): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(SaveConflictComponent);
  fixture.componentRef.setInput("conflict", conflict);
  fixture.componentRef.setInput("busy", busy);
  document.body.appendChild(fixture.nativeElement as HTMLElement);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

const GEAENDERT: SaveConflict = {
  version: 5, updatedBy: "studio-form", updatedAt: "2026-10-03T20:41:00+00:00",
};

const knopf = (h: Harness, text: string): HTMLButtonElement =>
  [...h.el.querySelectorAll("button")].find((b) => b.textContent?.includes(text))!;

/**
 * Paket 4, D5 (externes Audit F14): Wer als zweites speichert, bekam bisher
 * nichts zu sehen und überschrieb den ersten. Jetzt erscheint dieser Hinweis
 * — mit Wann und Quelle der anderen Änderung und den beiden Auswegen.
 */
describe("SaveConflictComponent", () => {
  it("nennt, wann und über welchen Weg gespeichert wurde", async () => {
    const h = await mount(GEAENDERT);
    const text = h.el.textContent ?? "";
    expect(text).toContain("inzwischen");
    expect(text).toContain("Formular"); // `studio-form`, nicht der Rohwert
    expect(text).toContain("2026"); // die Zeit, ortsüblich formatiert
  });

  it("zeigt eine unbekannte Quelle so, wie sie kam", async () => {
    const h = await mount({ ...GEAENDERT, updatedBy: "skript-x" });
    expect(h.el.textContent).toContain("skript-x");
  });

  it("sagt es, wenn der Bereich inzwischen gelöscht wurde", async () => {
    const h = await mount({ version: null, updatedBy: null, updatedAt: null });
    expect(h.el.textContent).toContain("gelöscht");
  });

  it("bietet Neu laden und Trotzdem speichern an", async () => {
    const h = await mount(GEAENDERT);
    const gerufen: string[] = [];
    h.fixture.componentInstance.reload.subscribe(() => gerufen.push("neu"));
    h.fixture.componentInstance.force.subscribe(() => gerufen.push("trotzdem"));
    knopf(h, "Neu laden").click();
    knopf(h, "Trotzdem speichern").click();
    expect(gerufen).toEqual(["neu", "trotzdem"]);
  });

  it("holt den Fokus, damit der Hinweis nicht unbemerkt unter dem Formular steht", async () => {
    const h = await mount(GEAENDERT);
    const box = h.el.querySelector<HTMLElement>("[role='group']");
    expect(box).not.toBeNull();
    expect(document.activeElement).toBe(box);
    // der Name der Gruppe ist der Satz selbst — ihn liest der Screenreader vor
    const label = document.getElementById(box!.getAttribute("aria-labelledby")!);
    expect(label?.textContent).toContain("inzwischen");
  });

  it("sperrt beide Knöpfe, solange gespeichert oder geladen wird", async () => {
    const h = await mount(GEAENDERT, true);
    expect(knopf(h, "Neu laden").disabled).toBe(true);
    expect(knopf(h, "Trotzdem speichern").disabled).toBe(true);
  });
});
