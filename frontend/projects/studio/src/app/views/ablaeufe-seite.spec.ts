// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import { HttpTestingController, provideHttpClientTesting } from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter, Router } from "@angular/router";
import { describe, expect, it } from "vitest";

import type { AblaufZeile } from "../core/ablauf-api.service";
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from "../i18n/studio-language.service";
import { AREA_SCHEMAS } from "../schema-form/area-schemas.fixture";
import { ablaufNotiz } from "./ablauf-notiz";
import { CURATED_VIEWS } from "./curated-views";
import type { CuratedSection } from "./curated-views";
import { GroupDocuments } from "./group-documents";
import { GroupSectionComponent } from "./group-section.component";

/**
 * AS-0 (Plan 2026-11-09): die Seite „Abläufe“ — der Ordner `06-ablaeufe` in `group-section`.
 * Die Liste kommt aus `GET /api/config/ablaeufe` und nennt je Ablauf Kennung, an/aus, Auslöser
 * und Befunde; eine neue Kennung hat die Form, die der Treiber liest.
 */
const ABLAEUFE: CuratedSection = {
  area: "06-ablaeufe", kind: "group",
  labelKey: "curated.ablaeufe.liste.label", hintKey: "curated.ablaeufe.liste.hint",
};

function zeile(id: string, mehr: Partial<AblaufZeile> = {}): AblaufZeile {
  return { key: `06-ablaeufe/${id}`, id, titel: { de: id.toUpperCase() }, aktiv: false,
           ausloeser: [], module: [], befunde: 0, lesbar: true, ...mehr };
}

const LISTE = { ablaeufe: [
  zeile("lesen", { titel: { de: "Vorlesen", en: "Read aloud" }, aktiv: true,
                   ausloeser: ["knopf", "text"], module: ["ui_upload"] }),
  zeile("kaputt", { lesbar: false }),
  zeile("pruefen", { befunde: 2 }),
] };

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<GroupSectionComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(sprache = "de"): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, sprache);
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(), provideHttpClient(withXhr()), provideHttpClientTesting(),
    provideRouter([]),
  ] });
  const fixture = TestBed.createComponent(GroupSectionComponent);
  fixture.componentRef.setInput("section", ABLAEUFE);
  fixture.componentRef.setInput("open", true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne("/studio/api/config/ablaeufe").flush(LISTE);
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

function eintraege(el: HTMLElement): string[] {
  return Array.from(el.querySelectorAll(".ol-entry")).map((b) =>
    `${b.querySelector(".ol-title")?.textContent?.trim()} · ${b.querySelector(".ol-note")?.textContent?.trim()}`);
}

describe("Seite „Abläufe“ (AS-0)", () => {
  it("steht als eigene Seite mit dem Ordner 06-ablaeufe", () => {
    const seite = CURATED_VIEWS.find((v) => v.slug === "ablaeufe");
    // Paket KF: darunter die Freigabe der Kestra-Flows — als eigener Abschnitt, klar benannt
    expect(seite?.sections).toEqual([
      expect.objectContaining({ area: "06-ablaeufe", kind: "group" }),
      expect.objectContaining({ area: "01-base/kestra-flows", labelKey: "curated.ablaeufe.kestra.label" }),
    ]);
    const uiModule = CURATED_VIEWS.find((v) => v.slug === "ui-module")!;
    expect(JSON.stringify(uiModule.sections)).not.toContain("06-ablaeufe");
  });

  it("listet jeden Ablauf mit Titel in der Sprache des Studios und seinem Stand als Text", async () => {
    const { el, fixture } = await mount();
    expect(eintraege(el)).toEqual([
      "Vorlesen · lesen · an · Knopf, Wendung · Module: ui_upload",
      "KAPUTT · kaputt · passt nicht zum Modell — öffnen und reparieren",
      "PRUEFEN · pruefen · aus · 2 Befunde",
    ]);
    // ein unlesbarer und einer mit Befunden sind in der Liste markiert
    const markiert = fixture.componentInstance.docs.entries().filter((e) => e.problem).map((e) => e.kennung);
    expect(markiert).toEqual(["kaputt", "pruefen"]);
  });

  it("zeigt auf Englisch den englischen Titel", async () => {
    const { el } = await mount("en");
    expect(eintraege(el)[0]).toBe("Read aloud · lesen · on · button, phrase · modules: ui_upload");
  });

  it("legt einen Ablauf unter einer Kennung in der Form des Treibers an", async () => {
    const { el, http, fixture } = await mount();
    const input = el.querySelector<HTMLInputElement>(".gs-new-name")!;
    input.value = "Sammlung prüfen & ergänzen";
    input.dispatchEvent(new Event("input"));
    await fixture.whenStable();
    expect(el.querySelector(".gs-new-key")?.textContent).toContain("sammlung_pruefen_ergaenzen");
    el.querySelector<HTMLButtonElement>(".gs-new-go")!.click();
    await fixture.whenStable();
    const req = http.expectOne("/studio/api/config/documents");
    expect(req.request.body).toEqual({
      group: "06-ablaeufe", id: "sammlung_pruefen_ergaenzen", label: "Sammlung prüfen & ergänzen",
    });
    req.flush({ status: "created", key: "06-ablaeufe/sammlung_pruefen_ergaenzen", version: 1 });
    await tick();
    await fixture.whenStable();
    http.expectOne("/studio/api/config/ablaeufe").flush({ ablaeufe: [
      ...LISTE.ablaeufe, zeile("sammlung_pruefen_ergaenzen")] });
    await tick();
    await fixture.whenStable();
    const key = "06-ablaeufe/sammlung_pruefen_ergaenzen";
    http.expectOne(`/studio/api/config/schema/${key}`).flush(AREA_SCHEMAS["06-ablaeufe"]);
    http.expectOne(`/studio/api/config/data/${key}`).flush({ area: key, type: "yaml", version: 1,
      data: { id: "sammlung_pruefen_ergaenzen", titel: { de: "Sammlung prüfen & ergänzen" },
              aktiv: false, schritte: [{ id: "ende", typ: "ende", text: { de: "" } }] } });
    http.match(() => true).forEach((r) => r.flush({}));   // Vorschlagslisten des Formulars
    await tick();
    await fixture.whenStable();
    expect(fixture.componentInstance.selected()).toBe(key);
    // „Prüfen“ und die Schrittfolge stehen genau einmal im Formular (Browser-Abnahme: vorher je
    // Abschnitt einmal)
    expect(el.querySelectorAll(".ap").length).toBe(1);
  });
});

describe("Seite „Abläufe“ — Sprung vom Modul (AS-2c)", () => {
  it("?ablauf=<id> wählt den Ablauf, sobald die Liste da ist — einmal", async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(), provideHttpClient(withXhr()), provideHttpClientTesting(),
      provideRouter([]),
    ] });
    await TestBed.inject(Router).navigateByUrl("/?ablauf=pruefen");
    const fixture = TestBed.createComponent(GroupSectionComponent);
    fixture.componentRef.setInput("section", ABLAEUFE);
    fixture.componentRef.setInput("open", true);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.expectOne("/studio/api/config/ablaeufe").flush(LISTE);
    await tick();
    await fixture.whenStable();
    expect(fixture.componentInstance.selected()).toBe("06-ablaeufe/pruefen");
    http.expectOne("/studio/api/config/schema/06-ablaeufe/pruefen");
    // eine neue Liste (nach dem Speichern) wählt nicht noch einmal
    fixture.componentInstance.selected.set("");
    const neu = fixture.componentInstance.loadList();
    http.expectOne("/studio/api/config/ablaeufe").flush(LISTE);
    await neu;
    await tick();
    await fixture.whenStable();
    expect(fixture.componentInstance.selected()).toBe("");
  });
});

describe("Seite „Abläufe“ — Stand der Liste (Review AS-0)", () => {
  it("ohne Abläufe lädt die Liste zum ersten ein", async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(), provideHttpClient(withXhr()), provideHttpClientTesting(),
      provideRouter([]),
    ] });
    const fixture = TestBed.createComponent(GroupSectionComponent);
    fixture.componentRef.setInput("section", ABLAEUFE);
    fixture.componentRef.setInput("open", true);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.expectOne("/studio/api/config/ablaeufe").flush({ ablaeufe: [] });
    await tick();
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain("Noch kein Ablauf");
  });

  it("ein Fehler beim Laden wird gesagt", async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(), provideHttpClient(withXhr()), provideHttpClientTesting(),
      provideRouter([]),
    ] });
    const fixture = TestBed.createComponent(GroupSectionComponent);
    fixture.componentRef.setInput("section", ABLAEUFE);
    fixture.componentRef.setInput("open", true);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.expectOne("/studio/api/config/ablaeufe").flush({ detail: "kaputt" },
      { status: 500, statusText: "Server Error" });
    await tick();
    await fixture.whenStable();
    expect(fixture.componentInstance.listError()).not.toBe("");
  });

  it("nach dem Speichern zeigt die Liste den neuen Stand", async () => {
    const { http, fixture } = await mount();
    const comp = fixture.componentInstance;
    comp.select("06-ablaeufe/pruefen");
    await fixture.whenStable();
    const key = "06-ablaeufe/pruefen";
    http.expectOne(`/studio/api/config/schema/${key}`).flush(AREA_SCHEMAS["06-ablaeufe"]);
    http.expectOne(`/studio/api/config/data/${key}`).flush({ area: key, type: "yaml", version: 3,
      data: { id: "pruefen", titel: { de: "PRUEFEN" }, aktiv: false,
              schritte: [{ id: "ende", typ: "ende", text: { de: "" } }] } });
    http.match(() => true).filter((r) => !r.request.url.endsWith(key)).forEach((r) => r.flush({}));
    await tick();
    await fixture.whenStable();
    comp.editor.setDoc({ ...comp.editor.doc()!, aktiv: true });
    comp.save();
    await fixture.whenStable();
    http.expectOne((r) => r.method === "PUT" && r.url === `/studio/api/config/data/${key}`)
      .flush({ status: "saved", area: key, version: 4, type: "yaml", data: {} });
    await tick();
    await fixture.whenStable();
    http.expectOne("/studio/api/config/ablaeufe").flush({ ablaeufe: [
      zeile("pruefen", { aktiv: true })] });
    await tick();
    await fixture.whenStable();
    expect(comp.docs.entries()[0].note).toContain("an");
  });
});

describe("GroupDocuments — Kennungen der Abläufe (AS-0)", () => {
  const docs = (area = "06-ablaeufe") =>
    new GroupDocuments(null as never, null as never, null as never, () => area);

  it.each([
    ["Lehrplan → Themenbaum", "lehrplan_themenbaum"],
    ["2. Durchgang", "a_2_durchgang"],
    ["  ", ""],
    ["x".repeat(60), "x".repeat(40)],
  ])("„%s“ wird %s", (name, kennung) => {
    expect(docs().neueKennung(name)).toBe(kennung);
  });

  it("lässt die Regel der Muster unverändert", () => {
    expect(docs("03-patterns").neueKennung("M03 Kuratieren")).toBe("m03-kuratieren");
  });

  it("eine Kopie passt in 40 Zeichen — auch die hundertste", () => {
    const d = docs();
    expect(d.freeCopyId("a".repeat(40))).toBe(`${"a".repeat(34)}_kopie`);
    expect(d.freeCopyId("lesen")).toBe("lesen_kopie");
    // Review AS-0 (NIT): ab `_kopie_100` wurde die Kennung 41 Zeichen lang
    const voll = Array.from({ length: 99 }, (_, i) => i ? `${"a".repeat(40 - `_kopie_${i + 1}`.length)}_kopie_${i + 1}` : `${"a".repeat(34)}_kopie`);
    d.entries.set(voll.map((k) => ({ id: `06-ablaeufe/${k}`, title: k, kennung: k, name: k })));
    const neu = d.freeCopyId("a".repeat(40));
    expect(neu.length).toBeLessThanOrEqual(40);
    expect(neu.endsWith("_kopie_100")).toBe(true);
  });

  it("„katalog“ gilt als vergeben", () => {
    expect(docs().taken("katalog")).toBe(true);
    expect(docs("03-patterns").taken("katalog")).toBe(false);
  });
});

describe("ablaufNotiz (AS-0)", () => {
  it("nennt Stand und Auslöser als Text, nicht nur als Farbe", () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const lang = TestBed.inject(StudioLanguageService);
    expect(ablaufNotiz(zeile("a", { aktiv: true, ausloeser: ["agent", "modul", "neu"], befunde: 1 }),
                       lang.t, lang.plural)).toBe("a · an · KI, Modul, neu · 1 Befund");
  });

  it("Review AS-7b, Befund 7: Gastseite und Seite in Worten", () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const lang = TestBed.inject(StudioLanguageService);
    expect(ablaufNotiz(zeile("a", { aktiv: false, ausloeser: ["extern", "seite"] }), lang.t, lang.plural))
      .toBe("a · aus · Gastseite, Seite");
  });
});
