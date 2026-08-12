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
import { QualityFlowComponent } from "./quality-flow.component";
import type { QualityScope } from "../core/quality-api.service";

const FLOW_URL = "/studio/api/quality/state-transitions";

const FLOW = {
  scope: "all",
  days: 30,
  total_turns: 40,
  total_transitions: 12,
  state_distribution: { S3: 22, S2: 15, S1: 3 },
  transitions: [
    { prev: "S2", next: "S3", count: 7 },
    { prev: "S2", next: "S2", count: 3 },
    { prev: "S3", next: "S3", count: 2 },
  ],
};

@Component({
  selector: "studio-flow-host",
  imports: [QualityFlowComponent],
  template: '<studio-quality-flow [scope]="scope()" />',
})
class HostComponent {
  readonly scope = signal<QualityScope>("all");
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
async function mount(flow: object = FLOW, locale = "de"): Promise<Harness> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
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
  http.expectOne((r) => r.url === FLOW_URL).flush(flow);
  await settle(h);
  return h;
}

/** The caption of each ranked table, in document order. */
const captions = (h: Harness): (string | null)[] =>
  Array.from(h.el.querySelectorAll("caption")).map((c) =>
    c.textContent!.trim(),
  );

describe("QualityFlowComponent", () => {
  it("reads the transitions for the scope, the window and the min-count", async () => {
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
    await fixture.whenStable();

    const req = http.expectOne((r) => r.url === FLOW_URL);
    expect(req.request.params.get("scope")).toBe("all");
    expect(req.request.params.get("days")).toBe("30");
    expect(req.request.params.get("min_count")).toBe("1");
    req.flush(FLOW);
  });

  it("separates a move between phases from a repeat of the same phase", async () => {
    // Two S2 turns in a row (another slot missing) is a different observation
    // from S2 → S3, and mixing them hides both.
    const h = await mount();
    const tables = captions(h);
    expect(tables).toHaveLength(3);
    expect(tables[1]).toContain("Übergänge");
    expect(tables[2]).toContain("Wiederholungen");

    const repeats = h.el.querySelectorAll("table")[2];
    expect(repeats.textContent).toContain("S2");
    expect(repeats.textContent).toContain("S3");
    // Only the two self-loops, not the S2 → S3 move.
    expect(repeats.querySelectorAll("tbody tr")).toHaveLength(2);
  });

  it("names both ends of a transition", async () => {
    const h = await mount();
    const moves = h.el.querySelectorAll("table")[1];
    expect(moves.textContent).toContain("S2");
    expect(moves.textContent).toContain("S3");
    expect(moves.querySelectorAll("tbody tr")).toHaveLength(1);
  });

  it("shows the state distribution as its own ranked table", async () => {
    const h = await mount();
    expect(captions(h)[0]).toContain("Phasen");
    const dist = h.el.querySelectorAll("table")[0];
    expect(dist.querySelectorAll("tbody tr")).toHaveLength(3);
  });

  it("counts the turns and transitions the window covered", async () => {
    const h = await mount();
    const summary = h.el.querySelector(".qf-total")!.textContent!;
    expect(summary).toContain("40");
    expect(summary).toContain("12");
    expect(summary).toContain("30");
  });

  it("re-reads when the window changes", async () => {
    const h = await mount();
    const input = h.el.querySelector<HTMLInputElement>("#qf-days")!;
    expect(input.labels?.[0]?.textContent).toContain("Tage");

    input.value = "7";
    input.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === FLOW_URL);
    expect(req.request.params.get("days")).toBe("7");
    req.flush({ ...FLOW, days: 7 });
    await settle(h);
  });

  it("re-reads when the min-count changes", async () => {
    const h = await mount();
    const input = h.el.querySelector<HTMLInputElement>("#qf-min")!;
    input.value = "3";
    input.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === FLOW_URL);
    expect(req.request.params.get("min_count")).toBe("3");
    req.flush(FLOW);
    await settle(h);
  });

  it("keeps a nonsense window out of the query", async () => {
    const h = await mount();
    const input = h.el.querySelector<HTMLInputElement>("#qf-days")!;
    input.value = "7";
    input.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === FLOW_URL).flush(FLOW);
    await settle(h);

    input.value = "-5";
    input.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === FLOW_URL);
    expect(req.request.params.get("days")).toBe("1");
    req.flush(FLOW);
    await settle(h);
  });

  it('says which window came up empty instead of just "keine Daten"', async () => {
    const h = await mount({
      scope: "all",
      days: 30,
      total_turns: 0,
      total_transitions: 0,
      state_distribution: {},
      transitions: [],
    });
    const message = h.el.querySelector(".as-line")!.textContent!;
    expect(message).toContain("30");
    expect(h.el.querySelectorAll("table")).toHaveLength(0);
  });

  it("shows the phases even when no turn followed another", async () => {
    // One turn per session produces a distribution but no transitions at all;
    // that is a finding, not an empty view.
    const h = await mount({ ...FLOW, total_transitions: 0, transitions: [] });
    expect(captions(h)[0]).toContain("Phasen");
    expect(h.el.textContent).toContain("Keine Übergänge");
  });

  it("re-reads on demand", async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>(".qf-reload")!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === FLOW_URL).flush(FLOW);
    await settle(h);
  });

  it("re-reads when the scope changes", async () => {
    const h = await mount();
    h.fixture.componentInstance.scope.set("production");
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === FLOW_URL);
    expect(req.request.params.get("scope")).toBe("production");
    req.flush(FLOW);
    await settle(h);
  });

  it("reports a failed read", async () => {
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
      .expectOne((r) => r.url === FLOW_URL)
      .flush(
        { detail: "Zeitfenster zu groß." },
        { status: 400, statusText: "x" },
      );
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain(
      "Zeitfenster",
    );
  });

  it("setzt alle drei Anzahlen der Kopfzeile in ihre eigene Mehrzahl", async () => {
    // Turns, Übergänge und Tage sind voneinander unabhängig — drei Wortgruppen
    // in EINEM Satz, keine Schlüssel-Matrix. Fest verdrahtet las sich das schon
    // auf Deutsch als „1 Turns mit Phase, 1 Übergänge (…, letzte 1 Tage)".
    const h = await mount({
      ...FLOW,
      days: 1,
      total_turns: 1,
      total_transitions: 1,
      transitions: [{ prev: "S2", next: "S3", count: 1 }],
    });
    expect(
      h.el.querySelector(".qf-total")!.textContent!.replace(/\s+/g, " ").trim(),
    ).toBe("1 Turn mit Phase, 1 Übergang (all, letzter 1 Tag).");
  });

  it("nimmt Beschriftungen der drei Tabellen aus dem Katalog", async () => {
    const h = await mount(FLOW, "en");
    expect(captions(h)).toEqual([
      "Frequency of the phases",
      "Transitions between phases",
      "Repeats of the same phase",
    ]);
  });
});
