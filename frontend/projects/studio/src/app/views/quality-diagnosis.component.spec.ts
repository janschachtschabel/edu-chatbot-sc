// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import {
  Component,
  provideZonelessChangeDetection,
  signal,
} from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { QualityDiagnosisComponent } from "./quality-diagnosis.component";
import type { LogFilters, QualityScope } from "../core/quality-api.service";

const DEG_URL = "/studio/api/quality/degradations";
const ENT_URL = "/studio/api/quality/empty-entities";
const CONF_URL = "/studio/api/quality/low-confidence";

const DEGRADATIONS = {
  scope: "all",
  total: 12,
  groups: [
    {
      pattern_id: "M10",
      missing_slots: ["thema", "material_typ"],
      count: 7,
      example_message: "Mach mir was",
      example_intent: "I04",
      example_persona: "P02",
    },
  ],
};

const EMPTY_ENTITIES = {
  scope: "all",
  total: 5,
  groups: [
    { intent_id: "I02", pattern_id: "M04", count: 5, example_message: "Hä?" },
  ],
};

const LOW_CONFIDENCE = {
  scope: "all",
  total: 2,
  max_confidence: 0.6,
  turns: [
    {
      id: 9,
      message: "irgendwas",
      intent_id: "I07",
      pattern_id: "M15",
      persona_id: "P01",
      state_id: "S2",
      final_confidence: 0.31,
      created_at: "2026-07-24T10:00:00Z",
    },
  ],
};

@Component({
  selector: "studio-diagnosis-host",
  imports: [QualityDiagnosisComponent],
  template:
    '<studio-quality-diagnosis [scope]="scope()" (drill)="last = $event" />',
})
class HostComponent {
  readonly scope = signal<QualityScope>("all");
  last: LogFilters | null = null;
}

interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

/** jsdom meldet `navigator.language === 'en-US'`; ohne gesetzte Wahl liefe die
 *  deutsche Oberfläche auf Englisch. */
async function mount(
  options: {
    degradations?: object;
    entities?: object;
    confidence?: object;
    failEntities?: boolean;
    locale?: string;
  } = {},
): Promise<Harness> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, options.locale ?? "de");
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();

  http
    .expectOne((r) => r.url === DEG_URL)
    .flush(options.degradations ?? DEGRADATIONS);
  const entities = http.expectOne((r) => r.url === ENT_URL);
  if (options.failEntities)
    entities.flush({ detail: "Kaputt." }, { status: 500, statusText: "x" });
  else entities.flush(options.entities ?? EMPTY_ENTITIES);
  http
    .expectOne((r) => r.url === CONF_URL)
    .flush(options.confidence ?? LOW_CONFIDENCE);

  await settle(h);
  return h;
}

describe("QualityDiagnosisComponent", () => {
  it("reads the three breakdowns independently", async () => {
    const h = await mount();
    h.http.verify(); // nothing left over, nothing fetched twice
    expect(h.el.querySelectorAll("details")).toHaveLength(3);
  });

  it("shows a failing breakdown as failed and leaves the other two alone", async () => {
    // ALT put all three in one Promise.all and dropped non-ok answers to null,
    // which rendered as "nothing found" — indistinguishable from healthy.
    const h = await mount({ failEntities: true });

    const boxes = Array.from(h.el.querySelectorAll("details"));
    expect(boxes[1].querySelector('[role="alert"]')!.textContent).toContain(
      "Kaputt.",
    );
    expect(boxes[0].textContent).toContain("M10");
    expect(boxes[2].textContent).toContain("I07");
  });

  it("names the missing slots and the example turn of a degradation", async () => {
    const h = await mount();
    const box = h.el.querySelectorAll("details")[0];
    expect(box.textContent).toContain("thema");
    expect(box.textContent).toContain("material_typ");
    expect(box.textContent).toContain("Mach mir was");
    expect(box.textContent).toContain("7×");
  });

  it("offers the drill-down as a real button, per row", async () => {
    // ALT made the whole coloured block clickable via onClick on a div.
    const h = await mount();
    const drill = h.el.querySelector<HTMLButtonElement>(".qd-drill")!;
    expect(drill.tagName).toBe("BUTTON");

    drill.click();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.last).toEqual({ patternId: "M10" });
  });

  it("drills into an intent from the empty-entity block", async () => {
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>(".qd-drill")[1].click();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.last).toEqual({ intentId: "I02" });
  });

  it("states the confidence threshold the list was cut at", async () => {
    const h = await mount();
    expect(h.el.querySelectorAll("details")[2].textContent).toContain("0,6");
  });

  it("distinguishes an empty breakdown from a broken one", async () => {
    const h = await mount({
      degradations: { scope: "all", total: 0, groups: [] },
    });
    const box = h.el.querySelectorAll("details")[0];
    expect(box.textContent).toContain("Keine Degradationen");
    expect(box.querySelector('[role="alert"]')).toBeNull();
  });

  it("setzt beide Anzahlen der Kopfzeile in ihre eigene Mehrzahl", async () => {
    // Zwei unabhängige Anzahlen in EINEM Satz — zwei Wortgruppen, keine
    // Schlüssel-Matrix. Bis hierher stand da fest „Turns · Muster", also
    // schon auf Deutsch „1 Turns · 1 Muster".
    const single = {
      scope: "all",
      total: 1,
      groups: [
        {
          pattern_id: "M10",
          missing_slots: ["thema"],
          count: 1,
          example_message: "",
        },
      ],
    };
    const h = await mount({ degradations: single });
    expect(h.el.querySelectorAll(".qd-count")[0].textContent!.trim()).toBe(
      "1 Turn · 1 Muster",
    );

    const en = await mount({ degradations: single, locale: "en" });
    expect(en.el.querySelectorAll(".qd-count")[0].textContent!.trim()).toBe(
      "1 turn · 1 pattern",
    );
  });

  it("zeichnet Fachbegriff und Slot-Namen im Hilfetext aus, statt den Satz zu zerlegen", async () => {
    const h = await mount();
    const help = h.el.querySelectorAll(".qd-help")[0];
    expect(help.querySelector("strong")!.textContent).toBe("degradiert");
    expect(
      Array.from(help.querySelectorAll("code")).map((c) => c.textContent),
    ).toEqual(["thema", "material_typ"]);
  });

  it("re-reads all three when the scope changes", async () => {
    const h = await mount();
    h.fixture.componentInstance.scope.set("production");
    await h.fixture.whenStable();

    for (const url of [DEG_URL, ENT_URL, CONF_URL]) {
      const req = h.http.expectOne((r) => r.url === url);
      expect(req.request.params.get("scope")).toBe("production");
      req.flush({
        scope: "production",
        total: 0,
        groups: [],
        turns: [],
        max_confidence: 0.6,
      });
    }
    await settle(h);
  });
});
