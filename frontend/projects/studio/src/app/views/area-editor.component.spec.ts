// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, UrlSegment } from "@angular/router";
import { BehaviorSubject, of } from "rxjs";
import { beforeEach, describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { AREA_SCHEMAS } from "../schema-form/area-schemas.fixture";
import { AreaEditorComponent } from "./area-editor.component";

const AREA = "01-base/welcome-config";
const SCHEMA_URL = `/studio/api/config/schema/${AREA}`;
const DATA_URL = `/studio/api/config/data/${AREA}`;
const FILE_URL = "/studio/api/config/file";

interface Harness {
  fixture: ComponentFixture<AreaEditorComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

async function mount(
  data: Record<string, unknown> = { welcome: { greeting: "Moin" } },
  raw = "welcome:\n  greeting: Moin\n",
): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
  // Zusagen unten brauchen deshalb die oberste Sprachquelle.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      {
        provide: ActivatedRoute,
        useValue: {
          url: of(
            ["bereich", ...AREA.split("/")].map(
              (path) => new UrlSegment(path, {}),
            ),
          ),
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(AreaEditorComponent);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne(SCHEMA_URL).flush(AREA_SCHEMAS[AREA]);
  http.expectOne(DATA_URL).flush({ area: AREA, data, type: "yaml" });
  await tick();
  await fixture.whenStable();
  http
    .expectOne((r) => r.url === FILE_URL)
    .flush({ path: `${AREA}.yaml`, content: raw });
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

function button(el: HTMLElement, text: string): HTMLButtonElement {
  const found = Array.from(el.querySelectorAll("button")).find((b) =>
    b.textContent?.trim().startsWith(text),
  );
  if (!found) throw new Error(`no button "${text}"`);
  return found;
}

function greetingInput(el: HTMLElement): HTMLInputElement {
  const control = el.querySelector<HTMLInputElement>(
    '#ae-welcome\\.greeting, [id="ae-welcome.greeting"]',
  );
  if (!control) throw new Error("greeting input not rendered");
  return control;
}

async function editGreeting(h: Harness, text: string): Promise<void> {
  const input = greetingInput(h.el);
  input.value = text;
  input.dispatchEvent(new Event("input"));
  await h.fixture.whenStable();
}

describe("AreaEditorComponent — loading", () => {
  it("derives the area key from the wildcard route and shows it", async () => {
    const h = await mount();
    expect(h.el.querySelector(".ae-title")?.textContent?.trim()).toBe(AREA);
  });

  it("renders the schema form with the loaded document", async () => {
    const h = await mount();
    expect(greetingInput(h.el).value).toBe("Moin");
  });

  it("offers a retry instead of a dead page when loading fails", async () => {
    TestBed.resetTestingModule();
    // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
    // Zusagen unten brauchen deshalb die oberste Sprachquelle.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: {
            url: of(
              ["bereich", ...AREA.split("/")].map(
                (path) => new UrlSegment(path, {}),
              ),
            ),
          },
        },
      ],
    });
    const fixture = TestBed.createComponent(AreaEditorComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http
      .expectOne(SCHEMA_URL)
      .flush(
        { detail: "unknown config area" },
        { status: 404, statusText: "x" },
      );
    http
      .expectOne(DATA_URL)
      .flush({ detail: "x" }, { status: 404, statusText: "x" });
    await tick();
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain(
      "Diesen Konfigurationsbereich gibt es nicht.",
    );
    expect(button(el, "Erneut versuchen")).toBeTruthy();
  });
});

describe("AreaEditorComponent — saving the form", () => {
  let h: Harness;
  beforeEach(async () => {
    h = await mount();
  });

  it("keeps Speichern inert until something changed", () => {
    expect(button(h.el, "Speichern").disabled).toBe(true);
  });

  it("sends the whole document, not just the edited field", async () => {
    await editGreeting(h, "Servus");
    button(h.el, "Speichern").click();
    await h.fixture.whenStable();
    const req = h.http.expectOne(DATA_URL);
    expect(req.request.method).toBe("PUT");
    expect(req.request.body).toEqual({
      data: { welcome: { greeting: "Servus" } },
    });
    req.flush({
      area: AREA,
      type: "yaml",
      data: { welcome: { greeting: "Servus" } },
    });
    await tick();
    await h.fixture.whenStable();
    // the YAML view would now be stale, so it is refetched
    h.http
      .expectOne((r) => r.url === FILE_URL)
      .flush({
        path: `${AREA}.yaml`,
        content: "welcome:\n  greeting: Servus\n",
      });
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".ae-status")?.textContent).toContain(
      "Gespeichert.",
    );
  });

  it("names the offending field when the backend rejects the document", async () => {
    await editGreeting(h, "Servus");
    button(h.el, "Speichern").click();
    await h.fixture.whenStable();
    h.http
      .expectOne(DATA_URL)
      .flush(
        {
          detail: [
            {
              loc: ["body", "welcome", "quick_replies"],
              msg: "Input should be a valid list",
            },
          ],
        },
        { status: 422, statusText: "Unprocessable Content" },
      );
    await tick();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("welcome.quick_replies");
    expect(alert?.textContent).toContain("valid list");
  });

  it("restores the loaded document on Verwerfen", async () => {
    await editGreeting(h, "Servus");
    button(h.el, "Verwerfen").click();
    await h.fixture.whenStable();
    expect(greetingInput(h.el).value).toBe("Moin");
    expect(button(h.el, "Speichern").disabled).toBe(true);
  });

  it("flags unsaved changes in words", async () => {
    await editGreeting(h, "Servus");
    expect(h.el.textContent).toContain("Ungespeicherte Änderungen");
  });
});

describe("AreaEditorComponent — the two tabs", () => {
  /**
   * The tab strip is shared (`studio-tab-bar`, B4) and the panels stay here, so
   * the contract between them is the ids: tab `x` points at `#panel-x`. A
   * dangling `aria-controls` is exactly the defect the shared component exists
   * to prevent, and it cannot be seen on screen.
   */
  it("points both tabs at a panel that exists, and labels it back", async () => {
    const h = await mount();
    const tabs = Array.from(h.el.querySelectorAll<HTMLElement>('[role="tab"]'));
    expect(tabs).toHaveLength(2);
    for (const tab of tabs) {
      const panel = h.el.querySelector(`#${tab.getAttribute("aria-controls")}`);
      expect(panel).not.toBeNull();
      expect(panel!.getAttribute("aria-labelledby")).toBe(tab.id);
    }
  });

  it("shows the YAML source in the raw tab", async () => {
    const h = await mount();
    button(h.el, "Rohtext").click();
    await h.fixture.whenStable();
    const box = h.el.querySelector<HTMLTextAreaElement>("#ae-raw");
    expect(box?.value).toBe("welcome:\n  greeting: Moin\n");
  });

  it("refuses to switch tabs while unsaved, and says why", async () => {
    const h = await mount();
    await editGreeting(h, "Servus");
    button(h.el, "Rohtext").click();
    await h.fixture.whenStable();
    // both panels stay in the DOM (so every aria-controls resolves); the
    // raw one must be hidden, i.e. the switch did not happen
    expect(h.el.querySelector("#panel-ae-raw")?.hasAttribute("hidden")).toBe(
      true,
    );
    expect(h.el.querySelector(".ae-status")?.textContent).toContain(
      "speichern oder verwerfen",
    );
  });

  it("saves the raw text through the file endpoint and reloads the document", async () => {
    const h = await mount();
    button(h.el, "Rohtext").click();
    await h.fixture.whenStable();
    const box = h.el.querySelector<HTMLTextAreaElement>("#ae-raw")!;
    box.value = "welcome:\n  greeting: Tach\n";
    box.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();
    button(h.el, "Speichern").click();
    await h.fixture.whenStable();
    const put = h.http.expectOne(
      (r) => r.url === FILE_URL && r.method === "PUT",
    );
    expect(put.request.body).toEqual({
      path: `${AREA}.yaml`,
      content: "welcome:\n  greeting: Tach\n",
    });
    put.flush({ status: "saved" });
    await tick();
    await h.fixture.whenStable();
    h.http
      .expectOne(DATA_URL)
      .flush({
        area: AREA,
        type: "yaml",
        data: { welcome: { greeting: "Tach" } },
      });
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".ae-status")?.textContent).toContain(
      "Gespeichert.",
    );
  });

  it("reports a YAML syntax error instead of failing silently", async () => {
    const h = await mount();
    button(h.el, "Rohtext").click();
    await h.fixture.whenStable();
    const box = h.el.querySelector<HTMLTextAreaElement>("#ae-raw")!;
    box.value = "welcome: [unclosed";
    box.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();
    button(h.el, "Speichern").click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === FILE_URL && r.method === "PUT")
      .flush(
        { detail: "Inhalt nicht lesbar: while parsing a flow node" },
        { status: 400, statusText: "Bad Request" },
      );
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain(
      "Inhalt nicht lesbar",
    );
  });
});

describe("AreaEditorComponent — switching to another area", () => {
  it("loads the second area — the component is reused, ngOnInit fires once", async () => {
    const url = new BehaviorSubject(
      ["bereich", "01-base", "welcome-config"].map(
        (p) => new UrlSegment(p, {}),
      ),
    );
    TestBed.resetTestingModule();
    // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
    // Zusagen unten brauchen deshalb die oberste Sprachquelle.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { url } },
      ],
    });
    const fixture = TestBed.createComponent(AreaEditorComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.expectOne(SCHEMA_URL).flush(AREA_SCHEMAS[AREA]);
    http
      .expectOne(DATA_URL)
      .flush({ area: AREA, type: "yaml", data: { welcome: {} } });
    await tick();
    await fixture.whenStable();
    http
      .expectOne((r) => r.url === FILE_URL)
      .flush({ path: `${AREA}.yaml`, content: "welcome: {}" });
    await tick();
    await fixture.whenStable();

    url.next(
      ["bereich", "01-base", "policy"].map((p) => new UrlSegment(p, {})),
    );
    await fixture.whenStable();
    http
      .expectOne("/studio/api/config/schema/01-base/policy")
      .flush(AREA_SCHEMAS["01-base/policy"]);
    http
      .expectOne("/studio/api/config/data/01-base/policy")
      .flush({ area: "01-base/policy", type: "yaml", data: { rules: [] } });
    await tick();
    await fixture.whenStable();
    http
      .expectOne((r) => r.url === FILE_URL)
      .flush({ path: "01-base/policy.yaml", content: "" });
    await tick();
    await fixture.whenStable();
    expect(
      (fixture.nativeElement as HTMLElement)
        .querySelector(".ae-title")
        ?.textContent?.trim(),
    ).toBe("01-base/policy");
  });

  it("says so instead of loading forever when no area is named", async () => {
    // `bereich/**` also matches the bare `/bereich`
    TestBed.resetTestingModule();
    // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
    // Zusagen unten brauchen deshalb die oberste Sprachquelle.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { url: of([new UrlSegment("bereich", {})]) },
        },
      ],
    });
    const fixture = TestBed.createComponent(AreaEditorComponent);
    await fixture.whenStable();
    TestBed.inject(HttpTestingController).verify(); // nothing was requested
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      "Es ist kein Bereich angegeben",
    );
  });
});

describe("AreaEditorComponent — a field that cannot be parsed blocks the save", () => {
  it("disables Speichern and names the field", async () => {
    const h = await mount({ welcome: { greeting: "Moin" } });
    await editGreeting(h, "Servus");
    expect(button(h.el, "Speichern").disabled).toBe(false);
    h.fixture.componentInstance.onFieldErrors(["welcome.irgendwas"]);
    await h.fixture.whenStable();
    // saving now would PUT the last parseable value and report success
    expect(button(h.el, "Speichern").disabled).toBe(true);
    await h.fixture.componentInstance.save();
    await h.fixture.whenStable();
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain(
      "welcome.irgendwas",
    );
    h.http.verify(); // and no request went out
  });
});

describe("AreaEditorComponent — markdown areas", () => {
  it("asks for the .md file when the document is a frontmatter/body pair", async () => {
    TestBed.resetTestingModule();
    // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
    // Zusagen unten brauchen deshalb die oberste Sprachquelle.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: {
            url: of(
              ["bereich", "01-base", "base-persona"].map(
                (p) => new UrlSegment(p, {}),
              ),
            ),
          },
        },
      ],
    });
    const fixture = TestBed.createComponent(AreaEditorComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http
      .expectOne("/studio/api/config/schema/01-base/base-persona")
      .flush(AREA_SCHEMAS["01-base/base-persona"]);
    http
      .expectOne("/studio/api/config/data/01-base/base-persona")
      .flush({
        area: "01-base/base-persona",
        type: "md",
        data: { frontmatter: { id: "x" }, body: "# Titel" },
      });
    await tick();
    await fixture.whenStable();
    const file = http.expectOne((r) => r.url === FILE_URL);
    expect(file.request.params.get("path")).toBe("01-base/base-persona.md");
    file.flush({ path: "01-base/base-persona.md", content: "# Titel" });
    await tick();
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      "Markdown",
    );
  });
});
