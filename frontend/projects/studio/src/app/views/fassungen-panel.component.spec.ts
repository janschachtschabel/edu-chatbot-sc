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
import { FassungenPanelComponent } from "./fassungen-panel.component";

const BASE = "/studio/api/config/fassungen";

interface Harness {
  fixture: ComponentFixture<FassungenPanelComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const LISTE = {
  available: true,
  bereiche: [
    { area: "01-base/welcome-config", status: "eigen", version: 3, hat_eigene_fassung: false },
    { area: "03-patterns/m05", status: "eigen-neues-werk", version: 7, hat_eigene_fassung: false },
    { area: "03-patterns/m06", status: "werk", version: 2, hat_eigene_fassung: true },
    { area: "03-patterns/m07", status: "werk", version: 1, hat_eigene_fassung: false },
    { area: "03-patterns/m08", status: "werk-entfernt", version: null, hat_eigene_fassung: false },
  ],
};

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(liste: object = LISTE): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(FassungenPanelComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne(BASE).flush(liste);
  await settle(h);
  return h;
}

const text = (h: Harness): string => h.el.textContent ?? "";

function zeile(h: Harness, area: string): HTMLElement {
  const z = h.el.querySelector<HTMLElement>(`[data-area="${area}"]`);
  if (!z) throw new Error(`keine Zeile ${area}`);
  return z;
}

function knopf(wurzel: HTMLElement, label: string): HTMLButtonElement {
  const k = Array.from(wurzel.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").trim().startsWith(label));
  if (!k) throw new Error(`kein Knopf "${label}"`);
  return k;
}

function filter(h: Harness, label: string): HTMLInputElement {
  const l = Array.from(h.el.querySelectorAll("label")).find((x) =>
    (x.textContent ?? "").trim().startsWith(label));
  const input = l?.querySelector("input");
  if (!input) throw new Error(`kein Filter "${label}"`);
  return input;
}

describe("FassungenPanelComponent", () => {
  it("zeigt zuerst nur, was angepasst ist — auch Bereiche mit stillgelegter eigener Fassung", async () => {
    const h = await mount();
    expect(filter(h, "Angepasst").checked).toBe(true);
    const sichtbar = Array.from(h.el.querySelectorAll("[data-area]")).map(
      (z) => z.getAttribute("data-area"));
    expect(sichtbar).toEqual([
      "01-base/welcome-config", "03-patterns/m05", "03-patterns/m06", "03-patterns/m08"]);
    // Status steht als Text, nicht nur als Farbe.
    expect(zeile(h, "03-patterns/m05").textContent).toContain("neue Werksfassung");
  });

  it("„Alle“ zeigt auch die unberührten Bereiche", async () => {
    const h = await mount();
    filter(h, "Alle").click();
    await settle(h);
    expect(h.el.querySelector('[data-area="03-patterns/m07"]')).not.toBeNull();
  });

  it("schaltet auf die Werksfassung um und lädt die Liste neu", async () => {
    const h = await mount();
    knopf(zeile(h, "01-base/welcome-config"), "Werksfassung verwenden").click();
    await settle(h);
    const req = h.http.expectOne(`${BASE}/umschalten`);
    expect(req.request.body).toEqual(
      { area: "01-base/welcome-config", ziel: "werk", expected_version: 3 });
    req.flush({ status: "ok", area: "01-base/welcome-config", version: 4 });
    await settle(h);
    h.http.expectOne(BASE).flush(LISTE);
    await settle(h);
    expect(text(h)).toContain("01-base/welcome-config");
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain("Werksfassung");
  });

  it("holt eine stillgelegte eigene Fassung zurück und stellt Gelöschtes wieder her", async () => {
    const h = await mount();
    knopf(zeile(h, "03-patterns/m06"), "Eigene Fassung verwenden").click();
    await settle(h);
    expect(h.http.expectOne(`${BASE}/umschalten`).request.body).toEqual(
      { area: "03-patterns/m06", ziel: "eigen", expected_version: 2 });
    knopf(zeile(h, "03-patterns/m08"), "Werksfassung wiederherstellen");
  });

  it("klappt den Unterschied auf, ohne die Kopfzeilen zu zeigen", async () => {
    const h = await mount();
    const k = knopf(zeile(h, "03-patterns/m05"), "Unterschied zeigen");
    expect(k.getAttribute("aria-expanded")).toBe("false");
    k.click();
    await settle(h);
    h.http.expectOne((r) => r.url === `${BASE}/vergleich`).flush({
      area: "03-patterns/m05", werk: "", gelebt: "", eigene: null,
      zeilen: ["--- werk", "+++ gelebt", "@@ -1 +1 @@", "-Werkstext", "+Eigener Text"],
    });
    await settle(h);
    const vergleich = zeile(h, "03-patterns/m05").textContent ?? "";
    expect(vergleich).toContain("-Werkstext");
    expect(vergleich).toContain("+Eigener Text");
    expect(vergleich).not.toContain("+++ gelebt");
    expect(knopf(zeile(h, "03-patterns/m05"), "Unterschied ausblenden")
      .getAttribute("aria-expanded")).toBe("true");
  });

  it("startet den Werksabgleich und meldet, was er tat", async () => {
    const h = await mount();
    knopf(h.el, "Werksabgleich starten").click();
    await settle(h);
    h.http.expectOne(`${BASE}/werksabgleich`).flush(
      { neu: 1, aktualisiert: 2, zugeordnet: 0, neues_werk: 1, uebersprungen: 0, konflikt: 0 });
    await settle(h);
    h.http.expectOne(BASE).flush(LISTE);
    await settle(h);
    const meldung = h.el.querySelector('[role="status"]')?.textContent ?? "";
    expect(meldung).toContain("1");
    expect(meldung).toContain("2");
  });

  it("zeigt fehlende Werksbereiche unter „Angepasst“ (Review #10)", async () => {
    const h = await mount({ available: true, bereiche: [
      { area: "03-patterns/m09", status: "werk-fehlt", version: null, hat_eigene_fassung: false }] });
    knopf(zeile(h, "03-patterns/m09"), "Werksfassung wiederherstellen");
  });

  it("bietet bei zwei eigenen Fassungen nur den Tausch an (Review #1)", async () => {
    const h = await mount({ available: true, bereiche: [
      { area: "01-base/x", status: "eigen", version: 4, hat_eigene_fassung: true }] });
    const knoepfe = Array.from(zeile(h, "01-base/x").querySelectorAll("button"))
      .map((b) => (b.textContent ?? "").trim());
    expect(knoepfe).toContain("Eigene Fassung verwenden");
    expect(knoepfe).not.toContain("Werksfassung verwenden");
  });

  it("bezieht jeden Knopf auf seinen Bereich und macht den Vergleich per Tastatur erreichbar (Review #9)", async () => {
    const h = await mount();
    const z = zeile(h, "03-patterns/m05");
    const k = knopf(z, "Werksfassung verwenden");
    const bezug = h.el.querySelector(`#${k.getAttribute("aria-describedby")}`);
    expect(bezug?.textContent).toContain("03-patterns/m05");
    knopf(z, "Unterschied zeigen").click();
    await settle(h);
    h.http.expectOne((r) => r.url === `${BASE}/vergleich`).flush({
      area: "03-patterns/m05", werk: "", gelebt: "", eigene: null,
      zeilen: ["--- werk", "+++ gelebt", "-a", "+b"] });
    await settle(h);
    const pre = zeile(h, "03-patterns/m05").querySelector("pre");
    expect(pre?.getAttribute("tabindex")).toBe("0");
    expect(pre?.getAttribute("role")).toBe("region");
    expect(pre?.getAttribute("aria-label")).toContain("03-patterns/m05");
  });

  it("meldet übersprungene und kollidierende Bereiche des Werksabgleichs", async () => {
    const h = await mount();
    knopf(h.el, "Werksabgleich starten").click();
    await settle(h);
    h.http.expectOne(`${BASE}/werksabgleich`).flush(
      { neu: 0, aktualisiert: 0, zugeordnet: 0, neues_werk: 0, uebersprungen: 1, konflikt: 2 });
    await settle(h);
    h.http.expectOne(BASE).flush(LISTE);
    await settle(h);
    const meldung = h.el.querySelector('[role="status"]')?.textContent ?? "";
    expect(meldung).toContain("übersprungen");
    expect(meldung).toContain("Kennung");
  });

  it("markiert eine angepasste Fassung als geprüft (Review 2 #5)", async () => {
    const h = await mount();
    knopf(zeile(h, "03-patterns/m05"), "Als geprüft markieren").click();
    await settle(h);
    expect(h.http.expectOne(`${BASE}/umschalten`).request.body).toEqual(
      { area: "03-patterns/m05", ziel: "geprueft", expected_version: 7 });
  });

  it("meldet bei veraltetem Werk eine Aktualisierung, kein Stilllegen (Review 2 #6)", async () => {
    const h = await mount({ available: true, bereiche: [
      { area: "01-base/v", status: "werk-veraltet", version: 2, hat_eigene_fassung: false }] });
    filter(h, "Alle").click();
    await settle(h);
    knopf(zeile(h, "01-base/v"), "Werksfassung verwenden").click();
    await settle(h);
    h.http.expectOne(`${BASE}/umschalten`).flush({ status: "ok", area: "01-base/v", version: 3 });
    await settle(h);
    h.http.expectOne(BASE).flush(LISTE);
    await settle(h);
    const meldung = h.el.querySelector('[role="status"]')?.textContent ?? "";
    expect(meldung).toContain("aktualisiert");
    expect(meldung).not.toContain("liegt still");
  });

  it("zeigt die stillgelegte Fassung vor dem Zurückholen (Review 2 #10)", async () => {
    const h = await mount();
    knopf(zeile(h, "03-patterns/m06"), "Unterschied zeigen").click();
    await settle(h);
    h.http.expectOne((r) => r.url === `${BASE}/vergleich`).flush({
      area: "03-patterns/m06", werk: "", gelebt: "", eigene: "x", zeilen: [],
      zeilen_eigene: ["--- werk", "+++ eigene", "-W", "+E"] });
    await settle(h);
    const text = zeile(h, "03-patterns/m06").textContent ?? "";
    expect(text).toContain("Stillgelegte");
    expect(text).toContain("+E");
  });

  it("sagt, wenn nichts angepasst ist", async () => {
    const h = await mount({ available: true, bereiche: [
      { area: "03-patterns/m07", status: "werk", version: 1, hat_eigene_fassung: false }] });
    expect(text(h)).toContain("Werksfassung");
    expect(h.el.querySelector("[data-area]")).toBeNull();
  });

  it("sagt, wenn das Abbild keine Werksfassung mitbringt", async () => {
    const h = await mount({ available: false, bereiche: [] });
    expect(text(h)).toContain("keine Werksfassung");
  });
});
